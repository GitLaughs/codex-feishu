#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request


DEFAULT_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
DEFAULT_ENV = "/etc/codex-feishu.env"
DEFAULT_AUTH = os.path.expanduser("~/.codex/auth.json")
DEFAULT_CODEX_CONFIG = os.path.expanduser("~/.codex/config.toml")
DEFAULT_FALLBACK_FILE = os.path.expanduser("~/.cc-switch/codex-fallback-providers.json")
DEFAULT_SERVICE = "cc-connect"
PRIMARY_MODEL = "gpt-5.5"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Select the best Codex provider from CC Switch by remaining balance."
    )
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--env", default=DEFAULT_ENV)
    parser.add_argument("--auth", default=DEFAULT_AUTH)
    parser.add_argument("--codex-config", default=DEFAULT_CODEX_CONFIG)
    parser.add_argument("--fallback-file", default=DEFAULT_FALLBACK_FILE)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--restart-service", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-balance", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--exclude-current", action="store_true")
    parser.add_argument("--force-fallback", action="store_true")
    return parser.parse_args()


def load_providers(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, name, settings_config, website_url, sort_index, is_current
        FROM providers
        WHERE app_type = 'codex'
        ORDER BY sort_index, name
        """
    ).fetchall()

    providers = []
    for row in rows:
        website = (row["website_url"] or "").rstrip("/")
        settings = parse_json_object(row["settings_config"])
        meta = load_provider_meta(conn, row["id"])
        key = extract_api_key(settings, meta)
        config = settings.get("config", "")
        base_url = extract_base_url(config) or website
        model = extract_model(config) or PRIMARY_MODEL
        usage_config = meta.get("usage_script") if isinstance(meta.get("usage_script"), dict) else {}
        base_url = usage_config.get("baseUrl") or base_url
        warmup_api = usage_config.get("warmupApi") or usage_config.get("warmup_api") or "responses"
        if not key or not base_url:
            continue
        providers.append(
            {
                "id": row["id"],
                "name": row["name"],
                "key": key,
                "base_url": base_url.rstrip("/"),
                "model": model,
                "codex_base_url": base_url.rstrip("/"),
                "warmup_api": warmup_api,
                "kind": "db",
                "sort_index": row["sort_index"],
                "is_current": bool(row["is_current"]),
            }
        )
    conn.close()
    return providers


def parse_json_object(text):
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_provider_meta(conn, provider_id):
    try:
        row = conn.execute("SELECT meta FROM providers WHERE id = ?", (provider_id,)).fetchone()
    except sqlite3.Error:
        return {}
    if not row:
        return {}
    return parse_json_object(row["meta"])


def extract_api_key(settings, meta):
    usage_config = meta.get("usage_script") if isinstance(meta.get("usage_script"), dict) else {}
    candidates = [
        usage_config.get("apiKey"),
        settings.get("api_key"),
        settings.get("OPENAI_API_KEY"),
    ]
    auth = settings.get("auth")
    if isinstance(auth, dict):
        candidates.extend([auth.get("OPENAI_API_KEY"), auth.get("apiKey"), auth.get("key")])
    elif isinstance(auth, str):
        candidates.append(auth)
    env = settings.get("env")
    if isinstance(env, dict):
        candidates.extend([env.get("OPENAI_API_KEY"), env.get("ANTHROPIC_AUTH_TOKEN")])
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_base_url(config_text):
    for line in config_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("base_url"):
            _, value = stripped.split("=", 1)
            return value.strip().strip('"').strip("'")
    return None


def extract_model(config_text):
    for line in config_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("model ="):
            _, value = stripped.split("=", 1)
            return value.strip().strip('"').strip("'")
    return None


def load_file_fallback(path):
    p = pathlib.Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    providers = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        key = item.get("key") or item.get("api_key") or item.get("OPENAI_API_KEY")
        base_url = (item.get("base_url") or item.get("codex_base_url") or "").rstrip("/")
        if not key or not base_url:
            continue
        providers.append(
            {
                "id": item.get("id") or f"fallback-{idx}",
                "name": item.get("name") or f"fallback-{idx}",
                "key": key,
                "base_url": base_url,
                "codex_base_url": (item.get("codex_base_url") or base_url).rstrip("/"),
                "model": item.get("model") or PRIMARY_MODEL,
                "warmup_api": item.get("warmup_api") or "responses",
                "kind": "fallback",
                "sort_index": item.get("sort_index") if item.get("sort_index") is not None else 1000 + idx,
                "is_current": False,
                "file_fallback": True,
            }
        )
    return providers


def api_url(provider, path):
    base = provider["base_url"].rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        return base + path[3:]
    if not base.endswith("/v1") and not path.startswith("/v1/"):
        path = "/v1/" + path.lstrip("/")
    return base + path


def response_unsupported_error(exc):
    if not isinstance(exc, urllib.error.HTTPError):
        return False
    if exc.code in {404, 405}:
        return True
    try:
        body = exc.read(4096).decode("utf-8", errors="replace").lower()
    except Exception:
        body = ""
    markers = ["unsupported", "not support", "not_supported", "responses", "response api"]
    return exc.code in {400, 422} and any(marker in body for marker in markers)


def warmup_provider(provider, timeout):
    if provider.get("warmup_api") == "chat":
        return warmup_chat_provider(provider, timeout)
    url = api_url(provider, "/v1/responses")
    payload = json.dumps(
        {
            "model": provider.get("model") or PRIMARY_MODEL,
            "input": "ping",
            "max_output_tokens": 8,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": "Bearer " + provider["key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read(4096)
        return {"ok": True}
    except urllib.error.HTTPError as exc:
        if response_unsupported_error(exc):
            chat_result = warmup_chat_provider(provider, timeout)
            if chat_result.get("ok"):
                chat_result["warmup_fallback"] = "chat"
            return chat_result
        return {"ok": False, "error": f"warmup http {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "error": "warmup " + str(exc)}


def warmup_chat_provider(provider, timeout):
    url = api_url(provider, "/v1/chat/completions")
    payload = json.dumps(
        {
            "model": provider.get("model") or PRIMARY_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": "Bearer " + provider["key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read(4096)
        return {"ok": True}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"warmup chat http {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "error": "warmup chat " + str(exc)}


def query_usage(provider, timeout, warmup=True):
    if warmup:
        warm = warmup_provider(provider, timeout)
        if not warm.get("ok"):
            return warm
        time.sleep(0.8)
    url = api_url(provider, "/v1/usage")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + provider["key"],
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"http {exc.code}: {exc.reason}"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}

    remaining = first_number(
        data,
        [
            ("remaining",),
            ("quota", "remaining"),
            ("balance",),
            ("data", "remaining"),
            ("data", "balance"),
            ("data", "totalBalance"),
        ],
    )
    is_valid = first_value(
        data,
        [
            ("is_active",),
            ("isValid",),
            ("is_valid",),
            ("data", "is_active"),
            ("data", "isValid"),
            ("data", "status"),
        ],
    )
    valid = normalize_valid(is_valid)
    if remaining is None and provider.get("kind") in {"db", "fallback"}:
        return {"ok": valid, "remaining": 0.0, "valid": valid, "balance_note": "usage unavailable after warmup"}
    if remaining is None:
        return {"ok": False, "error": "missing remaining/balance in usage response"}
    return {"ok": valid and remaining > 0, "remaining": remaining, "valid": valid}


def first_value(data, paths):
    for path in paths:
        node = data
        for part in path:
            if not isinstance(node, dict) or part not in node:
                node = None
                break
            node = node[part]
        if node is not None:
            return node
    return None


def first_number(data, paths):
    value = first_value(data, paths)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_valid(value):
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "inactive", "disabled", "expired"}
    return True


def read_current_key(env_path):
    try:
        for line in pathlib.Path(env_path).read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        return None
    return None


def write_env_key(env_path, key):
    path = pathlib.Path(env_path)
    lines = []
    found = False
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("OPENAI_API_KEY="):
            lines[i] = "OPENAI_API_KEY=" + key
            found = True
            break
    if not found:
        lines.append("OPENAI_API_KEY=" + key)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def write_auth_key(auth_path, key):
    path = pathlib.Path(auth_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"OPENAI_API_KEY": key}, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def patch_assignment(lines, key, value):
    rendered = f'{key} = "{value}"'
    for i, line in enumerate(lines):
        if line.strip().startswith(key + " ="):
            lines[i] = rendered
            return True
    return False


def write_codex_config(config_path, provider):
    path = pathlib.Path(config_path)
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f'model = "{PRIMARY_MODEL}"',
            f'review_model = "{PRIMARY_MODEL}"',
            "",
            "[model_providers.OpenAI]",
            'base_url = "https://api.openai.com/v1"',
        ]
    model = provider.get("model") or PRIMARY_MODEL
    base_url = provider.get("codex_base_url") or provider.get("base_url")
    patch_assignment(lines, "model", model)
    patch_assignment(lines, "review_model", model)

    in_openai = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[model_providers."):
            in_openai = stripped == "[model_providers.OpenAI]"
            continue
        if in_openai and stripped.startswith("base_url"):
            lines[i] = f'base_url = "{base_url.rstrip("/")}"'
            break
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def mark_current_provider(db_path, provider_id):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE providers SET is_current = 0 WHERE app_type = 'codex'")
        conn.execute(
            "UPDATE providers SET is_current = 1 WHERE app_type = 'codex' AND id = ?",
            (provider_id,),
        )
        conn.commit()
    finally:
        conn.close()


def filter_excluded(providers, current_key, exclude_current):
    if not exclude_current or not current_key:
        return providers
    return [item for item in providers if item.get("key") != current_key]


def evaluate(providers, timeout, min_balance, warmup):
    results = []
    for provider in providers:
        usage = query_usage(provider, timeout, warmup=warmup)
        item = {**provider, **usage}
        results.append(item)
    candidates = [
        item for item in results
        if item.get("ok") and item.get("remaining", -1) >= min_balance
    ]
    candidates.sort(key=lambda x: (x["remaining"], -int(x["sort_index"] or 0)), reverse=True)
    return results, candidates


def restart_service(service):
    subprocess.run(["systemctl", "restart", service], check=True)


def main():
    args = parse_args()
    all_db_providers = load_providers(args.db)
    primary_providers = [p for p in all_db_providers if not p.get("file_fallback")]
    fallback_providers = []
    fallback_providers.extend(load_file_fallback(args.fallback_file))
    if not primary_providers and not fallback_providers:
        raise SystemExit("no Codex providers found in CC Switch DB or fallback file")

    current_key = read_current_key(args.env)
    primary_pool = filter_excluded(primary_providers, current_key, args.exclude_current)
    fallback_pool = filter_excluded(fallback_providers, current_key, args.exclude_current)

    results = []
    candidates = []
    if not args.force_fallback:
        primary_results, primary_candidates = evaluate(
            primary_pool, args.timeout, args.min_balance, warmup=not args.no_warmup
        )
        results.extend(primary_results)
        candidates = primary_candidates

    if not candidates:
        fallback_results, fallback_candidates = evaluate(
            fallback_pool, args.timeout, args.min_balance, warmup=not args.no_warmup
        )
        results.extend(fallback_results)
        candidates = fallback_candidates
    if not candidates:
        print("No valid primary or fallback provider with positive balance; keeping current key.")
        for item in results:
            print_status(item)
        return 2

    selected = candidates[0]
    changed = current_key != selected["key"]

    for item in results:
        print_status(item, selected["id"])
    print(f"Selected provider: {selected['name']} ({selected['id']}), changed={changed}")

    if args.dry_run:
        return 0

    write_env_key(args.env, selected["key"])
    write_auth_key(args.auth, selected["key"])
    write_codex_config(args.codex_config, selected)
    if not selected.get("file_fallback"):
        mark_current_provider(args.db, selected["id"])
    if changed and args.restart_service:
        restart_service(args.service)
        print(f"Restarted service: {args.service}")
    return 0


def print_status(item, selected_id=None):
    marker = "*" if item["id"] == selected_id else "-"
    if item.get("ok"):
        print(f"{marker} {item['name']} {item['id']} remaining={item['remaining']}")
    else:
        print(f"{marker} {item['name']} {item['id']} unavailable={item.get('error', 'invalid')}")


if __name__ == "__main__":
    raise SystemExit(main())
