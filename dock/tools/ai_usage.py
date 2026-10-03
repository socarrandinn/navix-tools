from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..statusline import usage_path
from ..tool import Tool
from ..usage import UsageSnapshot, age_text, read_claude, read_codex, reset_text
from ..worker import RunAsync, run_async

SOURCES = ("Claude", "Codex")
HINTS = {
    "Claude": "Sin datos. Ejecutá `python -m dock.statusline install` y usá Claude Code.",
    "Codex": "Sin datos. Usá Codex CLI para registrar el uso.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AiUsageTool(Tool):
    title = "Uso de IA"
    icon = "📊"
    refresh_ms = 60_000

    def __init__(
        self,
        read_claude: Callable[[], UsageSnapshot | None] | None = None,
        read_codex: Callable[[], UsageSnapshot | None] | None = None,
        now: Callable[[], datetime] = _now,
        run: RunAsync = run_async,
    ):
        self._now = now
        self._read_claude = read_claude or (lambda: read_claude_default(self._now()))
        self._read_codex = read_codex or (lambda: read_codex_default(self._now()))
        self._run = run
        self.loading = False
        self.headers: dict[str, QLabel] = {}
        self.ages: dict[str, QLabel] = {}
        self.rows: dict[str, list[tuple[QLabel, QProgressBar]]] = {source: [] for source in SOURCES}
        self._grids: dict[str, QGridLayout] = {}

    def create_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for source in SOURCES:
            header = QLabel(source)
            header.setStyleSheet("font-weight: 600; margin-top: 4px;")
            age = QLabel("")
            age.setWordWrap(True)
            age.setStyleSheet("color: #8b949e; font-size: 11px;")
            grid = QGridLayout()
            grid.setColumnStretch(1, 1)
            layout.addWidget(header)
            layout.addLayout(grid)
            layout.addWidget(age)
            self.headers[source], self.ages[source], self._grids[source] = header, age, grid
        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #f85149;")
        layout.addWidget(self.message)
        return widget

    def refresh(self) -> None:
        if self.loading:
            return
        self.loading = True
        self._run(lambda: (self._read_claude(), self._read_codex()), self._show, self._show_error)

    def _show(self, snapshots) -> None:
        self.loading = False
        self.message.setText("")
        now = self._now()
        for source, snapshot in zip(SOURCES, snapshots):
            self._fill(source, snapshot, now)

    def _show_error(self, exc: Exception) -> None:
        self.loading = False
        self.message.setText(f"No se pudo leer el uso: {exc}")

    def _fill(self, source: str, snapshot: UsageSnapshot | None, now: datetime) -> None:
        grid = self._grids[source]
        for label, bar in self.rows[source]:
            for widget in (label, bar):
                grid.removeWidget(widget)
                widget.deleteLater()
        self.rows[source] = []
        if snapshot is None:
            self.headers[source].setText(source)
            self.ages[source].setText(HINTS[source])
            return
        self.headers[source].setText(f"{source} · {snapshot.plan}" if snapshot.plan else source)
        self.ages[source].setText(age_text(snapshot.captured_at, now))
        for index, window in enumerate(snapshot.windows):
            label = QLabel(window.label)
            label.setFixedWidth(52)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(round(window.percent))
            reset = reset_text(window.resets_at, now)
            bar.setFormat(f"{round(window.percent)}% · {reset}" if reset else f"{round(window.percent)}%")
            bar.setProperty("level", window.level)
            bar.style().unpolish(bar)
            bar.style().polish(bar)
            grid.addWidget(label, index, 0)
            grid.addWidget(bar, index, 1)
            self.rows[source].append((label, bar))


def read_claude_default(now: datetime) -> UsageSnapshot | None:
    return read_claude(usage_path(), now)


def read_codex_default(now: datetime) -> UsageSnapshot | None:
    return read_codex(Path.home() / ".codex" / "sessions", now)


def create_tool() -> Tool:
    return AiUsageTool()
