import numpy as np
from PyQt5.QtWidgets import QApplication, QGraphicsItem, QMessageBox
from PyQt5.QtGui import QImage, QPixmap, QPainter, QTransform
from PyQt5.QtCore import QRect, Qt
from PIL import Image, ImageEnhance
from editor import ImageEditor
from scene import MovableImageItem


try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

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
        from widgets import CustomMdiSubWindow
        self.cropped_image = self.original_image.copy(self.rect)
        self.editor.setImage(self.cropped_image)
        self.editor.window().statusBar().showMessage(f"Image cropped to {self.rect.width()}x{self.rect.height()}", 2000)

    def redo(self):
        self.execute() 
        
    def undo(self):
        """Restore the original image."""
        from widgets import CustomMdiSubWindow
        self.editor.setImage(self.original_image)
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
        image = self.original_image.copy()
        if self.autobalance:
            width, height = image.width(), image.height()
            ptr = image.bits()
            ptr.setsize(height * width * 4)
            img_array = np.frombuffer(ptr, dtype=np.uint8).reshape(height, width, 4).copy()

            r_hist = np.histogram(img_array[:, :, 2], bins=256, range=(0, 256))[0]
            g_hist = np.histogram(img_array[:, :, 1], bins=256, range=(0, 256))[0]
            b_hist = np.histogram(img_array[:, :, 0], bins=256, range=(0, 256))[0]
            total_pixels = width * height
            threshold = total_pixels * 0.05

            def find_bounds(hist):
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

            r_low, r_high = find_bounds(r_hist)
            g_low, g_high = find_bounds(g_hist)
            b_low, b_high = find_bounds(b_hist)

            r_range = max(r_high - r_low, 1)
            g_range = max(g_high - g_low, 1)
            b_range = max(b_high - b_low, 1)

            img_array[:, :, 2] = np.clip((img_array[:, :, 2].astype(np.float32) - r_low) * 255 / r_range, 0, 255).astype(np.uint8)
            img_array[:, :, 1] = np.clip((img_array[:, :, 1].astype(np.float32) - g_low) * 255 / g_range, 0, 255).astype(np.uint8)
            img_array[:, :, 0] = np.clip((img_array[:, :, 0].astype(np.float32) - b_low) * 255 / b_range, 0, 255).astype(np.uint8)

            image = QImage(img_array.tobytes(), width, height, image.bytesPerLine(), QImage.Format_RGB32)

        pil_img = Image.frombytes("RGBA", (image.width(), image.height()), image.bits().asstring(image.byteCount()))
        if self.brightness != 0:
            enhancer = ImageEnhance.Brightness(pil_img)
            pil_img = enhancer.enhance(1.0 + self.brightness)
        if self.contrast != 0:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1.0 + self.contrast)
        if self.gamma != 1.0:
            enhancer = ImageEnhance.Brightness(pil_img)
            pil_img = enhancer.enhance(self.gamma)

        self.adjusted_image = QImage(pil_img.tobytes(), image.width(), image.height(), image.bytesPerLine(), QImage.Format_RGB32)
        self.editor.setImage(self.adjusted_image)
    
    def redo(self):
        self.execute()  # Повторяем действия execute
 
    def undo(self):
        """Restore the original image."""
        self.editor.setImage(self.original_image)

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
        self.editor.setImage(self.transformed_image)

    def undo(self):
        """Restore the original image."""
        self.editor.setImage(self.original_image)
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
        print("Executing GrayscaleCommand")  # Отладка
        # Конвертируем изображение в нужный формат
        image = self.original_image.convertToFormat(QImage.Format_RGBA8888)
        width = image.width()
        height = image.height()
        print(f"Image size: {width}x{height}, Format: {image.format()}")  # Отладка
        ptr = image.bits()
        ptr.setsize(height * width * 4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        print("Converting to grayscale...")  # Отладка
        gray = cv2.cvtColor(arr, cv2.COLOR_RGBA2GRAY)
        gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGBA)
        self.grayscale_image = QImage(gray_rgb.data, width, height, gray_rgb.strides[0], QImage.Format_RGBA8888)
        if self.grayscale_image.isNull():
            print("Error: Grayscale image is null")  # Отладка
            QMessageBox.warning(self.editor.window(), "Error", "Failed to convert image to grayscale.")
            return
        print("Setting grayscale image")  # Отладка
        self.editor.setImage(self.grayscale_image)
        self.editor.window().statusBar().showMessage("Converted to grayscale", 2000)

    def undo(self):
        self.editor.setImage(self.original_image)
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

    def execute(self):
        """Paste the clipboard image either into a selection or as a movable item."""
        if self.selection_rect and not self.selection_rect.isEmpty():
            painter = QPainter(self.editor.current_image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(self.selection_rect.topLeft(), self.clipboard_image)
            painter.end()
            self.editor.setImage(self.editor.current_image)
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
        """Undo the paste operation."""
        if self.selection_rect and not self.selection_rect.isEmpty():
            self.editor.setImage(self.original_image)
        else:
            if self.movable_item and self.movable_item in self.editor.pasted_items:
                self.editor.scene.removeItem(self.movable_item)
                self.editor.pasted_items.remove(self.movable_item)
            self.editor.pasted_items = self.pasted_items_before.copy()
            for item in self.editor.pasted_items:
                if item not in self.editor.scene.items():
                    self.editor.scene.addItem(item)
            self.editor.setImage(self.original_image)
            self.editor.scene.update()
        self.editor.is_modified = bool(self.editor.undo_stack)
        self.editor.window().statusBar().showMessage("Paste undone", 2000)

class CutCommand(Command):
    def __init__(self, editor):
        self.editor = editor
        self.original_image = editor.getCurrentImage().copy()
        self.selection_rect = editor.scene.selection_rect.rect().toRect() if editor.scene.selection_rect else QRect()
        self.cut_image = None

    def execute(self):
        """Cut the selected area and copy it to the clipboard."""
        if not self.selection_rect.isValid() or self.selection_rect.isEmpty():
            self.editor.window().statusBar().showMessage("No valid selection to cut", 2000)
            return
        self.cut_image = self.original_image.copy(self.selection_rect)
        QApplication.clipboard().setImage(self.cut_image)
        result_image = self.original_image.copy()
        painter = QPainter(result_image)
        painter.fillRect(self.selection_rect, Qt.white)
        painter.end()
        self.editor.setImage(result_image)
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
        self.editor.setImage(self.original_image)
        self.editor.is_modified = bool(self.editor.undo_stack)
        self.editor.window().statusBar().showMessage("Cut undone", 2000)

class ResizeCommand(Command):
    def __init__(self, editor, old_image, new_image):
        self.editor = editor
        self.old_image = old_image
        self.new_image = new_image

    def undo(self):
        """Revert to the original image size."""
        self.editor.current_image = self.old_image
        self.editor.image_item.setPixmap(QPixmap.fromImage(self.editor.current_image))
        self.editor.scene.setSceneRect(0, 0, self.old_image.width(), self.old_image.height())
        self.editor.image_item.setPos(0, 0)
        self.editor.fitInViewWithRulers()
        self.editor.scene.update()
        self.editor.viewport().update()

    def redo(self):
        """Apply the resized image."""
        self.editor.current_image = self.new_image
        self.editor.image_item.setPixmap(QPixmap.fromImage(self.editor.current_image))
        self.editor.scene.setSceneRect(0, 0, self.new_image.width(), self.new_image.height())
        self.editor.image_item.setPos(0, 0)
        self.editor.fitInViewWithRulers()
        self.editor.scene.update()
        self.editor.viewport().update()

class FixPasteCommand(Command):
    def __init__(self, editor, old_image, new_image, pasted_items):
        self.editor = editor
        self.old_image = old_image
        self.new_image = new_image
        self.pasted_items = pasted_items
        self.positions = [item.pos() for item in pasted_items]

    def undo(self):
        """Undo the fixation of pasted items."""
        self.editor.current_image = self.old_image
        self.editor.image_item.setPixmap(QPixmap.fromImage(self.editor.current_image))
        self.editor.pasted_items.clear()
        for item, pos in zip(self.pasted_items, self.positions):
            self.editor.scene.addItem(item)
            item.setPos(pos)
            item.setFlag(QGraphicsItem.ItemIsMovable, True)
            item.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.editor.pasted_items.append(item)
        self.editor.scene.update()
        self.editor.viewport().update()

    def redo(self):
        """Redo the fixation of pasted items."""
        self.editor.current_image = self.new_image
        self.editor.image_item.setPixmap(QPixmap.fromImage(self.editor.current_image))
        for item in self.pasted_items:
            if item in self.editor.pasted_items:
                self.editor.pasted_items.remove(item)
            self.editor.scene.removeItem(item)
        self.editor.pasted_items.clear()
        self.editor.scene.update()
        self.editor.viewport().update()
