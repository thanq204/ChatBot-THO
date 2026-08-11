#!/usr/bin/env python3
"""Recover Codex prompts from the latest Desktop transcript.

Codex Desktop can keep a project hook from an older session alive while a
newer task is already running. This small repair utility imports the user
messages visible in the latest rollout transcript, skips entries it has
already imported, and sends the new entries through the normal Phoenix
client. It is intentionally separate from the live hook so recovery is
explicit and idempotent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import argparse
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import submit_log


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_FILE = PROJECT_ROOT / ".ai-log" / "session.jsonl"
VN_TZ = timezone(timedelta(hours=7))
USER_BLOCK = re.compile(
    r"(?ms)\[(\d+)\] user:\s*(.*?)(?=\n\n\[\d+\] (?:user|assistant|tool)|$)"
)


def _git(command: list[str]) -> str:
    try:
        return subprocess.check_output(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def _latest_transcript() -> Path:
    sessions_root = Path(os.environ.get("USERPROFILE", "")) / ".codex" / "sessions"
    candidates = list(sessions_root.rglob("rollout-*.jsonl")) if sessions_root.exists() else []
    if not candidates:
        raise RuntimeError(f"No Codex transcript found under {sessions_root}")
    # File mtimes can lag behind the active Desktop rollout. The timestamp is
    # part of the filename and is stable, so use it instead.
    return max(candidates, key=lambda path: path.name)


def _transcript_data(path: Path) -> tuple[str, str]:
    best_message = ""
    session_id = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        payload = record.get("payload", {})
        session_id = session_id or str(payload.get("id", ""))
        if record.get("type") == "event_msg" and payload.get("type") == "user_message":
            message = str(payload.get("message", ""))
            if len(USER_BLOCK.findall(message)) > len(USER_BLOCK.findall(best_message)):
                best_message = message

    if not best_message:
        raise RuntimeError(f"No user-message transcript found in {path}")
    if not session_id:
        session_id = path.stem.removeprefix("rollout-")
    return session_id, best_message


def _existing_turns() -> set[str]:
    if not LOG_FILE.exists():
        return set()
    turns: set[str] = set()
    for line in LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and entry.get("turn_id"):
            turns.add(str(entry["turn_id"]))
    return turns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extra-prompt",
        action="append",
        default=[],
        help="Also import a prompt that has not reached the Desktop transcript yet.",
    )
    args = parser.parse_args()
    transcript = _latest_transcript()
    session_id, message = _transcript_data(transcript)
    prompts = [(int(number), prompt.strip()) for number, prompt in USER_BLOCK.findall(message)]
    prompts = [(number, prompt) for number, prompt in prompts if prompt]
    for prompt in args.extra_prompt:
        clean_prompt = prompt.strip()
        if clean_prompt:
            digest = hashlib.sha256(clean_prompt.encode("utf-8")).hexdigest()[:12]
            prompts.append((f"extra-{digest}", clean_prompt))

    repo = _git(["git", "remote", "get-url", "origin"]).rstrip("/").split("/")[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    existing = _existing_turns()
    now = datetime.now(VN_TZ).isoformat()
    entries: list[dict[str, Any]] = []
    for number, prompt in prompts:
        turn_id = f"backfill-{session_id}-{number}"
        if turn_id in existing:
            continue
        entries.append(
            {
                "ts": now,
                "tool": "codex",
                "event": "UserPromptSubmit",
                "session_id": session_id,
                "model": "",
                "repo": repo,
                "branch": _git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
                "commit": _git(["git", "rev-parse", "--short", "HEAD"]),
                "student": _git(["git", "config", "user.email"]),
                "prompt": prompt[:1000],
                "turn_id": turn_id,
                "transcript_path": str(transcript),
            }
        )

    if not entries:
        print(f"[ai-log] Nothing new to backfill from {transcript.name}")
        return 0

    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"[ai-log] Backfilled {len(entries)} Codex prompts from {transcript.name}")
    return submit_log.submit_entries(entries)


if __name__ == "__main__":
    raise SystemExit(main())
