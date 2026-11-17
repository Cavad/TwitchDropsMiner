"""Desktop colour themes: palettes and the stylesheet built from them.

Themes are original designs. Some take their mood from a game's general visual style
(colour, shape language), but they use no official names, logos, characters or art.
This module has no Qt dependency so preferences can validate a saved theme key.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_THEME = "midnight"


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    description: str
    colors: dict[str, str]
    font: str = "'Segoe UI'"
    radius: int = 14  # Card corner radius; other radii scale from it.
    title_spacing: str = "0px"
    light: bool = False
    art: dict[str, str] = field(default_factory=dict)

    def color(self, token: str) -> str:
        return self.colors[token]

    def stylesheet(self, arrows: tuple[str, str] | None = None) -> str:
        """Return the stylesheet; ``arrows`` are (down, up) image paths for drop-down and spin controls."""
        c = self.colors
        small = max(2, round(self.radius * 8 / 14))
        hero = self.radius + 4
        tokens = {**c, "font": self.font, "radius": self.radius, "small": small, "hero": hero,
                  "banner_radius": max(2, round(self.radius * 10 / 14)), "title_extra": f" letter-spacing: {self.title_spacing};" if self.title_spacing != "0px" else "",
                  "bar": max(2, round(self.radius * 4 / 14)), "scroll": max(2, round(self.radius * 3 / 14)),
                  "check": max(2, round(self.radius * 5 / 14))}
        sheet = _TEMPLATE.format(**tokens)
        if arrows is not None:
            down, up = (path.replace("\\", "/") for path in arrows)
            sheet += _CONTROLS.format(down=down, up=up, hover=c["button_hover"])
        return sheet


_TEMPLATE = """
QWidget {{ background: {bg}; color: {text}; font-family: {font}; font-size: 14px; }}
QMainWindow {{ background: {bg}; }}
QLabel {{ background: transparent; }}
QLabel[role='muted'] {{ color: {muted}; }}
QLabel[role='eyebrow'] {{ color: {eyebrow}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
QLabel[role='title'] {{ color: {title}; font-size: 32px; font-weight: 700;{title_extra} }}
QLabel[role='section'] {{ color: {section}; font-size: 18px; font-weight: 600; }}
QLabel[role='metric'] {{ color: {metric}; font-size: 32px; font-weight: 600; }}
QFrame#sidebar {{ background: {sidebar}; border-right: 1px solid {sidebar_border}; }}
QFrame#card {{ background: {card}; border: 1px solid {card_border}; border-radius: {radius}px; }}
QFrame#hero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {hero_from},stop:1 {hero_to}); border: 1px solid {hero_border}; border-radius: {hero}px; }}
QFrame#banner {{ background: {banner}; border: 1px solid {hero_border}; border-radius: {banner_radius}px; }}
QPushButton {{ background: {button}; border: 1px solid {button_border}; border-radius: {small}px; padding: 10px 17px; font-weight: 600; min-height: 20px; }}
QPushButton:hover {{ background: {button_hover}; border-color: {button_hover_border}; }}
QPushButton:pressed {{ background: {button_pressed}; }}
QPushButton:focus {{ border: 2px solid {focus}; padding: 9px 16px; }}
QPushButton:disabled {{ color: {disabled_text}; background: {disabled_bg}; border-color: {disabled_border}; }}
QPushButton[role='primary'] {{ background: {accent}; color: {accent_text}; border-color: {accent_border}; font-weight: 700; }}
QPushButton[role='primary']:hover {{ background: {accent_hover}; }}
QPushButton[role='primary']:disabled {{ background: {primary_disabled_bg}; color: {primary_disabled_text}; border-color: {primary_disabled_border}; }}
QPushButton[role='nav'] {{ background: transparent; border: 1px solid transparent; text-align: left; color: {nav_text}; padding: 12px 18px; }}
QPushButton[role='nav']:checked {{ background: {nav_checked_bg}; color: {nav_checked_text}; border-color: {nav_checked_border}; }}
QPushButton[role='nav']:hover {{ background: {nav_hover_bg}; color: {nav_hover_text}; }}
QPushButton[role='nav']:focus {{ border: 2px solid {focus}; padding: 11px 17px; }}
QPushButton[role='link'] {{ background: transparent; border: none; color: {link}; text-align: left; padding: 6px 0; }}
QPushButton[role='link']:focus {{ border: none; padding: 6px 0; text-decoration: underline; }}
QPushButton[role='danger'] {{ color: {danger}; }}
QLineEdit,QComboBox,QSpinBox,QListWidget,QPlainTextEdit,QTableWidget {{ background: {input_bg}; border: 1px solid {input_border}; border-radius: {small}px; padding: 10px; selection-background-color: {selection}; }}
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QListWidget:focus {{ border-color: {accent}; }}
QComboBox QAbstractItemView {{ background: {popup_bg}; color: {popup_text}; selection-background-color: {selection}; }}
QCheckBox {{ spacing: 10px; background: transparent; padding: 7px 0; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: {check}px; background: {input_bg}; border: 1px solid {checkbox_border}; }}
QCheckBox::indicator:checked {{ background: {accent}; border: 4px solid {checkbox_ring}; }}
QProgressBar {{ background: {progress_bg}; border: none; border-radius: {bar}px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {progress}; border-radius: {bar}px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ width: 8px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {scroll_handle}; border-radius: {scroll}px; min-height: 30px; }}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{ height: 0px; }}
QTableWidget {{ gridline-color: {grid}; }}
QTableWidget::item {{ padding: 10px; }}
QHeaderView::section {{ background: {header_bg}; color: {header_text}; padding: 12px; border: none; border-bottom: 1px solid {input_border}; font-weight: 600; }}
QListWidget::item {{ padding: 10px; border-bottom: 1px solid {list_divider}; }}
QToolTip {{ background: {tooltip_bg}; color: {tooltip_text}; border: 1px solid {selection}; padding: 7px; }}
"""

# Flat arrow areas for drop-downs and number fields. Without these, Windows draws its
# own separator strip and arrows, which clash with the themed field and look skewed.
_CONTROLS = """
QComboBox {{ padding-right: 30px; }}
QComboBox::drop-down {{ border: none; width: 30px; background: transparent; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 6px; }}
QSpinBox {{ padding-right: 28px; }}
QSpinBox::up-button, QSpinBox::down-button {{ border: none; width: 26px; background: transparent; subcontrol-origin: border; }}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {hover}; }}
QSpinBox::up-arrow {{ image: url({up}); width: 9px; height: 5px; }}
QSpinBox::down-arrow {{ image: url({down}); width: 9px; height: 5px; }}
"""

# Every palette defines all tokens; tests check this against the template.
_MIDNIGHT = {
    "bg": "#101116", "text": "#ececf5", "muted": "#9294a7", "eyebrow": "#85889d", "title": "#fafaff",
    "section": "#f1f0fa", "metric": "#f5f4ff", "sidebar": "#14151c", "sidebar_border": "#252631",
    "card": "#1a1b24", "card_border": "#2b2c3a", "hero_from": "#252039", "hero_to": "#1a1b29",
    "hero_border": "#493665", "banner": "#282039", "button": "#252631", "button_border": "#363846",
    "button_hover": "#303140", "button_hover_border": "#606274", "button_pressed": "#1e1f29", "focus": "#c3a6ff",
    "disabled_text": "#6c6e80", "disabled_bg": "#20212b", "disabled_border": "#2d2e3a", "accent": "#a178f3",
    "accent_text": "#120c20", "accent_border": "#aa85f8", "accent_hover": "#b18afc",
    "primary_disabled_bg": "#4d3d69", "primary_disabled_text": "#a18bbd", "primary_disabled_border": "#574370",
    "nav_text": "#9ea0b2", "nav_checked_bg": "#2b233e", "nav_checked_text": "#d3b9ff", "nav_checked_border": "#443258",
    "nav_hover_bg": "#22232e", "nav_hover_text": "#f3edff", "link": "#c3a1ff", "danger": "#f9a6b1",
    "input_bg": "#14151d", "input_border": "#353744", "selection": "#604790", "popup_bg": "#22232e",
    "popup_text": "#f0eafa", "checkbox_border": "#55576b", "checkbox_ring": "#d4baff", "progress_bg": "#30303e",
    "progress": "#a178f3", "scroll_handle": "#414352", "grid": "#2b2c38", "header_bg": "#1d1e28",
    "header_text": "#989aaf", "list_divider": "#292a36", "tooltip_bg": "#2b2539", "tooltip_text": "#f1eafa",
    "success": "#83cfb3", "error": "#f0a3b0",
}


def _palette(base: dict[str, str], **overrides: str) -> dict[str, str]:
    unknown = set(overrides) - set(base)
    if unknown:
        raise KeyError(f"Unknown theme tokens: {sorted(unknown)}")
    return {**base, **overrides}


THEMES: dict[str, Theme] = {theme.key: theme for theme in (
    Theme(
        "midnight", "Midnight", "The original violet night.", _MIDNIGHT,
        art={"glow": "#c5a0ff", "a": "#bd98ff", "b": "#7447b8", "c": "#ddc4ff", "d": "#4b2e76",
             "line": "#49355f", "panel": "transparent"},
    ),
    Theme(
        "resonant_tide", "Resonant Tide",
        "Calm sea-glass teal, pale foam and gold, with rippling echoes.",
        _palette(
            _MIDNIGHT, bg="#0b1418", text="#e3f1f1", muted="#8aa6aa", eyebrow="#77a3a3", title="#f4fbfa",
            section="#e9f6f4", metric="#f2fbf9", sidebar="#0e1a1f", sidebar_border="#1d3036", card="#12222a",
            card_border="#21393f", hero_from="#14313a", hero_to="#0f1d24", hero_border="#2f6566", banner="#143038",
            button="#16292f", button_border="#28434a", button_hover="#1d3740", button_hover_border="#4d8a8a",
            button_pressed="#10201f", focus="#e3c98a", disabled_text="#58737a", disabled_bg="#13232a",
            disabled_border="#1f343b", accent="#57d1c4", accent_text="#05211f", accent_border="#7ae0d4",
            accent_hover="#77ded2", primary_disabled_bg="#24504d", primary_disabled_text="#8bb8b2",
            primary_disabled_border="#2d5d59", nav_text="#8fb0b2", nav_checked_bg="#173a40",
            nav_checked_text="#9ff1e6", nav_checked_border="#2b5d60", nav_hover_bg="#142a30",
            nav_hover_text="#eaffff", link="#e3c98a", danger="#f4a3a3", input_bg="#0d1a1f", input_border="#26414a",
            selection="#1f6b66", popup_bg="#15282f", popup_text="#e3f7f4", checkbox_border="#4b7176",
            checkbox_ring="#bff3ea", progress_bg="#1f3a40", progress="#57d1c4", scroll_handle="#2f4c52",
            grid="#1d333a", header_bg="#10242a", header_text="#86aaa9", list_divider="#1d343a",
            tooltip_bg="#16313a", tooltip_text="#e7fbf7", success="#7fe0c2", error="#f4a3a3",
        ),
        radius=16, title_spacing="0.5px",
        art={"sky1": "#16424a", "sky2": "#0b1920", "wave": "#57d1c4", "foam": "#e6fbf6", "gold": "#e3c98a",
             "deep": "#0a2a30"},
    ),
    Theme(
        "neon_hollow", "Neon Hollow",
        "Night-district street style: acid yellow on black, hazard stripes and halftone.",
        _palette(
            _MIDNIGHT, bg="#0c0c0b", text="#f2f2ea", muted="#9d9d90", eyebrow="#c8d43a", title="#ffffff",
            section="#f7f7ec", metric="#e9f53d", sidebar="#121210", sidebar_border="#2a2a24", card="#171714",
            card_border="#33332a", hero_from="#22230f", hero_to="#151512", hero_border="#6b7316", banner="#25270e",
            button="#1f1f1a", button_border="#3b3b31", button_hover="#2a2a22", button_hover_border="#a8b52a",
            button_pressed="#141410", focus="#e9f53d", disabled_text="#6b6b60", disabled_bg="#191915",
            disabled_border="#2a2a23", accent="#e2f03a", accent_text="#11120a", accent_border="#f0fb6a",
            accent_hover="#eefa62", primary_disabled_bg="#4d5218", primary_disabled_text="#a6ab72",
            primary_disabled_border="#5a601d", nav_text="#a3a395", nav_checked_bg="#2a2c10",
            nav_checked_text="#ecf74e", nav_checked_border="#5e6415", nav_hover_bg="#1d1d17",
            nav_hover_text="#ffffff", link="#ecf74e", danger="#ff8f8f", input_bg="#10100e", input_border="#3a3a30",
            selection="#5d6416", popup_bg="#1d1d17", popup_text="#f5f5e8", checkbox_border="#64645a",
            checkbox_ring="#f5fbb0", progress_bg="#2e2e26", progress="#e2f03a", scroll_handle="#45453a",
            grid="#2a2a23", header_bg="#1a1a15", header_text="#b9c240", list_divider="#2a2a23",
            tooltip_bg="#22230f", tooltip_text="#f8f8ea", success="#b9f35b", error="#ff8f8f",
        ),
        font="'Bahnschrift', 'Segoe UI'", radius=4, title_spacing="1px",
        art={"yellow": "#e2f03a", "ink": "#0c0c0b", "pink": "#ff5fa8", "teal": "#3fe0c5", "paper": "#f2f2ea",
             "screen": "#1b1d10"},
    ),
    Theme(
        "office", "Office",
        "Bright and businesslike: white surfaces, calm blue accents, flat document art.",
        _palette(
            _MIDNIGHT, bg="#f3f4f7", text="#1f2430", muted="#5d6474", eyebrow="#4f6a91", title="#141a26",
            section="#1b2230", metric="#1c4f99", sidebar="#ffffff", sidebar_border="#dfe3ea", card="#ffffff",
            card_border="#dde1e8", hero_from="#e8f0fd", hero_to="#ffffff", hero_border="#b9cdee", banner="#e6eefc",
            button="#ffffff", button_border="#c9cfda", button_hover="#eef2f8", button_hover_border="#8ea3c4",
            button_pressed="#e2e8f2", focus="#2b6fd6", disabled_text="#9aa1ad", disabled_bg="#eef0f3",
            disabled_border="#dde0e6", accent="#2b6fd6", accent_text="#ffffff", accent_border="#2463c4",
            accent_hover="#3a7de3", primary_disabled_bg="#a9c3ea", primary_disabled_text="#eef4fd",
            primary_disabled_border="#a0bbe4", nav_text="#4a5262", nav_checked_bg="#e3edfc",
            nav_checked_text="#1d5bbd", nav_checked_border="#c5d8f6", nav_hover_bg="#f0f3f8",
            nav_hover_text="#141a26", link="#1f62c9", danger="#c23b4a", input_bg="#ffffff", input_border="#c9cfda",
            selection="#cfe0fb", popup_bg="#ffffff", popup_text="#1f2430", checkbox_border="#9aa3b2",
            checkbox_ring="#cfe0fb", progress_bg="#e1e6ee", progress="#2b6fd6", scroll_handle="#c2c8d3",
            grid="#e4e7ed", header_bg="#f6f7fa", header_text="#4f5868", list_divider="#e6e9ee",
            tooltip_bg="#ffffff", tooltip_text="#1f2430", success="#1e8a5c", error="#c23b4a",
        ),
        radius=6, light=True,
        art={"paper": "#ffffff", "blue": "#2b6fd6", "sky": "#e3edfc", "green": "#34a26d", "orange": "#f0a03a",
             "line": "#c9d3e3", "ink": "#2a3446"},
    ),
    Theme(
        "starlit_rail", "Starlit Rail",
        "A night voyage between stars: deep indigo, warm gold and constellation lines.",
        _palette(
            _MIDNIGHT, bg="#0b0d1c", text="#ebe8f5", muted="#9a9ab7", eyebrow="#c8ad78", title="#fdf7ea",
            section="#f3eee2", metric="#f6dfa8", sidebar="#0e1124", sidebar_border="#21253f", card="#141831",
            card_border="#272c4d", hero_from="#1f2147", hero_to="#121530", hero_border="#5a4f7e", banner="#1d2044",
            button="#1a1e3a", button_border="#2e3358", button_hover="#232850", button_hover_border="#8b7a55",
            button_pressed="#121530", focus="#e9c987", disabled_text="#62658a", disabled_bg="#151834",
            disabled_border="#232744", accent="#e4bf74", accent_text="#1a1305", accent_border="#efd08f",
            accent_hover="#efcf8c", primary_disabled_bg="#5a4c2d", primary_disabled_text="#b5a37c",
            primary_disabled_border="#665634", nav_text="#a3a5c4", nav_checked_bg="#262a52",
            nav_checked_text="#f3d79c", nav_checked_border="#4a4470", nav_hover_bg="#181c3a",
            nav_hover_text="#fff6e2", link="#efcf8c", danger="#f7a3b2", input_bg="#0f1228", input_border="#2c3155",
            selection="#4a4278", popup_bg="#181c3a", popup_text="#f1edf9", checkbox_border="#555a85",
            checkbox_ring="#f6e2b4", progress_bg="#262a4a", progress="#e4bf74", scroll_handle="#363b63",
            grid="#22264a", header_bg="#13163a", header_text="#b8a477", list_divider="#22264a",
            tooltip_bg="#1f2147", tooltip_text="#fbf4e3", success="#92dcc0", error="#f7a3b2",
        ),
        radius=16, title_spacing="0.5px",
        art={"sky1": "#262a5c", "sky2": "#0b0d1c", "gold": "#e4bf74", "star": "#fff4d6", "violet": "#8e7cd6",
             "rail": "#b9975a"},
    ),
    Theme(
        "anomaly_city", "Anomaly City",
        "A city after dark where something strange glows: magenta and cyan neon, rifts and glitches.",
        _palette(
            _MIDNIGHT, bg="#0d0a14", text="#f0eaf6", muted="#9d93ad", eyebrow="#ff7ac0", title="#ffffff",
            section="#f6f0fb", metric="#7ff0ff", sidebar="#120e1b", sidebar_border="#2a2138", card="#18121f",
            card_border="#33263f", hero_from="#2a1235", hero_to="#121a2c", hero_border="#7a2d6a", banner="#2a1233",
            button="#21182b", button_border="#3b2c4a", button_hover="#2c1f38", button_hover_border="#c0479a",
            button_pressed="#170f20", focus="#7ff0ff", disabled_text="#6d6280", disabled_bg="#1b1424",
            disabled_border="#2c2238", accent="#ff4fa3", accent_text="#1b0612", accent_border="#ff79bb",
            accent_hover="#ff6db4", primary_disabled_bg="#5c2346", primary_disabled_text="#c191ad",
            primary_disabled_border="#6b2a52", nav_text="#a99bbd", nav_checked_bg="#2c1534",
            nav_checked_text="#ff9ccf", nav_checked_border="#5b2350", nav_hover_bg="#1f1729",
            nav_hover_text="#ffffff", link="#7ff0ff", danger="#ff9c9c", input_bg="#120d1a", input_border="#3a2c48",
            selection="#6b2457", popup_bg="#1f1729", popup_text="#f6efff", checkbox_border="#665777",
            checkbox_ring="#ffc2e1", progress_bg="#2d2338", progress="#ff4fa3", scroll_handle="#45364f",
            grid="#2b2136", header_bg="#1a1323", header_text="#d78ec0", list_divider="#2b2136",
            tooltip_bg="#2a1235", tooltip_text="#fbf2ff", success="#7ff0c8", error="#ff9c9c",
        ),
        radius=10, title_spacing="0.5px",
        art={"pink": "#ff4fa3", "cyan": "#36e2ff", "violet": "#8c5cff", "night1": "#251238", "night2": "#0d0a14",
             "window": "#ffd86b"},
    ),
)}


def theme(key: str | None) -> Theme:
    """Return the theme for a saved key, falling back to the default for unknown keys."""
    return THEMES.get(key or "", THEMES[DEFAULT_THEME])
