from datetime import datetime, timedelta, timezone

from dock.tools.ai_usage import AiUsageTool, create_tool
from dock.usage import UsageSnapshot, UsageWindow

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
CLAUDE = UsageSnapshot(
    "Claude",
    (UsageWindow("5 h", 34.0, NOW + timedelta(hours=2, minutes=10)), UsageWindow("Semana", 92.4, NOW + timedelta(days=3))),
    NOW - timedelta(minutes=5),
    None,
)
CODEX = UsageSnapshot("Codex", (UsageWindow("Semana", 70.0, NOW + timedelta(days=1, hours=21)),),
                      NOW - timedelta(hours=22), "prolite")


def run_sync(fn, on_done, on_error):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        on_error(exc)
    else:
        on_done(value)


def make(qtbot, claude=CLAUDE, codex=CODEX):
    tool = AiUsageTool(read_claude=lambda: claude, read_codex=lambda: codex, now=lambda: NOW, run=run_sync)
    widget = tool.create_widget()
    qtbot.addWidget(widget)
    tool.test_widget = widget
    tool.refresh()
    return tool


def bars(tool, source):
    return [(label.text(), bar.value(), bar.format(), bar.property("level")) for label, bar in tool.rows[source]]


def test_create_tool():
    tool = create_tool()
    assert isinstance(tool, AiUsageTool)
    assert tool.icon == "gauge"
    assert tool.title == "Uso de IA"


def test_shows_progress_bars_for_both_plans(qtbot):
    tool = make(qtbot)
    assert bars(tool, "Claude") == [
        ("5 h", 34, "34% · reinicia en 2 h 10 min", "ok"),
        ("Semana", 92, "92% · reinicia en 3 d", "high"),
    ]
    assert bars(tool, "Codex") == [("Semana", 70, "70% · reinicia en 1 d 21 h", "warn")]
    assert tool.headers["Codex"].text() == "Codex · prolite"
    assert tool.headers["Claude"].text() == "Claude"
    assert tool.ages["Claude"].text() == "actualizado hace 5 min"
    assert tool.ages["Codex"].text() == "actualizado hace 22 h"


def test_missing_data_shows_how_to_enable(qtbot):
    tool = make(qtbot, claude=None, codex=None)
    assert tool.rows["Claude"] == []
    assert "python -m dock.statusline install" in tool.ages["Claude"].text()
    assert "Codex" in tool.ages["Codex"].text()


def test_refresh_replaces_rows(qtbot):
    tool = make(qtbot)
    tool.refresh()
    assert len(tool.rows["Claude"]) == 2
    assert len(tool.rows["Codex"]) == 1


def test_read_error_is_shown_not_raised(qtbot):
    def boom():
        raise OSError("disco")

    tool = AiUsageTool(read_claude=boom, read_codex=lambda: CODEX, now=lambda: NOW, run=run_sync)
    widget = tool.create_widget()
    qtbot.addWidget(widget)
    tool.test_widget = widget
    tool.refresh()
    assert "disco" in tool.message.text()
