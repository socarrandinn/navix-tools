from __future__ import annotations

Rect = tuple[int, int, int, int]

BUBBLE = 50
MARGIN = 12
PANEL_HEIGHT = 420


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def bubble_rect(area: Rect, edge: str, position: float, size: int = BUBBLE, margin: int = MARGIN) -> Rect:
    """Círculo pegado al borde; position 0.0 = arriba, 1.0 = abajo del área disponible."""
    ax, ay, aw, ah = area
    travel = max(0, ah - 2 * margin - size)
    y = ay + margin + round(_clamp(position, 0.0, 1.0) * travel)
    x = ax + aw - size - margin if edge == "right" else ax + margin
    return x, y, size, size


def expanded_rect(
    area: Rect, edge: str, width: int, position: float, height: int = PANEL_HEIGHT, margin: int = MARGIN
) -> Rect:
    """Panel desplegado junto al borde, centrado en el círculo y siempre dentro del área."""
    ax, ay, aw, ah = area
    height = min(height, ah - 2 * margin)
    _, bubble_y, _, size = bubble_rect(area, edge, position, margin=margin)
    y = round(_clamp(bubble_y + size / 2 - height / 2, ay + margin, ay + ah - margin - height))
    x = ax + aw - width - margin if edge == "right" else ax + margin
    return x, y, width, height


def snap(area: Rect, x: int, y: int, size: int = BUBBLE, margin: int = MARGIN) -> tuple[str, float]:
    """Borde más cercano y posición vertical para un círculo soltado con esquina superior izquierda en (x, y)."""
    ax, ay, aw, ah = area
    edge = "left" if x + size / 2 < ax + aw / 2 else "right"
    travel = max(1, ah - 2 * margin - size)
    return edge, round(_clamp((y - ay - margin) / travel, 0.0, 1.0), 4)
