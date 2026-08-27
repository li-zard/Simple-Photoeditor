"""Тесты команд undo/redo (этап 4 роадмапа).

Каждая команда проверяется по полному циклу: execute → undo → redo,
с побайтовым сравнением изображения (image_bytes) там, где важна
точность восстановления.
"""

import pytest
from PyQt5.QtWidgets import QApplication, QGraphicsRectItem
from PyQt5.QtGui import QImage, qRgb, QColor
from PyQt5.QtCore import QRect, QRectF, Qt

from commands import (
    CropCommand,
    TransformCommand,
    AdjustmentsCommand,
    CutCommand,
    PasteCommand,
    ResizeCommand,
    FixPasteCommand,
)
from conftest import image_bytes, make_gradient, make_solid_image


# ---------------------------------------------------------------------------
# CropCommand
# ---------------------------------------------------------------------------

class TestCropCommand:
    def test_execute_crops_to_rect(self, editor):
        original = editor.getCurrentImage().copy()
        rect = QRect(10, 20, 30, 40)
        command = CropCommand(editor, rect)
        command.execute()

        assert editor.current_image.width() == 30
        assert editor.current_image.height() == 40
        # Содержимое кропа совпадает с соответствующей областью оригинала
        assert image_bytes(editor.current_image) == image_bytes(original.copy(rect))

    def test_undo_redo_restores_bytes(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        rect = QRect(5, 5, 50, 60)
        command = CropCommand(editor, rect)

        command.execute()
        assert image_bytes(editor.current_image) != original_bytes

        command.undo()
        assert image_bytes(editor.current_image) == original_bytes

        command.redo()
        assert editor.current_image.size() == rect.size()
        assert image_bytes(editor.current_image) != original_bytes


# ---------------------------------------------------------------------------
# TransformCommand
# ---------------------------------------------------------------------------

class TestTransformCommand:
    def test_rotate_90_swaps_dimensions(self, editor):
        w, h = editor.current_image.width(), editor.current_image.height()
        command = TransformCommand(editor, degrees=90)
        command.execute()

        assert (editor.current_image.width(), editor.current_image.height()) == (h, w)

        command.undo()
        assert (editor.current_image.width(), editor.current_image.height()) == (w, h)

        command.redo()
        assert (editor.current_image.width(), editor.current_image.height()) == (h, w)

    def test_rotate_90_corner_pixels(self, editor):
        # Градиент: пиксель (0,0) красный канал 0; после поворота на 90°
        # по часовой источник (0, h-1) попадает в (0, 0) целевого изображения.
        original = editor.getCurrentImage().copy()
        command = TransformCommand(editor, degrees=90)
        command.execute()

        src = QColor(original.pixel(0, original.height() - 1))
        dst = QColor(editor.current_image.pixel(0, 0))
        assert src == dst

    def test_flip_horizontal(self, editor):
        original = editor.getCurrentImage().copy()
        w = original.width()
        command = TransformCommand(editor, horizontal_flip=True)
        command.execute()

        src = QColor(original.pixel(0, 0))
        dst = QColor(editor.current_image.pixel(w - 1, 0))
        assert src == dst

        command.undo()
        assert image_bytes(editor.current_image) == image_bytes(original)


# ---------------------------------------------------------------------------
# AdjustmentsCommand
# ---------------------------------------------------------------------------

class TestAdjustmentsCommand:
    def test_brightness_changes_image(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        command = AdjustmentsCommand(editor, brightness=0.2, contrast=0, gamma=1.0)
        command.execute()

        assert image_bytes(editor.current_image) != original_bytes

        command.undo()
        assert image_bytes(editor.current_image) == original_bytes

    def test_redo_is_idempotent(self, editor):
        command = AdjustmentsCommand(editor, brightness=0.1, contrast=0.1, gamma=1.2)
        command.execute()
        first = image_bytes(editor.current_image)

        # Повторный redo пересчитывает результат из сохранённого
        # original_image — байты обязаны совпадать (идемпотентность).
        command.redo()
        assert image_bytes(editor.current_image) == first

    @pytest.mark.parametrize("kwargs", [
        {"brightness": 0.15},
        {"contrast": 0.15},
        {"gamma": 2.2},
        {"autobalance": True},
    ])
    def test_each_adjustment_changes_and_restores(self, editor, kwargs):
        original_bytes = image_bytes(editor.getCurrentImage())
        command = AdjustmentsCommand(
            editor,
            brightness=kwargs.get("brightness", 0),
            contrast=kwargs.get("contrast", 0),
            gamma=kwargs.get("gamma", 1.0),
            autobalance=kwargs.get("autobalance", False),
        )
        command.execute()
        assert image_bytes(editor.current_image) != original_bytes, kwargs

        command.undo()
        assert image_bytes(editor.current_image) == original_bytes, kwargs

    def test_autobalance_redo_idempotent(self, editor):
        command = AdjustmentsCommand(editor, 0, 0, 1.0, autobalance=True)
        command.execute()
        first = image_bytes(editor.current_image)

        command.redo()
        assert image_bytes(editor.current_image) == first


# ---------------------------------------------------------------------------
# CutCommand
# ---------------------------------------------------------------------------

def _make_selection(editor, rect):
    """Создать selection_rect в сцене (имитация выделения мышью)."""
    item = QGraphicsRectItem(QRectF(rect))
    editor.scene.addItem(item)
    editor.scene.selection_rect = item
    return item


class TestCutCommand:
    def test_cut_puts_selection_to_clipboard_and_fills(self, editor):
        original = editor.getCurrentImage().copy()
        rect = QRect(10, 10, 20, 25)
        _make_selection(editor, rect)

        command = CutCommand(editor)
        command.execute()

        # Буфер обмена содержит вырезанную область
        clipboard_image = QApplication.clipboard().image()
        assert not clipboard_image.isNull()
        assert clipboard_image.size() == rect.size()
        assert image_bytes(clipboard_image) == image_bytes(original.copy(rect))

        # Область залита белым (fill_color по умолчанию)
        assert QColor(editor.current_image.pixel(15, 15)) == QColor(Qt.white)
        # Остальная часть изображения не тронута
        assert QColor(editor.current_image.pixel(60, 60)) == QColor(original.pixel(60, 60))

        # Выделение удалено из сцены
        assert editor.scene.selection_rect is None
        assert editor.scene.handles == []

    def test_cut_undo_restores(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        rect = QRect(0, 0, 40, 40)
        _make_selection(editor, rect)

        command = CutCommand(editor)
        command.execute()
        command.undo()
        assert image_bytes(editor.current_image) == original_bytes

    def test_cut_without_selection_is_noop(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        command = CutCommand(editor)  # selection_rect is None → QRect()
        command.execute()

        assert image_bytes(editor.current_image) == original_bytes
        assert editor.is_modified is False

    def test_cut_custom_fill_color(self, editor):
        rect = QRect(10, 10, 20, 20)
        _make_selection(editor, rect)
        black = QColor(Qt.black)

        command = CutCommand(editor, fill_color=black)
        command.execute()

        assert QColor(editor.current_image.pixel(15, 15)) == black


# ---------------------------------------------------------------------------
# PasteCommand
# ---------------------------------------------------------------------------

class TestPasteCommand:
    def test_paste_into_selection(self, editor):
        original = editor.getCurrentImage().copy()
        rect = QRect(10, 10, 20, 20)
        _make_selection(editor, rect)

        paste_image = make_solid_image(20, 20, qRgb(255, 0, 0))
        command = PasteCommand(editor, paste_image)
        command.execute()

        # Пиксель внутри выделения заменён красным
        assert QColor(editor.current_image.pixel(15, 15)) == QColor(255, 0, 0)
        # За пределами выделения — нетронуто
        assert QColor(editor.current_image.pixel(60, 60)) == QColor(original.pixel(60, 60))
        # Плавающих элементов не появилось
        assert editor.pasted_items == []

        command.undo()
        assert image_bytes(editor.current_image) == image_bytes(original)

    def test_paste_as_movable_item_without_selection(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        paste_image = make_solid_image(30, 30, qRgb(0, 255, 0))
        command = PasteCommand(editor, paste_image)
        command.execute()

        # Холст не изменился — вставка стала плавающим элементом
        assert image_bytes(editor.current_image) == original_bytes
        assert len(editor.pasted_items) == 1
        assert editor.pasted_items[0].pos() == pytest.approx(10, abs=0.001) or \
            editor.pasted_items[0].pos().x() == 10

        command.undo()
        assert editor.pasted_items == []
        assert image_bytes(editor.current_image) == original_bytes

    def test_paste_redo_recreates_item(self, editor):
        paste_image = make_solid_image(10, 10, qRgb(0, 0, 255))
        command = PasteCommand(editor, paste_image)
        command.execute()
        command.undo()
        assert editor.pasted_items == []

        command.redo()
        assert len(editor.pasted_items) == 1


# ---------------------------------------------------------------------------
# ResizeCommand / FixPasteCommand (контракт этапа 3: мутация в execute())
# ---------------------------------------------------------------------------

class TestResizeCommand:
    def test_execute_undo_redo(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        command = ResizeCommand(editor, 50, 40, keep_aspect=False)
        command.execute()

        assert (editor.current_image.width(), editor.current_image.height()) == (50, 40)

        command.undo()
        assert (editor.current_image.width(), editor.current_image.height()) == (100, 100)
        assert image_bytes(editor.current_image) == original_bytes

        command.redo()
        assert (editor.current_image.width(), editor.current_image.height()) == (50, 40)

    def test_keep_aspect(self, editor):
        # 100×100 → вписать в 80×40 с сохранением пропорций → 40×40
        command = ResizeCommand(editor, 80, 40, keep_aspect=True)
        command.execute()
        assert (editor.current_image.width(), editor.current_image.height()) == (40, 40)


class TestFixPasteCommand:
    def test_execute_bakes_items_and_undo_restores(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        paste_image = make_solid_image(20, 20, qRgb(255, 0, 0))
        paste = PasteCommand(editor, paste_image)
        paste.execute()
        assert len(editor.pasted_items) == 1
        item = editor.pasted_items[0]

        fix = FixPasteCommand(editor, editor.pasted_items[:])
        fix.execute()

        # Элементы запечены: плавающих нет, холст изменился
        assert editor.pasted_items == []
        assert image_bytes(editor.current_image) != original_bytes
        # Пиксель в области (10..30, 10..30) теперь красный
        assert QColor(editor.current_image.pixel(15, 15)) == QColor(255, 0, 0)

        fix.undo()
        # Плавающий элемент восстановлен с флагами перемещаемости
        assert len(editor.pasted_items) == 1
        assert editor.pasted_items[0] is item
        assert image_bytes(editor.current_image) == original_bytes

        fix.redo()
        assert editor.pasted_items == []
        assert QColor(editor.current_image.pixel(15, 15)) == QColor(255, 0, 0)

    def test_execute_with_empty_list_is_noop(self, editor):
        original_bytes = image_bytes(editor.getCurrentImage())
        command = FixPasteCommand(editor, [])
        command.execute()
        assert image_bytes(editor.current_image) == original_bytes


# ---------------------------------------------------------------------------
# Интеграция с историей редактора (executeCommand / undo / redo)
# ---------------------------------------------------------------------------

class TestEditorHistory:
    def test_execute_command_updates_stacks_and_modified_flag(self, editor):
        command = CropCommand(editor, QRect(0, 0, 50, 50))
        editor.executeCommand(command)

        assert editor.undo_stack == [command]
        assert editor.redo_stack == []
        assert editor.is_modified is True

        editor.undo()
        assert editor.undo_stack == []
        assert editor.redo_stack == [command]

        editor.redo()
        assert editor.undo_stack == [command]
        assert editor.redo_stack == []

    def test_undo_limit_20(self, editor):
        for i in range(25):
            editor.executeCommand(
                AdjustmentsCommand(editor, 0.01 * (i + 1), 0, 1.0)
            )
        assert len(editor.undo_stack) == editor.UNDO_LIMIT == 20

    def test_new_command_clears_redo_stack(self, editor):
        editor.executeCommand(CropCommand(editor, QRect(0, 0, 50, 50)))
        editor.undo()
        assert len(editor.redo_stack) == 1

        editor.executeCommand(CropCommand(editor, QRect(0, 0, 30, 30)))
        assert editor.redo_stack == []
