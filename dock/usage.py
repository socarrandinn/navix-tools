"""Uso de los planes de Claude y Codex (0-100 %), leído de fuentes locales.

- Claude: Claude Code pasa ``rate_limits`` al comando de la status line (documentado en
  https://code.claude.com/docs/en/statusline). ``dock.statusline`` lo guarda con ``record_claude``.
- Codex: cada sesión guarda eventos con ``rate_limits`` en ``~/.codex/sessions/**/rollout-*.jsonl``.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_WINDOWS = (("five_hour", 300), ("seven_day", 10080))
MAX_CODEX_FILES = 40


@dataclass(frozen=True)
class UsageWindow:
    label: str
    percent: float
    resets_at: datetime | None

    @property
    def level(self) -> str:
        if self.percent >= 90:
            return "high"
        if self.percent >= 70:
            return "warn"
        return "ok"


@dataclass(frozen=True)
class UsageSnapshot:
    source: str
    windows: tuple[UsageWindow, ...]
    captured_at: datetime | None
    plan: str | None


def window_label(minutes: int) -> str:
    if minutes == 10080:
        return "Semana"
    if minutes % 1440 == 0:
        return f"{minutes // 1440} d"
    return f"{round(minutes / 60)} h"


def reset_text(resets_at: datetime | None, now: datetime) -> str:
    if resets_at is None:
        return ""
    minutes = max(1, math.ceil((resets_at - now).total_seconds() / 60))
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"reinicia en {days} d {hours} h" if hours else f"reinicia en {days} d"
    if hours:
        return f"reinicia en {hours} h {mins} min" if mins else f"reinicia en {hours} h"
    return f"reinicia en {mins} min"


def age_text(captured_at: datetime | None, now: datetime) -> str:
    if captured_at is None:
        return ""
    seconds = (now - captured_at).total_seconds()
    if seconds < 60:
        return "actualizado recién"
    if seconds < 3600:
        return f"actualizado hace {int(seconds // 60)} min"
    if seconds < 86400:
        return f"actualizado hace {int(seconds // 3600)} h"
    return f"actualizado hace {int(seconds // 86400)} d"


def _window(label: str, percent, resets_at, now: datetime) -> UsageWindow:
    reset = datetime.fromtimestamp(float(resets_at), timezone.utc) if resets_at is not None else None
    if reset is not None and reset <= now:
        # La ventana ya se reinició desde que se tomó el dato.
        return UsageWindow(label, 0.0, None)
    return UsageWindow(label, max(0.0, min(100.0, float(percent))), reset)


def record_claude(stdin_text: str, path: Path, now: datetime) -> bool:
    """Guarda los rate_limits que Claude Code pasa a la status line. False si no vienen."""
    try:
        limits = json.loads(stdin_text).get("rate_limits")
    except (ValueError, AttributeError):
        return False
    if not isinstance(limits, dict):
        return False
    snapshot = {"captured_at": now.timestamp()}
    for key, _ in CLAUDE_WINDOWS:
        window = limits.get(key)
        if isinstance(window, dict) and window.get("used_percentage") is not None:
            snapshot[key] = {"used_percentage": window["used_percentage"], "resets_at": window.get("resets_at")}
    if len(snapshot) == 1:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(snapshot), encoding="utf-8")
    os.replace(tmp, path)
    return True


def read_claude(path: Path, now: datetime) -> UsageSnapshot | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        windows = tuple(
            _window(window_label(minutes), raw[key]["used_percentage"], raw[key].get("resets_at"), now)
            for key, minutes in CLAUDE_WINDOWS
            if key in raw
        )
        captured = datetime.fromtimestamp(float(raw["captured_at"]), timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return UsageSnapshot("Claude", windows, captured, None) if windows else None


def _codex_snapshot(line: str, now: datetime) -> UsageSnapshot | None:
    try:
        event = json.loads(line)
        limits = event["payload"]["rate_limits"]
        if not isinstance(limits, dict):
            return None
        parts = [limits.get("primary"), limits.get("secondary")]
        windows = sorted(
            (p for p in parts if isinstance(p, dict) and p.get("used_percent") is not None),
            key=lambda p: p.get("window_minutes") or 0,
        )
        if not windows:
            return None
        stamp = event.get("timestamp")
        captured = datetime.fromisoformat(stamp) if stamp else None
        return UsageSnapshot(
            "Codex",
            tuple(_window(window_label(int(p.get("window_minutes") or 0)), p["used_percent"],
                          p.get("resets_at"), now) for p in windows),
            captured,
            limits.get("plan_type"),
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def read_codex(sessions: Path, now: datetime, max_files: int = MAX_CODEX_FILES) -> UsageSnapshot | None:
    if not sessions.is_dir():
        return None
    files = sorted(sessions.rglob("rollout-*.jsonl"), key=_mtime, reverse=True)[:max_files]
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if '"rate_limits"' in line:
                snapshot = _codex_snapshot(line, now)
                if snapshot is not None:
                    return snapshot
    return None
