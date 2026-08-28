# Simple Photo Editor — Documentation

Welcome to the complete documentation for **Simple Photo Editor** — an open-source, cross-platform image editing application built with Python and PyQt5, inspired by the classic Microsoft Photo Editor.

This documentation provides a full description of the project: its architecture, every module, the design patterns used, data flows, configuration system, and build instructions.

## Table of Contents

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture.md) | High-level architecture, component diagram, design patterns, data flows |
| [Modules Reference](modules.md) | Detailed description of every module and its classes/methods |
| [Undo/Redo System](undo-redo.md) | The Command pattern implementation and how history works |
| [Configuration](configuration.md) | `config.ini` structure, user config directory, recent files |
| [Building & Deployment](building.md) | Running from source, PyInstaller packaging, platform notes |
| [Roadmap](roadmap.md) | Step-by-step improvement plan: refactoring, fixes, features, Inno Setup installer with file associations |

## Project Snapshot

- **Language**: Python 3.10–3.13 (PyQt5 GUI toolkit)
- **Image processing**: Pillow (PIL), OpenCV (optional, for grayscale), NumPy
- **UI paradigm**: Multi-Document Interface (MDI) — each open image lives in its own child window
- **Editing model**: Command pattern with a two-stack undo/redo history
- **Configuration**: INI-based settings stored per-user via `appdirs`
- **Packaging**: PyInstaller (`--onedir --windowed`) + Inno Setup installer (Windows)

## Source Files at a Glance

| File | Responsibility |
|------|----------------|
| [`main.py`](../main.py) | Entry point: creates `QApplication`, loads config, shows the main window |
| [`main_window.py`](../main_window.py) | `MainWindow` (QMainWindow): menus, toolbars, actions, MDI area, file I/O, scanning, printing |
| [`editor.py`](../editor.py) | `ImageEditor` (QGraphicsView) and `EditorContainer`: image display, zoom, rulers layout |
| [`scene.py`](../scene.py) | `ImageEditorScene` (QGraphicsScene) and `MovableImageItem`: selection, handles, pasted items |
| [`widgets.py`](../widgets.py) | `RulerWidget`, `CustomMdiSubWindow`, and all dialogs (New Image, Adjustments, Resize, Rotation) |
| [`commands.py`](../commands.py) | Command pattern: `Command` base class and all concrete edit operations |
| [`utils.py`](../utils.py) | Config load/save, resource paths, recent-files management |
| [`theme.py`](../theme.py) | Light/dark themes, palette, theme-aware icon inversion |
| [`singleinstance.py`](../singleinstance.py) | Single-instance guard: forwards opened files to the running instance |

## Quick Start

```bash
# 1. Create and activate a virtual environment (Python 3.10–3.13)
python3.12 -m venv venv
source venv/bin/activate        # Windows: py -3.12 -m venv venv && venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py [optional_image_path]
```

See [Building & Deployment](building.md) for executable packaging details.
