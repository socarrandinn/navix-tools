import json
import os
from datetime import datetime, timezone

import pytest

from dock.usage import (
    UsageSnapshot,
    UsageWindow,
    age_text,
    read_claude,
    read_codex,
    record_claude,
    reset_text,
    window_label,
)

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
TS = int(NOW.timestamp())


def statusline_input(five=34, week=71, five_reset=TS + 7200, week_reset=TS + 3 * 86400):
    return json.dumps({
        "model": {"display_name": "Opus"},
        "rate_limits": {
            "five_hour": {"used_percentage": five, "resets_at": five_reset},
            "seven_day": {"used_percentage": week, "resets_at": week_reset},
        },
    })


def test_window_label():
    assert window_label(300) == "5 h"
    assert window_label(10080) == "Semana"
    assert window_label(60) == "1 h"
    assert window_label(2880) == "2 d"


def test_reset_and_age_text():
    assert reset_text(datetime.fromtimestamp(TS + 7800, timezone.utc), NOW) == "reinicia en 2 h 10 min"
    assert reset_text(datetime.fromtimestamp(TS + 3 * 86400 + 3600, timezone.utc), NOW) == "reinicia en 3 d 1 h"
    assert reset_text(datetime.fromtimestamp(TS + 59, timezone.utc), NOW) == "reinicia en 1 min"
    assert reset_text(None, NOW) == ""
    assert age_text(datetime.fromtimestamp(TS - 30, timezone.utc), NOW) == "actualizado recién"
    assert age_text(datetime.fromtimestamp(TS - 300, timezone.utc), NOW) == "actualizado hace 5 min"
    assert age_text(datetime.fromtimestamp(TS - 7200, timezone.utc), NOW) == "actualizado hace 2 h"
    assert age_text(datetime.fromtimestamp(TS - 2 * 86400, timezone.utc), NOW) == "actualizado hace 2 d"


def test_record_and_read_claude(tmp_path):
    path = tmp_path / "ipdock" / "claude_usage.json"
    assert record_claude(statusline_input(), path, NOW) is True
    snap = read_claude(path, NOW)
    assert snap == UsageSnapshot(
        "Claude",
        (
            UsageWindow("5 h", 34.0, datetime.fromtimestamp(TS + 7200, timezone.utc)),
            UsageWindow("Semana", 71.0, datetime.fromtimestamp(TS + 3 * 86400, timezone.utc)),
        ),
        NOW,
        None,
    )


def test_record_claude_ignores_input_without_rate_limits(tmp_path):
    path = tmp_path / "claude_usage.json"
    record_claude(statusline_input(), path, NOW)
    assert record_claude(json.dumps({"model": {}}), path, NOW) is False
    assert record_claude("no es json", path, NOW) is False
    assert read_claude(path, NOW).windows[0].percent == 34.0


def test_read_claude_missing_or_corrupt(tmp_path):
    assert read_claude(tmp_path / "nope.json", NOW) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{roto", encoding="utf-8")
    assert read_claude(bad, NOW) is None


def test_expired_window_reads_as_zero(tmp_path):
    path = tmp_path / "claude_usage.json"
    record_claude(statusline_input(five=90, five_reset=TS - 60), path, NOW)
    five = read_claude(path, NOW).windows[0]
    assert five.percent == 0.0
    assert five.resets_at is None


def test_percent_is_clamped(tmp_path):
    path = tmp_path / "claude_usage.json"
    record_claude(statusline_input(five=140, week=-5), path, NOW)
    assert [w.percent for w in read_claude(path, NOW).windows] == [100.0, 0.0]


def codex_line(primary=70.0, secondary=None, stamp="2026-10-02T18:06:51.766Z", plan="prolite"):
    limits = {
        "limit_id": "codex",
        "primary": {"used_percent": primary, "window_minutes": 10080, "resets_at": TS + 86400},
        "secondary": secondary,
        "plan_type": plan,
    }
    return json.dumps({"timestamp": stamp, "type": "event_msg",
                       "payload": {"type": "token_count", "info": None, "rate_limits": limits}})


def write_rollout(root, day, name, lines, mtime=None):
    folder = root / "2026" / "10" / day
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"rollout-{name}.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_read_codex_uses_latest_snapshot(tmp_path):
    write_rollout(tmp_path, "01", "a", [codex_line(10.0, stamp="2026-10-01T10:00:00Z")], mtime=TS - 90000)
    write_rollout(tmp_path, "02", "b", [
        codex_line(60.0, stamp="2026-10-02T17:00:00Z"),
        json.dumps({"type": "response_item", "payload": {}}),
        codex_line(70.0, secondary={"used_percent": 12.5, "window_minutes": 300, "resets_at": TS + 600},
                   stamp="2026-10-02T18:06:51.766Z"),
        json.dumps({"type": "event_msg", "payload": {"type": "token_count", "rate_limits": None}}),
    ], mtime=TS - 3600)
    snap = read_codex(tmp_path, NOW)
    assert snap.source == "Codex"
    assert snap.plan == "prolite"
    assert snap.captured_at == datetime(2026, 10, 2, 18, 6, 51, 766000, tzinfo=timezone.utc)
    assert [(w.label, w.percent) for w in snap.windows] == [("5 h", 12.5), ("Semana", 70.0)]


def test_read_codex_skips_files_without_limits(tmp_path):
    write_rollout(tmp_path, "01", "old", [codex_line(15.0)], mtime=TS - 90000)
    write_rollout(tmp_path, "02", "new", [json.dumps({"type": "session_meta"})], mtime=TS - 60)
    assert read_codex(tmp_path, NOW).windows[0].percent == 15.0


def test_read_codex_missing_dir_or_garbage(tmp_path):
    assert read_codex(tmp_path / "nope", NOW) is None
    write_rollout(tmp_path, "01", "x", ["{roto", '"rate_limits" pero no json'])
    assert read_codex(tmp_path, NOW) is None


@pytest.mark.parametrize("percent, level", [(0, "ok"), (69.9, "ok"), (70, "warn"), (89.9, "warn"), (90, "high")])
def test_window_level(percent, level):
    assert UsageWindow("5 h", percent, None).level == level
