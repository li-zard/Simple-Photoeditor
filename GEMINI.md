# Project Overview

This project is a simple, open-source photo editing application built with Python. It is inspired by the classic Microsoft Photo Editor and aims to provide a user-friendly, minimalistic interface for image creation, editing, and processing. The application is built using the PyQt5 framework for the graphical user interface, with image processing capabilities provided by OpenCV and Pillow.

The architecture is a multi-document interface (MDI) application. The main entry point is `main.py`, which initializes the application and the main window (`main_window.py`). The `MainWindow` class sets up the UI, including menus, toolbars, and the MDI area where multiple images can be opened in sub-windows. Each sub-window contains an `EditorContainer` which holds an `ImageEditor` instance (`editor.py`). The `ImageEditor` is a `QGraphicsView` that displays the image within a `QGraphicsScene` managed by the `ImageEditorScene` class (`scene.py`). This scene handles user interactions like selection and cropping. The application uses a command pattern (evident from `commands.py`) to manage operations like undo and redo.

## Building and Running

### Running the Application

To run the application from the source code, follow these steps:

1.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python main.py
    ```

### Building the Executable

The project uses PyInstaller to package the application into a standalone executable.

```bash
pyinstaller main.py --onefile --windowed --icon=icons/icon.ico --name="SimplePhotoEditor_v1.0"
```

## Development Conventions

*   **Modular Structure:** The codebase is organized into modules with clear responsibilities:
    *   `main.py`: The main entry point of the application.
    *   `main_window.py`: Defines the main application window, menus, toolbars, and MDI area.
    *   `editor.py`: Contains the core `ImageEditor` class, which is a `QGraphicsView` for displaying and manipulating images.
    *   `scene.py`: Implements the `ImageEditorScene`, a `QGraphicsScene` that handles interactive elements like selection rectangles and handles.
    *   `widgets.py`: Contains custom UI widgets used in the application, such as dialogs.
    *   `commands.py`: Implements the command pattern for undo/redo functionality.
    *   `utils.py`: Provides utility functions for tasks like loading and saving configuration.

*   **Undo/Redo:** The application uses the Command design pattern to implement undo and redo functionality. Each image modification is encapsulated in a command object that can be executed and un-executed.

*   **Local Imports:** To avoid circular dependencies, some modules use local imports within functions or methods (e.g., `editor.py` imports `ImageEditorScene` inside `__init__`).

*   **Styling:** The application uses Qt's signal and slot mechanism for communication between different UI components. The UI is built programmatically using PyQt5 widgets.
