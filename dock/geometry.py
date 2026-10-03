from __future__ import annotations

Rect = tuple[int, int, int, int]

BAR = 40          # ancho de la barra de apps
GRIP = 16         # zona de agarre para arrastrar
ICON = 30         # botón de cada app
ICON_GAP = 4
BAR_PADDING = 8
MARGIN = 12
PANEL_HEIGHT = 420


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def bar_height(tools: int) -> int:
    return GRIP + max(1, tools) * (ICON + ICON_GAP) + BAR_PADDING


def bar_rect(area: Rect, edge: str, position: float, height: int, width: int = BAR, margin: int = MARGIN) -> Rect:
    """Barra pegada al borde; position 0.0 = arriba, 1.0 = abajo del área disponible."""
    ax, ay, aw, ah = area
    height = min(height, ah - 2 * margin)
    travel = max(0, ah - 2 * margin - height)
    y = ay + margin + round(_clamp(position, 0.0, 1.0) * travel)
    x = ax + aw - width - margin if edge == "right" else ax + margin
    return x, y, width, height


def expanded_rect(
    area: Rect,
    edge: str,
    position: float,
    bar_h: int,
    flyout_width: int,
    content_height: int,
    margin: int = MARGIN,
) -> Rect:
    """Barra + app desplegada hacia adentro de la pantalla, con el borde superior en la barra."""
    ax, ay, aw, ah = area
    height = min(max(bar_h, content_height), ah - 2 * margin)
    _, bar_y, _, _ = bar_rect(area, edge, position, bar_h, margin=margin)
    y = round(_clamp(bar_y, ay + margin, ay + ah - margin - height))
    width = BAR + flyout_width
    x = ax + aw - width - margin if edge == "right" else ax + margin
    return x, y, width, height


def snap(area: Rect, x: int, y: int, height: int, width: int = BAR, margin: int = MARGIN) -> tuple[str, float]:
    """Borde más cercano y posición vertical para una barra soltada con esquina superior izquierda en (x, y)."""
    ax, ay, aw, ah = area
    edge = "left" if x + width / 2 < ax + aw / 2 else "right"
    travel = max(1, ah - 2 * margin - height)
    return edge, round(_clamp((y - ay - margin) / travel, 0.0, 1.0), 4)
