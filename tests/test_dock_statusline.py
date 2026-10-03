import json
import subprocess
from datetime import datetime, timezone

from dock.statusline import install, recorder_command, run, uninstall
from dock.usage import read_claude

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
TS = int(NOW.timestamp())
STDIN = json.dumps({"rate_limits": {"five_hour": {"used_percentage": 20, "resets_at": TS + 600}}})
CAVEMAN = {"type": "command", "command": "powershell -File caveman-statusline.ps1"}


class FakeChain:
    def __init__(self, output="caveman ok", error=None):
        self.calls = []
        self.output = output
        self.error = error

    def __call__(self, command, stdin_text):
        self.calls.append((command, stdin_text))
        if self.error:
            raise self.error
        return self.output


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_run_records_usage_and_returns_chained_status_line(tmp_path):
    usage, chain = tmp_path / "claude_usage.json", tmp_path / "chain.json"
    write_json(chain, CAVEMAN)
    fake = FakeChain()
    assert run(STDIN, usage, chain, NOW, fake) == "caveman ok"
    assert fake.calls == [(CAVEMAN["command"], STDIN)]
    assert read_claude(usage, NOW).windows[0].percent == 20.0


def test_run_without_chain_prints_nothing(tmp_path):
    fake = FakeChain()
    assert run(STDIN, tmp_path / "u.json", tmp_path / "missing.json", NOW, fake) == ""
    assert fake.calls == []


def test_run_survives_chain_failure(tmp_path):
    chain = tmp_path / "chain.json"
    write_json(chain, CAVEMAN)
    fake = FakeChain(error=subprocess.TimeoutExpired("x", 5))
    assert run(STDIN, tmp_path / "u.json", chain, NOW, fake) == ""
    assert (tmp_path / "u.json").exists()


def test_install_chains_previous_status_line_and_keeps_other_settings(tmp_path):
    settings, chain = tmp_path / "settings.json", tmp_path / "chain.json"
    write_json(settings, {"statusLine": CAVEMAN, "theme": "dark"})
    install(settings, chain, "RECORDER")
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["statusLine"] == {"type": "command", "command": "RECORDER"}
    assert data["theme"] == "dark"
    assert json.loads(chain.read_text(encoding="utf-8")) == CAVEMAN
    assert json.loads(settings.with_name("settings.json.ipdock.bak").read_text(encoding="utf-8"))["statusLine"] == CAVEMAN


def test_install_twice_does_not_chain_itself(tmp_path):
    settings, chain = tmp_path / "settings.json", tmp_path / "chain.json"
    write_json(settings, {"statusLine": CAVEMAN})
    install(settings, chain, "RECORDER")
    install(settings, chain, "RECORDER")
    assert json.loads(chain.read_text(encoding="utf-8")) == CAVEMAN


def test_uninstall_restores_previous(tmp_path):
    settings, chain = tmp_path / "settings.json", tmp_path / "chain.json"
    write_json(settings, {"statusLine": CAVEMAN, "theme": "dark"})
    install(settings, chain, "RECORDER")
    uninstall(settings, chain)
    assert json.loads(settings.read_text(encoding="utf-8")) == {"statusLine": CAVEMAN, "theme": "dark"}
    assert not chain.exists()


def test_install_and_uninstall_without_previous_status_line(tmp_path):
    settings, chain = tmp_path / "settings.json", tmp_path / "chain.json"
    write_json(settings, {"theme": "dark"})
    install(settings, chain, "RECORDER")
    uninstall(settings, chain)
    assert json.loads(settings.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_recorder_command_quotes_paths():
    assert recorder_command(r"C:\venv\Scripts\python.exe", r"E:\My Tools\ipdock_statusline.py") == \
        '"C:\\venv\\Scripts\\python.exe" "E:\\My Tools\\ipdock_statusline.py"'
