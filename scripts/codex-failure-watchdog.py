#!/usr/bin/env python3
import argparse
import os
import pathlib
import re
import subprocess
import time


DEFAULT_STATE = "/var/lib/codex-feishu/codex-failure-watchdog.state"
DEFAULT_ROTATE = "/opt/codex-feishu/scripts/codex-balance-rotate.py"
DEFAULT_SERVICE = "cc-connect"

FAIL_PATTERNS = [
    r"insufficient_quota",
    r"rate.?limit",
    r"429",
    r"401",
    r"403",
    r"5\d\d",
    r"upstream.*error",
    r"api.*error",
    r"provider.*(?:failed|error|unavailable)",
    r"codex.*(?:failed|error|exited)",
    r"reply.*(?:failed|error)",
    r"send.*(?:failed|error)",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Watch cc-connect logs and rotate Codex provider after reply/API failures."
    )
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--rotate-script", default=DEFAULT_ROTATE)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--systemd-user", action="store_true")
    parser.add_argument("--lookback-seconds", type=int, default=180)
    parser.add_argument(
        "--min-balance",
        type=float,
        default=float(os.environ.get("CODEX_FEISHU_CODEX_MIN_BALANCE", "20")),
    )
    parser.add_argument(
        "--fallback-min-balance",
        type=float,
        default=float(os.environ.get("CODEX_FEISHU_CODEX_FALLBACK_MIN_BALANCE", "0")),
    )
    parser.add_argument("--restart-service", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_since(path, lookback):
    p = pathlib.Path(path)
    if p.exists():
        try:
            return float(p.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return time.time() - lookback


def write_state(path, value):
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(value) + "\n", encoding="utf-8")


def read_journal(service, since_ts):
    cmd = ["journalctl"]
    if read_journal.systemd_user:
        cmd.append("--user")
    cmd.extend(
        [
            "-u",
            service,
            "--since",
            "@" + str(int(since_ts)),
            "--no-pager",
            "-o",
            "cat",
        ]
    )
    proc = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def has_failure(text):
    lower = text.lower()
    for pattern in FAIL_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return True, pattern
    return False, ""


def rotate(args):
    cmd = [
        "python3",
        args.rotate_script,
        "--exclude-current",
        "--min-balance",
        str(args.min_balance),
        "--fallback-min-balance",
        str(args.fallback_min_balance),
    ]
    if args.restart_service:
        cmd.append("--restart-service")
    if args.dry_run:
        cmd.append("--dry-run")
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


read_journal.systemd_user = False


def main():
    args = parse_args()
    read_journal.systemd_user = args.systemd_user
    now = time.time()
    since = read_since(args.state, args.lookback_seconds)
    text = read_journal(args.service, since)
    failed, pattern = has_failure(text)
    if not failed:
        write_state(args.state, now)
        print("No recent Codex/provider failure.")
        return 0

    print(f"Detected failure pattern: {pattern}")
    result = rotate(args)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    if result.returncode == 0:
        write_state(args.state, now)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
