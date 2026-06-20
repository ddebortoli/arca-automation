"""Stylesheet and theming for the PyQt6 desktop app.

Provides light/dark palettes and a `build_stylesheet` helper so the whole
window can switch themes at runtime.
"""

from __future__ import annotations

from string import Template

ACCENT = "#1D9E75"
ACCENT_HOVER = "#178f68"
ACCENT_PRESSED = "#0F6E56"

LIGHT_PALETTE: dict[str, str] = {
    "accent": ACCENT,
    "accent_hover": ACCENT_HOVER,
    "accent_pressed": ACCENT_PRESSED,
    "accent_soft_bg": "#E1F5EE",
    "accent_soft_fg": "#0F6E56",
    "bg_app": "#f5f5f3",
    "bg_primary": "#ffffff",
    "bg_secondary": "#fafafa",
    "border": "#e8e8e4",
    "border_input": "#dddddd",
    "text_primary": "#1a1a1a",
    "text_secondary": "#888888",
    "text_muted": "#555555",
    "input_disabled_bg": "#f0f0ee",
    "input_disabled_fg": "#bbbbbb",
    "warn_bg": "#FAECE7",
    "warn_border": "#F5C4B3",
    "warn_fg": "#993C1D",
    "ok_bg": "#E1F5EE",
    "ok_border": "#B9E7D2",
    "ok_fg": "#0F6E56",
}

DARK_PALETTE: dict[str, str] = {
    "accent": ACCENT,
    "accent_hover": "#23b888",
    "accent_pressed": "#178f68",
    "accent_soft_bg": "#14352c",
    "accent_soft_fg": "#5fd2ad",
    "bg_app": "#1b1b1d",
    "bg_primary": "#242427",
    "bg_secondary": "#2c2c30",
    "border": "#3a3a3e",
    "border_input": "#48484e",
    "text_primary": "#e6e6e6",
    "text_secondary": "#9a9a9f",
    "text_muted": "#b8b8bd",
    "input_disabled_bg": "#2a2a2d",
    "input_disabled_fg": "#6a6a6f",
    "warn_bg": "#3a2620",
    "warn_border": "#5e392c",
    "warn_fg": "#e9a98f",
    "ok_bg": "#14352c",
    "ok_border": "#22513f",
    "ok_fg": "#7bdcb8",
}

_QSS_TEMPLATE = Template(
    """
QWidget {
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: $text_primary;
    background-color: transparent;
}

QMainWindow {
    background-color: $bg_app;
}

/* ----- Sidebar ----- */
#sidebar {
    background-color: $bg_primary;
    border-right: 1px solid $border;
}

#sidebar_header {
    border-bottom: 1px solid $border;
}

#logo_icon_label {
    background-color: $accent;
    border-radius: 6px;
    color: white;
    font-weight: bold;
}

#app_name_label {
    font-size: 13px;
    font-weight: 600;
    color: $text_primary;
}

#app_sub_label {
    font-size: 11px;
    color: $text_secondary;
}

#nav_section_label {
    font-size: 10px;
    color: $text_secondary;
    letter-spacing: 1px;
    padding: 12px 16px 4px 16px;
}

QPushButton#nav_btn {
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
    margin: 1px 8px;
    min-height: 18px;
    text-align: left;
    color: $text_muted;
    background: transparent;
    font-size: 13px;
}

QPushButton#nav_btn:hover {
    background-color: $bg_secondary;
    color: $text_primary;
}

QPushButton#nav_btn[active="true"] {
    background-color: $accent_soft_bg;
    color: $accent_soft_fg;
    font-weight: 600;
}

#status_bar_widget {
    border-top: 1px solid $border;
}

/* ----- Content ----- */
#content_area {
    background-color: $bg_app;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

#card {
    background-color: $bg_primary;
    border: 1px solid $border;
    border-radius: 10px;
}

#section_title {
    font-size: 14px;
    font-weight: 600;
    color: $text_primary;
}

#section_desc {
    font-size: 12px;
    color: $text_secondary;
}

QLabel#field_label {
    font-size: 12px;
    font-weight: 500;
    color: $text_muted;
}

/* ----- Inputs ----- */
QLineEdit {
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
    background-color: $bg_secondary;
    color: $text_primary;
    selection-background-color: $accent;
}

QLineEdit:focus {
    border-color: $accent;
    background-color: $bg_primary;
}

QLineEdit:disabled {
    background-color: $input_disabled_bg;
    color: $input_disabled_fg;
    border-color: $border;
}

QLineEdit[readOnly="true"] {
    background-color: $bg_secondary;
    color: $text_secondary;
}

QPlainTextEdit, QTextEdit {
    border: 1px solid $border;
    border-radius: 6px;
    background-color: $bg_secondary;
    color: $text_primary;
    selection-background-color: $accent;
}

QCheckBox {
    color: $text_primary;
    spacing: 6px;
}

/* ----- Buttons ----- */
QPushButton#btn_primary {
    background-color: $accent;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
    min-height: 20px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#btn_primary:hover {
    background-color: $accent_hover;
}

QPushButton#btn_primary:pressed {
    background-color: $accent_pressed;
}

QPushButton#btn_secondary {
    background-color: $bg_primary;
    color: $text_primary;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 20px;
    font-size: 12px;
}

QPushButton#btn_secondary:hover {
    background-color: $bg_secondary;
}

QPushButton#btn_eye {
    background: transparent;
    border: none;
    color: $text_secondary;
    padding: 0px;
    min-height: 20px;
}

QPushButton#btn_eye:hover {
    color: $text_primary;
}

/* ----- Toggle group ----- */
QPushButton#toggle_btn_left {
    border: 1px solid $border_input;
    border-right: none;
    background: $bg_secondary;
    color: $text_muted;
    padding: 7px 18px;
    min-height: 18px;
    font-size: 13px;
    border-top-left-radius: 6px;
    border-bottom-left-radius: 6px;
}

QPushButton#toggle_btn_right {
    border: 1px solid $border_input;
    background: $bg_secondary;
    color: $text_muted;
    padding: 7px 18px;
    min-height: 18px;
    font-size: 13px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}

QPushButton#toggle_btn_left[active="true"],
QPushButton#toggle_btn_right[active="true"] {
    background-color: $accent;
    color: white;
    font-weight: 600;
    border-color: $accent;
}

QPushButton#theme_btn {
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 18px;
    color: $text_muted;
    background: $bg_primary;
    font-size: 12px;
    text-align: left;
}

QPushButton#theme_btn:hover {
    background-color: $bg_secondary;
    color: $text_primary;
}

/* ----- Alert banners ----- */
QLabel#alert_warning {
    background: $warn_bg;
    border: 1px solid $warn_border;
    border-radius: 10px;
    padding: 10px 14px;
    color: $warn_fg;
}

QLabel#alert_success {
    background: $ok_bg;
    border: 1px solid $ok_border;
    border-radius: 10px;
    padding: 10px 14px;
    color: $ok_fg;
}

/* ----- Stat cards ----- */
QWidget#stat_card {
    background-color: $bg_secondary;
    border: 1px solid $border;
    border-radius: 8px;
}
"""
)


def build_stylesheet(theme: str = "light") -> str:
    """Return the full QSS for the requested theme (``light`` or ``dark``)."""
    palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
    return _QSS_TEMPLATE.substitute(palette)


APP_STYLESHEET = build_stylesheet("light")
