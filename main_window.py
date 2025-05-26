import sys
import os
from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog, QDialog, QMenu, QMdiArea, QMessageBox,
    QApplication, QStatusBar, QGraphicsView, QCheckBox, QInputDialog
)
from PyQt5.QtGui import QIcon, QPixmap, QImage, QPen
from PyQt5.QtCore import Qt, QRectF, QTimer
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from editor import ImageEditor, EditorContainer
from widgets import CustomMdiSubWindow, NewImageDialog, AdjustmentsDialog, ResizeDialog, RotationDialog
from commands import CropCommand
from utils import load_config, save_config, get_recent_files, add_recent_file

try:
    from win32com.client import Dispatch
    import pythoncom
    from io import BytesIO
    WIA_AVAILABLE = True
except ImportError:
    WIA_AVAILABLE = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Photo Editor")
        self.setGeometry(100, 100, 1000, 800)
        
        self.mdi_area = QMdiArea()
        self.setCentralWidget(self.mdi_area)
        
        self.statusBar().showMessage("Ready")
        
        self.createActions()
        self.createMenus()
        self.createToolbars()
        
        self.clipboard = QApplication.clipboard()
        self.selection_tool_act = QAction("Selection Tool", self, checkable=True, triggered=lambda: self.setTool("selection"))
        self.selection_tool_act.setChecked(True)
        # Инициализируем подменю Recent Files
        #self.update_recent_files_menu()
        self.active_editor_scene = None
        self.mdi_area.subWindowActivated.connect(self.onSubWindowActivated)
        
    def closeEvent(self, event):
        """Handle closing of the main window."""
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
        self.new_act = QAction("&New", self, shortcut="Ctrl+N", triggered=self.newFile)
        self.new_act.setIcon(QIcon(resource_path("icons/new.png")))
        self.new_act.setToolTip("New Image (Ctrl+N)")

        self.open_act = QAction("&Open", self, shortcut="Ctrl+O", triggered=lambda checked: self.openFile())
        self.open_act.setIcon(QIcon(resource_path("icons/open.png")))
        self.open_act.setToolTip("Open File (Ctrl+O)")

        self.save_act = QAction("&Save", self, shortcut="Ctrl+S", triggered=lambda checked: self.saveFile())
        self.save_act.setIcon(QIcon(resource_path("icons/save.png")))
        self.save_act.setToolTip("Save File (Ctrl+S)")

        self.save_as_act = QAction("Save &As...", self, shortcut="Ctrl+Shift+S", triggered=self.saveFileAs)
        self.save_as_act.setIcon(QIcon(resource_path("icons/save_as.png")))  # Если нет иконки, можно использовать save.png
        self.save_as_act.setToolTip("Save As (Ctrl+Shift+S)")

        self.print_act = QAction("&Print", self, shortcut="Ctrl+P", triggered=self.printFile)
        self.print_act.setIcon(QIcon(resource_path("icons/print.png")))
        self.print_act.setToolTip("Print (Ctrl+P)")

        self.scan_act = QAction("S&can", self, shortcut="Ctrl+Shift+N", triggered=self.scanImage)
        self.scan_act.setIcon(QIcon(resource_path("icons/scan.png")))  # Если нет, подбери подходящую
        self.scan_act.setToolTip("Scan (Ctrl+Shift+N)")

        self.exit_act = QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)
        self.exit_act.setIcon(QIcon(resource_path("icons/exit.png")))  # Если нет, можно использовать close.png
        self.exit_act.setToolTip("Exit (Ctrl+Q)")

        # Edit actions
        self.undo_act = QAction("&Undo", self, shortcut="Ctrl+Z", triggered=self.undo)
        self.undo_act.setIcon(QIcon(resource_path("icons/undo.png")))
        self.undo_act.setToolTip("Undo (Ctrl+Z)")

        self.redo_act = QAction("&Redo", self, shortcut="Ctrl+Y", triggered=self.redo)  # Новое действие
        self.redo_act.setIcon(QIcon(resource_path("icons/redo.png")))  # Укажи путь к иконке redo.png
        self.redo_act.setToolTip("Redo (Ctrl+Y)")

        self.cut_act = QAction("Cu&t", self, shortcut="Ctrl+X", triggered=self.cut)
        self.cut_act.setIcon(QIcon(resource_path("icons/cut.png")))
        self.cut_act.setToolTip("Cut (Ctrl+X)")

        self.copy_act = QAction("&Copy", self, shortcut="Ctrl+C", triggered=self.copy)
        self.copy_act.setIcon(QIcon(resource_path("icons/copy.png")))
        self.copy_act.setToolTip("Copy (Ctrl+C)")

        self.paste_act = QAction("&Paste", self, shortcut="Ctrl+V", triggered=self.paste)
        self.paste_act.setIcon(QIcon(resource_path("icons/paste.png")))
        self.paste_act.setToolTip("Paste (Ctrl+V)")

        self.paste_as_new_act = QAction("Paste as New Image", self, triggered=self.pasteAsNewImage)
        self.paste_as_new_act.setToolTip("Pastes clipboard content as a new image")
        self.paste_as_new_act.setIcon(QIcon(resource_path("icons/paste.png")))

        self.crop_act = QAction("C&rop", self, shortcut="Ctrl+R", triggered=self.cropImage)
        self.crop_act.setIcon(QIcon(resource_path("icons/crop.png")))
        self.crop_act.setToolTip("Crop to Selection (Ctrl+R)")
        # Добавляем действие Crop
        self.crop_act = QAction("C&rop", self, shortcut="Ctrl+R", triggered=self.cropImage)
        self.crop_act.setIcon(QIcon(resource_path("icons/crop.png")))  # Укажи путь к иконке crop.png
        self.crop_act.setToolTip("Crop to Selection (Ctrl+R)")

        # Новое действие: Resize
        self.resizeAct = QAction(QIcon(resource_path("icons/resize.png")), "&Resize...", self)
        self.resizeAct.setStatusTip("Resize the image")
        self.resizeAct.triggered.connect(self.resizeImage)
        
        self.select_all_act = QAction("Select &All", self, shortcut="Ctrl+A", triggered=self.selectAll)
        self.select_all_act.setIcon(QIcon(resource_path("icons/select_all.png")))
        self.select_all_act.setToolTip("Select All (Ctrl+A)")

        # View actions
        self.zoom_in_act = QAction("Zoom &In", self, shortcut="Ctrl++", triggered=self.zoomIn)
        self.zoom_in_act.setIcon(QIcon(resource_path("icons/zoom_in.png")))
        self.zoom_in_act.setToolTip("Zoom In (Ctrl++)")

        self.zoom_out_act = QAction("Zoom &Out", self, shortcut="Ctrl+-", triggered=self.zoomOut)
        self.zoom_out_act.setIcon(QIcon(resource_path("icons/zoom_out.png")))
        self.zoom_out_act.setToolTip("Zoom Out (Ctrl+-)")

        self.fit_screen_act = QAction("&Fit to Screen", self, shortcut="Ctrl+0", triggered=self.fitToScreen)
        self.fit_screen_act.setIcon(QIcon(resource_path("icons/fit_screen.png")))
        self.fit_screen_act.setToolTip("Fit to Screen (Ctrl+0)")

        self.actual_size_act = QAction("&Actual Size", self, shortcut="Ctrl+1", triggered=self.actualSize)
        self.actual_size_act.setIcon(QIcon(resource_path("icons/actual_size.png")))  # Если нет, подбери подходящую
        self.actual_size_act.setToolTip("Actual Size (Ctrl+1)")

        self.toggle_rulers_act = QAction("Show &Rulers", self)
        self.toggle_rulers_act.setIcon(QIcon(resource_path("icons/ruler.png")))
        self.toggle_rulers_act.setToolTip("Show Rulers")
        self.toggle_rulers_act.triggered.connect(self.toggleRulers)  # Подключаем сигнал triggered
        
        #self.toggle_rulers_act = QAction("Show &Rulers", self, checkable=True, triggered=self.toggleRulers)
        #self.toggle_rulers_act.setIcon(QIcon(resource_path("icons/ruler.png")))  # Если нет, подбери подходящую
        #self.toggle_rulers_act.setToolTip("Show Rulers")

        # Image actions
        self.rotate_90_cw_act = QAction("Rotate 90° &CW", self, triggered=lambda: self.rotateImage(90))
        self.rotate_90_cw_act.setIcon(QIcon(resource_path("icons/rotate_cw.png")))
        self.rotate_90_cw_act.setToolTip("Rotate 90° Clockwise")

        self.rotate_90_ccw_act = QAction("Rotate 90° CC&W", self, triggered=lambda: self.rotateImage(-90))
        self.rotate_90_ccw_act.setIcon(QIcon(resource_path("icons/rotate_ccw.png")))
        self.rotate_90_ccw_act.setToolTip("Rotate 90° Counter-Clockwise")

        self.rotate_180_act = QAction("Rotate &180°", self, triggered=lambda: self.rotateImage(180))
        self.rotate_180_act.setIcon(QIcon(resource_path("icons/rotate_cw.png")))  # Если нет, можно использовать rotate_cw.png
        self.rotate_180_act.setToolTip("Rotate 180°")

        self.precise_rotate_act = QAction("Rotate...", self, triggered=self.openPreciseRotationDialog)
        self.precise_rotate_act.setIcon(QIcon(resource_path("icons/rotate_cw.png")))
        self.precise_rotate_act.setToolTip("Precise Rotation")

        self.flip_horizontal_act = QAction("Flip &Horizontal", self, triggered=lambda: self.flipImage(True))
        self.flip_horizontal_act.setIcon(QIcon(resource_path("icons/flip.png")))
        self.flip_horizontal_act.setToolTip("Flip Horizontal")

        self.flip_vertical_act = QAction("Flip &Vertical", self, triggered=lambda: self.flipImage(False))
        self.flip_vertical_act.setIcon(QIcon(resource_path("icons/flip.png")))
        self.flip_vertical_act.setToolTip("Flip Vertical")

        self.grayscale_act = QAction("Convert to &Grayscale", self, triggered=self.convertToGrayscale)
        self.grayscale_act.setIcon(QIcon(resource_path("icons/grayscale.png")))
        self.grayscale_act.setToolTip("Convert to Grayscale")

        self.adjustments_act = QAction("&Adjustments...", self, triggered=self.showAdjustmentsDialog)
        self.adjustments_act.setIcon(QIcon(resource_path("icons/tune.png")))
        self.adjustments_act.setToolTip("Adjustments...")

        # Window actions
        self.tile_act = QAction("&Tile", self, triggered=self.mdi_area.tileSubWindows)
        self.tile_act.setIcon(QIcon(resource_path("icons/tile.png")))  # Если нет, подбери подходящую
        self.tile_act.setToolTip("Tile Windows")

        self.cascade_act = QAction("&Cascade", self, triggered=self.mdi_area.cascadeSubWindows)
        self.cascade_act.setIcon(QIcon(resource_path("icons/cascade.png")))  # Если нет, подбери подходящую
        self.cascade_act.setToolTip("Cascade Windows")

        self.next_act = QAction("&Next", self, shortcut="Ctrl+Tab", triggered=self.mdi_area.activateNextSubWindow)
        self.next_act.setIcon(QIcon(resource_path("icons/next.png")))  # Если нет, подбери подходящую
        self.next_act.setToolTip("Next Window (Ctrl+Tab)")

        self.previous_act = QAction("&Previous", self, shortcut="Ctrl+Shift+Tab", triggered=self.mdi_area.activatePreviousSubWindow)
        self.previous_act.setIcon(QIcon(resource_path("icons/previous.png")))  # Если нет, подбери подходящую
        self.previous_act.setToolTip("Previous Window (Ctrl+Shift+Tab)")

        # Tools action
        #self.selection_tool_act = QAction("Selection Tool", self, triggered=lambda: self.setTool("selection"))
        #self.selection_tool_act.setIcon(QIcon(resource_path("icons/select.png")))
        #self.selection_tool_act.setToolTip("Selection Tool")
        # Tools action
        self.selection_tool_act = QAction("Selection Tool", self, triggered=self.activateSelectionTool)
        self.selection_tool_act.setIcon(QIcon(resource_path("icons/select.png")))
        self.selection_tool_act.setToolTip("Selection Tool")
        

        # Help actions
        self.about_act = QAction("&About", self, triggered=self.about)
        self.about_act.setIcon(QIcon(resource_path("icons/about.png")))
        self.about_act.setToolTip("About")
    
    def createMenus(self):
        """Create menu bar"""
        # File menu
        file_menu = self.menuBar().addMenu("&File")
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
        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.addAction(self.undo_act)
        edit_menu.addAction(self.redo_act)  # Добавляем Redo
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_act)
        edit_menu.addAction(self.copy_act)
        edit_menu.addAction(self.paste_act)
        edit_menu.addAction(self.paste_as_new_act)
        edit_menu.addAction(self.crop_act)
        edit_menu.addSeparator()
        edit_menu.addAction(self.select_all_act)
        
        # View menu
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.zoom_in_act)
        view_menu.addAction(self.zoom_out_act)
        view_menu.addAction(self.fit_screen_act)
        view_menu.addAction(self.actual_size_act)
        view_menu.addSeparator()
        view_menu.addAction(self.toggle_rulers_act)
        
        # Image menu
        image_menu = self.menuBar().addMenu("&Image")
        rotate_menu = image_menu.addMenu("&Rotate")
        rotate_menu.addAction(self.rotate_90_cw_act)
        rotate_menu.addAction(self.rotate_90_ccw_act)
        rotate_menu.addAction(self.rotate_180_act)
        rotate_menu.addSeparator() # Optional separator
        rotate_menu.addAction(self.precise_rotate_act)
        image_menu.addAction(self.crop_act)
        image_menu.addAction(self.resizeAct)
        
        
        flip_menu = image_menu.addMenu("&Flip")
        flip_menu.addAction(self.flip_horizontal_act)
        flip_menu.addAction(self.flip_vertical_act)
        
        image_menu.addSeparator()
        image_menu.addAction(self.grayscale_act)
        image_menu.addAction(self.adjustments_act)
        
        # Window menu
        window_menu = self.menuBar().addMenu("&Window")
        window_menu.addAction(self.tile_act)
        window_menu.addAction(self.cascade_act)
        window_menu.addSeparator()
        window_menu.addAction(self.next_act)
        window_menu.addAction(self.previous_act)
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_act)

        # Connect signals for dynamic menu updates
        edit_menu.aboutToShow.connect(self.updateEditMenuActions)

        # Initial call to set correct states
        self.updateEditMenuActions()

    def updateEditMenuActions(self):
        clipboard = QApplication.clipboard()
        has_image_in_clipboard = clipboard.mimeData().hasImage()

        self.paste_as_new_act.setEnabled(has_image_in_clipboard)

        editor = self.currentEditor()
        if editor and editor.getCurrentImage(): # Check if editor exists and has an image
            # Standard Paste: Enabled if editor is active and clipboard has an image
            self.paste_act.setEnabled(has_image_in_clipboard)
            
            # Undo/Redo: Enabled based on editor's undo/redo stack
            self.undo_act.setEnabled(len(editor.undo_stack) > 0)
            self.redo_act.setEnabled(len(editor.redo_stack) > 0)

            # Cut/Copy/Crop: Enabled if there's a selection in the editor
            # Assuming editor.scene.selection_rect exists and indicates a selection
            has_selection = editor.scene.selection_rect is not None and \
                            editor.scene.selection_rect.rect().isValid() and \
                            not editor.scene.selection_rect.rect().isEmpty()
            
            self.cut_act.setEnabled(has_selection)
            self.copy_act.setEnabled(has_selection)
            # The existing crop_act might have its own more specific enabling logic or can use this
            self.crop_act.setEnabled(has_selection) 

            # Select All: Enabled if there is an image to select
            self.select_all_act.setEnabled(True)
        else:
            # No active editor with an image
            self.paste_act.setEnabled(False)
            self.undo_act.setEnabled(False)
            self.redo_act.setEnabled(False)
            self.cut_act.setEnabled(False)
            self.copy_act.setEnabled(False)
            self.crop_act.setEnabled(False)
            self.select_all_act.setEnabled(False)

    def onSubWindowActivated(self, activated_sub_window):
        # Disconnect from the previous scene if any
        if self.active_editor_scene:
            try:
                self.active_editor_scene.selectionChanged.disconnect(self.handleSpecificSelectionChange)
            except TypeError: # Handles case where it might not have been connected
                pass 
            self.active_editor_scene = None

        editor = None
        if activated_sub_window and hasattr(activated_sub_window, 'editor_container'):
            # Assuming CustomMdiSubWindow structure where editor is accessible
            # via editor_container
            if hasattr(activated_sub_window.editor_container, 'editor'):
                editor = activated_sub_window.editor_container.editor
        
        if editor:
            self.active_editor_scene = editor.scene
            # Connect to the new active scene's selectionChanged signal
            self.active_editor_scene.selectionChanged.connect(self.handleSpecificSelectionChange)
        
        # Update all actions based on the new context (newly active editor or no editor)
        self.updateEditMenuActions()

    def handleSpecificSelectionChange(self, selection_qrectf):
        # This method is called when the selection rectangle changes in the active scene.
        # We just need to trigger a general update of actions.
        self.updateEditMenuActions()

    def update_recent_files_menu(self):
        """Обновить подменю Recent Files."""
        self.recent_files_menu.clear()
        config = load_config()
        recent_files = get_recent_files(config)
        if not recent_files:
            no_files_action = QAction("No recent files", self)
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
        dialog = NewImageDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            width, height, dpi, bg_color = dialog.getImageParameters()
            
            new_image = QImage(width, height, QImage.Format_RGBA8888)
            new_image.fill(bg_color if bg_color is not None else Qt.white)
            new_image.setDotsPerMeterX(int(dpi * 39.37))
            new_image.setDotsPerMeterY(int(dpi * 39.37))
            
            sub_window = CustomMdiSubWindow(self)
            sub_window.editor_container.editor.setImage(new_image)
            sub_window.setWindowTitle(f"Untitled ({width}x{height})")
            sub_window.file_path = None  # Убедимся, что file_path установлен
            self.mdi_area.addSubWindow(sub_window)
            sub_window.show()
            # Принудительно масштабируем сцену после отображения
            sub_window.editor_container.editor.fitInViewWithRulers()



    def openFile(self, file_name=None):
        """Открыть файл. Если file_name указан, открыть его напрямую, иначе показать диалог."""
        print("MainWindow.openFile called")
        print(f"file_name at start: {file_name}")  # Отладка
        if file_name is None:
            print("file_name is None, proceeding to open dialog")  # Отладка
            print("Opening file dialog...")  # Отладка
            try:
                file_name, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Open Image", 
                    "", 
                    "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
                )
                print(f"File dialog returned: {file_name}")  # Отладка
            except Exception as e:
                print(f"Error opening file dialog: {e}")  # Отладка
                QMessageBox.critical(self, "Error", f"Failed to open file dialog: {e}")
                return
        else:
            print(f"file_name provided: {file_name}")  # Отладка
        if file_name:
            print(f"Checking if file exists: {file_name}")  # Отладка
            if not os.path.exists(file_name):
                print("File does not exist")  # Отладка
                QMessageBox.warning(self, "Error", f"File does not exist: {file_name}")
                return
            print(f"Loading image: {file_name}")  # Отладка
            image = QImage(file_name)
            if image.isNull():
                print("Image is null, showing error message")  # Отладка
                QMessageBox.warning(self, "Error", "Failed to open image.")
                return
            print("Creating subwindow...")  # Отладка
            sub_window = CustomMdiSubWindow(self)
            sub_window.editor_container.editor.setImage(image)
            sub_window.setWindowTitle(f"{os.path.basename(file_name)} ({image.width()}x{image.height()})")
            sub_window.file_path = file_name  # Сохраняем путь к файлу
            print("Adding subwindow to MDI area...")  # Отладка
            self.mdi_area.addSubWindow(sub_window)
            print("Showing subwindow...")  # Отладка
            sub_window.show()

            # Корректируем позицию окна
            viewport = self.mdi_area.viewport()
            viewport_rect = viewport.rect()
            print("Moving subwindow to top-left...")  # Отладка
            sub_window.move(viewport_rect.topLeft())  # Перемещаем в верхний левый угол

            print("Scheduling fitInViewWithRulers...")  # Отладка
            QTimer.singleShot(100, sub_window.editor_container.editor.fitInViewWithRulers)
            self.statusBar().showMessage(f"Opened {file_name}", 2000)
            # Добавляем файл в список недавних
            print("Updating recent files...")  # Отладка
            config = load_config()
            add_recent_file(config, file_name)
            # Обновляем меню Recent Files
            self.update_recent_files_menu()
        else:
            print("No file selected, exiting openFile")  # Отладка

 
    
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
        print(f"Saving to: {file_name}")  # Отладка
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
                print(f"Failed to save file: {e}")  # Отладка
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
                print(f"Added .png extension: {file_path}")  # Отладка
            
            if self.saveImageToFile(editor, file_path):
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
        print("MainWindow.toggleRulers called")  # Отладка
        sub_window = self.mdi_area.activeSubWindow()
        if sub_window:
            # Переключаем состояние линеек
            current_state = sub_window.editor_container.editor.rulers_visible
            sub_window.editor_container.toggleRulers(not current_state)
  
    
    def saveImageToFile(self, editor, file_path):
        """Save the image to a file."""
        image = editor.getCurrentImage()
        if image:
            try:
                success = image.save(file_path)
                if success:
                    return True
                else:
                    print(f"Failed to save image to {file_path}: QImage.save returned False")  # Отладка
                    return False
            except Exception as e:
                print(f"Failed to save image to {file_path}: {e}")  # Отладка
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
            QMessageBox.warning(self, "Scanning Not Available", "WIA components are not installed. Scanning is not available.")
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

            # Диалог для выбора DPI
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

    def pasteAsNewImage(self):
        clipboard = QApplication.clipboard()
        if clipboard.mimeData().hasImage():
            image = QImage(clipboard.mimeData().imageData())
            if not image.isNull():
                # Create a new MDI sub-window for the image
                sub_window = CustomMdiSubWindow(self) # Assuming CustomMdiSubWindow is imported
                
                # Set the image in the editor contained within the sub-window
                # The editor is usually accessed via 'sub_window.editor_container.editor'
                editor_instance = sub_window.editor_container.editor
                editor_instance.setImage(image) # setImage should handle pixmap update, scene rect etc.
                
                # Set window title
                title = f"Pasted Image ({image.width()}x{image.height()})"
                sub_window.setWindowTitle(title)
                sub_window.file_path = None # It's a new, unsaved image

                self.mdi_area.addSubWindow(sub_window)
                sub_window.show()
                
                # Optional: Fit image to view after showing
                QTimer.singleShot(0, editor_instance.fitInViewWithRulers) # Or similar method

                self.statusBar().showMessage(f"Pasted image as new: {title}", 2000)
            else:
                self.statusBar().showMessage("Could not retrieve image data from clipboard.", 2000)
        else:
            self.statusBar().showMessage("No image in clipboard to paste as new.", 2000)
      
    def selectAll(self):
        """Select the entire image"""
        editor = self.currentEditor()
        if not editor:
            return
        editor.paste()  # Уже вызывает обновлённый метод
    
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
            sub_window = self.mdi_area.activeSubWindow()
            if sub_window:
                sub_window.setWindowTitle(f"{sub_window.windowTitle().split(' (')[0]} ({width}x{height})")
    
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
            "using Python and PyQt5.")

    #test
    def setTool(self, tool_name):
            editor = self.currentEditor()
            if editor:
                editor.scene.current_tool = tool_name
                self.statusBar().showMessage("Selection tool active: Click and drag to select an area")
                editor.setDragMode(QGraphicsView.NoDrag)


def resource_path(relative_path):
    """Get the absolute path to a resource, works for development and PyInstaller."""
    if getattr(sys, 'frozen', False):  # If App running as .exe
        base_path = sys._MEIPASS  # Resource folder of PyInstaller
    else:
        base_path = os.path.abspath(".")  # If running from py

    return os.path.join(base_path, relative_path)
