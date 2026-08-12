#!/usr/bin/env python3
"""Submit the newest local AI log entry to Phoenix."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without a third-party dependency.

    The pre-push hook can run with Codex's bundled Python, which deliberately
    contains only the standard library.  Keeping this script dependency-free
    means queued logs can still be submitted in that environment.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


_load_dotenv(PROJECT_ROOT / ".env")


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _redact(value: Any, api_key: str) -> Any:
    """Mask secrets before printing a server response."""
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if re.search(r"api[-_]?key|token|authorization|secret|password", key, re.I):
                masked[key] = "[REDACTED]"
            else:
                masked[key] = _redact(item, api_key)
        return masked
    if isinstance(value, list):
        return [_redact(item, api_key) for item in value]
    if isinstance(value, str):
        return value.replace(api_key, "[REDACTED]") if api_key else value
    return value


def _safe_response(body_text: str, api_key: str) -> str:
    try:
        body: Any = json.loads(body_text)
        rendered = json.dumps(_redact(body, api_key), ensure_ascii=False)
    except ValueError:
        rendered = _redact(body_text, api_key)
    return str(rendered)[:4000]


def _read_entries(log_file: Path) -> list[dict[str, Any]]:
    if not log_file.exists():
        raise RuntimeError(f"Log file not found: {log_file}")

    lines = [line for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No log entries to submit")

    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    if not entries:
        raise RuntimeError("No valid JSON log entries")
    return entries


def submit_entries(entries: list[dict[str, Any]]) -> int:
    server = os.environ.get("AI_LOG_SERVER", "").strip()
    api_key = os.environ.get("AI_LOG_API_KEY", "").strip()

    if not server:
        print("[ai-log] AI_LOG_SERVER is not set", file=sys.stderr)
        return 2
    if not api_key:
        print("[ai-log] AI_LOG_API_KEY is not set", file=sys.stderr)
        return 2

    try:
        request = urllib.request.Request(
            server,
            data=json.dumps({"entries": entries}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            status_code = response.status
            body_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        body_text = exc.read().decode("utf-8", errors="replace")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"[ai-log] Submit failed: {exc}", file=sys.stderr)
        return 1

    print(f"[ai-log] HTTP status: {status_code}", file=sys.stderr)
    print(f"[ai-log] Response: {_safe_response(body_text, api_key)}", file=sys.stderr)
    if not 200 <= status_code < 300:
        print("[ai-log] Submission failed: server did not return HTTP 2xx", file=sys.stderr)
        return 1
    return 0


def submit_entry(entry: dict[str, Any]) -> int:
    """Submit exactly the entry produced by the current Codex hook event."""
    return submit_entries([entry])


def main() -> int:
    """Submit the local queue when invoked manually or by git hooks."""
    log_file = _repo_path(os.environ.get("AI_LOG_DIR", ".ai-log")) / "session.jsonl"
    try:
        # Retry the complete local queue so entries kept during an outage are
        # uploaded on the next manual run or git push. Phoenix deduplicates
        # entries that were already accepted.
        entries = _read_entries(log_file)
        for start in range(0, len(entries), 500):
            status = submit_entries(entries[start:start + 500])
            if status != 0:
                return status
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"[ai-log] Submit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
