import os
import sys
import logging

from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog, QDialog, QMenu, QMdiArea, QMessageBox,
    QApplication, QStatusBar, QGraphicsView, QCheckBox, QInputDialog,
    QActionGroup
)
from PyQt5.QtGui import QIcon, QKeySequence, QColor, QImage, QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PIL import Image as PILImage, ImageOps
from editor import ImageEditor, EditorContainer
from widgets import CustomMdiSubWindow, NewImageDialog, AdjustmentsDialog, ResizeDialog, RotationDialog
from commands import CropCommand
from utils import load_config, save_config, get_recent_files, add_recent_file, resource_path
import theme

logger = logging.getLogger("photoeditor.main_window")

try:
    from win32com.client import Dispatch
    import pythoncom
    from io import BytesIO
    WIA_AVAILABLE = True
except ImportError:
    WIA_AVAILABLE = False


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.setWindowTitle("Simple Photo Editor")
        self.setGeometry(100, 100, 1000, 800)

        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)

        self.statusBar().showMessage("Ready")

        # --- Централизованное управление конфигурацией ---
        self.config = config

        self.createActions()
        self.createMenus()
        self.createToolbars()

        self.clipboard = QApplication.clipboard()

        # Загружаем последние настройки изображения из self.config
        if self.config.has_section('LastImageSettings'):
            self.last_image_settings = {
                'width': self.config.get('LastImageSettings', 'width', fallback='800'),
                'height': self.config.get('LastImageSettings', 'height', fallback='600'),
                'dpi': self.config.getint('LastImageSettings', 'dpi', fallback=150),
                'units': self.config.get('LastImageSettings', 'units', fallback='Pixels')
            }
        else:
            self.last_image_settings = {
                'width': '800',
                'height': '600',
                'dpi': 150,
                'units': 'Pixels'
            }

        self.update_recent_files_menu()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                # Check if it's an image file
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff']:
                    self.openFile(file_path)

    def closeEvent(self, event):
        """Обработка закрытия главного окна."""
        try:
            # --- Единое сохранение всех настроек ---
            # Обновляем последние настройки в self.config перед сохранением
            if not self.config.has_section('General'):
                self.config.add_section('General')
            self.config.set('General', 'window_width', str(self.width()))
            self.config.set('General', 'window_height', str(self.height()))

            # Последний открытый файл (открывается при следующем старте)
            active = self.mdi_area.activeSubWindow()
            if active is not None and getattr(active, 'file_path', None):
                self.config.set('General', 'last_opened_file', active.file_path)

            # Состояние линеек активного редактора
            if not self.config.has_section('Editor'):
                self.config.add_section('Editor')
            if active is not None:
                self.config.set('Editor', 'show_rulers',
                                'true' if active.editor_container.editor.rulers_visible else 'false')

            if not self.config.has_section('LastImageSettings'):
                self.config.add_section('LastImageSettings')
            self.config.set('LastImageSettings', 'width', str(self.last_image_settings['width']))
            self.config.set('LastImageSettings', 'height', str(self.last_image_settings['height']))
            self.config.set('LastImageSettings', 'dpi', str(self.last_image_settings['dpi']))
            self.config.set('LastImageSettings', 'units', self.last_image_settings['units'])

            # Сохраняем все изменения в файл
            save_config(self.config)
        except Exception as e:
            logger.exception("Error saving config on close: %s", e)

        # Проверяем несохраненные изменения в открытых окнах
        for sub_window in self.mdi_area.subWindowList():
            if sub_window.editor_container.editor.is_modified:
                reply = self.confirmSave(sub_window.windowTitle())
                if reply == "save":
                    if not self.saveFile(sub_window):
                        event.ignore()
                        return
                elif reply == "cancel":
                    event.ignore()
                    return
        event.accept()

    def confirmSave(self, title):
        """Show a dialog to confirm saving changes and return the user's choice."""
        if not title:
            title = "Untitled"
        reply = QMessageBox.question(
            self,
            "Save Changes?",
            f"The image '{title}' has unsaved changes. Do you want to save them?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save
        )
        if reply == QMessageBox.Save:
            return "save"
        elif reply == QMessageBox.Discard:
            return "discard"
        else:
            return "cancel"


    def createActions(self):
        """Create actions for menus and toolbars"""
        # File actions
        self.new_act = QAction(self.tr("&New"), self, shortcut="Ctrl+N", triggered=self.newFile)
        self.new_act.setIcon(theme.icon("new"))
        self.new_act.setObjectName("act_icon_new")
        self.new_act.setToolTip(self.tr("New Image (Ctrl+N)"))

        self.open_act = QAction(self.tr("&Open"), self, shortcut="Ctrl+O", triggered=lambda checked: self.openFile())
        self.open_act.setIcon(theme.icon("open"))
        self.open_act.setObjectName("act_icon_open")
        self.open_act.setToolTip(self.tr("Open File (Ctrl+O)"))

        self.save_act = QAction(self.tr("&Save"), self, shortcut="Ctrl+S", triggered=lambda checked: self.saveFile())
        self.save_act.setIcon(theme.icon("save"))
        self.save_act.setObjectName("act_icon_save")
        self.save_act.setToolTip(self.tr("Save File (Ctrl+S)"))

        self.save_as_act = QAction(self.tr("Save &As..."), self, shortcut="Ctrl+Shift+S", triggered=self.saveFileAs)
        self.save_as_act.setIcon(theme.icon("save_as"))  # Если нет иконки, можно использовать save.png
        self.save_as_act.setObjectName("act_icon_save_as")
        self.save_as_act.setToolTip(self.tr("Save As (Ctrl+Shift+S)"))

        self.print_act = QAction(self.tr("&Print"), self, shortcut="Ctrl+P", triggered=self.printFile)
        self.print_act.setIcon(theme.icon("print"))
        self.print_act.setObjectName("act_icon_print")
        self.print_act.setToolTip(self.tr("Print (Ctrl+P)"))

        self.scan_act = QAction(self.tr("S&can"), self, shortcut="Ctrl+Shift+N", triggered=self.scanImage)
        self.scan_act.setIcon(theme.icon("scan"))  # Если нет, подбери подходящую
        self.scan_act.setObjectName("act_icon_scan")
        self.scan_act.setToolTip(self.tr("Scan (Ctrl+Shift+N)"))

        self.exit_act = QAction(self.tr("E&xit"), self, shortcut="Ctrl+Q", triggered=self.close)
        self.exit_act.setIcon(theme.icon("exit"))  # Если нет, можно использовать close.png
        self.exit_act.setObjectName("act_icon_exit")
        self.exit_act.setToolTip(self.tr("Exit (Ctrl+Q)"))

        # Edit actions
        self.undo_act = QAction(self.tr("&Undo"), self, shortcut="Ctrl+Z", triggered=self.undo)
        self.undo_act.setIcon(theme.icon("undo"))
        self.undo_act.setObjectName("act_icon_undo")
        self.undo_act.setToolTip(self.tr("Undo (Ctrl+Z)"))

        self.redo_act = QAction(self.tr("&Redo"), self, shortcut="Ctrl+Y", triggered=self.redo)  # Новое действие
        self.redo_act.setIcon(theme.icon("redo"))  # Укажи путь к иконке redo.png
        self.redo_act.setObjectName("act_icon_redo")
        self.redo_act.setToolTip(self.tr("Redo (Ctrl+Y)"))

        self.cut_act = QAction(self.tr("Cu&t"), self, shortcut="Ctrl+X", triggered=self.cut)
        self.cut_act.setIcon(theme.icon("cut"))
        self.cut_act.setObjectName("act_icon_cut")
        self.cut_act.setToolTip(self.tr("Cut (Ctrl+X)"))

        self.copy_act = QAction(self.tr("&Copy"), self, shortcut="Ctrl+C", triggered=self.copy)
        self.copy_act.setIcon(theme.icon("copy"))
        self.copy_act.setObjectName("act_icon_copy")
        self.copy_act.setToolTip(self.tr("Copy (Ctrl+C)"))

        self.paste_act = QAction(self.tr("&Paste"), self, shortcut="Ctrl+V", triggered=self.paste)
        self.paste_act.setIcon(theme.icon("paste"))
        self.paste_act.setObjectName("act_icon_paste")
        self.paste_act.setToolTip(self.tr("Paste (Ctrl+V)"))

        self.crop_act = QAction(self.tr("C&rop"), self, shortcut="Ctrl+R", triggered=self.cropImage)
        self.crop_act.setIcon(theme.icon("crop"))
        self.crop_act.setObjectName("act_icon_crop")
        self.crop_act.setToolTip(self.tr("Crop to Selection (Ctrl+R)"))

        # Новое действие: Resize
        self.resizeAct = QAction(self.tr("&Resize..."), self)
        self.resizeAct.setIcon(theme.icon("resize"))
        self.resizeAct.setObjectName("act_icon_resize")
        self.resizeAct.setStatusTip(self.tr("Resize the image"))
        self.resizeAct.triggered.connect(self.resizeImage)

        self.select_all_act = QAction(self.tr("Select &All"), self, shortcut="Ctrl+A", triggered=self.selectAll)
        self.select_all_act.setIcon(theme.icon("select_all"))
        self.select_all_act.setObjectName("act_icon_select_all")
        self.select_all_act.setToolTip(self.tr("Select All (Ctrl+A)"))

        # View actions
        self.zoom_in_act = QAction(self.tr("Zoom &In"), self, shortcut="Ctrl++", triggered=self.zoomIn)
        self.zoom_in_act.setIcon(theme.icon("zoom_in"))
        self.zoom_in_act.setObjectName("act_icon_zoom_in")
        self.zoom_in_act.setToolTip(self.tr("Zoom In (Ctrl++)"))

        self.zoom_out_act = QAction(self.tr("Zoom &Out"), self, shortcut="Ctrl+-", triggered=self.zoomOut)
        self.zoom_out_act.setIcon(theme.icon("zoom_out"))
        self.zoom_out_act.setObjectName("act_icon_zoom_out")
        self.zoom_out_act.setToolTip(self.tr("Zoom Out (Ctrl+-)"))

        self.fit_screen_act = QAction(self.tr("&Fit to Screen"), self, shortcut="Ctrl+0", triggered=self.fitToScreen)
        self.fit_screen_act.setIcon(theme.icon("fit_screen"))
        self.fit_screen_act.setObjectName("act_icon_fit_screen")
        self.fit_screen_act.setToolTip(self.tr("Fit to Screen (Ctrl+0)"))

        self.actual_size_act = QAction(self.tr("&Actual Size"), self, shortcut="Ctrl+1", triggered=self.actualSize)
        self.actual_size_act.setIcon(theme.icon("actual_size"))  # Если нет, подбери подходящую
        self.actual_size_act.setObjectName("act_icon_actual_size")
        self.actual_size_act.setToolTip(self.tr("Actual Size (Ctrl+1)"))

        self.toggle_rulers_act = QAction(self.tr("Show &Rulers"), self)
        self.toggle_rulers_act.setIcon(theme.icon("ruler"))
        self.toggle_rulers_act.setObjectName("act_icon_ruler")
        self.toggle_rulers_act.setToolTip(self.tr("Show Rulers"))
        self.toggle_rulers_act.triggered.connect(self.toggleRulers)  # Подключаем сигнал triggered

        # Image actions
        self.rotate_90_cw_act = QAction(self.tr("Rotate 90° &CW"), self, triggered=lambda: self.rotateImage(90))
        self.rotate_90_cw_act.setIcon(theme.icon("rotate_cw"))
        self.rotate_90_cw_act.setObjectName("act_icon_rotate_cw")
        self.rotate_90_cw_act.setToolTip(self.tr("Rotate 90° Clockwise"))

        self.rotate_90_ccw_act = QAction(self.tr("Rotate 90° CC&W"), self, triggered=lambda: self.rotateImage(-90))
        self.rotate_90_ccw_act.setIcon(theme.icon("rotate_ccw"))
        self.rotate_90_ccw_act.setObjectName("act_icon_rotate_ccw")
        self.rotate_90_ccw_act.setToolTip(self.tr("Rotate 90° Counter-Clockwise"))

        self.rotate_180_act = QAction(self.tr("Rotate &180°"), self, triggered=lambda: self.rotateImage(180))
        self.rotate_180_act.setIcon(theme.icon("rotate_cw"))  # Если нет, можно использовать rotate_cw.png
        self.rotate_180_act.setObjectName("act_icon_rotate_cw")
        self.rotate_180_act.setToolTip(self.tr("Rotate 180°"))

        self.precise_rotate_act = QAction(self.tr("Rotate..."), self, triggered=self.openPreciseRotationDialog)
        self.precise_rotate_act.setIcon(theme.icon("rotate_cw"))
        self.precise_rotate_act.setObjectName("act_icon_rotate_cw")
        self.precise_rotate_act.setToolTip(self.tr("Precise Rotation"))

        self.flip_horizontal_act = QAction(self.tr("Flip &Horizontal"), self, triggered=lambda: self.flipImage(True))
        self.flip_horizontal_act.setIcon(theme.icon("flip"))
        self.flip_horizontal_act.setObjectName("act_icon_flip")
        self.flip_horizontal_act.setToolTip(self.tr("Flip Horizontal"))

        self.flip_vertical_act = QAction(self.tr("Flip &Vertical"), self, triggered=lambda: self.flipImage(False))
        self.flip_vertical_act.setIcon(theme.icon("flip"))
        self.flip_vertical_act.setObjectName("act_icon_flip")
        self.flip_vertical_act.setToolTip(self.tr("Flip Vertical"))

        self.grayscale_act = QAction(self.tr("Convert to &Grayscale"), self, triggered=self.convertToGrayscale)
        self.grayscale_act.setIcon(theme.icon("grayscale"))
        self.grayscale_act.setObjectName("act_icon_grayscale")
        self.grayscale_act.setToolTip(self.tr("Convert to Grayscale"))

        self.adjustments_act = QAction(self.tr("&Adjustments..."), self, triggered=self.showAdjustmentsDialog)
        self.adjustments_act.setIcon(theme.icon("tune"))
        self.adjustments_act.setObjectName("act_icon_tune")
        self.adjustments_act.setToolTip(self.tr("Adjustments..."))

        # Window actions
        self.tile_act = QAction(self.tr("&Tile"), self, triggered=self.mdi_area.tileSubWindows)
        self.tile_act.setIcon(theme.icon("tile"))  # Если нет, подбери подходящую
        self.tile_act.setObjectName("act_icon_tile")
        self.tile_act.setToolTip(self.tr("Tile Windows"))

        self.cascade_act = QAction(self.tr("&Cascade"), self, triggered=self.mdi_area.cascadeSubWindows)
        self.cascade_act.setIcon(theme.icon("cascade"))  # Если нет, подбери подходящую
        self.cascade_act.setObjectName("act_icon_cascade")
        self.cascade_act.setToolTip(self.tr("Cascade Windows"))

        self.next_act = QAction(self.tr("&Next"), self, shortcut="Ctrl+Tab", triggered=self.mdi_area.activateNextSubWindow)
        self.next_act.setIcon(theme.icon("next"))  # Если нет, подбери подходящую
        self.next_act.setObjectName("act_icon_next")
        self.next_act.setToolTip(self.tr("Next Window (Ctrl+Tab)"))

        self.previous_act = QAction(self.tr("&Previous"), self, shortcut="Ctrl+Shift+Tab", triggered=self.mdi_area.activatePreviousSubWindow)
        self.previous_act.setIcon(theme.icon("previous"))  # Если нет, подбери подходящую
        self.previous_act.setObjectName("act_icon_previous")
        self.previous_act.setToolTip(self.tr("Previous Window (Ctrl+Shift+Tab)"))

        # Tools action
        self.selection_tool_act = QAction(self.tr("Selection Tool"), self, triggered=self.activateSelectionTool)
        self.selection_tool_act.setIcon(theme.icon("select"))
        self.selection_tool_act.setObjectName("act_icon_select")
        self.selection_tool_act.setToolTip(self.tr("Selection Tool"))


        # Help actions
        self.about_act = QAction(self.tr("&About"), self, triggered=self.about)
        self.about_act.setIcon(theme.icon("about"))
        self.about_act.setObjectName("act_icon_about")
        self.about_act.setToolTip(self.tr("About"))

    def createMenus(self):
        """Create menu bar"""
        # File menu
        file_menu = self.menuBar().addMenu(self.tr("&File"))
        file_menu.addAction(self.new_act)
        file_menu.addAction(self.open_act)
        # Добавляем подменю Recent Files
        self.recent_files_menu = QMenu("Recent Files", self)
        file_menu.addMenu(self.recent_files_menu)
        file_menu.addAction(self.save_act)
        file_menu.addAction(self.save_as_act)
        file_menu.addSeparator()
        file_menu.addAction(self.scan_act)
        file_menu.addAction(self.print_act)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_act)


        # Edit menu
        edit_menu = self.menuBar().addMenu(self.tr("&Edit"))
        edit_menu.addAction(self.undo_act)
        edit_menu.addAction(self.redo_act)  # Добавляем Redo
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_act)
        edit_menu.addAction(self.copy_act)
        edit_menu.addAction(self.paste_act)
        edit_menu.addAction(self.crop_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.select_all_act)

        # View menu
        view_menu = self.menuBar().addMenu(self.tr("&View"))
        view_menu.addAction(self.zoom_in_act)
        view_menu.addAction(self.zoom_out_act)
        view_menu.addAction(self.fit_screen_act)
        view_menu.addAction(self.actual_size_act)
        view_menu.addSeparator()
        view_menu.addAction(self.toggle_rulers_act)

        # Image menu
        image_menu = self.menuBar().addMenu(self.tr("&Image"))
        rotate_menu = image_menu.addMenu(self.tr("&Rotate"))
        rotate_menu.addAction(self.rotate_90_cw_act)
        rotate_menu.addAction(self.rotate_90_ccw_act)
        rotate_menu.addAction(self.rotate_180_act)
        rotate_menu.addSeparator() # Optional separator
        rotate_menu.addAction(self.precise_rotate_act)
        image_menu.addAction(self.crop_act)
        image_menu.addAction(self.resizeAct)


        flip_menu = image_menu.addMenu(self.tr("&Flip"))
        flip_menu.addAction(self.flip_horizontal_act)
        flip_menu.addAction(self.flip_vertical_act)

        image_menu.addSeparator()
        image_menu.addAction(self.grayscale_act)
        image_menu.addAction(self.adjustments_act)

        # Window menu
        window_menu = self.menuBar().addMenu(self.tr("&Window"))
        window_menu.addAction(self.tile_act)
        window_menu.addAction(self.cascade_act)
        window_menu.addSeparator()
        window_menu.addAction(self.next_act)
        window_menu.addAction(self.previous_act)

        # Settings menu: переключатель темы
        settings_menu = self.menuBar().addMenu(self.tr("&Settings"))
        theme_menu = settings_menu.addMenu(self.tr("&Theme"))
        self._theme_group = QActionGroup(self)
        for theme_name, label in (("system", "System"), ("light", "Light"), ("dark", "Dark")):
            act = QAction(label, self, checkable=True)
            act.setObjectName(f"theme_act_{theme_name}")
            act.triggered.connect(lambda checked, name=theme_name: self.switchTheme(name))
            self._theme_group.addAction(act)
            theme_menu.addAction(act)
        self.update_theme_menu_actions()

        # Help menu
        help_menu = self.menuBar().addMenu(self.tr("&Help"))
        help_menu.addAction(self.about_act)

    def switchTheme(self, theme_name):
        """Переключить тему оформления (палитра + иконки) и сохранить выбор в конфиг."""
        theme.apply_theme(QApplication.instance(), theme_name)
        if not self.config.has_section('General'):
            self.config.add_section('General')
        self.config.set('General', 'theme', theme_name)
        save_config(self.config)
        self.update_theme_menu_actions()
        self.statusBar().showMessage(f"Theme: {theme_name}", 2000)

    def update_theme_menu_actions(self):
        """Отметить галочкой пункт темы, соответствующий конфигу."""
        current = 'light'
        try:
            current = self.config['General'].get('theme', 'light') if 'General' in self.config else 'light'
        except Exception:
            pass
        for act in self._theme_group.actions():
            act.setChecked(act.objectName() == f"theme_act_{current}")

    def update_recent_files_menu(self):
        """Обновить подменю Recent Files."""
        self.recent_files_menu.clear()
        recent_files = get_recent_files(self.config)
        if not recent_files:
            no_files_action = QAction(self.tr("No recent files"), self)
            no_files_action.setEnabled(False)
            self.recent_files_menu.addAction(no_files_action)
        else:
            for file_path in recent_files:
                file_action = QAction(os.path.basename(file_path), self)
                file_action.setData(file_path)  # Сохраняем полный путь в данных действия
                file_action.triggered.connect(lambda checked, path=file_path: self.openFile(path))
                self.recent_files_menu.addAction(file_action)


    def createToolbars(self):
        """Create toolbars with icons and tooltips"""
        style = self.style()

        # File toolbar
        file_toolbar = self.addToolBar("File")
        file_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        file_toolbar.addAction(self.new_act)
        file_toolbar.addAction(self.open_act)
        file_toolbar.addAction(self.save_act)
        file_toolbar.addAction(self.print_act)

        # Edit toolbar
        edit_toolbar = self.addToolBar("Edit")
        edit_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        edit_toolbar.addAction(self.undo_act)
        edit_toolbar.addAction(self.redo_act)  # Добавляем Redo
        edit_toolbar.addAction(self.cut_act)
        edit_toolbar.addAction(self.copy_act)
        edit_toolbar.addAction(self.paste_act)

        # View toolbar
        view_toolbar = self.addToolBar("View")
        view_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        view_toolbar.addAction(self.zoom_in_act)
        view_toolbar.addAction(self.zoom_out_act)
        view_toolbar.addAction(self.fit_screen_act)

        # Image toolbar
        image_toolbar = self.addToolBar("Image")
        image_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        image_toolbar.addAction(self.rotate_90_cw_act)
        image_toolbar.addAction(self.rotate_90_ccw_act)
        image_toolbar.addAction(self.flip_horizontal_act)
        image_toolbar.addAction(self.grayscale_act)
        image_toolbar.addAction(self.adjustments_act)
        image_toolbar.addAction(self.crop_act)  # Добавляем Crop
        image_toolbar.addAction(self.resizeAct)

        # Tools toolbar
        tool_toolbar = self.addToolBar("Tools")
        tool_toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        tool_toolbar.addAction(self.selection_tool_act)

    def activateSelectionTool(self):
        editor = self.currentEditor()
        if editor:
            editor.scene.current_tool = "selection"
            self.statusBar().showMessage("Selection tool active: Click and drag to select an area")
            editor.setDragMode(QGraphicsView.NoDrag)


    def currentEditor(self):
        """Get the current active editor"""
        active_window = self.mdi_area.activeSubWindow()
        if active_window:
            return active_window.editor_container.editor  # Получаем ImageEditor из EditorContainer
        return None

    def newFile(self):
        dialog = NewImageDialog(
            self,
            width=self.last_image_settings['width'],
            height=self.last_image_settings['height'],
            dpi=self.last_image_settings['dpi'],
            units=self.last_image_settings['units']
        )

        if dialog.exec_() == QDialog.Accepted:
            pixel_width, pixel_height, dpi, bg_color, color_depth, raw_width, raw_height, units = dialog.getImageParameters()

            # Обновляем последние использованные настройки в памяти
            self.last_image_settings = {
                'width': raw_width,
                'height': raw_height,
                'dpi': dpi,
                'units': units
            }

            # Determine image format from color depth
            if color_depth == "24-bit color":
                image_format = QImage.Format_RGB32
            elif color_depth == "8-bit palette":
                image_format = QImage.Format_Indexed8
            elif color_depth == "8-bit grayscale":
                image_format = QImage.Format_Grayscale8
            elif color_depth == "1-bit monochrome":
                image_format = QImage.Format_Mono
            else:
                image_format = QImage.Format_RGB32  # Default

            new_image = QImage(pixel_width, pixel_height, image_format)
            new_image.setDotsPerMeterX(int(dpi * 39.37))
            new_image.setDotsPerMeterY(int(dpi * 39.37))

            # Handle background color based on format
            if image_format == QImage.Format_Indexed8:
                color_table = [QColor(Qt.white).rgb(), QColor(Qt.black).rgb()]
                if bg_color:
                    color_table[0] = bg_color.rgb()
                new_image.setColorTable(color_table)
                new_image.fill(0)
            elif image_format == QImage.Format_Mono:
                new_image.setColor(0, QColor(Qt.white).rgb())
                new_image.setColor(1, QColor(Qt.black).rgb())
                if bg_color.lightness() < 128:
                    new_image.fill(1)
                else:
                    new_image.fill(0)
            else:
                new_image.fill(bg_color if bg_color is not None else Qt.white)

            sub_window = CustomMdiSubWindow(self)
            sub_window.editor_container.editor.setImage(new_image)
            sub_window.setWindowTitle(f"Untitled ({pixel_width}x{pixel_height})")
            sub_window.file_path = None
            self.mdi_area.addSubWindow(sub_window)
            sub_window.show()
            sub_window.editor_container.editor.fitInViewWithRulers()



    def openFile(self, file_name=None):
        """Открыть файл. Если file_name указан, открыть его напрямую, иначе показать диалог."""
        logger.debug("openFile called, file_name=%r", file_name)
        if file_name is None:
            logger.debug("file_name is None, showing open dialog")
            try:
                file_name, _ = QFileDialog.getOpenFileName(
                    self,
                    "Open Image",
                    "",
                    "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
                )
                logger.debug("File dialog returned: %r", file_name)
            except Exception as e:
                logger.exception("Error opening file dialog: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to open file dialog: {e}")
                return
        if file_name:
            if not os.path.exists(file_name):
                logger.warning("File does not exist: %s", file_name)
                QMessageBox.warning(self, "Error", f"File does not exist: {file_name}")
                return
            logger.debug("Loading image: %s", file_name)
            image = self.load_image_with_exif(file_name)
            if image is None or image.isNull():
                logger.warning("Failed to load image (isNull): %s", file_name)
                QMessageBox.warning(self, "Error", "Failed to open image.")
                return
            sub_window = CustomMdiSubWindow(self)
            sub_window.editor_container.editor.setImage(image)
            sub_window.base_title = os.path.basename(file_name)
            sub_window.setWindowTitle(f"{os.path.basename(file_name)} ({image.width()}x{image.height()}) @ 100%")
            sub_window.file_path = file_name  # Сохраняем путь к файлу
            self.mdi_area.addSubWindow(sub_window)
            sub_window.show()

            # Корректируем позицию окна
            viewport = self.mdi_area.viewport()
            viewport_rect = viewport.rect()
            sub_window.move(viewport_rect.topLeft())  # Перемещаем в верхний левый угол

            QTimer.singleShot(100, sub_window.editor_container.editor.fitInViewWithRulers)
            self.statusBar().showMessage(f"Opened {file_name}", 2000)

            # Обновляем список недавних файлов в self.config
            add_recent_file(self.config, file_name)
            # Сохраняем конфиг сразу — иначе краш приложения теряет MRU-список
            save_config(self.config)
            self.update_recent_files_menu()
        else:
            logger.debug("No file selected, openFile aborted")

    def load_image_with_exif(self, file_name):
        """Загрузить QImage с учётом EXIF-ориентации (фото с телефонов не открываются боком).

        Возвращает None, если файл не удалось открыть.
        """
        try:
            with PILImage.open(file_name) as pil_img:
                transposed = ImageOps.exif_transpose(pil_img)
                if transposed is None:  # старые версии Pillow могли вернуть None
                    transposed = pil_img.copy()
                if transposed.mode != "RGBA":
                    transposed = transposed.convert("RGBA")
                data = transposed.tobytes("raw", "RGBA")
                # У PIL Image width/height — свойства, а не методы
                image = QImage(data, transposed.width, transposed.height,
                               transposed.width * 4, QImage.Format_RGBA8888)
                return image.copy()  # отсоединяемся от буфера Python
        except Exception as e:
            logger.warning("EXIF-aware load failed for %s (%s), falling back to QImage", file_name, e)
            image = QImage(file_name)
            return image if not image.isNull() else None



    def loadFile(self, file_path):
        sub_window = CustomMdiSubWindow(self)
        if sub_window.editor_container.editor.openImage(file_path):  # Используем openImage через EditorContainer
            self.mdi_area.addSubWindow(sub_window)
            image_size = sub_window.editor_container.editor.getCurrentImage().size()
            width = image_size.width()
            height = image_size.height()
            sub_window.setWindowTitle(f"{os.path.basename(file_path)} ({width}x{height})")
            sub_window.file_path = file_path
            sub_window.show()
            self.statusBar().showMessage(f"Opened {file_path}", 2000)
            return True
        return False

    def saveFile(self, sub_window=None):
        """Save the current image to a file."""
        if sub_window is None:
            sub_window = self.mdi_area.activeSubWindow()
        if not sub_window:
            self.statusBar().showMessage("No active image to save", 2000)
            return False
        editor = sub_window.editor_container.editor
        if not editor.current_image:
            self.statusBar().showMessage("No image to save", 2000)
            return False

        # Проверяем, есть ли уже путь к файлу
        file_name = getattr(sub_window, 'file_path', None)
        if not file_name:  # Если пути нет, открываем диалог
            file_name, selected_filter = QFileDialog.getSaveFileName(
                self,
                "Save Image",
                "",
                "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;BMP Files (*.bmp);;GIF Files (*.gif);;TIFF Files (*.tiff);;All Files (*)",
                "PNG Files (*.png)"  # Фильтр по умолчанию
            )
        logger.debug("Saving to: %s", file_name)
        if file_name:
            try:
                success = editor.current_image.save(file_name)
                if not success:
                    raise Exception("QImage.save returned False")
                editor.is_modified = False
                sub_window.file_path = file_name  # Сохраняем путь в подокне
                sub_window.setWindowTitle(f"{os.path.basename(file_name)} ({editor.current_image.width()}x{editor.current_image.height()})")
                self.statusBar().showMessage(f"Saved to {file_name}", 2000)
                return True
            except Exception as e:
                logger.exception("Failed to save file: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")
                return False
        return False

    def saveFileAs(self, sub_window=None):
        if not sub_window:
            sub_window = self.mdi_area.activeSubWindow()
        if not sub_window:
            return False

        editor = sub_window.editor_container.editor
        if not editor:
            return False

        editor.applyAllPastedItems()

        file_path, selected_filter = QFileDialog.getSaveFileName(self, "Save Image", "",
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;BMP Files (*.bmp);;TIFF Files (*.tif *.tiff);;All Files (*)",
            "PNG Files (*.png)"  # Фильтр по умолчанию
        )

        if file_path:
            # Проверяем, есть ли расширение в имени файла
            if not os.path.splitext(file_path)[1]:  # Если расширения нет
                file_path += ".png"  # Добавляем .png по умолчанию
                logger.debug("Added .png extension: %s", file_path)

            # Для форматов с потерями спрашиваем качество (1–100)
            quality = -1  # -1 — качество по умолчанию Qt
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.jpg', '.jpeg', '.webp'):
                quality, ok = QInputDialog.getInt(
                    self, "Save Image", "Quality (1-100):", 90, 1, 100
                )
                if not ok:
                    logger.debug("Quality dialog cancelled, save aborted: %s", file_path)
                    return False

            if self.saveImageToFile(editor, file_path, quality):
                image_size = editor.getCurrentImage().size()
                width = image_size.width()
                height = image_size.height()
                sub_window.setWindowTitle(f"{os.path.basename(file_path)} ({width}x{height})")
                sub_window.file_path = file_path
                editor.is_modified = False
                return True
            else:
                QMessageBox.critical(self, "Error", f"Failed to save file: {file_path}\nEnsure the path is valid and you have write permissions.")
                return False
        return False

    def toggleRulers(self):
        logger.debug("toggleRulers called")
        sub_window = self.mdi_area.activeSubWindow()
        if sub_window:
            # Переключаем состояние линеек
            current_state = sub_window.editor_container.editor.rulers_visible
            sub_window.editor_container.toggleRulers(not current_state)


    def saveImageToFile(self, editor, file_path, quality=-1):
        """Save the image to a file. quality — качество для JPEG/WebP (-1: значение Qt по умолчанию)."""
        image = editor.getCurrentImage()
        if image:
            try:
                success = image.save(file_path, None, quality)
                if success:
                    return True
                else:
                    logger.warning("Failed to save image to %s: QImage.save returned False", file_path)
                    return False
            except Exception as e:
                logger.exception("Failed to save image to %s: %s", file_path, e)
                return False
        return False

    def printFile(self):
        """Print the current image"""
        editor = self.currentEditor()
        if not editor:
            return

        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)

        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            rect = painter.viewport()
            size = editor.getCurrentImage().size()
            size.scale(rect.size(), Qt.KeepAspectRatio)
            painter.setViewport(rect.x(), rect.y(), size.width(), size.height())
            painter.setWindow(editor.getCurrentImage().rect())
            painter.drawImage(0, 0, editor.getCurrentImage())
            painter.end()

    def scanImage(self):
        """Scan an image using WIA with DPI selection"""
        if not WIA_AVAILABLE:
            if sys.platform.startswith("win"):
                QMessageBox.warning(
                    self, "Scanning Not Available",
                    "WIA components are not installed.\n\n"
                    "Scanning requires the 'pywin32' package (win32com/pythoncom).\n"
                    "Install it with:  pip install pywin32\n\n"
                    "If you are using the installed .exe version, reinstall it\n"
                    "with a build that includes WIA support.")
            else:
                QMessageBox.warning(
                    self, "Scanning Not Available",
                    "WIA components are not installed.\n\n"
                    "Scanning is only available on Windows (via WIA).")
            return

        from win32com.client import Dispatch
        import pythoncom
        from io import BytesIO

        try:
            pythoncom.CoInitialize()  # Инициализация COM
            wia = Dispatch("WIA.CommonDialog")
            dev = wia.ShowSelectDevice()  # Выбор устройства
            if not dev:
                QMessageBox.warning(self, "Warning", "No scanner found.")
                return

            #Диалог для выбора DPI
            dpi, ok = QInputDialog.getInt(self, "Scan Settings", "Enter DPI (e.g., 150, 300, 600):",
                                           150, 75, 1200, 75)  # Мин: 75, Макс: 1200, Шаг: 75
            if not ok:
                return  # Пользователь отменил

            item = dev.Items[1]  # Первый элемент для сканирования

            # Настройка разрешения
            try:
                item.Properties("6147").Value = dpi  # Horizontal Resolution
                item.Properties("6148").Value = dpi  # Vertical Resolution
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"DPI {dpi} not supported by scanner: {str(e)}")
                return

            # Настройка цветового режима (опционально)
            item.Properties("6146").Value = 1  # Цветной режим

            # Выполняем сканирование
            image_file = item.Transfer() # WIA.ImageFile object
            binary_data = image_file.FileData.BinaryData # This is a bytes object

            # Create QImage from binary data
            qimage = QImage()
            qimage.loadFromData(binary_data)


            if qimage.isNull():
                QMessageBox.critical(self, "Error", "Failed to load scanned image data.")
                return

            # Создаем новый редактор
            sub_window = CustomMdiSubWindow(self) # Pass self as main_window
            sub_window.editor_container.editor.setImage(qimage)
            self.mdi_area.addSubWindow(sub_window)
            sub_window.setWindowTitle(f"Scanned Image ({dpi} DPI)")
            sub_window.file_path = None
            sub_window.show()
            # Ensure the image is fitted after showing
            QTimer.singleShot(100, sub_window.editor_container.editor.fitInViewWithRulers)


        except Exception as e:
            QMessageBox.critical(self, "Error", f"Scanning failed: {str(e)}")
        finally:
            pythoncom.CoUninitialize()  # Очистка COM

    def openPreciseRotationDialog(self):
        editor = self.currentEditor()
        if not editor or not editor.getCurrentImage():
            self.statusBar().showMessage("No active image to rotate.", 2000)
            return

        dialog = RotationDialog(editor, self) # Pass editor and parent
        if dialog.exec_() == QDialog.Accepted:
            angle = dialog.get_angle()
            editor.apply_rotation(angle) # Use the new method in ImageEditor
            self.statusBar().showMessage(f"Image rotated by {angle} degrees.", 2000)
        else:
            self.statusBar().showMessage("Rotation cancelled.", 2000)

    def undo(self):
        """Undo the last operation"""
        editor = self.currentEditor()
        if editor:
            editor.undo()
            self.statusBar().showMessage("Undo performed", 2000)

    def redo(self):
        """Redo the last undone operation"""
        editor = self.currentEditor()
        if editor:
            editor.redo()
            self.statusBar().showMessage("Redo performed", 2000)

    def cut(self):
            """Cut the selected area"""
            editor = self.currentEditor()
            if editor:
                editor.cut()  # Перенаправляем вызов на ImageEditor.cut
    def copy(self):
            """Copy the selected area to clipboard"""
            editor = self.currentEditor()
            if not editor:
                return
            selection_rect = editor.scene.selection_rect
            if not selection_rect or not selection_rect.rect().isValid() or selection_rect.rect().isEmpty():
                self.statusBar().showMessage("No valid selection to copy", 2000)
                return
            image = editor.getCurrentImage().copy(selection_rect.rect().toRect())
            QApplication.clipboard().setImage(image)
            self.statusBar().showMessage("Selection copied to clipboard", 2000)


    def paste(self):
    	"""Paste from clipboard"""
    	editor = self.currentEditor()
    	if not editor:
        	return
    	editor.paste()  # Delegate to ImageEditor

    def selectAll(self):
        """Select the entire image"""
        editor = self.currentEditor()
        if not editor:
            return

        image = editor.getCurrentImage()
        if image:
            if editor.scene.selection_rect:
                editor.scene.removeItem(editor.scene.selection_rect)

            # Create selection rectangle for the entire image
            rect = QRectF(0, 0, image.width(), image.height())
            editor.scene.selection_rect = editor.scene.addRect(rect, QPen(Qt.DashLine))
            editor.scene.selectionChanged.emit(rect)

    def cropImage(self):
        editor = self.currentEditor()
        if not editor:
            self.statusBar().showMessage("No active image to crop", 2000)
            return

        selection_rect = editor.scene.selection_rect
        if not selection_rect or not selection_rect.rect().isValid() or selection_rect.rect().isEmpty():
            self.statusBar().showMessage("No valid selection to crop", 2000)
            return

        rect = selection_rect.rect().toRect()
        command = CropCommand(editor, rect)
        editor.executeCommand(command)
        editor.scene.removeItem(selection_rect)
        editor.scene.selection_rect = None
        for handle in editor.scene.handles:
            editor.scene.removeItem(handle)
        editor.scene.handles.clear()
        self.statusBar().showMessage(f"Image cropped to {rect.width()}x{rect.height()}", 2000)

    def zoomIn(self):
        editor = self.currentEditor()
        if editor:
            editor.zoomIn()

    def zoomOut(self):
        editor = self.currentEditor()
        if editor:
            editor.zoomOut()

    def fitToScreen(self):
        editor = self.currentEditor()
        if editor:
            editor.fitInViewWithRulers()

    def actualSize(self):
        editor = self.currentEditor()
        if editor:
            editor.actualSize()


    def resizeImage(self):
        """Resize the current image."""
        editor = self.currentEditor()
        if not editor or not editor.current_image:
            self.statusBar().showMessage("No image to resize", 2000)
            return
        current_size = editor.current_image.size()
        dialog = ResizeDialog(current_size.width(), current_size.height(), self)
        if dialog.exec_():
            width, height, keep_aspect = dialog.getNewSize()
            editor.resizeImage(width, height, keep_aspect)
            self.statusBar().showMessage(f"Image resized to {width}x{height}", 2000)

    def rotateImage(self, degrees):
        """Rotate the image by specified degrees"""
        editor = self.currentEditor()
        if editor:
            editor.rotateImage(degrees)

    def flipImage(self, horizontal):
        """Flip the image horizontally or vertically"""
        editor = self.currentEditor()
        if editor:
            editor.flipImage(horizontal)

    def convertToGrayscale(self):
        """Convert the image to grayscale"""
        editor = self.currentEditor()
        if editor:
            editor.convertToGrayscale()

    def showAdjustmentsDialog(self):
        """Show adjustments dialog"""
        editor = self.currentEditor()
        if editor:
            dialog = AdjustmentsDialog(editor, self)
            if dialog.exec_():
                self.statusBar().showMessage("Adjustments applied", 2000)


    def about(self):
        """Show the about dialog"""
        QMessageBox.about(self, "About Simple Photo Editor",
            "Simple Photo Editor is a basic image editing application similar to "
            "Microsoft Photo Editor. It was created as a cross-platform alternative "
            "using Python and PyQt5. (c)Li_Zard")
