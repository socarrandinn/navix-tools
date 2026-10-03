from __future__ import annotations

Rect = tuple[int, int, int, int]


def panel_rect(area: Rect, edge: str, width: int, revealed: bool, margin: int = 12, handle: int = 6) -> Rect:
    ax, ay, aw, ah = area
    y = ay + margin
    height = ah - 2 * margin
    if revealed:
        x = ax + aw - width - margin if edge == "right" else ax + margin
        return x, y, width, height
    x = ax + aw - handle if edge == "right" else ax
    return x, y, handle, height
