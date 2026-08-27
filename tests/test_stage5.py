"""Тесты новых функций этапа 5: zoom под курсором, одноэкземплярность,
перемещение выделения, i18n-подготовка."""

import pytest
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtCore import QRect, QRectF, QPoint, QPointF, Qt
from PyQt5.QtGui import QWheelEvent

from singleinstance import SingleInstance


# ---------------------------------------------------------------------------
# 5.1: Ctrl+колесо — зум под курсором
# ---------------------------------------------------------------------------

class TestWheelZoom:
    def _wheel(self, widget, delta_y, modifiers=Qt.NoModifier):
        """Синтетическое событие колеса в центре виджета (сигнатура PyQt5)."""
        pos = widget.rect().center()
        global_pos = widget.mapToGlobal(pos)
        return QWheelEvent(
            QPointF(pos.x(), pos.y()),
            QPointF(global_pos.x(), global_pos.y()),
            QPoint(0, 0),
            QPoint(0, delta_y),
            Qt.NoButton,
            modifiers,
            Qt.ScrollUpdate,
            False,
        )

    def test_ctrl_wheel_zooms(self, editor):
        before = editor.zoom_factor
        editor.wheelEvent(self._wheel(editor, 120, Qt.ControlModifier))
        assert editor.zoom_factor == pytest.approx(before * 1.25)

        editor.wheelEvent(self._wheel(editor, -120, Qt.ControlModifier))
        assert editor.zoom_factor == pytest.approx(before)

    def test_plain_wheel_does_not_zoom(self, editor):
        before = editor.zoom_factor
        editor.wheelEvent(self._wheel(editor, 120, Qt.NoModifier))
        assert editor.zoom_factor == pytest.approx(before)

    def test_zoom_limits(self, editor):
        editor.zoom_factor = 19.0
        editor.applyZoom(1.25)
        assert editor.zoom_factor == pytest.approx(20.0)

        # 0.021 / 1.25 = 0.0168 < 0.02 → зажимается нижним пределом
        editor.zoom_factor = 0.021
        editor.applyZoom(1 / 1.25)
        assert editor.zoom_factor == pytest.approx(0.02)

    def test_zoom_in_out_use_applyzoom(self, editor):
        before = editor.zoom_factor
        editor.zoomIn()
        assert editor.zoom_factor == pytest.approx(before * 1.25)
        editor.zoomOut()
        assert editor.zoom_factor == pytest.approx(before)


# ---------------------------------------------------------------------------
# 5.2: одноэкземплярность
# ---------------------------------------------------------------------------

class TestSingleInstance:
    SERVER = "SimplePhotoEditor_test_5_2"

    def test_first_instance_activates(self, qapp):
        first = SingleInstance(server_name=self.SERVER)
        try:
            assert first.activate("") is True
            assert first._server is not None
            assert first._server.isListening()
        finally:
            first.shutdown()

    def test_second_instance_forwards_and_exits(self, qapp):
        first = SingleInstance(server_name=self.SERVER)
        try:
            assert first.activate("") is True

            received = []
            first.fileOpened.connect(received.append)

            second = SingleInstance(server_name=self.SERVER)
            assert second.activate("/tmp/picture.png") is False
            assert second._server is None  # второй не слушает

            # Доставка пути идёт по цепочке сигналов newConnection →
            # readyRead — нужно несколько циклов обработки событий.
            for _ in range(20):
                qapp.processEvents()
                if received:
                    break
            assert received == ["/tmp/picture.png"]
        finally:
            first.shutdown()

    def test_reactivate_after_shutdown(self, qapp):
        first = SingleInstance(server_name=self.SERVER)
        assert first.activate("") is True
        first.shutdown()

        second = SingleInstance(server_name=self.SERVER)
        try:
            # После shutdown() первого новый экземпляр снова становится
            # единственным (обработка «краха» предыдущего).
            assert second.activate("") is True
        finally:
            second.shutdown()


# ---------------------------------------------------------------------------
# 5.3: перемещение выделения целиком
# ---------------------------------------------------------------------------

class TestMoveSelection:
    def _make_selection(self, editor, rect):
        item = QGraphicsRectItem(QRectF(rect))
        editor.scene.addItem(item)
        editor.scene.selection_rect = item
        return item

    def test_move_selection_preserves_size(self, editor):
        self._make_selection(editor, QRect(10, 10, 30, 20))
        editor.scene.move_offset = QPointF(0, 0)

        editor.scene.moveSelectionTo(QPointF(50, 40))

        rect = editor.scene.selection_rect.rect().toRect()
        assert (rect.width(), rect.height()) == (30, 20)
        assert (rect.x(), rect.y()) == (50, 40)

    def test_move_selection_clamped_to_image(self, editor):
        # Изображение 100×100; пытаемся утащить выделение за край
        self._make_selection(editor, QRect(10, 10, 30, 20))
        editor.scene.move_offset = QPointF(0, 0)

        editor.scene.moveSelectionTo(QPointF(500, 500))

        rect = editor.scene.selection_rect.rect().toRect()
        assert rect.right() <= 100
        assert rect.bottom() <= 100
        assert rect.x() >= 0 and rect.y() >= 0

    def test_move_selection_emits_signal(self, editor):
        self._make_selection(editor, QRect(10, 10, 30, 20))
        editor.scene.move_offset = QPointF(0, 0)

        emitted = []
        editor.scene.selectionChanged.connect(lambda r: emitted.append(r))
        editor.scene.moveSelectionTo(QPointF(20, 20))

        assert len(emitted) == 1
        assert emitted[0].toRect().topLeft() == QPoint_check(20, 20)


def QPoint_check(x, y):
    from PyQt5.QtCore import QPoint
    return QPoint(x, y)


# ---------------------------------------------------------------------------
# 5.4: i18n-подготовка
# ---------------------------------------------------------------------------

class TestI18n:
    def test_actions_use_tr(self, qapp):
        from utils import load_config
        from main_window import MainWindow

        window = MainWindow(load_config())
        try:
            # tr() без установленного переводчика возвращает исходную
            # строку — главное, что обёртка не ломает создание действий.
            assert window.new_act.text() == "&New"
            assert window.open_act.text() == "&Open"
            assert window.undo_act.text() == "&Undo"
        finally:
            window.close()

    def test_dialogs_use_tr(self, qapp):
        from widgets import NewImageDialog

        dialog = NewImageDialog()
        try:
            assert dialog.windowTitle() == "New Image"
        finally:
            dialog.close()
