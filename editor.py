
import numpy as np
from PyQt5.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QApplication, QWidget, QGridLayout
from PyQt5.QtGui import QImage, QPixmap, QPainter, QTransform
from PyQt5.QtCore import Qt, QSizeF, QRectF, QPointF
from PIL import Image, ImageEnhance


#from commands import FixPasteCommand, CropCommand, TransformCommand, GrayscaleCommand, CutCommand, PasteCommand, ResizeCommand
#from widgets import RulerWidget


def __init__(self, parent=None):
    super().__init__(parent)
    from scene import ImageEditorScene
    self.scene = ImageEditorScene(self)
    self.setScene(self.scene)

class ImageEditor(QGraphicsView):
    def __init__(self, parent=None):
        """Initialize the image editor."""
        super().__init__(parent)
        from scene import ImageEditorScene  # Local import
        self.scene = ImageEditorScene(self)
        self.setScene(self.scene)
        self.image_item = None
        self.original_image = None
        self.current_image = None
        self.zoom_factor = 1.0
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.rulers_visible = False
        self.scene.selectionChanged.connect(self.updateStatusBar)
        self.pasted_items = []
        self.clipboard = QApplication.clipboard()
        self.is_modified = False
        self.undo_stack = []
        self.redo_stack = []
        self.ruler_width = 30
        self.cursor_pos = QPointF(-1, -1)
        self.image_before_preview = None

    def adjustTickSpacing(self, spacing):
        """Adjust tick spacing to a convenient number."""
        if spacing <= 0:
            return 10
        magnitude = 10 ** int(np.log10(spacing))
        normalized = spacing / magnitude
        if normalized < 1.5:
            return 1 * magnitude
        elif normalized < 3:
            return 2 * magnitude
        elif normalized < 7:
            return 5 * magnitude
        else:
            return 10 * magnitude

    def paintEvent(self, event):
        """Handle paint events."""
        super().paintEvent(event)

    def setImage(self, image):
        """Set the current image in the editor."""
        if not image:
            return
        self.current_image = image
        self.original_image = image.copy()
        if not self.image_item:
            self.image_item = QGraphicsPixmapItem()
            self.scene.addItem(self.image_item)
        self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
        self.scene.setSceneRect(0, 0, image.width(), image.height())
        self.image_item.setPos(0, 0)  # Always set to (0, 0)
        self.zoom_factor = 1.0
        self.is_modified = False
        self.fitInViewWithRulers()
        self.scene.update()
        self.viewport().update()
        
    def scrollContentsBy(self, dx, dy):
        """Update rulers during scrolling."""
        super().scrollContentsBy(dx, dy)
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def executeCommand(self, command):
        """Execute a command and add it to the undo stack."""
        command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.is_modified = True

    def mouseMoveEvent(self, event):
        """Handle mouse movement for cursor tracking."""
        super().mouseMoveEvent(event)
        scene_pos = self.mapToScene(event.pos())
        self.cursor_pos = scene_pos
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def mousePressEvent(self, event):
        """Handle mouse press to fix pasted items."""
        super().mousePressEvent(event)
        if not self.scene.selectedItems() and self.pasted_items:
            self.fixPastedItems()

    def fixPastedItems(self):
        """Fix all pasted items onto the canvas."""
        if not self.pasted_items:
            return
        old_image = self.current_image.copy()
        painter = QPainter(self.current_image)
        for item in self.pasted_items:
            pos = item.pos()
            pixmap = item.pixmap()
            painter.drawPixmap(int(pos.x()), int(pos.y()), pixmap)
            self.scene.removeItem(item)
        painter.end()
        self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
        self.scene.update()
        self.viewport().update()
        from commands import FixPasteCommand
        command = FixPasteCommand(self, old_image, self.current_image.copy(), self.pasted_items[:])
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.pasted_items.clear()

    def leaveEvent(self, event):
        """Handle cursor leaving the widget."""
        super().leaveEvent(event)
        self.cursor_pos = QPointF(-1, -1)
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def fitInViewWithRulers(self):
        """Fit the image in the view, considering rulers."""
        if not self.current_image:
            return
        rect = self.scene.sceneRect()
        self.resetTransform()
        #Rullers, if they visible
        view_rect = self.viewport().rect()
        if self.rulers_visible:
            view_rect.adjust(self.ruler_width, self.ruler_width, -self.ruler_width, -self.ruler_width)
        self.fitInView(rect, Qt.KeepAspectRatio)
        #  zoom_factor from scale
        transform = self.transform()
        self.zoom_factor = transform.m11()  # Scale by X (If Keep aspect ratio then m11 == m22)
        self.scene.update()
        self.viewport().update()
    
    def resizeEvent(self, event):
        """Handle resize events without resetting zoom."""
        super().resizeEvent(event)
        self.scene.update()
        self.viewport().update()


    def undo(self):
        """Undo last operation"""
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        self.redo_stack.append(command)
        command.undo()
        self.is_modified = bool(self.undo_stack)  # Update flag of changes
        self.scene.update()
        self.viewport().update()
        self.window().statusBar().showMessage("Undo performed", 2000)

    def redo(self):
        """Redo undone operation"""
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        self.undo_stack.append(command)
        command.redo()
        self.is_modified = True  # After redo always chsnges there
        self.scene.update()
        self.viewport().update()
        self.window().statusBar().showMessage("Redo performed", 2000)


    def loadImage(self, image_path):
        """Load an image from a file."""
        self.original_image = QImage(image_path)
        if self.original_image.isNull():
            return False
        self.setImage(self.original_image)
        return True

    def openImage(self, file_name):
        """Open an image file."""
        image = QImage(file_name)
        if image.isNull():
            return False
        self.setImage(image)
        self.original_image = self.current_image.copy()
        self.fitInView(self.image_item, Qt.KeepAspectRatio)
        self.zoom_factor = 1.0
        self.is_modified = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        return True

    def resetView(self):
        """Reset the view to fit the image."""
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        self.zoom_factor = 1.0

    def zoomIn(self):
        """Zoom in by 25%."""
        if not self.image_item:
            return
        self.zoom_factor *= 1.25
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
        self.scene.update()
        self.viewport().update()
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def zoomOut(self):
        """Zoom out by 25%."""
        if not self.image_item:
            return
        self.zoom_factor /= 1.25
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
        self.scene.update()
        self.viewport().update()
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def actualSize(self):
        """Reset zoom to 1:1."""
        if not self.image_item:
            return
        self.zoom_factor = 1.0
        self.resetTransform()
        self.scale(self.zoom_factor, self.zoom_factor)
        self.scene.update()
        self.viewport().update()
        if self.rulers_visible:
            self.parent().updateRulerLayout()

    def getCurrentImage(self):
        """Return the current image."""
        return self.current_image

    def getSelectedRegion(self):
        """Get the selected region as a QImage."""
        if not self.scene.selection_rect or not self.current_image:
            return None
        selection = self.scene.selection_rect.rect().toRect()
        if selection.isValid() and not selection.isEmpty():
            return self.current_image.copy(selection)
        return None

    def setSelectedRegion(self, image):
        """Replace the selected region with an image."""
        if not self.scene.selection_rect or not self.current_image:
            return False
        selection = self.scene.selection_rect.rect().toRect()
        if selection.isValid() and not selection.isEmpty():
            painter = QPainter(self.current_image)
            painter.drawImage(selection.topLeft(), image)
            painter.end()
            self.setImage(self.current_image)
            return True
        return False

    def rotateImage(self, degrees):
        """Rotate the image by specified degrees."""
        if not self.current_image: return
        from commands import TransformCommand
        # For direct rotations, the 'original' for the command is always a fresh copy of the current state.
        command = TransformCommand(self, degrees=degrees, original_image_override=self.current_image.copy())
        self.executeCommand(command)
        # Ensure preview state is cleared if any was inadvertently active
        self.image_before_preview = None

    def flipImage(self, horizontal=True):
        """Flip the image horizontally or vertically."""
        if not self.current_image:
            return
        from commands import TransformCommand  # Local import
        command = TransformCommand(self, horizontal_flip=horizontal)
        self.executeCommand(command)
    '''
    def resizeImage(self, new_width, new_height):
        """Change size of image"""
        if not self.current_image:
            return
        # Save image for Undo
        old_image = self.current_image.copy()

        # Create new image with nrew size
        resized_image = self.current_image.scaled(new_width, new_height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        # Если размеры не совпадают (из-за сохранения пропорций), обрезаем изображение
        if resized_image.width() != new_width or resized_image.height() != new_height:
            painter = QPainter(resized_image)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(resized_image.rect(), Qt.transparent)
            painter.end()
            resized_image = resized_image.copy(0, 0, new_width, new_height)

        # Обновляем текущее изображение
        self.current_image = resized_image
        self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
        self.scene.setSceneRect(0, 0, new_width, new_height)
        self.image_item.setPos(0, 0)
        self.fitInViewWithRulers()
        self.scene.update()
        self.viewport().update()
        self.is_modified = True

        # Ограничиваем размер стека
        if len(self.undo_stack) > 10:  # Максимум 10 операций
            self.undo_stack.pop(0)

        # Создаём команду для Undo/Redo
        from commands import ResizeCommand
        command = ResizeCommand(self, old_image, self.current_image.copy())
        self.undo_stack.append(command)
        self.redo_stack.clear()
    '''
    
    def resizeImage(self, new_width, new_height, keep_aspect=True):
        """Resize the current image."""
        if not self.current_image:
            return
        old_image = self.current_image.copy()
        # Выбираем режим масштабирования в зависимости от keep_aspect
        aspect_mode = Qt.KeepAspectRatio if keep_aspect else Qt.IgnoreAspectRatio
        resized_image = self.current_image.scaled(new_width, new_height, aspect_mode, Qt.SmoothTransformation)
        self.current_image = resized_image
        self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
        self.scene.setSceneRect(0, 0, new_width, new_height)
        self.image_item.setPos(0, 0)
        self.fitInViewWithRulers()
        self.scene.update()
        self.viewport().update()
        self.is_modified = True
        if len(self.undo_stack) > 10:
            self.undo_stack.pop(0)
        from commands import ResizeCommand
        command = ResizeCommand(self, old_image, self.current_image.copy())
        self.undo_stack.append(command)
        self.redo_stack.clear()
        # Обновляем заголовок окна
        sub_window = self.parent().parent()
        if sub_window:
            sub_window.setWindowTitle(f"{sub_window.windowTitle().split(' (')[0]} ({new_width}x{new_height})")
        
    
    def convertToGrayscale(self):
        """Convert the image to grayscale."""
        if not self.current_image:
            return
        from commands import GrayscaleCommand
        command = GrayscaleCommand(self)
        self.executeCommand(command)

    def updateStatusBar(self, rect=None):
        """Update the status bar with selection info."""
        if rect and rect.isValid():
            status_message = f"Selection: {rect.width():.0f}x{rect.height():.0f} at ({rect.x():.0f}, {rect.y():.0f})"
            window = self.window()
            if hasattr(window, 'statusBar'):
                window.statusBar().showMessage(status_message)

    def applyAllPastedItems(self):
        """Apply all pasted movable items to the main image."""
        if not self.current_image:
            return
        for item in self.pasted_items[:]:
            self.scene.fixMovableItem(item, self)
            self.scene.removeItem(item)
            self.pasted_items.remove(item)
        self.scene.update()

    def cut(self):
        """Cut the selected area to the clipboard."""
        if not self.current_image:
            self.window().statusBar().showMessage("No image to cut", 2000)
            return
        from commands import CutCommand
        command = CutCommand(self)
        self.executeCommand(command)

    def paste(self):
        """Paste an image from the clipboard as a movable item."""
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        if mime_data.hasImage():
            clipboard_image = QImage(mime_data.imageData())
            if not clipboard_image.isNull():
                from commands import PasteCommand
                
                command = PasteCommand(self, clipboard_image)
                self.executeCommand(command)

    def start_preview(self):
        self.image_before_preview = self.current_image.copy() if self.current_image else None

    def preview_rotation(self, angle):
        if self.image_before_preview and self.image_item:
            transform = QTransform().rotate(angle)
            preview_image = self.image_before_preview.transformed(transform, Qt.SmoothTransformation)
            self.current_image = preview_image
            self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
            self.scene.setSceneRect(0, 0, self.current_image.width(), self.current_image.height())
            self.image_item.setPos(0, 0)
            self.scene.update()
            self.viewport().update()

    def cancel_preview(self):
        if self.image_before_preview and self.image_item:
            self.current_image = self.image_before_preview.copy() # Restore from the saved state
            self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
            self.scene.setSceneRect(0, 0, self.current_image.width(), self.current_image.height())
            self.image_item.setPos(0, 0)
            self.scene.update()
            self.viewport().update()
        self.image_before_preview = None # Clear the saved state

    def apply_rotation(self, degrees):
        if not self.current_image: return
        from commands import TransformCommand
        # Use image_before_preview if available (meaning dialog was used),
        # otherwise, current_image for direct calls (though rotateImage is now primary for that).
        image_for_command_basis = self.image_before_preview if self.image_before_preview else self.current_image
        command = TransformCommand(self, degrees=degrees, original_image_override=image_for_command_basis.copy())
        self.executeCommand(command)
        self.image_before_preview = None # Clear preview state post-command

    def preview_adjustments(self, brightness, contrast, gamma, autobalance):
        if self.image_before_preview and self.image_item:
            image = self.image_before_preview.copy()
            if autobalance:
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
            if brightness != 0:
                enhancer = ImageEnhance.Brightness(pil_img)
                pil_img = enhancer.enhance(1.0 + brightness)
            if contrast != 0:
                enhancer = ImageEnhance.Contrast(pil_img)
                pil_img = enhancer.enhance(1.0 + contrast)
            if gamma != 1.0:
                enhancer = ImageEnhance.Brightness(pil_img)
                pil_img = enhancer.enhance(gamma)

            preview_image = QImage(pil_img.tobytes(), image.width(), image.height(), image.bytesPerLine(), QImage.Format_RGB32)
            self.current_image = preview_image
            self.image_item.setPixmap(QPixmap.fromImage(self.current_image))
            self.scene.update()
            self.viewport().update()

    def apply_adjustments(self, brightness, contrast, gamma, autobalance):
        if not self.current_image: return
        from commands import AdjustmentsCommand
        image_for_command_basis = self.image_before_preview if self.image_before_preview else self.current_image
        command = AdjustmentsCommand(self, brightness, contrast, gamma, autobalance, original_image_override=image_for_command_basis.copy())
        self.executeCommand(command)
        self.image_before_preview = None

'''
class EditorContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = ImageEditor(self)
        self.top_ruler = RulerWidget(editor=self.editor, orientation="horizontal", parent=self)
        self.left_ruler = RulerWidget(editor=self.editor, orientation="vertical", parent=self)
        self.top_ruler.setFixedHeight(self.editor.ruler_width)
        self.left_ruler.setFixedWidth(self.editor.ruler_width)
        self.corner_widget = QWidget(self)
        self.corner_widget.setFixedSize(self.editor.ruler_width, self.editor.ruler_width)
        self.corner_widget.setStyleSheet("background-color: rgb(200, 200, 200);")
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self.corner_widget, 0, 0)
        self.layout.addWidget(self.top_ruler, 0, 1)
        self.layout.addWidget(self.left_ruler, 1, 0)
        self.layout.addWidget(self.editor, 1, 1)
        self.top_ruler.hide()
        self.left_ruler.hide()
        self.corner_widget.hide()
        # Устанавливаем политику размеров
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def toggleRulers(self, visible):
        self.editor.rulers_visible = visible
        if visible:
            self.top_ruler.show()
            self.left_ruler.show()
            self.corner_widget.show()
        else:
            self.top_ruler.hide()
            self.left_ruler.hide()
            self.corner_widget.hide()
        self.editor.fitInViewWithRulers()
        self.updateRulerLayout()
        self.top_ruler.update()
        self.left_ruler.update()

    def updateRulerLayout(self):
        if not self.editor.rulers_visible:
            return
        container_width = self.width()
        container_height = self.height()
        self.top_ruler.setFixedWidth(container_width - self.editor.ruler_width)
        self.left_ruler.setFixedHeight(container_height - self.editor.ruler_width)
        self.top_ruler.update()
        self.left_ruler.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateRulerLayout()
        self.editor.fitInViewWithRulers()  # Перемасштабируем при изменении размера


'''
class EditorContainer(QWidget):
    def __init__(self, parent=None):
        """Initialize the editor container with rulers."""
        super().__init__(parent)
        self.editor = ImageEditor(self)
        from widgets import RulerWidget
        self.top_ruler = RulerWidget(editor=self.editor, orientation="horizontal", parent=self)
        self.left_ruler = RulerWidget(editor=self.editor, orientation="vertical", parent=self)
        self.top_ruler.setFixedHeight(self.editor.ruler_width)
        self.left_ruler.setFixedWidth(self.editor.ruler_width)
        self.corner_widget = QWidget(self)
        self.corner_widget.setFixedSize(self.editor.ruler_width, self.editor.ruler_width)
        self.corner_widget.setStyleSheet("background-color: rgb(200, 200, 200);")
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self.corner_widget, 0, 0)
        self.layout.addWidget(self.top_ruler, 0, 1)
        self.layout.addWidget(self.left_ruler, 1, 0)
        self.layout.addWidget(self.editor, 1, 1)
        self.top_ruler.hide()
        self.left_ruler.hide()
        self.corner_widget.hide()

    def toggleRulers(self, visible):
        """Toggle visibility of rulers."""
        self.editor.rulers_visible = visible
        if visible:
            self.top_ruler.show()
            self.left_ruler.show()
            self.corner_widget.show()
        else:
            self.top_ruler.hide()
            self.left_ruler.hide()
            self.corner_widget.hide()
        self.editor.fitInViewWithRulers()
        self.updateRulerLayout()
        self.top_ruler.update()
        self.left_ruler.update()

    def updateRulerLayout(self):
        """Update ruler sizes and visibility."""
        if not self.editor.rulers_visible:
            return
        container_width = self.width()
        container_height = self.height()
        self.top_ruler.setFixedWidth(container_width - self.editor.ruler_width)
        self.left_ruler.setFixedHeight(container_height - self.editor.ruler_width)
        self.top_ruler.update()
        self.left_ruler.update()

    def resizeEvent(self, event):
        """Handle resize events to update ruler layout."""
        super().resizeEvent(event)
        self.updateRulerLayout()
