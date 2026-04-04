from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from model.config import ThemeConfigModel
from server.config import ThemeConfig

THEME_MODE_AUTO = "auto"
THEME_MODE_LIGHT = "light"
THEME_MODE_DARK = "dark"
THEME_LABELS = {
    THEME_MODE_AUTO: "自动",
    THEME_MODE_LIGHT: "浅色",
    THEME_MODE_DARK: "深色",
}


@dataclass(frozen=True)
class ThemeTokens:
    is_dark: bool
    window: QColor
    base: QColor
    surface: QColor
    surface_hover: QColor
    header: QColor
    border: QColor
    text: QColor
    subtle_text: QColor
    accent: QColor
    accent_hover: QColor
    accent_text: QColor
    selection: QColor
    selection_text: QColor


def theme_mode_label(mode: str) -> str:
    return THEME_LABELS.get(mode, THEME_LABELS[THEME_MODE_AUTO])


def color_to_hex(color: QColor) -> str:
    return color.name()


def mix_color(left: QColor, right: QColor, ratio: float) -> QColor:
    ratio = max(0.0, min(1.0, ratio))
    inverse = 1.0 - ratio
    return QColor(
        int(left.red() * inverse + right.red() * ratio),
        int(left.green() * inverse + right.green() * ratio),
        int(left.blue() * inverse + right.blue() * ratio),
    )


def _build_tokens(is_dark: bool) -> ThemeTokens:
    if is_dark:
        return ThemeTokens(
            is_dark=True,
            window=QColor("#1d222b"),
            base=QColor("#242a34"),
            surface=QColor("#2b313c"),
            surface_hover=QColor("#333a47"),
            header=QColor("#323947"),
            border=QColor("#414b5b"),
            text=QColor("#e6edf7"),
            subtle_text=QColor("#98a3b3"),
            accent=QColor("#2f7eea"),
            accent_hover=QColor("#4a93ff"),
            accent_text=QColor("#ffffff"),
            selection=QColor("#254774"),
            selection_text=QColor("#f5f8ff"),
        )

    return ThemeTokens(
        is_dark=False,
        window=QColor("#f4f6f8"),
        base=QColor("#ffffff"),
        surface=QColor("#ffffff"),
        surface_hover=QColor("#edf3fb"),
        header=QColor("#eef2f7"),
        border=QColor("#d7dee8"),
        text=QColor("#1f2937"),
        subtle_text=QColor("#6b7280"),
        accent=QColor("#0078d4"),
        accent_hover=QColor("#005fb3"),
        accent_text=QColor("#ffffff"),
        selection=QColor("#d8e8ff"),
        selection_text=QColor("#10243c"),
    )


def _build_palette(tokens: ThemeTokens) -> QPalette:
    palette = QPalette()
    shadow = mix_color(tokens.border, QColor("#000000"), 0.45)
    dark = mix_color(tokens.border, tokens.window, 0.35)
    midlight = mix_color(tokens.border, tokens.base, 0.3)
    disabled_text = mix_color(tokens.text, tokens.window, 0.58)
    disabled_base = mix_color(tokens.base, tokens.window, 0.32)
    disabled_button = mix_color(tokens.surface, tokens.window, 0.45)

    for group in (QPalette.Active, QPalette.Inactive):
        palette.setColor(group, QPalette.Window, tokens.window)
        palette.setColor(group, QPalette.WindowText, tokens.text)
        palette.setColor(group, QPalette.Base, tokens.base)
        palette.setColor(group, QPalette.AlternateBase, tokens.surface)
        palette.setColor(group, QPalette.ToolTipBase, tokens.surface)
        palette.setColor(group, QPalette.ToolTipText, tokens.text)
        palette.setColor(group, QPalette.Text, tokens.text)
        palette.setColor(group, QPalette.Button, tokens.surface)
        palette.setColor(group, QPalette.ButtonText, tokens.text)
        palette.setColor(group, QPalette.BrightText, QColor("#ffffff"))
        palette.setColor(group, QPalette.Highlight, tokens.accent)
        palette.setColor(group, QPalette.HighlightedText, tokens.accent_text)
        palette.setColor(group, QPalette.PlaceholderText, tokens.subtle_text)
        palette.setColor(group, QPalette.Link, tokens.accent)
        palette.setColor(group, QPalette.Light, tokens.surface_hover)
        palette.setColor(group, QPalette.Midlight, midlight)
        palette.setColor(group, QPalette.Mid, tokens.border)
        palette.setColor(group, QPalette.Dark, dark)
        palette.setColor(group, QPalette.Shadow, shadow)

    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.PlaceholderText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.Base, disabled_base)
    palette.setColor(QPalette.Disabled, QPalette.Button, disabled_button)
    palette.setColor(QPalette.Disabled, QPalette.Highlight, mix_color(tokens.accent, tokens.window, 0.4))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, disabled_text)
    return palette


def _build_stylesheet(tokens: ThemeTokens) -> str:
    button_border = mix_color(tokens.accent, tokens.window, 0.35)
    accent_pressed = mix_color(tokens.accent_hover, tokens.window, 0.15)
    disabled_button = mix_color(tokens.surface, tokens.window, 0.35)
    disabled_border = mix_color(tokens.border, tokens.window, 0.28)

    return f"""
        QWidget {{
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            font-size: 14px;
        }}
        QToolTip {{
            color: {color_to_hex(tokens.text)};
            background-color: {color_to_hex(tokens.surface)};
            border: 1px solid {color_to_hex(tokens.border)};
        }}
        QPushButton {{
            background-color: {color_to_hex(tokens.accent)};
            color: {color_to_hex(tokens.accent_text)};
            padding: 6px 12px;
            border-radius: 6px;
            border: 1px solid {color_to_hex(button_border)};
        }}
        QPushButton:hover {{
            background-color: {color_to_hex(tokens.accent_hover)};
        }}
        QPushButton:pressed {{
            background-color: {color_to_hex(accent_pressed)};
        }}
        QPushButton:disabled {{
            background-color: {color_to_hex(disabled_button)};
            color: {color_to_hex(mix_color(tokens.text, tokens.window, 0.58))};
            border: 1px solid {color_to_hex(disabled_border)};
        }}
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
        QComboBox,
        QAbstractSpinBox {{
            background-color: {color_to_hex(tokens.base)};
            border: 1px solid {color_to_hex(tokens.border)};
            border-radius: 6px;
            padding: 4px 8px;
            selection-background-color: {color_to_hex(tokens.accent)};
            selection-color: {color_to_hex(tokens.accent_text)};
        }}
        QLineEdit:focus,
        QPlainTextEdit:focus,
        QTextEdit:focus,
        QComboBox:focus,
        QAbstractSpinBox:focus {{
            border: 1px solid {color_to_hex(tokens.accent)};
        }}
        QComboBox QAbstractItemView {{
            background-color: {color_to_hex(tokens.base)};
            border: 1px solid {color_to_hex(tokens.border)};
            selection-background-color: {color_to_hex(tokens.selection)};
            selection-color: {color_to_hex(tokens.selection_text)};
        }}
        QListWidget {{
            background-color: {color_to_hex(tokens.surface)};
            border: 1px solid {color_to_hex(tokens.border)};
            border-radius: 10px;
            outline: none;
            padding: 4px;
        }}
        QListWidget::item {{
            padding: 10px 12px;
            border-radius: 8px;
            margin: 2px 0;
        }}
        QListWidget::item:selected {{
            background-color: {color_to_hex(tokens.selection)};
            color: {color_to_hex(tokens.selection_text)};
            font-weight: 600;
        }}
        QTabWidget::pane {{
            border: 1px solid {color_to_hex(tokens.border)};
            border-radius: 10px;
            top: -1px;
        }}
        QTabBar::tab {{
            background-color: {color_to_hex(tokens.header)};
            color: {color_to_hex(tokens.text)};
            padding: 7px 14px;
            border: 1px solid {color_to_hex(tokens.border)};
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            background-color: {color_to_hex(tokens.surface)};
        }}
        QHeaderView::section {{
            background-color: {color_to_hex(tokens.header)};
            color: {color_to_hex(tokens.text)};
            border: none;
            border-bottom: 1px solid {color_to_hex(tokens.border)};
            padding: 6px 8px;
            font-weight: 600;
        }}
        QMenu {{
            background-color: {color_to_hex(tokens.surface)};
            border: 1px solid {color_to_hex(tokens.border)};
            padding: 6px;
        }}
        QMenu::item {{
            padding: 6px 18px 6px 10px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background-color: {color_to_hex(tokens.selection)};
            color: {color_to_hex(tokens.selection_text)};
        }}
        QToolButton#themeToggleButton {{
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid {color_to_hex(tokens.border)};
            background-color: {color_to_hex(tokens.surface)};
        }}
        QToolButton#themeToggleButton:hover {{
            background-color: {color_to_hex(tokens.surface_hover)};
        }}
        QFrame#mainHeaderBar {{
            background-color: {color_to_hex(tokens.surface)};
            border: 1px solid {color_to_hex(tokens.border)};
            border-radius: 10px;
        }}
    """


class ThemeManager(QObject):
    theme_changed = Signal(str, bool)

    _instance: "ThemeManager | None" = None

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app
        self._mode = THEME_MODE_AUTO
        self._is_dark = False
        self._has_applied_theme = False
        self._tokens = _build_tokens(False)
        self._app.setStyle("Fusion")

        style_hints = self._app.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._on_system_color_scheme_changed)

    @classmethod
    def initialize(cls, app: QApplication) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls(app)
        return cls._instance

    @classmethod
    def instance(cls) -> "ThemeManager":
        app = QApplication.instance()
        if cls._instance is None:
            if app is None:
                raise RuntimeError("ThemeManager 需要先初始化 QApplication")
            cls._instance = cls(app)
        return cls._instance

    def apply_saved_theme(self):
        config = ThemeConfig.read_config()
        self.apply_theme(config.mode, persist=False)

    def current_mode(self) -> str:
        return self._mode

    def is_dark(self) -> bool:
        return self._is_dark

    def resolved_mode(self) -> str:
        return THEME_MODE_DARK if self._is_dark else THEME_MODE_LIGHT

    def tokens(self) -> ThemeTokens:
        return self._tokens

    def apply_theme(self, mode: str, persist: bool = True):
        normalized_mode = mode if mode in THEME_LABELS else THEME_MODE_AUTO
        next_is_dark = self._should_use_dark(normalized_mode)
        if (
            self._has_applied_theme
            and normalized_mode == self._mode
            and next_is_dark == self._is_dark
        ):
            if persist:
                ThemeConfig.save_config(ThemeConfigModel(mode=normalized_mode))
            return

        self._mode = normalized_mode
        self._is_dark = next_is_dark
        self._tokens = _build_tokens(next_is_dark)
        self._app.setPalette(_build_palette(self._tokens))
        self._app.setStyleSheet(_build_stylesheet(self._tokens))
        self._has_applied_theme = True

        if persist:
            ThemeConfig.save_config(ThemeConfigModel(mode=normalized_mode))
        self.theme_changed.emit(self._mode, self._is_dark)

    def _should_use_dark(self, mode: str) -> bool:
        if mode == THEME_MODE_DARK:
            return True
        if mode == THEME_MODE_LIGHT:
            return False

        style_hints = self._app.styleHints()
        scheme = style_hints.colorScheme() if hasattr(style_hints, "colorScheme") else Qt.ColorScheme.Unknown
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        return self._app.palette().color(QPalette.Window).lightness() < 128

    def _on_system_color_scheme_changed(self, _scheme):
        if self._mode == THEME_MODE_AUTO:
            self.apply_theme(THEME_MODE_AUTO, persist=False)
