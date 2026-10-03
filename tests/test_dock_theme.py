import re

from dock import panel, settings
from dock.theme import R_CARD, R_CONTROL, R_SMALL, R_SURFACE


def radius_of(style, selector):
    block = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", style).group(1)
    return int(re.search(r"border-radius:\s*(\d+)px", block).group(1))


def test_radius_scale_is_concentric():
    assert R_SURFACE > R_CARD > R_CONTROL > R_SMALL > 0


def test_panel_uses_the_scale():
    assert panel.EXPANDED_RADIUS == R_SURFACE
    assert radius_of(panel.STYLE, "QFrame#card") == R_CARD
    assert radius_of(panel.STYLE, "QPushButton#headerButton") == R_CONTROL
    assert radius_of(panel.STYLE, "QProgressBar") == R_SMALL
    assert radius_of(panel.STYLE, "QToolButton#appIcon") == panel.ICON // 2


def test_settings_uses_the_scale():
    for selector in ("QListWidget::item", "QComboBox, QSpinBox"):
        assert radius_of(settings.STYLE, selector) == R_CONTROL
    assert radius_of(settings.STYLE, "QTableWidget") == R_CARD
    assert radius_of(settings.STYLE, "QCheckBox::indicator") == R_SMALL
