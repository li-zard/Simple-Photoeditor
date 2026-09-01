"""Tests for Approach 1: resizable pasted items (MovableImageItem handles).

Covers:
- paste creates a floating item with base (unscaled) size
- item resize via scene.updateItemResize: aspect lock, Shift = free, min clamp
- FixPasteCommand bakes the scaled item onto the canvas
- undo restores the floating item with its transform
- redo re-bakes
"""
import pytest
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QImage, QColor, QPixmap, QTransform
from PyQt5.QtCore import QRectF, QPointF, QSizeF, Qt

from editor import ImageEditor
from scene import MovableImageItem
from commands import PasteCommand, FixPasteCommand


@pytest.fixture
def editor(qapp):
    """ImageEditor с белым холстом 400×300 внутри QMainWindow
    (window() нужен командам для statusBar())."""
    window = QMainWindow()
    ed = ImageEditor()
    window.setCentralWidget(ed)
    window.resize(400, 400)
    canvas = QImage(400, 300, QImage.Format_RGB32)
    canvas.fill(QColor(255, 255, 255))
    ed.setImage(canvas)
    yield ed
    window.close()


@pytest.fixture
def clipboard_image():
    img = QImage(100, 50, QImage.Format_RGB32)
    img.fill(QColor(255, 0, 0))
    return img


def _paste_floating(editor, clipboard_image):
    editor.scene.selection_rect = None  # no selection -> floating item
    cmd = PasteCommand(editor, clipboard_image)
    cmd.execute()
    return cmd


class TestPasteFloatingItem:
    def test_paste_creates_floating_item(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        assert isinstance(cmd.movable_item, MovableImageItem)
        assert cmd.movable_item in editor.pasted_items
        assert cmd.movable_item.baseSize() == QSizeF(100, 50)

    def test_visual_rect_reflects_transform(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(10, 10))
        item.setTransform(QTransform().scale(2.0, 2.0))
        rect = item.visualRect()
        assert rect == QRectF(10, 10, 200, 100)


class TestItemResize:
    def test_corner_resize_keeps_aspect(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(0, 0))
        editor.scene.handles_item = item
        editor.scene.createItemHandles(item)
        # drag bottomRight to (200,200): anchor (topLeft) fixed at (0,0)
        editor.scene.item_resize_handle = "bottomRight"
        editor.scene.beginItemResize(QPointF(100, 50))
        editor.scene.updateItemResize(QPointF(200, 200), free_aspect=False)
        rect = item.visualRect()
        # base 100x50, scale = max(200/100, 200/50) = 4 -> 400x200
        assert rect.width() == pytest.approx(400, abs=1)
        assert rect.height() == pytest.approx(200, abs=1)
        # aspect preserved
        assert rect.height() / rect.width() == pytest.approx(0.5, abs=0.01)

    def test_shift_gives_free_resize(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(0, 0))
        editor.scene.handles_item = item
        editor.scene.createItemHandles(item)
        editor.scene.item_resize_handle = "bottomRight"
        editor.scene.beginItemResize(QPointF(100, 50))
        editor.scene.updateItemResize(QPointF(200, 200), free_aspect=True)
        rect = item.visualRect()
        assert rect.width() == pytest.approx(200, abs=1)
        assert rect.height() == pytest.approx(200, abs=1)

    def test_min_size_clamp(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(0, 0))
        editor.scene.handles_item = item
        editor.scene.createItemHandles(item)
        editor.scene.item_resize_handle = "bottomRight"
        editor.scene.beginItemResize(QPointF(100, 50))
        # drag almost onto the anchor -> clamped to MIN_SIZE
        editor.scene.updateItemResize(QPointF(1, 1), free_aspect=True)
        rect = item.visualRect()
        assert rect.width() >= MovableImageItem.MIN_SIZE
        assert rect.height() >= MovableImageItem.MIN_SIZE

    def test_anchor_corner_stays_fixed(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(20, 20))
        editor.scene.handles_item = item
        editor.scene.createItemHandles(item)
        editor.scene.item_resize_handle = "bottomRight"
        editor.scene.beginItemResize(QPointF(120, 70))
        editor.scene.updateItemResize(QPointF(220, 170), free_aspect=False)
        rect = item.visualRect()
        assert rect.topLeft().x() == pytest.approx(20, abs=1)
        assert rect.topLeft().y() == pytest.approx(20, abs=1)


class TestBakeScaledItem:
    def test_fix_bakes_scaled_item(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(0, 0))
        item.setTransform(QTransform().scale(2.0, 2.0))  # 200x100 red block
        editor.executeCommand(FixPasteCommand(editor, [item]))
        # canvas center of the pasted area must be red now
        assert editor.current_image.pixelColor(100, 50) == QColor(255, 0, 0)
        assert editor.pasted_items == []

    def test_undo_restores_item_with_transform(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(5, 5))
        item.setTransform(QTransform().scale(2.0, 2.0))
        fix = FixPasteCommand(editor, [item])
        editor.executeCommand(fix)
        editor.undo()
        assert item in editor.pasted_items
        assert item.transform().m11() == pytest.approx(2.0)
        assert item.pos() == QPointF(5, 5)
        # canvas restored: pasted area is white again
        assert editor.current_image.pixelColor(100, 50) == QColor(255, 255, 255)

    def test_redo_rebakes(self, editor, clipboard_image):
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(0, 0))
        item.setTransform(QTransform().scale(2.0, 2.0))
        fix = FixPasteCommand(editor, [item])
        editor.executeCommand(fix)
        editor.undo()
        editor.redo()
        assert editor.current_image.pixelColor(100, 50) == QColor(255, 0, 0)
        assert editor.pasted_items == []

    def test_bake_clips_to_canvas(self, editor, clipboard_image):
        """Item partially outside the canvas: bake must not crash and must
        draw only the visible part."""
        cmd = _paste_floating(editor, clipboard_image)
        item = cmd.movable_item
        item.setPos(QPointF(350, 250))  # mostly outside 400x300 canvas
        editor.executeCommand(FixPasteCommand(editor, [item]))
        # pixel inside both canvas and item area is red
        assert editor.current_image.pixelColor(370, 260) == QColor(255, 0, 0)
        assert editor.pasted_items == []


class TestPasteUndoTransform:
    def test_paste_undo_restores_previous_item_transform(self, editor, clipboard_image):
        # first paste + scale
        first = _paste_floating(editor, clipboard_image)
        first.movable_item.setTransform(QTransform().scale(3.0, 3.0))
        # second paste (fixes nothing, adds another floating item)
        second_img = QImage(20, 20, QImage.Format_RGB32)
        second_img.fill(QColor(0, 0, 255))
        second = PasteCommand(editor, second_img)
        editor.scene.selection_rect = None
        second.execute()
        second.undo()
        # first item is back with its 3x transform
        assert first.movable_item in editor.pasted_items
        assert first.movable_item.transform().m11() == pytest.approx(3.0)
