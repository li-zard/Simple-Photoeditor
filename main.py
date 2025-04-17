
"""
Simple-Photoeditor: A Python-based photo editing application using PyQt5.
Loads configuration, initializes a GUI window, and saves settings on exit.
"""

from PyQt5.QtGui import QIcon
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow, resource_path
from utils import load_config, save_config
import os

if __name__ == "__main__":
    # Initialize the PyQt5 application
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    # Load configuration from file
    config = load_config()

    # Create the main window
    window = MainWindow()

    # Apply configuration settings for window size and last opened file
    if 'General' in config:
        window_width = int(config['General'].get('window_width', 800))
        window_height = int(config['General'].get('window_height', 600))
        last_opened_file = config['General'].get('last_opened_file', '')
    else:
        window_width = 800
        window_height = 600
        last_opened_file = ''
        print("Warning: 'General' section missing in config, using defaults")

    
    # Resize and display the main window
    window.resize(window_width, window_height)    
    window.show()
    
    # Save configuration when the application closes
    app.aboutToQuit.connect(lambda: save_config(config))
    # Start the application event loop
    sys.exit(app.exec_())
