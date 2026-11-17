"""Desktop themes: palettes, stylesheet, persisted choice and page artwork."""

import hashlib
import json
import os

import pytest

from desktop.preferences import DesktopPreferences
from desktop.themes import DEFAULT_THEME, THEMES, theme


pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from desktop.theme_art import PAGES, ThemeArt, paint  # noqa: E402


# SHA-256 of the stylesheet the app used before themes existed.
ORIGINAL_STYLESHEET = "dd749b67ac4c652e629e15c4f54f9c8dd2de254ca736532111b668af7fa5c41d"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_default_theme_keeps_the_original_look_apart_from_focus_sizing():
    assert DEFAULT_THEME == "midnight"
    sheet = THEMES["midnight"].stylesheet()
    # The only intended change: focus rings keep each button's size (they used to grow
    # it by 2px, which shifted the focused button), and nav/link buttons get focus styles.
    focus = "QPushButton:focus { border: 2px solid #c3a6ff; padding: 9px 16px; }"
    assert focus in sheet
    original = "\n".join(
        line for line in sheet.replace(focus, "QPushButton:focus { border: 2px solid #c3a6ff; }").split("\n")
        if not line.startswith(("QPushButton[role='nav']:focus", "QPushButton[role='link']:focus"))
    )
    assert hashlib.sha256(original.encode()).hexdigest() == ORIGINAL_STYLESHEET


def test_drop_down_and_spin_arrows_are_themed_only_when_images_are_given():
    plain = THEMES["office"].stylesheet()
    assert "QComboBox::drop-down" not in plain
    sheet = THEMES["office"].stylesheet(("C:\\tmp\\down.png", "C:\\tmp\\up.png"))
    assert sheet.startswith(plain)
    assert "url(C:/tmp/down.png)" in sheet and "url(C:/tmp/up.png)" in sheet


def test_six_complete_themes_build_valid_stylesheets():
    assert list(THEMES) == ["midnight", "resonant_tide", "neon_hollow", "office", "starlit_rail", "anomaly_city"]
    tokens = set(THEMES["midnight"].colors)
    for item in THEMES.values():
        assert set(item.colors) == tokens, item.key
        assert all(QColor(value).isValid() for value in item.colors.values()), item.key
        stylesheet = item.stylesheet()
        assert "{" in stylesheet and "{{" not in stylesheet and "None" not in stylesheet
        assert item.name and item.description
    assert THEMES["office"].light and not THEMES["midnight"].light


def test_unknown_or_missing_theme_falls_back_to_default():
    assert theme(None).key == DEFAULT_THEME
    assert theme("removed-theme").key == DEFAULT_THEME
    assert theme("office").key == "office"


def test_theme_preference_round_trip_and_validation(tmp_path):
    path = tmp_path / "prefs.json"
    prefs = DesktopPreferences(path)
    assert prefs.values["theme"] == DEFAULT_THEME
    prefs.save({**prefs.values, "theme": "starlit_rail"})
    assert DesktopPreferences(path).values["theme"] == "starlit_rail"
    with pytest.raises(ValueError):
        prefs.save({**prefs.values, "theme": "not-a-theme"})
    with pytest.raises(ValueError):
        prefs.save({**prefs.values, "theme": True})
    path.write_text(json.dumps({"theme": "not-a-theme", "notifications": False}))
    loaded = DesktopPreferences(path)
    assert loaded.values["theme"] == DEFAULT_THEME and loaded.values["notifications"] is False


def render(item, page, width=300, height=110):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(item.colors["bg"]))
    painter = QPainter(image)
    paint(painter, QRectF(0, 0, width, height), page, item)
    painter.end()
    return image


@pytest.mark.parametrize("key", list(THEMES))
def test_every_page_has_its_own_artwork_in_every_theme(app, key):
    item = THEMES[key]
    images = {}
    for page in PAGES:
        image = render(item, page)
        background = QColor(item.colors["bg"]).rgb()
        drawn = sum(image.pixel(x, y) != background for x in range(0, 300, 6) for y in range(0, 110, 6))
        assert drawn > 40, (key, page)
        images[page] = bytes(image.constBits())
    assert len(set(images.values())) == len(PAGES)
    # Art is deterministic, so a page looks the same every time it is drawn.
    assert bytes(render(item, "queue").constBits()) == images["queue"]


def test_artwork_widget_follows_theme_and_rejects_unknown_pages(app):
    artwork = ThemeArt("history", 290, 104)
    assert artwork.theme.key == DEFAULT_THEME
    artwork.set_theme(THEMES["office"])
    assert artwork.theme.key == "office"
    assert artwork.grab().size().width() == 290
    with pytest.raises(ValueError):
        ThemeArt("unknown", 10, 10)
