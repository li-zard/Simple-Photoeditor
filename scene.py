from PyQt5.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem
from PyQt5.QtGui import QColor, QPen, QCursor, QTransform, QPainter
from PyQt5.QtCore import Qt, QRectF, QSizeF, QPointF, QTimer, pyqtSignal

# Типы и курсоры якорей ресайза вставленных элементов (подход 1:
# растягивание вставленного изображения перед фиксацией на холсте).
ITEM_HANDLE_CURSORS = {
    "topLeft": Qt.SizeFDiagCursor, "bottomRight": Qt.SizeFDiagCursor,
    "topRight": Qt.SizeBDiagCursor, "bottomLeft": Qt.SizeBDiagCursor,
    "left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor,
    "top": Qt.SizeVerCursor, "bottom": Qt.SizeVerCursor,
}

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
        # Перемещение выделения целиком (этап 5.3): тащим прямоугольник
        # за внутреннюю область, а не только за 8 маркеров.
        self.moving_selection = False
        self.move_offset = QPointF(0, 0)
        # Ресайз вставленных элементов (подход 1): якоря вокруг
        # MovableImageItem и состояние перетаскивания за якорь.
        self.item_handles = []
        self.handles_item = None
        self.item_resize_handle = None
        self.item_resize_anchor = None
        self.item_resize_start_rect = QRectF()
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

    def moveSelectionTo(self, scene_pos):
        """Переместить выделение так, чтобы курсор сохранял точку захвата.

        Размер прямоугольника сохраняется; topLeft ограничивается
        пределами изображения (этап 5.3).
        """
        if not self.selection_rect:
            return
        scene_rect = self.sceneRect()
        rect = self.selection_rect.rect()
        new_top_left = scene_pos - self.move_offset
        new_top_left.setX(max(scene_rect.left(),
                              min(new_top_left.x(),
                                  scene_rect.right() - rect.width())))
        new_top_left.setY(max(scene_rect.top(),
                              min(new_top_left.y(),
                                  scene_rect.bottom() - rect.height())))
        rect.moveTopLeft(new_top_left)
        self.selection_rect.setRect(rect)
        self.createHandles()
        self.selectionChanged.emit(rect)

    def fixMovableItem(self, item, editor):
        """Fix a movable item onto the image (с учётом масштаба элемента)."""
        if not isinstance(item, MovableImageItem) or not editor.current_image:
            return
        target = item.visualRect().toRect()
        painter = QPainter(editor.current_image)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(target, item.pixmap())
        painter.end()
        if self.handles_item is item:
            self.clearItemHandles()
        editor.setImage(editor.current_image, keep_view=True)
        editor.is_modified = True

    # --- Якоря ресайза вставленных элементов (подход 1) ---

    def createItemHandles(self, item):
        """Создать 8 якорей ресайза вокруг вставленного элемента."""
        if item is None or item.scene() is not self:
            return
        self.clearItemHandles()
        self.handles_item = item
        editor = self.views()[0]
        img_size = max(editor.current_image.width(), editor.current_image.height()) if editor.current_image else 1000
        handle_size = max(12, min(30, img_size // 150))

        rect = item.visualRect()
        positions = [
            (rect.topLeft(), "topLeft"), (rect.topRight(), "topRight"),
            (rect.bottomLeft(), "bottomLeft"), (rect.bottomRight(), "bottomRight"),
            (QPointF(rect.center().x(), rect.top()), "top"),
            (QPointF(rect.center().x(), rect.bottom()), "bottom"),
            (QPointF(rect.left(), rect.center().y()), "left"),
            (QPointF(rect.right(), rect.center().y()), "right"),
        ]

        for pos, handle_type in positions:
            handle = QGraphicsRectItem(QRectF(pos.x() - handle_size / 2, pos.y() - handle_size / 2,
                                               handle_size, handle_size))
            handle.setBrush(QColor(0, 120, 215))
            handle.setPen(QPen(Qt.white, 1))
            handle.setFlag(QGraphicsRectItem.ItemIsMovable, False)
            handle.setZValue(300)
            handle.setCursor(ITEM_HANDLE_CURSORS[handle_type])
            handle.setData(0, handle_type)
            self.addItem(handle)
            self.item_handles.append(handle)
        self.update()

    def clearItemHandles(self):
        """Убрать якоря ресайза вставленного элемента."""
        for handle in self.item_handles:
            if handle.scene():
                self.removeItem(handle)
        self.item_handles = []
        self.handles_item = None
        self.item_resize_handle = None

    def updateItemHandles(self):
        """Перестроить якоря под текущее положение/размер элемента."""
        if self.handles_item is not None and self.item_handles:
            self.createItemHandles(self.handles_item)

    def beginItemResize(self, scene_pos):
        """Начать ресайз за якорь: запомнить стартовый rect и якорную точку."""
        item = self.handles_item
        if item is None:
            return
        rect = item.visualRect()
        self.item_resize_start_rect = rect
        ht = self.item_resize_handle
        anchor = QPointF(rect.left(), rect.top())
        if ht == "topLeft":
            anchor = rect.bottomRight()
        elif ht == "topRight":
            anchor = rect.bottomLeft()
        elif ht == "bottomLeft":
            anchor = rect.topRight()
        elif ht == "bottomRight":
            anchor = rect.topLeft()
        elif ht == "top":
            anchor = QPointF(rect.center().x(), rect.bottom())
        elif ht == "bottom":
            anchor = QPointF(rect.center().x(), rect.top())
        elif ht == "left":
            anchor = QPointF(rect.right(), rect.center().y())
        elif ht == "right":
            anchor = QPointF(rect.left(), rect.center().y())
        self.item_resize_anchor = anchor

    def updateItemResize(self, scene_pos, free_aspect):
        """Изменить размер элемента по позиции курсора.

        Пропорции сохраняются по умолчанию; free_aspect=True (Shift) —
        свободный ресайз. Противоположный угол/сторона неподвижны.
        """
        item = self.handles_item
        if item is None or self.item_resize_handle is None:
            return
        editor = self.views()[0]
        base = item.baseSize()
        if base.width() <= 0 or base.height() <= 0:
            return
        aspect = base.height() / base.width()
        start = self.item_resize_start_rect
        anchor = self.item_resize_anchor
        ht = self.item_resize_handle
        min_size = MovableImageItem.MIN_SIZE
        max_w = self.sceneRect().width() * 4
        max_h = self.sceneRect().height() * 4

        corner = ht in ("topLeft", "topRight", "bottomLeft", "bottomRight")
        if corner:
            new_w = abs(scene_pos.x() - anchor.x())
            new_h = abs(scene_pos.y() - anchor.y())
            if not free_aspect:
                s = max(new_w / base.width(), new_h / base.height())
                new_w, new_h = base.width() * s, base.height() * s
        elif ht in ("left", "right"):
            new_w = abs(scene_pos.x() - anchor.x())
            new_h = start.height() if free_aspect else new_w * aspect
        else:  # top / bottom
            new_h = abs(scene_pos.y() - anchor.y())
            new_w = start.width() if free_aspect else new_h / aspect

        # Ограничения размера
        new_w = max(min_size, min(new_w, max_w))
        new_h = max(min_size, min(new_h, max_h))
        if not free_aspect:
            if new_w / base.width() > new_h / base.height():
                new_w = new_h / aspect
            else:
                new_h = new_w * aspect

        # Итоговый rect: якорь неподвижен, расширение в сторону курсора
        if corner:
            dx = 1.0 if scene_pos.x() >= anchor.x() else -1.0
            dy = 1.0 if scene_pos.y() >= anchor.y() else -1.0
            rect = QRectF(anchor.x(), anchor.y(), dx * new_w, dy * new_h).normalized()
        elif ht == "left":
            rect = QRectF(start.right() - new_w, start.center().y() - new_h / 2, new_w, new_h)
        elif ht == "right":
            rect = QRectF(start.left(), start.center().y() - new_h / 2, new_w, new_h)
        elif ht == "top":
            rect = QRectF(start.center().x() - new_w / 2, start.bottom() - new_h, new_w, new_h)
        else:  # bottom
            rect = QRectF(start.center().x() - new_w / 2, start.top(), new_w, new_h)

        item.setPos(rect.topLeft())
        item.setTransform(QTransform().scale(new_w / base.width(), new_h / base.height()))
        self.createItemHandles(item)
        editor.window().statusBar().showMessage(
            f"Pasted image: {int(new_w)}×{int(new_h)} px", 2000)

    def mousePressEvent(self, event):
        """Handle mouse press events for selection."""
        if self.current_tool == "selection":
            item = self.itemAt(event.scenePos(), QTransform())
            if item in self.handles:
                self.active_handle = item
                return
            if item in self.item_handles:
                self.item_resize_handle = item.data(0)
                self.beginItemResize(event.scenePos())
                return

            editor = self.views()[0]
            if not editor.current_image:
                return

            # Клик внутри существующего выделения — тащим его целиком
            # (этап 5.3), не начиная новое.
            if (self.selection_rect is not None
                    and not isinstance(item, MovableImageItem)
                    and self.selection_rect.rect().contains(event.scenePos())):
                self.moving_selection = True
                self.move_offset = event.scenePos() - self.selection_rect.rect().topLeft()
                return

            if not isinstance(item, MovableImageItem):
                self.clearItemHandles()
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
        if self.item_resize_handle:
            self.updateItemResize(event.scenePos(),
                                  event.modifiers() & Qt.ShiftModifier)
            return
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
        elif self.moving_selection and self.selection_rect:
            self.moveSelectionTo(event.scenePos())
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
        if self.item_resize_handle:
            self.item_resize_handle = None
            return
        if self.selecting and self.current_tool == "selection":
            self.selecting = False
            self.createHandles()
        elif self.moving_selection:
            self.moving_selection = False
        elif self.active_handle:
            self.active_handle = None
        super().mouseReleaseEvent(event)

class MovableImageItem(QGraphicsPixmapItem):
    # Минимальный размер визуального прямоугольника (px)
    MIN_SIZE = 8

    def __init__(self, pixmap, parent=None):
        """Initialize a movable image item."""
        super().__init__(pixmap, parent)
        self.setTransformationMode(Qt.SmoothTransformation)
        self.setFlag(QGraphicsPixmapItem.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.ItemIsSelectable, True)
        self.setCursor(Qt.SizeAllCursor)
        self.setZValue(100)

    def visualRect(self):
        """Визуальный прямоугольник в координатах сцены (с учётом масштаба).

        boundingRect() QGraphicsPixmapItem добавляет полупиксельную рамку
        вокруг pixmap, поэтому используем точный размер pixmap.
        """
        pm = self.pixmap()
        return self.mapRectToScene(QRectF(0, 0, pm.width(), pm.height()))

    def baseSize(self):
        """Исходный размер pixmap (без масштабирования)."""
        pm = self.pixmap()
        return QSizeF(pm.width(), pm.height())

    def mouseMoveEvent(self, event):
        """Перетаскивание: элемент может выходить за края холста,
        но не менее 10% должно оставаться внутри, чтобы его можно было захватить."""
        super().mouseMoveEvent(event)
        scene_rect = self.scene().sceneRect()
        vis = self.visualRect()
        new_pos = self.pos()
        min_x = scene_rect.left() - vis.width() * 0.9
        max_x = scene_rect.right() - vis.width() * 0.1
        min_y = scene_rect.top() - vis.height() * 0.9
        max_y = scene_rect.bottom() - vis.height() * 0.1
        new_pos.setX(max(min_x, min(new_pos.x(), max_x)))
        new_pos.setY(max(min_y, min(new_pos.y(), max_y)))
        self.setPos(new_pos)
        scene = self.scene()
        if scene and scene.handles_item is self:
            scene.updateItemHandles()

    def mousePressEvent(self, event):
        """Select the item on left-click and show its resize handles."""
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            scene = self.scene()
            if scene:
                scene.createItemHandles(self)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Keep the item selected after release."""
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
        super().mouseReleaseEvent(event)
