#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import sqlite3
import subprocess
import urllib.error
import urllib.request


DEFAULT_DB = os.path.expanduser("~/.cc-switch/cc-switch.db")
DEFAULT_ENV = "/etc/openclaw.env"
DEFAULT_AUTH = os.path.expanduser("~/.codex/auth.json")
DEFAULT_SERVICE = "cc-connect"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Select the best Codex provider from CC Switch by remaining balance."
    )
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--env", default=DEFAULT_ENV)
    parser.add_argument("--auth", default=DEFAULT_AUTH)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--restart-service", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-balance", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=10.0)
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
        if "otokapi.com" not in website:
            continue
        settings = parse_json_object(row["settings_config"])
        meta = load_provider_meta(conn, row["id"])
        key = extract_api_key(settings, meta)
        config = settings.get("config", "")
        base_url = extract_base_url(config) or website
        usage_config = meta.get("usage_script") if isinstance(meta.get("usage_script"), dict) else {}
        base_url = usage_config.get("baseUrl") or base_url
        if not key:
            continue
        providers.append(
            {
                "id": row["id"],
                "name": row["name"],
                "key": key,
                "base_url": base_url.rstrip("/"),
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


def query_usage(provider, timeout):
    url = provider["base_url"].rstrip("/") + "/v1/usage"
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


def restart_service(service):
    subprocess.run(["systemctl", "restart", service], check=True)


def main():
    args = parse_args()
    providers = load_providers(args.db)
    if not providers:
        raise SystemExit("no otokapi codex providers found in CC Switch DB")

    results = []
    for provider in providers:
        usage = query_usage(provider, args.timeout)
        item = {**provider, **usage}
        results.append(item)

    candidates = [
        item for item in results
        if item.get("ok") and item.get("remaining", -1) >= args.min_balance
    ]
    if not candidates:
        print("No valid provider with positive balance; keeping current key.")
        for item in results:
            print_status(item)
        return 2

    candidates.sort(key=lambda x: (x["remaining"], -int(x["sort_index"] or 0)), reverse=True)
    selected = candidates[0]
    current_key = read_current_key(args.env)
    changed = current_key != selected["key"]

    for item in results:
        print_status(item, selected["id"])
    print(f"Selected provider: {selected['name']} ({selected['id']}), changed={changed}")

    if args.dry_run:
        return 0

    write_env_key(args.env, selected["key"])
    write_auth_key(args.auth, selected["key"])
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
