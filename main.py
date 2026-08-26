
"""
Simple-Photoeditor: A Python-based photo editing application using PyQt5.
Loads configuration, initializes a GUI window, and saves settings on exit.
"""

import logging
import os
import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from main_window import MainWindow
from utils import load_config, save_config, resource_path

if __name__ == "__main__":
    # Configure logging; level can be raised via PHOTOEDITOR_LOGLEVEL env variable
    log_level = os.environ.get("PHOTOEDITOR_LOGLEVEL", "WARNING").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # Initialize the PyQt5 application
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    # Load configuration from file
    config = load_config()

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

    # Start the application event loop
    sys.exit(app.exec_())
