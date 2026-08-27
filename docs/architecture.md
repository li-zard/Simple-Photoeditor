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
   │              │                │
   │              ├──► widgets.py ─┘
   │              ├──► commands.py ──► imageops.py
   │              ├──► theme.py ──► utils.py (deferred)
   │              └──► utils.py
   └──► utils.py

(commands.py also imports editor.py and scene.py at module level;
 editor.py breaks the resulting cycles with deferred, inside-method
 imports of commands.py / imageops.py / widgets.py.)
```

Key points:

- [`main.py`](../main.py) imports [`MainWindow`](../main_window.py) and config helpers from [`utils.py`](../utils.py).
- [`main_window.py`](../main_window.py) imports the editor ([`editor.py`](../editor.py)), dialogs and sub-window ([`widgets.py`](../widgets.py)), [`CropCommand`](../commands.py), and config utilities.
- [`scene.py`](../scene.py) imports no project module (the unused `ImageEditor` import was removed during Roadmap stage 3).
- [`commands.py`](../commands.py) imports [`ImageEditor`](../editor.py), [`MovableImageItem`](../scene.py), and the shared pipeline from [`imageops.py`](../imageops.py) at module level.
- [`editor.py`](../editor.py) sits at the center of the import cycles (commands ↔ editor, widgets ↔ editor), so it defers its imports of `commands.py`, `imageops.py`, and `widgets.py` into method bodies.
- [`widgets.py`](../widgets.py) imports [`ImageEditor`](../editor.py)/[`EditorContainer`](../editor.py) and [`AdjustmentsCommand`](../commands.py).
- [`imageops.py`](../imageops.py) and [`theme.py`](../theme.py) are leaf modules (NumPy/PyQt5/Pillow only), reusable and testable in isolation; `theme.py` defers its `utils` import into [`icon()`](../theme.py).

## 3. Layers and Responsibilities

### 3.1 Application layer — [`main.py`](../main.py)

- Enables High-DPI attributes (`AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`) before creating the [`QApplication`](../main.py) — prevents blurry stretched rendering (including MDI title bars) on scaled displays; sets the window icon.
- Loads configuration via [`load_config()`](../utils.py).
- Initializes the theme via [`theme.init_theme()`](../theme.py) (`General.theme`: `system`/`light` → system palette, `dark` → dark palette + inverted icons).
- Instantiates [`MainWindow`](../main_window.py), applies persisted window size, opens the CLI-argument file or — in its absence — `General.last_opened_file` from the previous session, and starts the event loop.

### 3.2 Application UI layer — [`main_window.py`](../main_window.py)

[`MainWindow`](../main_window.py) owns everything the user sees at the top level:

- **Actions** — one [`QAction`](../main_window.py) per operation (New, Open, Save, Print, Scan, Undo, Redo, Cut, Copy, Paste, Crop, Resize, Select All, Zoom In/Out, Fit, Actual Size, Rulers, Rotate, Flip, Grayscale, Adjustments, Tile, Cascade, Next, Previous, Selection Tool, About). Each action binds a keyboard shortcut, an icon from `icons/`, and a handler method.
- **Menus** — File, Edit, View, Image (with Rotate/Flip submenus), Settings (with the **Theme** radio submenu: System/Light/Dark), Window, Help, plus a dynamic **Recent Files** submenu rebuilt by [`update_recent_files_menu()`](../main_window.py).
- **Theme switching** — [`switchTheme()`](../main_window.py) live-applies the palette and inverted icons via [`theme.apply_theme()`](../theme.py) and persists `General.theme` immediately.
- **Toolbars** — File, Edit, View, Image, Tools.
- **File operations** — [`newFile()`](../main_window.py) (with [`NewImageDialog`](../widgets.py)), [`openFile()`](../main_window.py) (dialog or direct path, also used by drag-and-drop and recent files), [`saveFile()`](../main_window.py)/[`saveFileAs()`](../main_window.py), [`printFile()`](../main_window.py) (QPrinter), [`scanImage()`](../main_window.py) (WIA on Windows).
- **Edit dispatching** — most Edit/Image handlers resolve the active editor via [`currentEditor()`](../main_window.py) and delegate to it.
- **Shutdown** — [`closeEvent()`](../main_window.py) persists window size, `last_opened_file`, ruler visibility, and last-image settings, then walks all MDI sub-windows asking to save unsaved work.

### 3.3 Editor layer — [`editor.py`](../editor.py)

- [`ImageEditor`](../editor.py) (a `QGraphicsView`) is the per-image editing surface:
  - Holds `current_image` / `original_image` (`QImage`), the `image_item` (`QGraphicsPixmapItem`), zoom factor, modification flag, and the undo/redo stacks.
  - [`setImage(image, keep_view=False)`](../editor.py) is the single entry point for putting a `QImage` on screen. New images (`keep_view=False`) reset zoom, refit the view and clear the modified flag; edits and undo/redo (`keep_view=True`) preserve the current zoom and scroll position.
  - Zoom/navigation: [`zoomIn()`](../editor.py), [`zoomOut()`](../editor.py), [`actualSize()`](../editor.py), [`fitInViewWithRulers()`](../editor.py).
  - Command execution: [`executeCommand()`](../editor.py) runs a command, pushes it onto the undo stack, and trims the stack to `UNDO_LIMIT` (20).
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

All destructive operations are encapsulated as command objects (see [Undo/Redo System](undo-redo.md)). Since Roadmap stage 3 every command performs its mutation inside `execute()` and delegates pixel math to [`imageops.py`](../imageops.py):

| Command | Operation |
|---------|-----------|
| [`CropCommand`](../commands.py) | Crop to the selection rectangle |
| [`AdjustmentsCommand`](../commands.py) | Brightness / contrast / gamma / auto-levels |
| [`TransformCommand`](../commands.py) | Rotation (arbitrary angle) and mirroring |
| [`GrayscaleCommand`](../commands.py) | RGBA → grayscale via OpenCV |
| [`PasteCommand`](../commands.py) | Paste clipboard image (into selection or as movable item) |
| [`CutCommand`](../commands.py) | Cut selection to clipboard (fills with a configurable color, white by default) |
| [`ResizeCommand`](../commands.py) | Image rescaling |
| [`FixPasteCommand`](../commands.py) | Bake floating pasted items into the base image |

### 3.6 Image processing layer — [`imageops.py`](../imageops.py)

- [`apply_adjustments_pipeline(image, brightness, contrast, gamma, autobalance)`](../imageops.py) — the single implementation of the corrections chain (autobalance → brightness → contrast → gamma), shared by [`AdjustmentsCommand.execute()`](../commands.py) and [`ImageEditor.preview_adjustments()`](../editor.py) so the live preview always matches the committed result.
- Helpers: per-channel histogram stretching with a 5% clip ([`_autobalance_rgba8888()`](../imageops.py)), true power-curve gamma via a NumPy LUT ([`_apply_gamma()`](../imageops.py)), and QImage ↔ PIL conversions pinned to the platform-independent `Format_RGBA8888` byte order.

### 3.7 Widgets & dialogs layer — [`widgets.py`](../widgets.py)

- [`RulerWidget`](../widgets.py) — custom-painted horizontal/vertical ruler with adaptive tick spacing and a red cursor indicator.
- [`CustomMdiSubWindow`](../widgets.py) — MDI child window hosting an `EditorContainer`; applies the persisted `Editor.show_rulers` setting to new windows and intercepts close to prompt for unsaved changes.
- [`NewImageDialog`](../widgets.py) — width/height/units (px/cm/in)/DPI/color depth/background color.
- [`AdjustmentsDialog`](../widgets.py) — live-preview sliders for brightness/contrast/gamma plus an autobalance toggle.
- [`ResizeDialog`](../widgets.py) — width/height/percent fields with linked aspect-ratio logic.
- [`RotationDialog`](../widgets.py) — spinbox + slider (-180…180°) with live rotation preview.

### 3.8 Utilities layer — [`utils.py`](../utils.py)

- [`get_user_config_path()`](../utils.py) — per-user config directory via `appdirs`.
- [`resource_path()`](../utils.py) — resource resolution that works both in development and under PyInstaller (`sys._MEIPASS`).
- [`load_config()`](../utils.py) / [`save_config()`](../utils.py) — INI read/write with default-section seeding.
- [`add_recent_file()`](../utils.py) / [`get_recent_files()`](../utils.py) — MRU list (max 5 entries, existence-checked on read).

## 4. Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **Command** | [`commands.py`](../commands.py), [`executeCommand()`](../editor.py) | Encapsulates each edit as an object with `execute/undo/redo`; bounded history (`UNDO_LIMIT` = 20) |
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
   ├─ save_config(config)                                  # persist MRU immediately
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
   │     ├─ editor.redo_stack.clear()      # new branch invalidates redo history
   │     ├─ editor.is_modified = True
   │     └─ trim undo_stack to UNDO_LIMIT (20)   # oldest commands dropped
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
   ├─ persist General.last_opened_file      # active sub-window's path
   ├─ persist Editor.show_rulers            # active editor's ruler state
   ├─ persist LastImageSettings.*
   ├─ save_config(config)                  # utils.py → user config dir
   └─ for each MDI sub-window with is_modified:
        └─ confirmSave() → save / discard / cancel
```

## 6. Error Handling & Robustness Notes

- Optional dependencies degrade gracefully: `cv2` (grayscale) and WIA/`win32com` (scanning) are wrapped in try/except imports with `CV2_AVAILABLE` / `WIA_AVAILABLE` flags; the UI shows a warning instead of crashing.
- File operations validate existence and `QImage.isNull()` before use; save failures raise user-visible error dialogs.
- Config save failures are caught and printed rather than aborting shutdown.
- Undo history is bounded: [`executeCommand()`](../editor.py) trims `undo_stack` to the class constant `UNDO_LIMIT` (20 commands, oldest dropped), keeping memory use predictable in long sessions.

## 7. Known Quirks (documented behavior)

- The `os` and `sys` entries in the repository root are files, not directories.
- Logging is configured in [`main.py`](../main.py) via the `PHOTOEDITOR_LOGLEVEL` environment variable (default `WARNING`); loggers are named `photoeditor.<module>`.

> Historical quirks (dead code in `editor.py`, duplicated action definitions, duplicated `resource_path()`, debug `print()` statements) were resolved during Roadmap stage 1.

> Behavioral quirks (zoom reset on edits, fake gamma via `ImageEnhance.Brightness`, MRU lost on crash, missing EXIF orientation, no JPEG quality control, unthrottled live preview, hardcoded Cut fill color) were resolved during Roadmap stage 2.

> Architectural quirks (duplicated adjustments pipeline, resize/paste-fix mutations outside `execute()`, unbounded undo history, dead config keys `theme`/`show_rulers`/`last_opened_file`, unused import in `scene.py`) were resolved during Roadmap stage 3.
