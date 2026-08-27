"""Общий пайплайн обработки изображений (этап 3 рефакторинга).

Единая реализация коррекций для AdjustmentsCommand.execute() и
ImageEditor.preview_adjustments(): раньше там было ~50 скопированных строк
(гистограмма → границы → растяжка каналов → PIL).

Все функции работают с QImage; внутренне используется формат RGBA8888,
у которого порядок байтов в памяти (R, G, B, A) не зависит от платформы.
"""

import numpy as np
from PyQt5.QtGui import QImage
from PIL import Image, ImageEnhance


def apply_adjustments_pipeline(image, brightness=0.0, contrast=0.0, gamma=1.0, autobalance=False):
    """Применить к QImage цепочку коррекций и вернуть новый QImage.

    Порядок: autobalance (перканальная растяжка гистограммы, отсечение 5%)
    → яркость → контраст → гамма (степенная кривая через LUT NumPy).

    Вход не модифицируется; результат — независимая копия в Format_RGBA8888.
    """
    if image is None or image.isNull():
        return image

    src = image.convertToFormat(QImage.Format_RGBA8888)

    if autobalance:
        src = _autobalance_rgba8888(src)

    pil_img = _qimage_to_pil(src)
    if brightness != 0:
        pil_img = ImageEnhance.Brightness(pil_img).enhance(1.0 + brightness)
    if contrast != 0:
        pil_img = ImageEnhance.Contrast(pil_img).enhance(1.0 + contrast)
    if gamma != 1.0:
        pil_img = _apply_gamma(pil_img, gamma)

    return _pil_to_qimage(pil_img)


def _find_bounds(hist, threshold):
    """Границы значимого диапазона гистограммы ( отсечение по threshold с каждого края)."""
    low, high = 0, 255
    count = 0
    for i, val in enumerate(hist):
        count += val
        if count > threshold:
            low = i
            break
    count = 0
    for i, val in enumerate(hist[::-1]):
        count += val
        if count > threshold:
            high = 255 - i
            break
    if low >= high:
        high = low + 1 if low < 255 else 255
        low = high - 1 if high > 0 else 0
    return low, high


def _qimage_to_ndarray_rgba(qimg):
    """QImage (RGBA8888) → ndarray (h, w, 4) с отбрасыванием padding строк."""
    w, h = qimg.width(), qimg.height()
    ptr = qimg.bits()
    ptr.setsize(qimg.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, qimg.bytesPerLine())
    return arr[:, :w * 4].reshape(h, w, 4).copy()


def _autobalance_rgba8888(qimg):
    """Перканальная растяжка гистограммы (5% отсечение), альфа не трогается."""
    arr = _qimage_to_ndarray_rgba(qimg)
    h, w = arr.shape[:2]
    threshold = w * h * 0.05

    for ch in range(3):  # R, G, B
        hist = np.histogram(arr[:, :, ch], bins=256, range=(0, 256))[0]
        low, high = _find_bounds(hist, threshold)
        rng = max(high - low, 1)
        arr[:, :, ch] = np.clip(
            (arr[:, :, ch].astype(np.float32) - low) * 255 / rng, 0, 255
        ).astype(np.uint8)

    return QImage(arr.tobytes(), w, h, w * 4, QImage.Format_RGBA8888).copy()


def _apply_gamma(pil_img, gamma):
    """Настоящая гамма: степенная кривая ((px / 255) ** (1 / gamma)) * 255 через LUT.

    Одна кривая на все каналы; альфа-канал не затрагивается (255 → 255).
    """
    inv_gamma = 1.0 / gamma
    lut = ((np.arange(256, dtype=np.float32) / 255.0) ** inv_gamma * 255.0 + 0.5).astype(np.uint8)
    return pil_img.point(lut.tolist() * 4)


def _qimage_to_pil(qimg):
    """QImage (RGBA8888) → PIL Image (RGBA)."""
    arr = _qimage_to_ndarray_rgba(qimg)
    return Image.fromarray(arr, "RGBA")


def _pil_to_qimage(pil_img):
    """PIL Image → независимый QImage в Format_RGBA8888."""
    if pil_img.mode != "RGBA":
        pil_img = pil_img.convert("RGBA")
    arr = np.asarray(pil_img, dtype=np.uint8)
    h, w = arr.shape[:2]
    return QImage(arr.tobytes(), w, h, w * 4, QImage.Format_RGBA8888).copy()
