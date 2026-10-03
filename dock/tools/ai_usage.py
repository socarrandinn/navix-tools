from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..config import AI_SOURCES, DockConfigError, dock_dir, load_dock_config
from ..statusline import usage_path
from ..tool import Tool
from ..usage import UsageSnapshot, age_text, read_claude, read_codex, reset_text
from ..worker import RunAsync, run_async

SOURCES = ("Claude", "Codex")
MODEL_GAP = 16  # separación entre el bloque de cada modelo
BAR_HEIGHT = 6
HINTS = {
    "Claude": "Sin datos. Ejecutá `python -m dock.statusline install` y usá Claude Code.",
    "Codex": "Sin datos. Usá Codex CLI para registrar el uso.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AiUsageTool(Tool):
    title = "Uso de IA"
    icon = "gauge"
    refresh_ms = 60_000

    def __init__(
        self,
        read_claude: Callable[[], UsageSnapshot | None] | None = None,
        read_codex: Callable[[], UsageSnapshot | None] | None = None,
        now: Callable[[], datetime] = _now,
        run: RunAsync = run_async,
        sources: Callable[[], tuple[str, ...]] | None = None,
    ):
        self._now = now
        self._read_claude = read_claude or (lambda: read_claude_default(self._now()))
        self._read_codex = read_codex or (lambda: read_codex_default(self._now()))
        self._run = run
        self._sources = sources or enabled_sources
        self.loading = False
        self.headers: dict[str, QLabel] = {}
        self.ages: dict[str, QLabel] = {}
        self.rows: dict[str, list[tuple[QLabel, QProgressBar, QLabel]]] = {source: [] for source in SOURCES}
        self.blocks: dict[str, QWidget] = {}
        self._grids: dict[str, QGridLayout] = {}

    def create_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(MODEL_GAP)
        self._layout = layout
        for source in SOURCES:
            block = QWidget()
            inner = QVBoxLayout(block)
            inner.setContentsMargins(0, 0, 0, 0)
            inner.setSpacing(6)
            header = QLabel(source)
            header.setStyleSheet("font-weight: 600;")
            age = QLabel("")
            age.setWordWrap(True)
            age.setStyleSheet("color: rgba(240, 244, 248, 150); font-size: 11px;")
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(3)
            grid.setColumnStretch(0, 1)
            inner.addWidget(header)
            inner.addLayout(grid)
            inner.addWidget(age)
            layout.addWidget(block)
            self.blocks[source] = block
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
        enabled = {s.lower() for s in self._sources()}
        for source, snapshot in zip(SOURCES, snapshots):
            shown = source.lower() in enabled
            for widget in (self.blocks[source], self.headers[source], self.ages[source]):
                widget.setVisible(shown)
            self._fill(source, snapshot if shown else None, now, shown)

    def _show_error(self, exc: Exception) -> None:
        self.loading = False
        self.message.setText(f"No se pudo leer el uso: {exc}")

    def _fill(self, source: str, snapshot: UsageSnapshot | None, now: datetime, shown: bool = True) -> None:
        grid = self._grids[source]
        for row in self.rows[source]:
            for widget in row:
                grid.removeWidget(widget)
                widget.deleteLater()
        self.rows[source] = []
        if not shown:
            return
        if snapshot is None:
            self.headers[source].setText(source)
            self.ages[source].setText(HINTS[source])
            return
        self.headers[source].setText(f"{source} · {snapshot.plan}" if snapshot.plan else source)
        self.ages[source].setText(age_text(snapshot.captured_at, now))
        for index, window in enumerate(snapshot.windows):
            # Fila de texto (ventana a la izquierda, % y reinicio a la derecha) y debajo la barra fina.
            label = QLabel(window.label)
            label.setStyleSheet("font-size: 12px;")
            reset = reset_text(window.resets_at, now)
            value = QLabel(f"{round(window.percent)}% · {reset}" if reset else f"{round(window.percent)}%")
            value.setStyleSheet("font-size: 11px; color: rgba(240, 244, 248, 190);")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(round(window.percent))
            bar.setTextVisible(False)
            bar.setFixedHeight(BAR_HEIGHT)
            bar.setProperty("level", window.level)
            bar.style().unpolish(bar)
            bar.style().polish(bar)
            grid.addWidget(label, index * 2, 0)
            grid.addWidget(value, index * 2, 1, Qt.AlignmentFlag.AlignRight)
            grid.addWidget(bar, index * 2 + 1, 0, 1, 2)
            self.rows[source].append((label, bar, value))

    def layout_spacing_between_models(self) -> int:
        return self._layout.spacing()


def enabled_sources() -> tuple[str, ...]:
    try:
        return load_dock_config(dock_dir() / "dock.json").ai_sources
    except DockConfigError:
        return AI_SOURCES


def read_claude_default(now: datetime) -> UsageSnapshot | None:
    return read_claude(usage_path(), now)


def read_codex_default(now: datetime) -> UsageSnapshot | None:
    return read_codex(Path.home() / ".codex" / "sessions", now)


def create_tool() -> Tool:
    return AiUsageTool()
