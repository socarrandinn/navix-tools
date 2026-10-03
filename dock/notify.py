"""Avisos cuando un plan de IA está por agotarse (uso >= umbral), una vez por ciclo de reinicio."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .usage import UsageSnapshot, reset_text

MAX_REMEMBERED = 200


@dataclass(frozen=True)
class Alert:
    key: str
    title: str
    message: str


def usage_alerts(snapshots: Sequence[UsageSnapshot | None], threshold: int, now: datetime) -> list[Alert]:
    alerts = []
    for snapshot in snapshots:
        if snapshot is None:
            continue
        for window in snapshot.windows:
            if window.percent < threshold:
                continue
            cycle = window.resets_at.isoformat() if window.resets_at else "sin-reinicio"
            reset = reset_text(window.resets_at, now)
            alerts.append(Alert(
                key=f"{snapshot.source}|{window.label}|{threshold}|{cycle}",
                title=f"{snapshot.source}: {window.label} al {round(window.percent)} %",
                message="Plan casi agotado" + (f" · {reset}" if reset else ""),
            ))
    return alerts


class AlertLog:
    """Recuerda qué avisos ya se mostraron, también entre reinicios de la app."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self._seen = list(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            self._seen = []

    def fresh(self, alerts: Sequence[Alert]) -> list[Alert]:
        new = [alert for alert in alerts if alert.key not in self._seen]
        if new:
            self._seen = (self._seen + [alert.key for alert in new])[-MAX_REMEMBERED:]
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text(json.dumps(self._seen), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass
        return new


class UsageWatcher:
    """Lee el uso en segundo plano y muestra los avisos nuevos (si están activados)."""

    def __init__(self, read, config, log: AlertLog, show, now, run):
        self._read, self._config, self._log, self._show, self._now, self._run = read, config, log, show, now, run

    def check(self) -> None:
        config = self._config()
        if not config.notify:
            return
        threshold = config.notify_threshold
        self._run(self._read, lambda snapshots: self._notify(snapshots, threshold), lambda exc: None)

    def _notify(self, snapshots, threshold: int) -> None:
        for alert in self._log.fresh(usage_alerts(snapshots, threshold, self._now())):
            self._show(alert)
