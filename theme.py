"""Управление темами оформления (светлая / тёмная / системная).

Модуль держит глобальное состояние текущей темы и предоставляет:

- init_theme(app, config)  — инициализация при старте (читает General.theme);
- apply_theme(app, name)   — живое переключение темы (палитра + иконки);
- icon(name)               — QIcon для действия/меню/тулбара с учётом темы:
  в тёмной теме иконки инвертируются, чтобы читались на тёмном фоне.

Инверсия иконок: PNG грузится как QImage, конвертируется в RGBA8888,
яркость каждого пикселя инвертируется (255 - v) для RGB, альфа не трогается.
Иконки кэшируются по (имя, тема).
"""

import logging

from PyQt5.QtCore import QBuffer, QIODevice
from PyQt5.QtGui import QIcon, QImage, QPalette, QColor, QPixmap
from PyQt5.QtWidgets import QApplication

logger = logging.getLogger("photoeditor.theme")

# Текущее имя темы: 'light' | 'dark' (системная сводится к одной из них)
_current_theme = "light"

# Кэш иконок: (icon_name, theme) -> QIcon
_icon_cache = {}


def current_theme():
    """Вернуть имя активной темы ('light' или 'dark')."""
    return _current_theme


def is_dark():
    """True, если активна тёмная тема."""
    return _current_theme == "dark"


def _dark_palette():
    """Тёмная палитра в стиле Fusion-dark."""
    palette = QPalette()
    window_color = QColor(53, 53, 53)
    text_color = QColor(255, 255, 255)
    disabled_text = QColor(120, 120, 120)
    palette.setColor(QPalette.Window, window_color)
    palette.setColor(QPalette.WindowText, text_color)
    palette.setColor(QPalette.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.AlternateBase, window_color)
    palette.setColor(QPalette.ToolTipBase, text_color)
    palette.setColor(QPalette.ToolTipText, text_color)
    palette.setColor(QPalette.Text, text_color)
    palette.setColor(QPalette.Button, window_color)
    palette.setColor(QPalette.ButtonText, text_color)
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, text_color)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.Disabled, QPalette.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.Disabled, QPalette.Button, QColor(45, 45, 45))
    return palette


def _invert_image(image):
    """Инвертировать RGB-каналы QImage (альфа не трогается)."""
    if image is None or image.isNull():
        return image
    src = image.convertToFormat(QImage.Format_RGBA8888)
    w, h = src.width(), src.height()
    ptr = src.bits()
    ptr.setsize(src.byteCount())
    import numpy as np
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, src.bytesPerLine()).copy()
    view = arr[:, :w * 4].reshape(h, w, 4)
    view[:, :, :3] = 255 - view[:, :, :3]  # инверсия R, G, B
    return QImage(view.tobytes(), w, h, w * 4, QImage.Format_RGBA8888).copy()


def icon(name):
    """Вернуть QIcon из icons/<name>.png с учётом темы.

    В тёмной теме пиксели инвертируются, чтобы тёмные иконки
    читались на тёмном фоне. Результат кэшируется.
    """
    from utils import resource_path

    key = (name, _current_theme)
    if key in _icon_cache:
        return _icon_cache[key]

    file_path = resource_path("icons/{}.png".format(name))
    base = QImage(file_path)
    if base.isNull():
        logger.warning("Icon not found or unreadable: %s", file_path)
        result = QIcon()
        _icon_cache[key] = result
        return result

    pixmap = QPixmap.fromImage(base)
    if is_dark():
        inverted = _invert_image(base)
        if inverted is not None and not inverted.isNull():
            pixmap = QPixmap.fromImage(inverted)

    result = QIcon(pixmap)
    _icon_cache[key] = result
    return result


def _refresh_all_icons(app):
    """Пересоздать иконки всех действий главного окна под новую тему.

    Пробегает по всем окнам приложения, ищет QAction с объектным именем
    вида 'act_icon_<name>' (его выставляет MainWindow.createActions) и
    заменяет иконку на theme.icon(<name>).
    """
    from PyQt5.QtWidgets import QAction

    for widget in app.topLevelWidgets():
        for action in widget.findChildren(QAction):
            object_name = action.objectName()
            if object_name.startswith("act_icon_"):
                icon_name = object_name[len("act_icon_"):]
                action.setIcon(icon(icon_name))


def apply_theme(app, name):
    """Применить тему по имени и обновить все окна.

    'system' выбирает светлую (системную) палитру, 'dark' — тёмную.
    После смены палитры иконки всех действий пересоздаются (инверсия
    в тёмной теме) и виджеты принудительно перерисовываются.
    """
    global _current_theme

    if not isinstance(app, QApplication):
        raise TypeError("apply_theme expects a QApplication instance")

    name = (name or "light").lower()
    if name not in ("light", "dark", "system"):
        logger.warning("Unknown theme %r, falling back to 'light'", name)
        name = "light"

    _current_theme = "dark" if name == "dark" else "light"

    if is_dark():
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())

    _refresh_all_icons(app)

    # Принудительная перерисовка всех виджетов под новую палитру
    for widget in app.topLevelWidgets():
        widget.update()


def init_theme(app, config):
    """Инициализировать тему при старте приложения.

    Читает General.theme из конфига (по умолчанию 'light').
    """
    theme_name = "light"
    try:
        if config is not None and "General" in config:
            theme_name = config["General"].get("theme", "light")
    except Exception:
        logger.exception("Failed to read theme from config, using 'light'")
    apply_theme(app, theme_name)
