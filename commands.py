import logging

import numpy as np
from PyQt5.QtWidgets import QApplication, QGraphicsItem, QMessageBox
from PyQt5.QtGui import QImage, QPixmap, QPainter, QTransform
from PyQt5.QtCore import QRect, Qt
from imageops import apply_adjustments_pipeline
from editor import ImageEditor
from scene import MovableImageItem


try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger("photoeditor.commands")

class Command:
    def execute(self):
        """Execute the command."""
        pass

    def undo(self):
        """Undo the command."""
        pass

class CropCommand(Command):
    def __init__(self, editor, rect):
        self.editor = editor
        self.rect = rect
        self.original_image = editor.getCurrentImage().copy()
        self.cropped_image = None

    def execute(self):
        """Crop the image to the specified rectangle."""
        self.cropped_image = self.original_image.copy(self.rect)
        self.editor.setImage(self.cropped_image, keep_view=True)
        self.editor.window().statusBar().showMessage(f"Image cropped to {self.rect.width()}x{self.rect.height()}", 2000)

    def redo(self):
        self.execute()

    def undo(self):
        """Restore the original image."""
        self.editor.setImage(self.original_image, keep_view=True)
        self.editor.window().statusBar().showMessage("Crop undone", 2000)

class AdjustmentsCommand(Command):
    def __init__(self, editor, brightness, contrast, gamma, autobalance=False, original_image_override=None):
        self.editor = editor
        self.brightness = brightness
        self.contrast = contrast
        self.gamma = gamma
        self.autobalance = autobalance
        if original_image_override:
            self.original_image = original_image_override
        else:
            self.original_image = editor.getCurrentImage().copy()
        self.adjusted_image = None

    def execute(self):
        """Apply brightness, contrast, gamma adjustments, and optionally autobalance."""
        self.adjusted_image = apply_adjustments_pipeline(
            self.original_image,
            brightness=self.brightness,
            contrast=self.contrast,
            gamma=self.gamma,
            autobalance=self.autobalance,
        )
        self.editor.setImage(self.adjusted_image, keep_view=True)

    def redo(self):
        self.execute()  # Повторяем действия execute

    def undo(self):
        """Restore the original image."""
        self.editor.setImage(self.original_image, keep_view=True)

class TransformCommand(Command):
    def __init__(self, editor, degrees=None, horizontal_flip=None, original_image_override=None):
        self.editor = editor
        self.degrees = degrees
        self.horizontal_flip = horizontal_flip
        self.original_image_override = original_image_override
        if self.original_image_override:
            self.original_image = self.original_image_override
        else:
            self.original_image = editor.getCurrentImage().copy()
        self.transformed_image = None

    def execute(self):
        """Apply rotation or flip transformation."""
        image = self.original_image.copy()
        if self.degrees is not None:
            transform = QTransform().rotate(self.degrees)
            # Ensure smooth transformation for rotations
            image = image.transformed(transform, Qt.SmoothTransformation)
        elif self.horizontal_flip is not None:
            image = image.mirrored(self.horizontal_flip, not self.horizontal_flip)
        self.transformed_image = image
        self.editor.setImage(self.transformed_image, keep_view=True)

    def undo(self):
        """Restore the original image."""
        self.editor.setImage(self.original_image, keep_view=True)
    def redo(self):
        self.execute()


class GrayscaleCommand(Command):
    def __init__(self, editor):
        self.editor = editor
        self.original_image = editor.getCurrentImage().copy()
        self.grayscale_image = None

    def execute(self):
        if not CV2_AVAILABLE:
            QMessageBox.warning(self.editor.window(), "Error", "OpenCV (cv2) is not installed. Please install it to use the Grayscale feature.")
            return
        logger.debug("Executing GrayscaleCommand")
        # Конвертируем изображение в нужный формат
        image = self.original_image.convertToFormat(QImage.Format_RGBA8888)
        width = image.width()
        height = image.height()
        logger.debug("Image size: %dx%d, Format: %s", width, height, image.format())
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        logger.debug("Converting to grayscale...")
        gray = cv2.cvtColor(arr, cv2.COLOR_RGBA2GRAY)
        gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGBA)
        self.grayscale_image = QImage(gray_rgb.data, width, height, gray_rgb.strides[0], QImage.Format_RGBA8888)
        if self.grayscale_image.isNull():
            logger.error("Grayscale image is null")
            QMessageBox.warning(self.editor.window(), "Error", "Failed to convert image to grayscale.")
            return
        logger.debug("Setting grayscale image")
        self.editor.setImage(self.grayscale_image, keep_view=True)
        self.editor.window().statusBar().showMessage("Converted to grayscale", 2000)

    def undo(self):
        self.editor.setImage(self.original_image, keep_view=True)
        self.editor.window().statusBar().showMessage("Grayscale undone", 2000)

    def redo(self):
        self.execute()

class PasteCommand(Command):
    def __init__(self, editor, clipboard_image):
        self.editor = editor
        self.clipboard_image = clipboard_image.copy()
        self.original_image = editor.getCurrentImage().copy() if editor.getCurrentImage() else None
        self.movable_item = None
        self.selection_rect = editor.scene.selection_rect.rect().toRect() if editor.scene.selection_rect and editor.scene.selection_rect.rect().isValid() else None
        self.pasted_items_before = editor.pasted_items.copy()
        # Трансформации предыдущих плавающих элементов — для корректного undo
        self.transforms_before = [QTransform(i.transform()) for i in editor.pasted_items]

    def execute(self):
        """Paste the clipboard image either into a selection or as a movable item."""
        if self.selection_rect and not self.selection_rect.isEmpty():
            painter = QPainter(self.editor.current_image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(self.selection_rect.topLeft(), self.clipboard_image)
            painter.end()
            self.editor.setImage(self.editor.current_image, keep_view=True)
            self.editor.window().statusBar().showMessage("Image pasted into selection", 2000)
        else:
            pixmap = QPixmap.fromImage(self.clipboard_image)
            self.movable_item = MovableImageItem(pixmap)
            self.movable_item.setPos(10, 10)
            for item in self.editor.pasted_items[:]:
                if item.isSelected():
                    self.editor.scene.fixMovableItem(item, self.editor)
                    self.editor.scene.removeItem(item)
                    self.editor.pasted_items.remove(item)
            self.editor.scene.addItem(self.movable_item)
            self.editor.pasted_items.append(self.movable_item)
            self.movable_item.setSelected(True)
            self.editor.window().statusBar().showMessage(f"Image pasted as movable object (items: {len(self.editor.pasted_items)})", 2000)
            self.editor.scene.update()
        self.editor.is_modified = True

    def redo(self):
        self.execute()

    def undo(self):
        """Undo the paste operation (restores items with their transforms)."""
        if self.selection_rect and not self.selection_rect.isEmpty():
            self.editor.setImage(self.original_image, keep_view=True)
        else:
            if self.movable_item and self.movable_item in self.editor.pasted_items:
                self.editor.scene.removeItem(self.movable_item)
                self.editor.pasted_items.remove(self.movable_item)
            self.editor.pasted_items = self.pasted_items_before.copy()
            for item, tr in zip(self.editor.pasted_items, self.transforms_before):
                if item not in self.editor.scene.items():
                    self.editor.scene.addItem(item)
                item.setTransform(tr)
            self.editor.setImage(self.original_image, keep_view=True)
            self.editor.scene.update()
        self.editor.is_modified = bool(self.editor.undo_stack)
        self.editor.window().statusBar().showMessage("Paste undone", 2000)

class CutCommand(Command):
    def __init__(self, editor, fill_color=None):
        self.editor = editor
        self.original_image = editor.getCurrentImage().copy()
        self.selection_rect = editor.scene.selection_rect.rect().toRect() if editor.scene.selection_rect else QRect()
        self.cut_image = None
        # Цвет заливки вырезанной области: настраиваемый, белый по умолчанию
        self.fill_color = fill_color if fill_color is not None else Qt.white

    def execute(self):
        """Cut the selected area and copy it to the clipboard."""
        if not self.selection_rect.isValid() or self.selection_rect.isEmpty():
            self.editor.window().statusBar().showMessage("No valid selection to cut", 2000)
            return
        self.cut_image = self.original_image.copy(self.selection_rect)
        QApplication.clipboard().setImage(self.cut_image)
        result_image = self.original_image.copy()
        painter = QPainter(result_image)
        painter.fillRect(self.selection_rect, self.fill_color)
        painter.end()
        self.editor.setImage(result_image, keep_view=True)
        self.editor.scene.removeItem(self.editor.scene.selection_rect)
        self.editor.scene.selection_rect = None
        for handle in self.editor.scene.handles:
            self.editor.scene.removeItem(handle)
        self.editor.scene.handles.clear()
        self.editor.is_modified = True
        self.editor.window().statusBar().showMessage("Selection cut to clipboard", 2000)

    def redo(self):
        self.execute()

    def undo(self):
        """Restore the original image after cutting."""
        self.editor.setImage(self.original_image, keep_view=True)
        self.editor.is_modified = bool(self.editor.undo_stack)
        self.editor.window().statusBar().showMessage("Cut undone", 2000)

class ResizeCommand(Command):
    """Изменение размера изображения.

    Мутация выполняется в execute() (контракт этапа 3): раньше изображение
    масштабировалось в ImageEditor.resizeImage() до создания команды.
    """

    def __init__(self, editor, new_width, new_height, keep_aspect=True):
        self.editor = editor
        self.new_width = new_width
        self.new_height = new_height
        self.keep_aspect = keep_aspect
        self.old_image = None
        self.new_image = None

    def execute(self):
        """Compute and apply the resized image."""
        if self.old_image is None:
            self.old_image = self.editor.getCurrentImage().copy()
        aspect_mode = Qt.KeepAspectRatio if self.keep_aspect else Qt.IgnoreAspectRatio
        self.new_image = self.editor.getCurrentImage().scaled(
            self.new_width, self.new_height, aspect_mode, Qt.SmoothTransformation)
        self._apply(self.new_image)

    def _apply(self, image):
        self.editor.setImage(image, keep_view=True)
        # Размеры сцены изменились — вписать изображение в окно
        self.editor.fitInViewWithRulers()
        self.editor.scene.update()
        self.editor.viewport().update()

    def undo(self):
        """Revert to the original image size."""
        self._apply(self.old_image)

    def redo(self):
        """Apply the resized image."""
        self._apply(self.new_image)

class FixPasteCommand(Command):
    """Фиксация плавающих вставленных элементов на холсте.

    Мутация выполняется в execute() (контракт этапа 3): раньше рисование
    выполнялось в ImageEditor.fixPastedItems() до создания команды.
    Элементы запекаются с учётом их текущего масштаба (подход 1:
    растянутый перед фиксацией элемент рисуется в целевой размер).
    """

    def __init__(self, editor, pasted_items):
        self.editor = editor
        self.pasted_items = list(pasted_items)
        self.positions = [item.pos() for item in pasted_items]
        self.transforms = [QTransform(item.transform()) for item in pasted_items]
        self.old_image = None
        self.new_image = None

    def execute(self):
        """Bake all floating pasted items onto the canvas (with scale)."""
        if not self.pasted_items:
            return
        if self.old_image is None:
            self.old_image = self.editor.getCurrentImage().copy()
        image = self.editor.getCurrentImage()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        for item in self.pasted_items:
            target = item.visualRect().toRect()
            painter.drawPixmap(target, item.pixmap())
            if item.scene():
                self.editor.scene.removeItem(item)
        painter.end()
        if self.editor.scene.handles_item in self.pasted_items:
            self.editor.scene.clearItemHandles()
        self.new_image = image
        self.editor.setImage(image, keep_view=True)
        self.editor.pasted_items.clear()
        self.editor.scene.update()
        self.editor.viewport().update()

    def undo(self):
        """Undo the fixation of pasted items (restores pos + scale)."""
        self.editor.setImage(self.old_image, keep_view=True)
        self.editor.pasted_items.clear()
        for item, pos, tr in zip(self.pasted_items, self.positions, self.transforms):
            self.editor.scene.addItem(item)
            item.setPos(pos)
            item.setTransform(tr)
            item.setFlag(QGraphicsItem.ItemIsMovable, True)
            item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.editor.pasted_items.append(item)
        self.editor.scene.update()
        self.editor.viewport().update()

    def redo(self):
        """Redo the fixation of pasted items."""
        self.execute()
