from __future__ import annotations

Rect = tuple[int, int, int, int]

BAR = 54          # grosor de la barra de apps (riel + columna de íconos)
RAIL = 10         # riel de arrastre, a todo lo largo del lado pegado a la pantalla
ICON = 28         # botón de cada app
ICON_GAP = 4
END_PAD = 16      # aire en cada extremo de la columna de íconos
SETTINGS_SLOT = 28  # engranaje (menú) al final de la barra
FLARE = 8         # curva cóncava donde la gota se "derrama" sobre el borde de la pantalla
MARGIN = 12       # separación mínima a lo largo del borde
GAP = 16          # hueco entre la barra y la gota de la app (lugar para el cuello líquido)
PANEL_HEIGHT = 420
EDGES = ("left", "right", "top")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def is_vertical(edge: str) -> bool:
    return edge != "top"


def bar_length(tools: int) -> int:
    return max(1, tools) * (ICON + ICON_GAP) + SETTINGS_SLOT + 2 * END_PAD + 2 * FLARE


def bar_rect(area: Rect, edge: str, position: float, length: int, thickness: int = BAR,
             margin: int = MARGIN) -> Rect:
    """Barra pegada al borde (sin margen) y ubicada a lo largo de él; position va de 0.0 a 1.0."""
    ax, ay, aw, ah = area
    position = _clamp(position, 0.0, 1.0)
    if is_vertical(edge):
        length = min(length, ah - 2 * margin)
        y = ay + margin + round(position * max(0, ah - 2 * margin - length))
        x = ax + aw - thickness if edge == "right" else ax
        return x, y, thickness, length
    length = min(length, aw - 2 * margin)
    x = ax + margin + round(position * max(0, aw - 2 * margin - length))
    return x, ay, length, thickness


def expanded_rect(area: Rect, edge: str, position: float, length: int, flyout_width: int,
                  content_height: int, margin: int = MARGIN) -> Rect:
    """Barra + app desplegada hacia adentro de la pantalla, sin despegarse del borde."""
    ax, ay, aw, ah = area
    bx, by, _, _ = bar_rect(area, edge, position, length, margin=margin)
    if is_vertical(edge):
        height = min(max(length, content_height), ah - 2 * margin)
        y = round(_clamp(by, ay + margin, ay + ah - margin - height))
        width = BAR + GAP + flyout_width
        x = ax + aw - width if edge == "right" else ax
        return x, y, width, height
    width = min(max(length, flyout_width), aw - 2 * margin)
    x = round(_clamp(bx, ax + margin, ax + aw - margin - width))
    height = min(BAR + GAP + content_height, ah - margin)
    return x, ay, width, height


def snap(area: Rect, x: int, y: int, width: int, height: int, margin: int = MARGIN) -> tuple[str, float]:
    """Borde más cercano (izquierdo, derecho o superior) y posición para una barra soltada en (x, y)."""
    ax, ay, aw, ah = area
    cx, cy = x + width / 2, y + height / 2
    length = max(width, height)
    distances = {"left": cx - ax, "right": ax + aw - cx, "top": cy - ay}
    edge = min(distances, key=distances.get)
    if is_vertical(edge):
        travel = max(1, ah - 2 * margin - length)
        return edge, round(_clamp((cy - length / 2 - ay - margin) / travel, 0.0, 1.0), 4)
    travel = max(1, aw - 2 * margin - length)
    return edge, round(_clamp((cx - length / 2 - ax - margin) / travel, 0.0, 1.0), 4)


def stretched_rect(area: Rect, edge: str, position: float, length: int, pull: float,
                   margin: int = MARGIN) -> Rect:
    """Barra estirada hacia adentro mientras se la arrastra, todavía pegada al borde."""
    x, y, w, h = bar_rect(area, edge, position, length, margin=margin)
    pull = max(0, round(pull))
    if edge == "right":
        return x - pull, y, w + pull, h
    if edge == "left":
        return x, y, w + pull, h
    return x, y, w, h + pull
