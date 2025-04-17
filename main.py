
from PyQt5.QtGui import QIcon
import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow, resource_path
from utils import load_config, save_config
import os

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
    # Load config
    config = load_config()
    window = MainWindow()
    # Apply config with check
    if 'General' in config:
        window_width = int(config['General'].get('window_width', 800))
        window_height = int(config['General'].get('window_height', 600))
        last_opened_file = config['General'].get('last_opened_file', '')
    else:
        window_width = 800
        window_height = 600
        last_opened_file = ''
        print("Warning: 'General' section missing in config, using defaults")

    

    window.resize(window_width, window_height)    
    window.show()
    
    # Save on exit
    app.aboutToQuit.connect(lambda: save_config(config))
    sys.exit(app.exec_())
