from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem
from PyQt5.QtGui import QColor, QPen, QCursor, QTransform, QPainter
from PyQt5.QtCore import Qt, QRectF, QSizeF, QPointF, QTimer, pyqtSignal
from editor import ImageEditor  # Импорт из editor.py

class ImageEditorScene(QGraphicsScene):
    selectionChanged = pyqtSignal(QRectF)
    
    def __init__(self, parent=None):
        """Initialize the image editor scene."""
        super().__init__(parent)
        self.selecting = False
        self.selection_rect = None
        self.start_pos = None
        self.current_tool = "selection"
        self.setBackgroundBrush(QColor(200, 200, 200))
        self.handles = []
        self.active_handle = None
        self.dash_offset = 0
        self.dash_timer = QTimer(self)
        self.dash_timer.timeout.connect(self.updateDash)
        self.dash_timer.start(100)
        
    def updateDash(self):
        """Update the dashed line animation for the selection rectangle."""
        if self.selection_rect:
            self.dash_offset = (self.dash_offset + 1) % 10
            pen = self.selection_rect.pen()
            pen.setDashOffset(self.dash_offset)
            self.selection_rect.setPen(pen)
            self.update()

    def createHandles(self):
        """Create resize handles for the selection rectangle."""
        if not self.selection_rect:
            return
        rect = self.selection_rect.rect()
        editor = self.views()[0]
        img_size = max(editor.current_image.width(), editor.current_image.height()) if editor.current_image else 1000
        handle_size = max(12, min(30, img_size // 150))

        for handle in self.handles:
            self.removeItem(handle)
        self.handles.clear()

        positions = [
            (rect.topLeft(), "topLeft"), (rect.topRight(), "topRight"),
            (rect.bottomLeft(), "bottomLeft"), (rect.bottomRight(), "bottomRight"),
            (QPointF(rect.center().x(), rect.top()), "top"),
            (QPointF(rect.center().x(), rect.bottom()), "bottom"),
            (QPointF(rect.left(), rect.center().y()), "left"),
            (QPointF(rect.right(), rect.center().y()), "right")
        ]

        for pos, handle_type in positions:
            handle = QGraphicsRectItem(QRectF(pos.x() - handle_size / 2, pos.y() - handle_size / 2, handle_size, handle_size))
            handle.setBrush(QColor(255, 0, 0))
            handle.setPen(QPen(Qt.black, 2))
            handle.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
            handle.setFlag(QGraphicsPixmapItem.ItemIsSelectable, False)
            handle.setZValue(200)
            handle.setData(0, handle_type)
            self.addItem(handle)
            self.handles.append(handle)

    def updatePenWidth(self):
        """Adjust the pen width of the selection rectangle based on image size."""
        if not self.selection_rect:
            return
        editor = self.views()[0]
        if editor.current_image:
            img_size = max(editor.current_image.width(), editor.current_image.height())
            pen_width = max(2, min(5, img_size // 1000))
            pen = QPen(Qt.black, pen_width, Qt.DashLine)
            pen.setDashPattern([4, 4])
            pen.setDashOffset(self.dash_offset)
            self.selection_rect.setPen(pen)

    def fixMovableItem(self, item, editor):
        """Fix a movable item onto the image."""
        if not isinstance(item, MovableImageItem) or not editor.current_image:
            return
        pixmap = item.pixmap()
        pos = item.pos()
        painter = QPainter(editor.current_image)
        painter.drawPixmap(int(pos.x()), int(pos.y()), pixmap)
        painter.end()
        editor.setImage(editor.current_image)
        editor.is_modified = True

    def mousePressEvent(self, event):
        """Handle mouse press events for selection."""
        if self.current_tool == "selection":
            item = self.itemAt(event.scenePos(), QTransform())
            if item in self.handles:
                self.active_handle = item
                return

            editor = self.views()[0]
            if not editor.current_image:
                return

            if not isinstance(item, MovableImageItem):
                for selected_item in self.selectedItems():
                    if isinstance(selected_item, MovableImageItem):
                        self.fixMovableItem(selected_item, editor)
                        selected_item.setSelected(False)
                        self.removeItem(selected_item)
                        editor.pasted_items.remove(selected_item)

                if self.selection_rect:
                    self.removeItem(self.selection_rect)
                    self.selection_rect = None
                for handle in self.handles:
                    self.removeItem(handle)
                self.handles.clear()

                self.selecting = True
                self.start_pos = event.scenePos()
                self.selection_rect = self.addRect(QRectF(self.start_pos, QSizeF(0, 0)))
                self.updatePenWidth()
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for resizing or creating selections."""
        scene_rect = self.sceneRect()
        if self.active_handle:
            new_pos = event.scenePos()
            handle_type = self.active_handle.data(0)
            rect = self.selection_rect.rect()

            new_pos.setX(max(scene_rect.left(), min(new_pos.x(), scene_rect.right())))
            new_pos.setY(max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom())))

            if handle_type == "topLeft":
                rect.setTopLeft(new_pos)
            elif handle_type == "topRight":
                rect.setTopRight(new_pos)
            elif handle_type == "bottomLeft":
                rect.setBottomLeft(new_pos)
            elif handle_type == "bottomRight":
                rect.setBottomRight(new_pos)
            elif handle_type == "top":
                rect.setTop(new_pos.y())
            elif handle_type == "bottom":
                rect.setBottom(new_pos.y())
            elif handle_type == "left":
                rect.setLeft(new_pos.x())
            elif handle_type == "right":
                rect.setRight(new_pos.x())

            rect = rect.normalized()
            rect.setLeft(max(scene_rect.left(), rect.left()))
            rect.setRight(min(scene_rect.right(), rect.right()))
            rect.setTop(max(scene_rect.top(), rect.top()))
            rect.setBottom(min(scene_rect.bottom(), rect.bottom()))

            self.selection_rect.setRect(rect)
            self.updatePenWidth()
            self.createHandles()
            self.selectionChanged.emit(rect)
        elif self.selecting and self.start_pos and self.current_tool == "selection":
            current_pos = event.scenePos()
            current_pos.setX(max(scene_rect.left(), min(current_pos.x(), scene_rect.right())))
            current_pos.setY(max(scene_rect.top(), min(current_pos.y(), scene_rect.bottom())))
            rect = QRectF(self.start_pos, current_pos).normalized()
            rect.setLeft(max(scene_rect.left(), rect.left()))
            rect.setRight(min(scene_rect.right(), rect.right()))
            rect.setTop(max(scene_rect.top(), rect.top()))
            rect.setBottom(min(scene_rect.bottom(), rect.bottom()))
            if self.selection_rect:
                self.selection_rect.setRect(rect)
                self.updatePenWidth()
                self.selectionChanged.emit(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events to finalize selections."""
        if self.selecting and self.current_tool == "selection":
            self.selecting = False
            self.createHandles()
        elif self.active_handle:
            self.active_handle = None
        super().mouseReleaseEvent(event)

class MovableImageItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, parent=None):
        """Initialize a movable image item."""
        super().__init__(pixmap, parent)
        self.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(100)

    def mouseMoveEvent(self, event):
        """Handle movement of the item, constraining it within the scene."""
        super().mouseMoveEvent(event)
        scene_rect = self.scene().sceneRect()
        new_pos = self.pos()
        item_rect = self.boundingRect()
        new_pos.setX(max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - item_rect.width())))
        new_pos.setY(max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - item_rect.height())))
        self.setPos(new_pos)

    def mousePressEvent(self, event):
        """Select the item on left-click."""
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Keep the item selected after release."""
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
        super().mouseReleaseEvent(event)
