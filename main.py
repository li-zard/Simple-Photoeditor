
"""
Simple-Photoeditor: A Python-based photo editing application using PyQt5.
Loads configuration, initializes a GUI window, and saves settings on exit.
"""

import logging
import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from main_window import MainWindow
from utils import load_config, save_config, resource_path



if __name__ == "__main__":  # noqa: E402 (импорты PyQt должны идти после настройки логирования)
    # Configure logging; level can be raised via PHOTOEDITOR_LOGLEVEL env variable
    log_level = os.environ.get("PHOTOEDITOR_LOGLEVEL", "WARNING").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # High-DPI: без этих атрибутов на масштабированных экранах (125–150%)
    # интерфейс, включая тайтлбары MDI-подокон, рисуется мелко и затем
    # растягивается — отсюда размытый заголовок окна с изображением.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Initialize the PyQt5 application
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    # Load configuration from file
    config = load_config()

    # Тема оформления (General.theme: system / light / dark)
    import theme as theme_module
    theme_module.init_theme(app, config)

    # Create the main window
    window = MainWindow(config)

    # Apply configuration settings for window size
    if 'General' in config:
        window_width = int(config['General'].get('window_width', 800))
        window_height = int(config['General'].get('window_height', 600))
    else:
        window_width = 800
        window_height = 600
        logging.getLogger("photoeditor").warning(
            "'General' section missing in config, using defaults")

    # Resize and display the main window
    window.resize(window_width, window_height)
    window.show()

    # Open file from command line argument if provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            window.openFile(file_path)
    else:
        # Иначе открываем последний файл из предыдущей сессии (General.last_opened_file)
        last_file = config['General'].get('last_opened_file', '') if 'General' in config else ''
        if last_file and os.path.isfile(last_file):
            window.openFile(last_file)

    # Start the application event loop
    sys.exit(app.exec_())
