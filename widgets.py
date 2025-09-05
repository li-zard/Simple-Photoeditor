from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QMdiSubWindow, QDialogButtonBox, QCheckBox, 
    QMessageBox, QSpinBox, QComboBox, QColorDialog
)
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from PyQt5.QtCore import Qt, QSize, QRectF
from editor import ImageEditor, EditorContainer
from commands import AdjustmentsCommand


class RulerWidget(QWidget):
    def __init__(self, editor, orientation, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.orientation = orientation  # "horizontal" или "vertical"
        self.ruler_width = 30
        self.ruler_color = QColor(200, 200, 200)
        self.tick_color = QColor(50, 50, 50)
        self.label_color = QColor(0, 0, 0)

    def paintEvent(self, event):
        if not self.editor.current_image:
            return

        painter = QPainter(self)
        viewport_rect = self.editor.viewport().rect()
        # Get visible scene area in scene coordinates
        top_left = self.editor.mapToScene(viewport_rect.topLeft())
        bottom_right = self.editor.mapToScene(viewport_rect.bottomRight())
        visible_scene_rect = QRectF(top_left, bottom_right)

        # Scale
        zoom_factor = self.editor.zoom_factor
        if zoom_factor == 0:
            zoom_factor = 1.0  # Escape divide by zero

        # Calculate step of strips in Scenes pixels
        target_tick_spacing_pixels = 50  # Destination step in pix of viewport
        tick_spacing = target_tick_spacing_pixels / zoom_factor  # Step in coordinate of Scene
        tick_spacing = self.editor.adjustTickSpacing(tick_spacing)

       #Start from closest to start visible area point, but >=0
        start_x = max(0, int(visible_scene_rect.left() // tick_spacing) * tick_spacing)
        start_y = max(0, int(visible_scene_rect.top() // tick_spacing) * tick_spacing)

        # Draw ruller background
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.ruler_color)
        painter.drawRect(self.rect())

        painter.setPen(QPen(self.tick_color, 1))
        painter.setFont(QFont("Arial", 8))
        fm = QFontMetrics(painter.font())

        # Draw horizontal ruler
        if self.orientation == "horizontal":
            x = start_x
            while x <= self.editor.current_image.width():
                if visible_scene_rect.left() <= x <= visible_scene_rect.right():
                    viewport_x = self.editor.mapFromScene(x, 0).x()
                    if 0 <= viewport_x <= self.width():
                        painter.drawLine(viewport_x, self.ruler_width - 10, viewport_x, self.ruler_width)
                        label = str(int(x))
                        label_rect = fm.boundingRect(label)
                        painter.setPen(self.label_color)
                        painter.drawText(viewport_x - label_rect.width() // 2, self.ruler_width - 12, label)
                        painter.setPen(self.tick_color)
                        for i in range(1, 5):
                            minor_x = x + (tick_spacing / 5) * i
                            minor_viewport_x = self.editor.mapFromScene(minor_x, 0).x()
                            if 0 <= minor_viewport_x <= self.width():
                                painter.drawLine(minor_viewport_x, self.ruler_width - 5, minor_viewport_x, self.ruler_width)
                x += tick_spacing

            # Draw cursor strip
            if self.editor.cursor_pos.x() >= 0:
                cursor_x = self.editor.cursor_pos.x()
                if visible_scene_rect.left() <= cursor_x <= visible_scene_rect.right():
                    viewport_cursor_x = self.editor.mapFromScene(cursor_x, 0).x()
                    if 0 <= viewport_cursor_x <= self.width():
                        painter.setPen(QPen(Qt.red, 2))
                        painter.drawLine(viewport_cursor_x, 0, viewport_cursor_x, self.ruler_width)

        # Draw vertical rule
        if self.orientation == "vertical":
            y = start_y
            while y <= self.editor.current_image.height():
                if visible_scene_rect.top() <= y <= visible_scene_rect.bottom():
                    viewport_y = self.editor.mapFromScene(0, y).y()
                    if 0 <= viewport_y <= self.height():
                        painter.drawLine(self.ruler_width - 10, viewport_y, self.ruler_width, viewport_y)
                        label = str(int(y))
                        label_rect = fm.boundingRect(label)
                        painter.save()
                        painter.translate(self.ruler_width - 20, viewport_y)
                        painter.rotate(-90)
                        painter.setPen(self.label_color)
                        painter.drawText(-label_rect.width() // 2, -2, label)
                        painter.restore()
                        painter.setPen(self.tick_color)
                        for i in range(1, 5):
                            minor_y = y + (tick_spacing / 5) * i
                            minor_viewport_y = self.editor.mapFromScene(0, minor_y).y()
                            if 0 <= minor_viewport_y <= self.height():
                                painter.drawLine(self.ruler_width - 5, minor_viewport_y, self.ruler_width, minor_viewport_y)
                y += tick_spacing

            # Draw cursor strip 
            if self.editor.cursor_pos.y() >= 0:
                cursor_y = self.editor.cursor_pos.y()
                if visible_scene_rect.top() <= cursor_y <= visible_scene_rect.bottom():
                    viewport_cursor_y = self.editor.mapFromScene(0, cursor_y).y()
                    if 0 <= viewport_cursor_y <= self.height():
                        painter.setPen(QPen(Qt.red, 2))
                        painter.drawLine(0, viewport_cursor_y, self.ruler_width, viewport_cursor_y)

        painter.end()




class CustomMdiSubWindow(QMdiSubWindow):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.editor_container = EditorContainer(self)
        self.setWidget(self.editor_container)
        # Устанавливаем минимальный размер
        self.setMinimumSize(200, 150)
        # Устанавливаем начальный размер, подстраиваясь под QMdiArea
        mdi_area = main_window.mdi_area
        viewport_size = mdi_area.viewport().size()
        # Оставляем небольшой отступ (например, 50 пикселей), чтобы учесть скролл-бары
        max_width = max(200, viewport_size.width() - 50)
        max_height = max(150, viewport_size.height() - 50)
        self.resize(max_width, max_height)

    def closeEvent(self, event):
        editor = self.editor_container.editor
        if isinstance(editor, ImageEditor) and editor.is_modified:
            reply = QMessageBox.question(
                self,
                "Save Changes",
                f"The image '{self.windowTitle()}' has unsaved changes. Do you want to save it before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                try:
                    if not self.main_window.saveFile():
                        event.ignore()
                        return
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save the image: {str(e)}")
                    event.ignore()
                    return
            elif reply == QMessageBox.Discard:
                editor.is_modified = False
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()

'''
class CustomMdiSubWindow(QMdiSubWindow):
    def __init__(self, main_window):
        """Initialize a custom MDI subwindow."""
        super().__init__()
        self.main_window = main_window
        self.editor_container = EditorContainer(self)
        self.setWidget(self.editor_container)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def closeEvent(self, event):
        """Handle closing of the subwindow."""
        if not self.editor_container.editor.is_modified:
            event.accept()
            return

        reply = self.main_window.confirmSave(self.windowTitle())
        if reply == "save":
            if self.main_window.saveFile(self):
                event.accept()
            else:
                event.ignore()
        elif reply == "discard":
            event.accept()
        else:
            event.ignore()
'''
class NewImageDialog(QDialog):
    def __init__(self, parent=None):
        """Initialize the new image dialog."""
        super().__init__(parent)
        self.setWindowTitle("New Image")
        self.layout = QGridLayout(self)
        
        # Width
        self.width_label = QLabel("Width:", self)
        self.width_edit = QLineEdit("800", self)
        
        # Height
        self.height_label = QLabel("Height:", self)
        self.height_edit = QLineEdit("600", self)
        
        # Units
        self.units_label = QLabel("Units:", self)
        self.units_combo = QComboBox(self)
        self.units_combo.addItems(["Pixels", "Centimeters", "Inches"])
        
        # DPI
        self.dpi_label = QLabel("DPI:", self)
        self.dpi_edit = QLineEdit("150", self)
        
        # Color Depth
        self.color_depth_label = QLabel("Color depth:", self)
        self.color_depth_combo = QComboBox(self)
        self.color_depth_combo.addItems(["24-bit color", "8-bit palette", "8-bit grayscale", "1-bit monochrome"])
        
        # Background Color
        self.bg_color_button = QPushButton("Background color", self)
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        self.bg_color_label = QLabel(self)
        self.bg_color = QColor(Qt.white)
        self.update_bg_color_label()
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # Layout
        self.layout.addWidget(self.width_label, 0, 0)
        self.layout.addWidget(self.width_edit, 0, 1)
        self.layout.addWidget(self.units_combo, 0, 2)
        
        self.layout.addWidget(self.height_label, 1, 0)
        self.layout.addWidget(self.height_edit, 1, 1)
        
        self.layout.addWidget(self.dpi_label, 2, 0)
        self.layout.addWidget(self.dpi_edit, 2, 1)
        
        self.layout.addWidget(self.color_depth_label, 3, 0)
        self.layout.addWidget(self.color_depth_combo, 3, 1, 1, 2)
        
        self.layout.addWidget(self.bg_color_button, 4, 0)
        self.layout.addWidget(self.bg_color_label, 4, 1, 1, 2)
        
        self.layout.addWidget(self.buttons, 5, 0, 1, 3)

    def choose_bg_color(self):
        color = QColorDialog.getColor(self.bg_color, self)
        if color.isValid():
            self.bg_color = color
            self.update_bg_color_label()

    def update_bg_color_label(self):
        self.bg_color_label.setStyleSheet(f"background-color: {self.bg_color.name()}; border: 1px solid black;")
        self.bg_color_label.setText(self.bg_color.name())

    def getImageParameters(self):
        """Return width, height, DPI, and background color."""
        width = float(self.width_edit.text())
        height = float(self.height_edit.text())
        dpi = int(self.dpi_edit.text())
        units = self.units_combo.currentText()

        if units == "Centimeters":
            width = int(width * dpi / 2.54)
            height = int(height * dpi / 2.54)
        elif units == "Inches":
            width = int(width * dpi)
            height = int(height * dpi)
        else: # Pixels
            width = int(width)
            height = int(height)

        color_depth = self.color_depth_combo.currentText()
        return width, height, dpi, self.bg_color, color_depth

class AdjustmentsDialog(QDialog):
    def __init__(self, editor, parent=None):
        """Initialize the adjustments dialog."""
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Adjust Image")
        self.editor.start_preview()
        self.layout = QVBoxLayout(self)

        self.brightness_label = QLabel("Brightness: 0", self)
        self.brightness_slider = QSlider(Qt.Horizontal, self)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.updateBrightnessLabel)
        self.brightness_slider.valueChanged.connect(self.previewAdjustments)

        self.contrast_label = QLabel("Contrast: 0", self)
        self.contrast_slider = QSlider(Qt.Horizontal, self)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.valueChanged.connect(self.updateContrastLabel)
        self.contrast_slider.valueChanged.connect(self.previewAdjustments)

        self.gamma_label = QLabel("Gamma: 1.0", self)
        self.gamma_slider = QSlider(Qt.Horizontal, self)
        self.gamma_slider.setRange(1, 500)
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self.updateGammaLabel)
        self.gamma_slider.valueChanged.connect(self.previewAdjustments)

        self.autobalance_button = QPushButton("Autobalance", self)
        self.autobalance_button.setCheckable(True)
        self.autobalance_button.clicked.connect(self.previewAdjustments)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.applyAdjustments)
        self.buttons.rejected.connect(self.reject_dialog)

        self.layout.addWidget(self.brightness_label)
        self.layout.addWidget(self.brightness_slider)
        self.layout.addWidget(self.contrast_label)
        self.layout.addWidget(self.contrast_slider)
        self.layout.addWidget(self.gamma_label)
        self.layout.addWidget(self.gamma_slider)
        self.layout.addWidget(self.autobalance_button)
        self.layout.addWidget(self.buttons)

    def updateBrightnessLabel(self, value):
        """Update brightness label text."""
        self.brightness_label.setText(f"Brightness: {value / 100:.2f}")

    def updateContrastLabel(self, value):
        """Update contrast label text."""
        self.contrast_label.setText(f"Contrast: {value / 100:.2f}")

    def updateGammaLabel(self, value):
        """Update gamma label text."""
        self.gamma_label.setText(f"Gamma: {value / 100:.2f}")

    def previewAdjustments(self):
        """Preview the adjustments on the image."""
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0
        gamma = self.gamma_slider.value() / 100.0
        autobalance = self.autobalance_button.isChecked()
        self.editor.preview_adjustments(brightness, contrast, gamma, autobalance)

    def applyAdjustments(self):
        """Apply the adjustments and close the dialog."""
        brightness = self.brightness_slider.value() / 100.0
        contrast = self.contrast_slider.value() / 100.0
        gamma = self.gamma_slider.value() / 100.0
        autobalance = self.autobalance_button.isChecked()
        self.editor.apply_adjustments(brightness, contrast, gamma, autobalance)
        self.accept()

    def reject_dialog(self):
        """Cancel the preview and reject the dialog."""
        self.editor.cancel_preview()
        self.reject()

class ResizeDialog(QDialog):
    def __init__(self, current_width, current_height, parent=None):
        """Initialize the resize dialog."""
        super().__init__(parent)
        self.setWindowTitle("Resize Image")
        self.current_width = current_width
        self.current_height = current_height
        self.layout = QGridLayout(self)

        self.width_label = QLabel("Width:", self)
        self.width_edit = QLineEdit(str(current_width), self)
        self.height_label = QLabel("Height:", self)
        self.height_edit = QLineEdit(str(current_height), self)
        self.percent_label = QLabel("Percent:", self)
        self.percent_edit = QLineEdit("100", self)  # 100% by default
        self.aspect_ratio_checkbox = QCheckBox("Keep Aspect Ratio", self)
        self.aspect_ratio_checkbox.setChecked(True)  # Default On

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # Connect signals for dynamic update
        self.width_edit.textEdited.connect(self.updateAspectRatio)
        self.height_edit.textEdited.connect(self.updateAspectRatio)
        self.percent_edit.textEdited.connect(self.updateFromPercent)
        self.aspect_ratio_checkbox.stateChanged.connect(self.updateAspectRatio)

        # Put element in grid
        self.layout.addWidget(self.width_label, 0, 0)
        self.layout.addWidget(self.width_edit, 0, 1)
        self.layout.addWidget(self.height_label, 1, 0)
        self.layout.addWidget(self.height_edit, 1, 1)
        self.layout.addWidget(self.percent_label, 2, 0)
        self.layout.addWidget(self.percent_edit, 2, 1)
        self.layout.addWidget(self.aspect_ratio_checkbox, 3, 0, 1, 2)
        self.layout.addWidget(self.buttons, 4, 0, 1, 2)

        # Init ratio
        self.aspect_ratio = current_width / current_height if current_height != 0 else 1

    def updateAspectRatio(self, *args):
        """Update height or width based on aspect ratio."""
        if not self.aspect_ratio_checkbox.isChecked():
            self.updatePercent()  # Update % if don't keep ratio 
            return

        try:
            sender = self.sender()
            if sender == self.width_edit:
                width = int(self.width_edit.text())
                height = int(width / self.aspect_ratio)
                self.height_edit.setText(str(height))
            elif sender == self.height_edit:
                height = int(self.height_edit.text())
                width = int(height * self.aspect_ratio)
                self.width_edit.setText(str(width))
            elif sender == self.percent_edit:
                # If % changed, lets update width & heigh
                percent = float(self.percent_edit.text()) / 100
                width = int(self.current_width * percent)
                height = int(self.current_height * percent)
                self.width_edit.setText(str(width))
                self.height_edit.setText(str(height))
            self.updatePercent()  # Update % after changed
        except (ValueError, ZeroDivisionError):
            pass

    def updateFromPercent(self, text):
        """Update width and height based on percentage."""
        try:
            percent = float(text) / 100
            width = int(self.current_width * percent)
            height = int(self.current_height * percent)
            self.width_edit.setText(str(width))
            self.height_edit.setText(str(height) if not self.aspect_ratio_checkbox.isChecked() else str(int(width / self.aspect_ratio)))
        except (ValueError, ZeroDivisionError):
            pass

    def updatePercent(self):
        """Update percent field based on current width or height."""
        try:
            width = int(self.width_edit.text())
            percent = (width / self.current_width) * 100 if self.current_width != 0 else 100
            self.percent_edit.setText(f"{percent:.1f}")
        except (ValueError, ZeroDivisionError):
            pass

    def getNewSize(self):
        """Return the new width, height, and aspect ratio flag."""
        width = int(self.width_edit.text())
        height = int(self.height_edit.text())
        keep_aspect = self.aspect_ratio_checkbox.isChecked()
        return width, height, keep_aspect


class RotationDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Precise Rotation")
        self.editor.start_preview()

        main_layout = QVBoxLayout(self)

        # Angle Display
        angle_layout = QHBoxLayout()
        angle_label = QLabel("Angle:", self)
        self.angle_spinbox = QSpinBox(self)
        self.angle_spinbox.setRange(-180, 180)
        self.angle_spinbox.setValue(0)
        self.angle_spinbox.valueChanged.connect(self.update_slider_from_spinbox)
        angle_layout.addWidget(angle_label)
        angle_layout.addWidget(self.angle_spinbox)
        main_layout.addLayout(angle_layout)

        # Slider
        self.angle_slider = QSlider(Qt.Horizontal, self)
        self.angle_slider.setRange(-180, 180)
        self.angle_slider.setValue(0)
        self.angle_slider.valueChanged.connect(self.update_spinbox_from_slider)
        self.angle_slider.sliderMoved.connect(self.live_preview_rotation)
        main_layout.addWidget(self.angle_slider)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject_dialog)
        main_layout.addWidget(self.buttons)

        self.setLayout(main_layout)

    def update_slider_from_spinbox(self, value):
        self.angle_slider.setValue(value)

    def update_spinbox_from_slider(self, value):
        self.angle_spinbox.setValue(value)

    def live_preview_rotation(self, angle):
        self.editor.preview_rotation(angle)

    def get_angle(self):
        return self.angle_spinbox.value()

    def reject_dialog(self):
        self.editor.cancel_preview()
        self.reject()
