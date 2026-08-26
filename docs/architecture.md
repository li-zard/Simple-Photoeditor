# Architecture Overview

This document describes the architecture of Simple Photo Editor: the overall structure, the responsibilities of each layer, the design patterns in use, and the main data flows.

## 1. High-Level Structure

The application is a **Multi-Document Interface (MDI)** desktop editor: one top-level window hosts any number of child windows, each editing a separate image.

```
┌─────────────────────────────────────────────────────────────────┐
│ MainWindow (QMainWindow)                          main_window.py │
│  • Menu bar (File/Edit/View/Image/Window/Help)                   │
│  • Toolbars (File/Edit/View/Image/Tools)                         │
│  • Status bar                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ QMdiArea (central widget)                                   │ │
│  │  ┌───────────────────────────────────────────────────────┐  │ │
│  │  │ CustomMdiSubWindow (QMdiSubWindow)        widgets.py  │  │ │
│  │  │  ┌─────────────────────────────────────────────────┐  │  │ │
│  │  │  │ EditorContainer (QWidget)           editor.py   │  │  │ │
│  │  │  │  ┌──────────┬──────────────────────────────┐    │  │  │ │
│  │  │  │  │ Ruler    │  RulerWidget (horizontal)    │    │  │  │ │
│  │  │  │  │ corner   ├──────────────────────────────┤    │  │  │ │
│  │  │  │  │ Ruler    │                              │    │  │  │ │
│  │  │  │  │ (vert.)  │  ImageEditor (QGraphicsView) │    │  │  │ │
│  │  │  │  │          │   └─ ImageEditorScene        │    │  │  │ │
│  │  │  │  │          │       ├─ image_item          │    │  │  │ │
│  │  │  │  │          │       ├─ selection_rect      │    │  │  │ │
│  │  │  │  │          │       ├─ handles[]           │    │  │  │ │
│  │  │  │  │          │       └─ MovableImageItem[]  │    │  │  │ │
│  │  │  │  └──────────┴──────────────────────────────┘    │  │  │ │
│  │  │  └─────────────────────────────────────────────────┘  │  │ │
│  │  └───────────────────────────────────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Module Dependency Graph

Arrows mean "imports".

```
main.py ──► main_window.py ──► editor.py ──► scene.py
   │              │                │            │
   │              ├──► widgets.py ─┘            │
   │              ├──► commands.py ──► scene.py │
   │              └──► utils.py                 │
   └──► utils.py                               (editor.py ◄──┘)
```

Key points:

- [`main.py`](../main.py) imports [`MainWindow`](../main_window.py) and config helpers from [`utils.py`](../utils.py).
- [`main_window.py`](../main_window.py) imports the editor ([`editor.py`](../editor.py)), dialogs and sub-window ([`widgets.py`](../widgets.py)), [`CropCommand`](../commands.py), and config utilities.
- [`editor.py`](../editor.py) and [`scene.py`](../scene.py) reference each other, so they use **local (deferred) imports inside methods** to avoid circular-import problems at load time.
- [`commands.py`](../commands.py) imports both [`ImageEditor`](../editor.py) (only for typing context) and [`MovableImageItem`](../scene.py), and defers importing [`CustomMdiSubWindow`](../widgets.py) inside method bodies.
- [`widgets.py`](../widgets.py) imports [`ImageEditor`](../editor.py)/[`EditorContainer`](../editor.py) and [`AdjustmentsCommand`](../commands.py).

## 3. Layers and Responsibilities

### 3.1 Application layer — [`main.py`](../main.py)

- Creates the [`QApplication`](../main.py), sets the window icon.
- Loads configuration via [`load_config()`](../utils.py).
- Instantiates [`MainWindow`](../main_window.py), applies persisted window size, optionally opens a file passed as a command-line argument, and starts the event loop.

### 3.2 Application UI layer — [`main_window.py`](../main_window.py)

[`MainWindow`](../main_window.py) owns everything the user sees at the top level:

- **Actions** — one [`QAction`](../main_window.py) per operation (New, Open, Save, Print, Scan, Undo, Redo, Cut, Copy, Paste, Crop, Resize, Select All, Zoom In/Out, Fit, Actual Size, Rulers, Rotate, Flip, Grayscale, Adjustments, Tile, Cascade, Next, Previous, Selection Tool, About). Each action binds a keyboard shortcut, an icon from `icons/`, and a handler method.
- **Menus** — File, Edit, View, Image (with Rotate/Flip submenus), Window, Help, plus a dynamic **Recent Files** submenu rebuilt by [`update_recent_files_menu()`](../main_window.py).
- **Toolbars** — File, Edit, View, Image, Tools.
- **File operations** — [`newFile()`](../main_window.py) (with [`NewImageDialog`](../widgets.py)), [`openFile()`](../main_window.py) (dialog or direct path, also used by drag-and-drop and recent files), [`saveFile()`](../main_window.py)/[`saveFileAs()`](../main_window.py), [`printFile()`](../main_window.py) (QPrinter), [`scanImage()`](../main_window.py) (WIA on Windows).
- **Edit dispatching** — most Edit/Image handlers resolve the active editor via [`currentEditor()`](../main_window.py) and delegate to it.
- **Shutdown** — [`closeEvent()`](../main_window.py) persists window size and last-image settings, then walks all MDI sub-windows asking to save unsaved work.

### 3.3 Editor layer — [`editor.py`](../editor.py)

- [`ImageEditor`](../editor.py) (a `QGraphicsView`) is the per-image editing surface:
  - Holds `current_image` / `original_image` (`QImage`), the `image_item` (`QGraphicsPixmapItem`), zoom factor, modification flag, and the undo/redo stacks.
  - [`setImage()`](../editor.py) is the single entry point for putting a `QImage` on screen (resets zoom, refits view, clears the modified flag).
  - Zoom/navigation: [`zoomIn()`](../editor.py), [`zoomOut()`](../editor.py), [`actualSize()`](../editor.py), [`fitInViewWithRulers()`](../editor.py).
  - Command execution: [`executeCommand()`](../editor.py) runs a command and pushes it onto the undo stack.
  - Live-preview mechanism for dialogs: [`start_preview()`](../editor.py) / [`preview_rotation()`](../editor.py) / [`preview_adjustments()`](../editor.py) / [`cancel_preview()`](../editor.py) / [`apply_rotation()`](../editor.py) / [`apply_adjustments()`](../editor.py).
  - Pasted-item management: [`fixPastedItems()`](../editor.py), [`applyAllPastedItems()`](../editor.py).
- [`EditorContainer`](../editor.py) composes one `ImageEditor` with two [`RulerWidget`](../widgets.py) instances and a corner widget in a `QGridLayout`; it toggles ruler visibility and keeps ruler sizes in sync on resize.

### 3.4 Interaction layer — [`scene.py`](../scene.py)

- [`ImageEditorScene`](../scene.py) (a `QGraphicsScene`) implements the interactive behavior:
  - Rubber-band selection with an animated dashed rectangle ([`updateDash()`](../scene.py) driven by a 100 ms `QTimer`).
  - Eight resize handles around the selection ([`createHandles()`](../scene.py)), draggable and clamped to the scene rect.
  - Fixing pasted items into the base image ([`fixMovableItem()`](../scene.py)).
  - Emits a custom [`selectionChanged(QRectF)`](../scene.py) signal consumed by the editor's status-bar updater.
- [`MovableImageItem`](../scene.py) (a `QGraphicsPixmapItem`) represents a pasted image floating above the canvas: movable, selectable, constrained to the scene bounds.

### 3.5 Operations layer — [`commands.py`](../commands.py)

All destructive operations are encapsulated as command objects (see [Undo/Redo System](undo-redo.md)):

| Command | Operation |
|---------|-----------|
| [`CropCommand`](../commands.py) | Crop to the selection rectangle |
| [`AdjustmentsCommand`](../commands.py) | Brightness / contrast / gamma / auto-levels |
| [`TransformCommand`](../commands.py) | Rotation (arbitrary angle) and mirroring |
| [`GrayscaleCommand`](../commands.py) | RGBA → grayscale via OpenCV |
| [`PasteCommand`](../commands.py) | Paste clipboard image (into selection or as movable item) |
| [`CutCommand`](../commands.py) | Cut selection to clipboard (fills with white) |
| [`ResizeCommand`](../commands.py) | Image rescaling |
| [`FixPasteCommand`](../commands.py) | Bake floating pasted items into the base image |

### 3.6 Widgets & dialogs layer — [`widgets.py`](../widgets.py)

- [`RulerWidget`](../widgets.py) — custom-painted horizontal/vertical ruler with adaptive tick spacing and a red cursor indicator.
- [`CustomMdiSubWindow`](../widgets.py) — MDI child window hosting an `EditorContainer`; intercepts close to prompt for unsaved changes.
- [`NewImageDialog`](../widgets.py) — width/height/units (px/cm/in)/DPI/color depth/background color.
- [`AdjustmentsDialog`](../widgets.py) — live-preview sliders for brightness/contrast/gamma plus an autobalance toggle.
- [`ResizeDialog`](../widgets.py) — width/height/percent fields with linked aspect-ratio logic.
- [`RotationDialog`](../widgets.py) — spinbox + slider (-180…180°) with live rotation preview.

### 3.7 Utilities layer — [`utils.py`](../utils.py)

- [`get_user_config_path()`](../utils.py) — per-user config directory via `appdirs`.
- [`resource_path()`](../utils.py) — resource resolution that works both in development and under PyInstaller (`sys._MEIPASS`).
- [`load_config()`](../utils.py) / [`save_config()`](../utils.py) — INI read/write with default-section seeding.
- [`add_recent_file()`](../utils.py) / [`get_recent_files()`](../utils.py) — MRU list (max 5 entries, existence-checked on read).

## 4. Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Command** | [`commands.py`](../commands.py), [`executeCommand()`](../editor.py) | Encapsulates each edit as an object with `execute/undo/redo`; enables unlimited-depth history |
| **MDI** | [`QMdiArea`](../main_window.py) + [`CustomMdiSubWindow`](../widgets.py) | Multiple simultaneous documents in one application window |
| **MVC (loose)** | Model: `QImage` data; View: `QGraphicsView`/`QGraphicsScene`; Controller: `MainWindow` + dialogs | Separation of data, presentation, and input handling |
| **Deferred imports** | [`editor.py`](../editor.py), [`commands.py`](../commands.py) | Breaks circular-import cycles between tightly coupled modules |
| **Live preview (Memento-like)** | [`image_before_preview`](../editor.py) | Dialogs snapshot the image, preview non-destructively, then commit via a command or restore |
| **Signal/slot** | e.g. [`selectionChanged`](../scene.py) → [`updateStatusBar()`](../editor.py) | Decoupled UI communication |

## 5. Data Flows

### 5.1 Opening an image

```
User (menu / drag&drop / recent file / CLI arg)
   │
   ▼
MainWindow.openFile(file_name?)            main_window.py
   ├─ no path → QFileDialog.getOpenFileName
   ├─ validate existence; QImage(file_name); isNull() check
   ├─ sub_window = CustomMdiSubWindow(self)
   ├─ sub_window.editor_container.editor.setImage(image)
   ├─ mdi_area.addSubWindow(sub_window); sub_window.show()
   ├─ QTimer.singleShot(100, editor.fitInViewWithRulers)   # fit after layout
   ├─ add_recent_file(config, file_name)                   # utils.py
   └─ update_recent_files_menu()
```

### 5.2 Applying an edit (example: crop)

```
User → Crop action (Ctrl+R)
   │
   ▼
MainWindow.cropImage()                     main_window.py
   ├─ editor = currentEditor()             # active MDI child
   ├─ validate editor.scene.selection_rect
   ├─ command = CropCommand(editor, rect)  # commands.py (snapshots original)
   ├─ editor.executeCommand(command)
   │     ├─ command.execute()              # editor.setImage(cropped)
   │     ├─ editor.undo_stack.append(command)
   │     ├─ editor.redo_stack.clear()
   │     └─ editor.is_modified = True
   └─ remove selection rect + handles from scene
```

### 5.3 Undo / Redo

```
User → Undo (Ctrl+Z)
   ▼
MainWindow.undo() → editor.undo()          editor.py
   ├─ command = undo_stack.pop()
   ├─ redo_stack.append(command)
   ├─ command.undo()                       # restores snapshot
   ├─ is_modified = bool(undo_stack)
   └─ refresh scene + viewport + title
```

See [Undo/Redo System](undo-redo.md) for the full contract every command must satisfy.

### 5.4 Dialog with live preview (Adjustments)

```
Image → Adjustments…
   ▼
MainWindow.showAdjustmentsDialog()
   └─ AdjustmentsDialog(editor)            widgets.py
        ├─ editor.start_preview()          # snapshot current_image
        ├─ slider valueChanged ──────────► editor.preview_adjustments(...)
        │                                     (non-destructive, no command)
        ├─ OK  → editor.apply_adjustments(...)  # AdjustmentsCommand pushed
        └─ Cancel → editor.cancel_preview()     # snapshot restored
```

### 5.5 Paste as movable item

```
User → Paste (Ctrl+V)
   ▼
MainWindow.paste() → editor.paste()        editor.py
   └─ PasteCommand.execute()               commands.py
        ├─ valid selection? → draw clipboard image into selection
        └─ otherwise → MovableImageItem added to scene (floating layer)
User drags item; clicks empty canvas area
   ▼
ImageEditorScene.mousePressEvent()         scene.py
   └─ fixMovableItem(item, editor)         # bakes pixmap into current_image
      (also FixPasteCommand pushed via editor.fixPastedItems())
```

### 5.6 Application shutdown

```
User closes window
   ▼
MainWindow.closeEvent()                    main_window.py
   ├─ persist General.window_width/height
   ├─ persist LastImageSettings.*
   ├─ save_config(config)                  # utils.py → user config dir
   └─ for each MDI sub-window with is_modified:
        └─ confirmSave() → save / discard / cancel
```

## 6. Error Handling & Robustness Notes

- Optional dependencies degrade gracefully: `cv2` (grayscale) and WIA/`win32com` (scanning) are wrapped in try/except imports with `CV2_AVAILABLE` / `WIA_AVAILABLE` flags; the UI shows a warning instead of crashing.
- File operations validate existence and `QImage.isNull()` before use; save failures raise user-visible error dialogs.
- Config save failures are caught and printed rather than aborting shutdown.
- The undo stack for resize operations is capped at 10 entries ([`resizeImage()`](../editor.py)) to bound memory use.

## 7. Known Quirks (documented behavior)

- The `os` and `sys` entries in the repository root are files, not directories.
- `last_opened_file` is seeded in the `General` config section but is no longer read anywhere (see [Roadmap, stage 3](roadmap.md)).
- Logging is configured in [`main.py`](../main.py) via the `PHOTOEDITOR_LOGLEVEL` environment variable (default `WARNING`); loggers are named `photoeditor.<module>`.

> Historical quirks (dead code in `editor.py`, duplicated action definitions, duplicated `resource_path()`, debug `print()` statements) were resolved during Roadmap stage 1.
