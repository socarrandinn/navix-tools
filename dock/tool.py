from __future__ import annotations

from abc import ABC, abstractmethod

from PySide6.QtWidgets import QWidget


class Tool(ABC):
    title: str = ""
    icon: str = "•"  # 1-2 caracteres o emoji que se muestra en la barra
    refresh_ms: int = 0

    @abstractmethod
    def create_widget(self) -> QWidget:
        """Crea el cuerpo de la tarjeta. Se llama una vez, en el hilo de la UI."""

    def refresh(self) -> None:
        """Actualiza datos. No debe bloquear: usar dock.worker.run_async para trabajo lento."""
