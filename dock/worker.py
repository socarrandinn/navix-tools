from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_live: set["_Relay"] = set()


class _Relay(QObject):
    """Vive en el hilo de la UI; sus slots corren ahí aunque la señal se emita desde un worker."""

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, on_done: Callable[[Any], None], on_error: Callable[[Exception], None]):
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error
        self.done.connect(self._handle_done)
        self.failed.connect(self._handle_failed)

    @Slot(object)
    def _handle_done(self, value: Any) -> None:
        _live.discard(self)
        self._on_done(value)

    @Slot(object)
    def _handle_failed(self, exc: Exception) -> None:
        _live.discard(self)
        self._on_error(exc)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], relay: _Relay):
        super().__init__()
        self._fn = fn
        self._relay = relay

    def run(self) -> None:
        try:
            value = self._fn()
        except Exception as exc:  # noqa: BLE001 - se reporta a la herramienta
            self._relay.failed.emit(exc)
        else:
            self._relay.done.emit(value)


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None], on_error: Callable[[Exception], None]) -> None:
    relay = _Relay(on_done, on_error)
    _live.add(relay)
    QThreadPool.globalInstance().start(_Job(fn, relay))


RunAsync = Callable[[Callable[[], Any], Callable[[Any], None], Callable[[Exception], None]], None]
