#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path


CHAT_ID = ""


def now_iso():
    return dt.datetime.now().astimezone().isoformat()


def short_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def ensure_file(path, content):
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def append_jsonl(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def append_unique_line(path, line):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    lines = path.read_text(encoding="utf-8").splitlines()
    if line not in lines:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def escape_md(value):
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def ensure_memory_files(workspace):
    family = workspace / "memory" / "family"
    people = workspace / "memory" / "people"
    for rel in ["messages", "people", "family", "summaries"]:
        ensure_dir(workspace / "memory" / rel)
    ensure_file(
        people / "INDEX.md",
        "# 人物索引\n\n| person_id | display_name | open_ids | profile |\n| --- | --- | --- | --- |\n",
    )
    ensure_file(
        family / "tasks.md",
        "# 家庭待办\n\n| Status | Item | Owner | Source | Created |\n| --- | --- | --- | --- | --- |\n",
    )
    ensure_file(
        family / "shopping.md",
        "# 购物清单\n\n| Status | Item | Source | Created |\n| --- | --- | --- | --- |\n",
    )
    ensure_file(
        family / "decisions.md",
        "# 家庭决策\n\n记录家庭群中已经形成的决定。\n\n| Date | Decision | Source |\n| --- | --- | --- |\n",
    )
    ensure_file(
        family / "facts.md",
        "# 家庭事实\n\n记录家庭层面的长期事实。只写明确、可追溯、适合在家庭群内使用的信息。\n",
    )
    ensure_file(
        family / "preferences.md",
        "# 家庭偏好\n\n记录家庭共同偏好，例如饮食、采购、出行、沟通方式。\n",
    )
    ensure_file(
        family / "files.md",
        "# 文件索引摘要\n\n重要文件的语义摘要放这里；具体路径仍以 `local_files/INDEX.md` 为准。\n",
    )


def new_person_profile(path, person_id, name, open_id):
    body = f"""# {name}

person_id: {person_id}
open_ids:
- {open_id}

## 称呼

- {name}

## 明确记忆

## 偏好

## 近期关注

## 待确认
"""
    path.write_text(body, encoding="utf-8")


def resolve_person(workspace, open_id, name):
    people = workspace / "memory" / "people"
    index = people / "INDEX.md"
    text = index.read_text(encoding="utf-8")
    person_id = None
    for line in text.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|", line)
        if not m:
            continue
        candidate = m.group(1).strip()
        if candidate in {"person_id", "---"}:
            continue
        if open_id and open_id in line:
            person_id = candidate
            break

    if not person_id:
        seed = open_id or name or "unknown"
        person_id = "person_" + short_hash(seed)
        profile_rel = f"memory/people/{person_id}.md"
        profile = people / f"{person_id}.md"
        new_person_profile(profile, person_id, name, open_id)
        row = f"| {person_id} | {escape_md(name)} | `{open_id}` | `{profile_rel}` |"
        append_unique_line(index, row)
    else:
        profile = people / f"{person_id}.md"
        if not profile.exists():
            new_person_profile(profile, person_id, name, open_id)
    return person_id, profile


def add_profile_memory(profile, text, source, time):
    line = f"- {text}。来源：{source}。时间：{time}。置信度：高。"
    lines = profile.read_text(encoding="utf-8").splitlines()
    if line in lines:
        return
    try:
        idx = lines.index("## 明确记忆")
    except ValueError:
        lines.extend(["", "## 明确记忆", ""])
        idx = lines.index("## 明确记忆")
    insert_at = idx + 1
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    lines.insert(insert_at, line)
    if insert_at + 1 < len(lines) and lines[insert_at + 1].strip():
        lines.insert(insert_at + 1, "")
    profile.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_remembered(workspace, profile):
    parts = []
    if profile.exists():
        parts.append("人物档案：\n" + profile.read_text(encoding="utf-8").strip())
    for rel in ["memory/family/tasks.md", "memory/family/shopping.md", "memory/family/decisions.md"]:
        path = workspace / rel
        if path.exists():
            parts.append(rel + ":\n" + path.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(parts)


def message_date(time_text):
    try:
        return dt.datetime.fromisoformat(time_text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return dt.date.today().isoformat()


def capture(args):
    workspace = Path(args.workspace).resolve()
    ensure_memory_files(workspace)
    time = args.time or now_iso()
    message_id = args.message_id or ("fake_" + dt.datetime.now().strftime("%Y%m%d%H%M%S%f"))
    sender_open_id = args.sender_open_id or "unknown_open_id"
    sender_name = args.sender_name or "未命名成员"
    text = args.text or ""

    person_id, profile = resolve_person(workspace, sender_open_id, sender_name)
    source = f"群消息 {message_id} / {sender_name}"
    log_path = workspace / "memory" / "messages" / f"{message_date(time)}.jsonl"
    event = {
        "time": time,
        "chat_id": args.chat_id or CHAT_ID,
        "message_id": message_id,
        "sender_open_id": sender_open_id,
        "sender_name": sender_name,
        "person_id": person_id,
        "message_type": "text",
        "text": text,
        "importance": "normal",
    }
    append_jsonl(log_path, event)

    actions = []
    reply = "NO_REPLY"

    m = re.match(r"^(记住|帮我记住|请记住)[：:\s]*(.+)$", text)
    if m:
        memory_text = m.group(2).strip()
        add_profile_memory(profile, memory_text, source, time)
        append_jsonl(
            workspace / "memory" / "review_queue.jsonl",
            {"time": time, "action": "remember_committed", "person_id": person_id, "text": memory_text, "source": source},
        )
        actions.append("profile_memory_added")
        reply = "已记住。"
    else:
        m = re.match(r"^(忘掉|删除记忆|以后别记)[：:\s]*(.+)$", text)
        if m:
            forget_text = m.group(2).strip()
            append_jsonl(
                workspace / "memory" / "review_queue.jsonl",
                {"time": time, "action": "forget_requested", "person_id": person_id, "text": forget_text, "source": source},
            )
            actions.append("forget_requested")
            reply = "已记录删除请求，等确认后清理对应记忆。"

    if not actions:
        m = re.match(r"^(待办|记一下|提醒一下|提醒)[：:\s]*(.+)$", text)
        if m:
            item = m.group(2).strip()
            append_unique_line(
                workspace / "memory" / "family" / "tasks.md",
                f"| open | {escape_md(item)} | 未指定 | {source} | {time} |",
            )
            actions.append("task_added")
            reply = "已加入家庭待办。"

    if not actions:
        m = re.match(r"^(购物|购物清单|买|采购)[：:\s]*(.+)$", text)
        if m:
            item = m.group(2).strip()
            append_unique_line(
                workspace / "memory" / "family" / "shopping.md",
                f"| open | {escape_md(item)} | {source} | {time} |",
            )
            actions.append("shopping_added")
            reply = "已加入购物清单。"

    if not actions and re.search(r"你记得.*什么|记得什么|查记忆|查看记忆", text):
        actions.append("memory_read")
        reply = read_remembered(workspace, profile)

    return {
        "ok": True,
        "reply": reply,
        "actions": actions,
        "person_id": person_id,
        "profile": str(profile),
        "message_log": str(log_path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--chat-id", default=CHAT_ID)
    parser.add_argument("--message-id", default="")
    parser.add_argument("--sender-open-id", default="")
    parser.add_argument("--sender-name", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--time", default="")
    args = parser.parse_args()
    print(json.dumps(capture(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
