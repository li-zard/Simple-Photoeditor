"""Общие фикстуры pytest (этап 4 роадмапа).

Особенности:
- QT_QPA_PLATFORM=offscreen устанавливается ДО импорта PyQt5 — тесты
  запускаются headless (без X-сервера, пригодно для CI).
- Команды (commands.py) вызывают editor.window().statusBar(), поэтому
  ImageEditor размещается внутри QMainWindow.
- Корень проекта добавляется в sys.path, чтобы импортировать модули
  приложения независимо от того, откуда запущен pytest.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QImage, qRgb


def make_gradient(width=100, height=100):
    """Детерминированный градиент width×height (Format_RGB32).

    R и G пробегают полный диапазон 0..255 — это гарантирует, что
    autobalance (растяжка гистограммы) реально меняет пиксели.
    """
    image = QImage(width, height, QImage.Format_RGB32)
    for y in range(height):
        for x in range(width):
            image.setPixel(
                x, y,
                qRgb((x * 255) // max(width - 1, 1),
                     (y * 255) // max(height - 1, 1),
                     (x + y) % 256),
            )
    return image


def make_solid_image(width, height, rgb):
    """Прямоугольник width×height, залитый цветом rgb (qRgb)."""
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(rgb)
    return image


def image_bytes(image):
    """Байты пикселей QImage в Format_RGBA8888 — для побайтового сравнения.

    Учитывает выравнивание строк (bytesPerLine); для RGBA8888 padding
    отсутствует, но код устойчив к любому формату-источнику.
    """
    import numpy as np

    img = image.convertToFormat(QImage.Format_RGBA8888)
    h, w = img.height(), img.width()
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, img.bytesPerLine())
    return arr[:, :w * 4].tobytes()


@pytest.fixture(scope="session")
def qapp():
    """Единый QApplication на всю сессию тестов."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def gradient_image():
    """Градиент 100×100 (значение по умолчанию из роадмапа)."""
    return make_gradient(100, 100)


@pytest.fixture
def editor(qapp, gradient_image):
    """ImageEditor с загруженным градиентом, размещённый в QMainWindow.

    QMainWindow нужен, потому что команды обращаются к
    editor.window().statusBar(). updateWindowTitle() безопасно выходит
    рано: parent() не является CustomMdiSubWindow.
    """
    from editor import ImageEditor

    window = QMainWindow()
    editor = ImageEditor()
    window.setCentralWidget(editor)
    window.resize(400, 400)
    window.show()
    editor.setImage(gradient_image)
    yield editor
    window.close()
