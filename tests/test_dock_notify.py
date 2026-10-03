from datetime import datetime, timedelta, timezone

from dock.notify import Alert, AlertLog, usage_alerts
from dock.usage import UsageSnapshot, UsageWindow

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
RESET = NOW + timedelta(hours=2, minutes=10)
CLAUDE = UsageSnapshot("Claude", (UsageWindow("5 h", 91.4, RESET), UsageWindow("Semana", 40, NOW + timedelta(days=3))), NOW, None)
CODEX = UsageSnapshot("Codex", (UsageWindow("Semana", 85, NOW + timedelta(days=1)),), NOW, "prolite")


def test_alerts_for_windows_at_or_above_threshold():
    alerts = usage_alerts([CLAUDE, CODEX, None], threshold=85, now=NOW)
    assert [a.title for a in alerts] == ["Claude: 5 h al 91 %", "Codex: Semana al 85 %"]
    assert alerts[0].message == "Plan casi agotado · reinicia en 2 h 10 min"


def test_no_alerts_below_threshold():
    assert usage_alerts([CLAUDE], threshold=95, now=NOW) == []


def test_alert_key_changes_with_each_reset_cycle():
    first = usage_alerts([CLAUDE], 85, NOW)[0]
    later = UsageSnapshot("Claude", (UsageWindow("5 h", 92, RESET + timedelta(hours=5)),), NOW, None)
    assert usage_alerts([later], 85, NOW)[0].key != first.key


def test_alert_log_shows_each_alert_once_and_persists(tmp_path):
    path = tmp_path / "ipdock" / "alerts.json"
    alerts = usage_alerts([CLAUDE, CODEX], 85, NOW)
    log = AlertLog(path)
    assert log.fresh(alerts) == alerts
    assert log.fresh(alerts) == []
    assert AlertLog(path).fresh(alerts) == []


def test_alert_log_survives_corrupt_file(tmp_path):
    path = tmp_path / "alerts.json"
    path.write_text("{roto", encoding="utf-8")
    alert = Alert("k", "t", "m")
    assert AlertLog(path).fresh([alert]) == [alert]


def run_sync(fn, on_done, on_error):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        on_error(exc)
    else:
        on_done(value)


def test_watcher_shows_fresh_alerts_only_when_enabled(tmp_path):
    from dataclasses import replace

    from dock.config import DockConfig
    from dock.notify import UsageWatcher

    shown = []
    config = {"value": DockConfig(notify_threshold=85)}
    watcher = UsageWatcher(read=lambda: [CLAUDE, CODEX], config=lambda: config["value"],
                           log=AlertLog(tmp_path / "alerts.json"), show=shown.append, now=lambda: NOW, run=run_sync)
    watcher.check()
    assert [a.title for a in shown] == ["Claude: 5 h al 91 %", "Codex: Semana al 85 %"]
    watcher.check()
    assert len(shown) == 2
    config["value"] = replace(config["value"], notify=False, notify_threshold=50)
    watcher.check()
    assert len(shown) == 2


def test_watcher_ignores_read_errors(tmp_path):
    from dock.config import DockConfig
    from dock.notify import UsageWatcher

    def boom():
        raise OSError("disco")

    shown = []
    watcher = UsageWatcher(read=boom, config=DockConfig, log=AlertLog(tmp_path / "a.json"),
                           show=shown.append, now=lambda: NOW, run=run_sync)
    watcher.check()
    assert shown == []
