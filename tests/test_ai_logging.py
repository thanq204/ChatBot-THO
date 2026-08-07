import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import log_hook  # noqa: E402
import submit_log  # noqa: E402


def test_codex_hook_emits_only_valid_json_and_submits_current_entry(monkeypatch, tmp_path, capsys):
    entry = {
        "ts": "2026-07-30T12:00:00+07:00",
        "tool": "codex",
        "event": "UserPromptSubmit",
        "prompt": "Xin chào",
    }
    captured = []

    def fake_submit(item):
        captured.append(item)
        return 0

    monkeypatch.setattr(submit_log, "submit_entry", fake_submit)

    log_hook.main.__globals__["PROJECT_ROOT"] = tmp_path
    monkeypatch.setenv("AI_LOG_DIR", str(tmp_path / ".ai-log"))
    monkeypatch.setattr(log_hook, "normalize", lambda data, tool: entry)
    monkeypatch.setattr(log_hook.sys, "argv", ["log_hook.py", "--tool=codex"])
    monkeypatch.setattr(log_hook.sys, "stdin", type("Input", (), {"buffer": type("Buffer", (), {"read": lambda self: b"{}"})()})())

    log_hook.main()

    assert json.loads(capsys.readouterr().out) == {"status": "logged"}
    assert captured == [entry]
