# Modules Reference

This document describes every module of Simple Photo Editor in detail: its classes, key methods, attributes, and how they interact.

---

## 1. [`main.py`](../main.py) — Entry Point

The application bootstrap script. Runs only under `if __name__ == "__main__":`.

### Startup sequence

1. Configure logging: level from the `PHOTOEDITOR_LOGLEVEL` environment variable (default `WARNING`), format `время уровень [имя] сообщение`.
2. Create [`QApplication(sys.argv)`](../main.py) and set the window icon from `icons/icon.ico` (resolved via [`resource_path()`](../utils.py)).
3. Load configuration with [`load_config()`](../utils.py).
4. Instantiate [`MainWindow(config)`](../main_window.py).
5. Read persisted window geometry from the `General` section (`window_width`, `window_height`, defaulting to 800×600) and resize the window.
6. Show the window.
7. If a command-line argument was supplied and it is an existing file, open it immediately via [`window.openFile(file_path)`](../main_window.py).
8. Enter the Qt event loop with `app.exec_()`.

### CLI usage

```bash
python main.py                    # start with an empty workspace
python main.py picture.png        # start and open picture.png
```

---

## 2. [`main_window.py`](../main_window.py) — Main Application Window

### `MainWindow(QMainWindow)`

The top-level window. Owns the MDI area, all actions, menus, toolbars, and the application configuration object.

#### Key attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| `mdi_area` | `QMdiArea` | Central widget hosting all image sub-windows |
| `config` | `configparser.ConfigParser` | Live configuration tree (persisted on close) |
| `last_image_settings` | `dict` | Last used New Image parameters (width, height, dpi, units) |
| `recent_files_menu` | `QMenu` | Dynamic MRU submenu |
| `clipboard` | `QClipboard` | Application clipboard reference |
| `selection_tool_act` | `QAction` | Checkable selection-tool toggle |

#### Construction ([`__init__`](../main_window.py))

Sets title *"Simple Photo Editor"*, geometry 100,100,1000×800, creates the MDI area and status bar, then calls [`createActions()`](../main_window.py) → [`createMenus()`](../main_window.py) → [`createToolbars()`](../main_window.py), restores `LastImageSettings` from config (with fallback defaults 800/600/150/Pixels), rebuilds the recent-files menu, and enables drag-and-drop.

#### Window events

- [`dragEnterEvent()`](../main_window.py) / [`dropEvent()`](../main_window.py) — accept file URLs; image extensions (`.png .jpg .jpeg .bmp .gif .tiff`) are opened via [`openFile()`](../main_window.py).
- [`closeEvent()`](../main_window.py) — persists `General.window_width/height` and all `LastImageSettings` values, calls [`save_config()`](../utils.py), then iterates all MDI sub-windows; for each modified image shows a Save/Discard/Cancel prompt ([`confirmSave()`](../main_window.py)). Cancel aborts the shutdown.

#### Actions, menus, toolbars

[`createActions()`](../main_window.py) builds one `QAction` per operation with shortcut, icon, and tooltip:

| Group | Actions (shortcut) |
|-------|--------------------|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As (Ctrl+Shift+S), Print (Ctrl+P), Scan (Ctrl+Shift+N), Exit (Ctrl+Q) |
| Edit | Undo (Ctrl+Z), Redo (Ctrl+Y), Cut (Ctrl+X), Copy (Ctrl+C), Paste (Ctrl+V), Crop (Ctrl+R), Select All (Ctrl+A) |
| View | Zoom In (Ctrl++), Zoom Out (Ctrl+-), Fit to Screen (Ctrl+0), Actual Size (Ctrl+1), Show Rulers |
| Image | Rotate 90° CW / CCW / 180°, Rotate… (precise), Crop, Resize…, Flip Horizontal/Vertical, Grayscale, Adjustments… |
| Window | Tile, Cascade, Next (Ctrl+Tab), Previous (Ctrl+Shift+Tab) |
| Tools | Selection Tool |
| Help | About |

[`createMenus()`](../main_window.py) arranges these into File / Edit / View / Image (with **Rotate** and **Flip** submenus) / Window / Help menus and inserts the Recent Files submenu into File.

[`createToolbars()`](../main_window.py) builds five icon-only toolbars: File, Edit, View, Image, Tools.

[`update_recent_files_menu()`](../main_window.py) clears and repopulates the MRU submenu from [`get_recent_files()`](../utils.py); each entry stores the full path in action data and opens it on trigger.

#### File operations

- [`newFile()`](../main_window.py) — opens [`NewImageDialog`](../widgets.py) pre-filled with `last_image_settings`; on accept, maps the color-depth choice to a `QImage.Format` (`RGB32`, `Indexed8`, `Grayscale8`, `Mono`), sets DPI via `setDotsPerMeterX/Y(dpi * 39.37)`, fills the background (with special handling for palette and mono formats), creates a `CustomMdiSubWindow`, and fits the view.
- [`openFile(file_name=None)`](../main_window.py) — if no path given, shows `QFileDialog`; validates existence and loadability; loads via [`load_image_with_exif()`](../main_window.py) (Pillow `ImageOps.exif_transpose`, so phone photos open correctly oriented; falls back to plain `QImage` on failure); creates a sub-window, sets its title to `name (WxH) @ 100%`, moves it to the viewport's top-left, schedules `fitInViewWithRulers` after 100 ms, updates the MRU list and persists the config immediately.
- [`loadFile(file_path)`](../main_window.py) — alternative loader delegating to [`editor.openImage()`](../editor.py).
- [`saveFile(sub_window=None)`](../main_window.py) — saves the active image; asks for a path (PNG default filter) when the sub-window has none; uses `QImage.save()`; clears `is_modified` and updates the title.
- [`saveFileAs(sub_window=None)`](../main_window.py) — always asks for a path; first calls [`editor.applyAllPastedItems()`](../editor.py) so floating items are baked in; appends `.png` when no extension was given; for `.jpg/.jpeg/.webp` asks for quality (1–100, default 90) via `QInputDialog`; delegates the actual write to [`saveImageToFile()`](../main_window.py).
- [`printFile()`](../main_window.py) — `QPrintDialog`; paints the image scaled with `KeepAspectRatio` into the printer viewport.
- [`scanImage()`](../main_window.py) — Windows-only WIA workflow: COM init → device selection → DPI prompt (`QInputDialog.getInt`, 75–1200 step 75) → set horizontal/vertical resolution properties (6147/6148) and color mode (6146) → `Transfer()` → load binary data into `QImage` → new sub-window titled `Scanned Image (N DPI)`. Guarded by `WIA_AVAILABLE`.

#### Edit/view dispatchers

All of the following resolve the active editor through [`currentEditor()`](../main_window.py) (the active MDI sub-window's `editor_container.editor`) and delegate:

[`undo()`](../main_window.py), [`redo()`](../main_window.py), [`cut()`](../main_window.py), [`paste()`](../main_window.py), [`zoomIn()`](../main_window.py), [`zoomOut()`](../main_window.py), [`fitToScreen()`](../main_window.py), [`actualSize()`](../main_window.py), [`rotateImage(degrees)`](../main_window.py), [`flipImage(horizontal)`](../main_window.py), [`convertToGrayscale()`](../main_window.py).

Handlers with local logic:

- [`copy()`](../main_window.py) — validates the selection rect, copies the region to the clipboard.
- [`selectAll()`](../main_window.py) — replaces the selection with a dashed rect covering the whole image and emits `selectionChanged`.
- [`cropImage()`](../main_window.py) — validates the selection, builds a [`CropCommand`](../commands.py), executes it via [`editor.executeCommand()`](../editor.py), then removes the selection rectangle and handles.
- [`resizeImage()`](../main_window.py) — opens [`ResizeDialog`](../widgets.py) with current dimensions; on accept calls [`editor.resizeImage(width, height, keep_aspect)`](../editor.py).
- [`openPreciseRotationDialog()`](../main_window.py) — opens [`RotationDialog`](../widgets.py); on accept calls [`editor.apply_rotation(angle)`](../editor.py).
- [`showAdjustmentsDialog()`](../main_window.py) — opens [`AdjustmentsDialog`](../widgets.py).
- [`toggleRulers()`](../main_window.py) — flips `editor.rulers_visible` through [`EditorContainer.toggleRulers()`](../editor.py).
- [`activateSelectionTool()`](../main_window.py) / [`setTool(name)`](../main_window.py) — set `scene.current_tool` and switch the view's drag mode to `NoDrag`.
- [`about()`](../main_window.py) — "About" message box.

#### Module-level helper

Icons and other resources are resolved via [`resource_path()`](../utils.py) imported from [`utils.py`](../utils.py) — see [Utilities layer](#7-utilspy--utilities).

---

## 3. [`editor.py`](../editor.py) — Image Editor View & Container

### `ImageEditor(QGraphicsView)`

The per-image editing widget. One instance lives inside each `EditorContainer`.

#### Key attributes

| Attribute | Purpose |
|-----------|---------|
| `scene` | The associated [`ImageEditorScene`](../scene.py) |
| `image_item` | `QGraphicsPixmapItem` displaying `current_image` |
| `original_image` / `current_image` | `QImage` snapshots (original = state at load) |
| `zoom_factor` | Current scale (1.0 = 100%) |
| `rulers_visible` | Whether rulers are shown (drives `fitInViewWithRulers`) |
| `pasted_items` | List of floating [`MovableImageItem`](../scene.py) objects |
| `undo_stack` / `redo_stack` | Command history lists |
| `is_modified` | Dirty flag (drives the `*` title marker and close prompts) |
| `ruler_width` | Ruler thickness in pixels (30) |
| `cursor_pos` | Last known cursor position in scene coordinates |
| `image_before_preview` | Snapshot used by the live-preview mechanism |

#### View configuration ([`__init__`](../editor.py))

Antialiasing + smooth pixmap transform rendering, `ScrollHandDrag` mode, full viewport updates, as-needed scroll bars, `AnchorUnderMouse` transformation and resize anchors. Connects `scene.selectionChanged` → [`updateStatusBar()`](../editor.py).

#### Image lifecycle

- [`setImage(image, keep_view=False)`](../editor.py) — central setter: stores the image, refreshes `original_image`, lazily creates `image_item`, updates the pixmap and scene rect. With `keep_view=False` (new image) resets zoom, clears `is_modified` and refits the view; with `keep_view=True` (edits, undo/redo) the current zoom and scroll position are preserved.
- [`loadImage(path)`](../editor.py) / [`openImage(file_name)`](../editor.py) — load from disk; `openImage` additionally clears both history stacks and the modified flag.
- [`getCurrentImage()`](../editor.py) — accessor used by commands and dialogs.
- [`getSelectedRegion()`](../editor.py) / [`setSelectedRegion(image)`](../editor.py) — read/replace the pixels under the selection rectangle.

#### Command execution & history

- [`executeCommand(command)`](../editor.py) — runs `command.execute()`, appends to `undo_stack`, clears `redo_stack`, sets `is_modified = True`.
- [`undo()`](../editor.py) / [`redo()`](../editor.py) — move a command between the stacks and invoke its `undo()`/`redo()`; update the modified flag, window title, scene, and viewport.

#### Zoom & navigation

- [`zoomIn()`](../editor.py) / [`zoomOut()`](../editor.py) — multiply/divide `zoom_factor` by 1.25 and re-apply the transform.
- [`actualSize()`](../editor.py) — reset to 1:1.
- [`fitInViewWithRulers()`](../editor.py) — fits the scene rect into the viewport (minus ruler margins when visible) and recomputes `zoom_factor` from `transform().m11()`.
- [`resetView()`](../editor.py) — plain fit.
- [`adjustTickSpacing(spacing)`](../editor.py) — snaps an arbitrary tick spacing to 1/2/5×10ⁿ for ruler rendering.
- [`resizeEvent()`](../editor.py) — repaints without resetting zoom.

#### Edit operations (command factories)

- [`rotateImage(degrees)`](../editor.py) — builds a [`TransformCommand`](../commands.py) from a fresh copy of the current image.
- [`flipImage(horizontal=True)`](../editor.py) — `TransformCommand` with `horizontal_flip`.
- [`resizeImage(new_width, new_height, keep_aspect=True)`](../editor.py) — scales via `QImage.scaled` (`KeepAspectRatio` or `IgnoreAspectRatio`, smooth transform), updates scene rect, pushes a [`ResizeCommand`](../commands.py); caps the undo stack at 10 entries.
- [`convertToGrayscale()`](../editor.py) — pushes a [`GrayscaleCommand`](../commands.py).
- [`cut(fill_color=None)`](../editor.py) — pushes a [`CutCommand`](../commands.py) with an optional fill color (white by default).
- [`paste()`](../editor.py) — reads the clipboard image, converts to `ARGB32`, pushes a [`PasteCommand`](../commands.py).

#### Live-preview mechanism (used by dialogs)

- [`start_preview()`](../editor.py) — snapshots `current_image` into `image_before_preview`.
- [`preview_rotation(angle)`](../editor.py) — shows a rotated preview without touching history.
- [`preview_adjustments(brightness, contrast, gamma, autobalance)`](../editor.py) — applies the same pipeline as [`AdjustmentsCommand.execute()`](../commands.py) (autobalance via per-channel histogram stretching with a 5% threshold, PIL `ImageEnhance` brightness/contrast, and a true power-curve gamma via a NumPy LUT `((px/255) ** (1/gamma)) * 255`) directly to the display.
- [`apply_rotation(degrees)`](../editor.py) / [`apply_adjustments(...)`](../editor.py) — commit the dialog result as a real command based on the pre-preview snapshot, then clear it.
- [`cancel_preview()`](../editor.py) — restores the snapshot.

#### Pasted items

- [`fixPastedItems()`](../editor.py) — bakes all floating items into `current_image` with a `QPainter`, removes them from the scene, and records a [`FixPasteCommand`](../commands.py).
- [`applyAllPastedItems()`](../editor.py) — same, via [`scene.fixMovableItem()`](../scene.py); called before saving.
- [`mousePressEvent()`](../editor.py) — clicking empty space (no selected items) while floating items exist triggers [`fixPastedItems()`](../editor.py).

#### UI feedback

- [`updateStatusBar(rect)`](../editor.py) — shows `Selection: WxH at (X, Y)` in the main window's status bar.
- [`updateWindowTitle()`](../editor.py) — rebuilds the sub-window title as `name[*] (WxH) @ Z%` (walks up `parent().parent()` to reach the `CustomMdiSubWindow`).
- [`mouseMoveEvent()`](../editor.py) / [`leaveEvent()`](../editor.py) — track `cursor_pos` for the ruler cursor indicator and refresh rulers.
- [`scrollContentsBy()`](../editor.py) — refreshes ruler layout while scrolling.

### `EditorContainer(QWidget)`

Grid composition of one `ImageEditor` with rulers:

```
┌────────┬──────────────────────┐
│ corner │  top_ruler (horiz.)  │
├────────┼──────────────────────┤
│ left   │                      │
│ ruler  │      ImageEditor     │
│ (vert.)│                      │
└────────┴──────────────────────┘
```

- [`toggleRulers(visible)`](../editor.py) — shows/hides both rulers and the corner widget, refits the editor view, and refreshes ruler geometry.
- [`updateRulerLayout()`](../editor.py) — keeps ruler lengths equal to container size minus `ruler_width`.
- [`resizeEvent()`](../editor.py) — re-runs the ruler layout on resize.


---

## 4. [`scene.py`](../scene.py) — Interactive Scene

### `ImageEditorScene(QGraphicsScene)`

Custom scene providing selection and item interaction on top of the displayed image.

#### State

| Attribute | Purpose |
|-----------|---------|
| `current_tool` | Active tool name (`"selection"`) |
| `selection_rect` | `QGraphicsRectItem` for the current selection |
| `selecting` / `start_pos` | Rubber-band drag state |
| `handles` / `active_handle` | Eight resize handles + the one being dragged |
| `dash_offset` / `dash_timer` | Animated "marching ants" dash offset (100 ms timer) |

#### Signal

[`selectionChanged = pyqtSignal(QRectF)`](../scene.py) — emitted whenever the selection is created or resized; consumed by [`ImageEditor.updateStatusBar()`](../editor.py).

#### Methods

- [`updateDash()`](../scene.py) — advances the dash offset for the selection pen animation.
- [`createHandles()`](../scene.py) — (re)creates 8 red square handles (corners + edge midpoints) sized adaptively from the image size (`max(12, min(30, img_size // 150))`), each flagged movable with a `handle_type` stored in item data and `ZValue` 200.
- [`updatePenWidth()`](../scene.py) — scales the dashed pen width with image size (`max(2, min(5, img_size // 1000))`).
- [`fixMovableItem(item, editor)`](../scene.py) — draws a floating item's pixmap onto `editor.current_image` at its position, calls [`editor.setImage()`](../editor.py), marks modified.
- [`mousePressEvent()`](../main_window.py) — if a handle was clicked, marks it active; otherwise fixes any selected floating items, clears the previous selection and handles, and starts a new rubber-band selection.
- [`mouseMoveEvent()`](../scene.py) — drags the active handle (clamped to the scene rect, rect re-normalized) or extends the rubber band; emits `selectionChanged`.
- [`mouseReleaseEvent()`](../scene.py) — finalizes the selection by (re)creating handles.

### `MovableImageItem(QGraphicsPixmapItem)`

A floating pasted image:

- Smooth transformation, movable + selectable flags, `SizeAllCursor`, `ZValue` 100 (above the base image, below handles).
- [`mouseMoveEvent()`](../scene.py) — constrains the item inside the scene rect.
- [`mousePressEvent()`](../scene.py) / [`mouseReleaseEvent()`](../scene.py) — keep the item selected on left-click.

---

## 5. [`commands.py`](../commands.py) — Command Pattern

Module constant: `CV2_AVAILABLE` — whether OpenCV imported successfully (grayscale requires it).

### `Command` (base)

Interface with no-op [`execute()`](../commands.py), [`undo()`](../commands.py); concrete classes add `redo()`.

### Concrete commands

| Class | Init captures | `execute()` | `undo()` / `redo()` |
|-------|---------------|-------------|---------------------|
| [`CropCommand(editor, rect)`](../commands.py) | Snapshot of the image | `QImage.copy(rect)` → [`setImage()`](../editor.py) + status message | Restore snapshot / re-execute |
| [`AdjustmentsCommand(editor, brightness, contrast, gamma, autobalance, original_image_override)`](../commands.py) | Snapshot (or override) | Autobalance (NumPy per-channel histogram stretch, 5% clip threshold) → PIL brightness/contrast → true gamma via NumPy LUT `((px/255) ** (1/gamma)) * 255` → `setImage(keep_view=True)` | Restore snapshot / re-execute |
| [`TransformCommand(editor, degrees=None, horizontal_flip=None, original_image_override)`](../commands.py) | Snapshot (or override) | `QTransform().rotate(degrees)` with `SmoothTransformation`, or `mirrored(horizontal, not horizontal)` | Restore snapshot / re-execute |
| [`GrayscaleCommand(editor)`](../commands.py) | Snapshot | Converts to `RGBA8888`, `cv2.cvtColor(RGBA2GRAY)` then back to RGBA; warns if cv2 missing | Restore snapshot / re-execute |
| [`PasteCommand(editor, clipboard_image)`](../commands.py) | Snapshot, selection rect, prior pasted items | With selection: paints the clipboard image at the selection's top-left. Without: creates a [`MovableImageItem`](../scene.py) at (10, 10), fixes any currently selected floating items first, selects the new item | Selection case: restore snapshot. Floating case: remove item, restore prior items and snapshot |
| [`CutCommand(editor, fill_color=None)`](../commands.py) | Snapshot, selection rect | Copies the region to the clipboard, fills it with `fill_color` (white by default), removes selection + handles | Restore snapshot |
| [`ResizeCommand(editor, old_image, new_image)`](../commands.py) | Both images | — (applied by the editor) | `undo()`/`redo()` swap `current_image`, pixmap, scene rect, and refit the view |
| [`FixPasteCommand(editor, old_image, new_image, pasted_items)`](../commands.py) | Images, items, positions | — (applied by the editor) | `undo()` restores the old image and re-adds the floating items at their positions; `redo()` bakes the new image and removes the items |

Design notes:

- Every command snapshots the image **at construction time**, so undo is O(1) image swap.
- `original_image_override` lets the live-preview dialogs pass the pre-preview snapshot so that committing a dialog result doesn't double-apply previewed changes.
- Status-bar feedback is emitted from inside commands via `editor.window().statusBar()`.

Full behavior contracts are described in [Undo/Redo System](undo-redo.md).

---

## 6. [`widgets.py`](../widgets.py) — Custom Widgets & Dialogs

### `RulerWidget(QWidget)`

Renders one ruler beside the editor.

- Constructor takes the owning `editor` and `orientation` (`"horizontal"` / `"vertical"`); colors: background `#C8C8C8`, ticks dark gray, labels black; thickness 30 px.
- [`paintEvent()`](../widgets.py):
  1. Skips painting when no image is loaded.
  2. Maps the viewport rect into scene coordinates to find the visible range.
  3. Computes tick spacing for ~50 px on screen, snapped via [`editor.adjustTickSpacing()`](../editor.py).
  4. Draws major ticks with integer labels (vertical labels rotated −90°) and 4 minor subdivisions per interval.
  5. Draws a red 2-px cursor indicator at [`editor.cursor_pos`](../editor.py) when inside the visible range.

### `CustomMdiSubWindow(QMdiSubWindow)`

MDI child window:

- Constructor stores `main_window`, creates an [`EditorContainer`](../editor.py) as its widget, sets minimum size 200×150, and sizes itself to the MDI viewport minus a 50 px margin.
- [`closeEvent()`](../widgets.py) — when the editor `is_modified`, asks Save/Discard/Cancel; Save delegates to [`main_window.saveFile()`](../main_window.py) and cancels closing on failure.

### `NewImageDialog(QDialog)`

Fields: width, height, units combo (Pixels / Centimeters / Inches), DPI, color depth combo (24-bit color / 8-bit palette / 8-bit grayscale / 1-bit monochrome), background color picker ([`choose_bg_color()`](../widgets.py) with live swatch via [`update_bg_color_label()`](../widgets.py)).

[`getImageParameters()`](../widgets.py) converts units to pixels (cm: `size * dpi / 2.54`; in: `size * dpi`) and returns `(pixel_width, pixel_height, dpi, bg_color, color_depth, raw_width, raw_height, units)` — raw values are kept so the config can restore exactly what the user typed.

### `AdjustmentsDialog(QDialog)`

Live-preview adjustments dialog:

- Sliders: brightness −100…100, contrast −100…100, gamma 1…500 (displayed /100); checkable **Autobalance** button.
- Every change calls [`previewAdjustments()`](../widgets.py), which debounces the recomputation through a single-shot `QTimer` (80 ms) before calling [`editor.preview_adjustments()`](../editor.py) (the editor snapshots first via [`start_preview()`](../editor.py) in the dialog constructor).
- OK → [`applyAdjustments()`](../widgets.py) → [`editor.apply_adjustments()`](../editor.py) (commits an [`AdjustmentsCommand`](../commands.py)).
- Cancel → [`reject_dialog()`](../widgets.py) → [`editor.cancel_preview()`](../editor.py).

### `ResizeDialog(QDialog)`

Fields: width, height, percent (default 100), and a *Keep Aspect Ratio* checkbox (default on).

- [`updateAspectRatio()`](../widgets.py) — when ratio lock is on, editing width/height recomputes the partner field; editing percent scales both original dimensions.
- [`updateFromPercent()`](../widgets.py) — percent-driven recalculation.
- [`updatePercent()`](../widgets.py) — recomputes the percent field from the current width.
- [`getNewSize()`](../widgets.py) — returns `(width, height, keep_aspect)`.

### `RotationDialog(QDialog)`

Precise rotation with live preview:

- `QSpinBox` (−180…180) and a horizontal slider kept in sync ([`update_slider_from_spinbox()`](../widgets.py) / [`update_spinbox_from_slider()`](../widgets.py)).
- `sliderMoved` → [`live_preview_rotation()`](../widgets.py) → debounced through a single-shot `QTimer` (80 ms) → [`editor.preview_rotation()`](../editor.py).
- OK → caller reads [`get_angle()`](../widgets.py) and calls [`editor.apply_rotation()`](../editor.py); Cancel → [`reject_dialog()`](../widgets.py) restores the snapshot.

---

## 7. [`utils.py`](../utils.py) — Utilities

### Configuration

- [`get_user_config_path()`](../utils.py) — returns `<appdirs user_config_dir>/Photoed/YourCompany/config.ini`, creating the directory if needed.
- [`load_config()`](../utils.py) — reads the user config if present; otherwise seeds defaults from a bundled `config.ini` (via [`resource_path()`](../utils.py)), injects missing sections (`General`: theme/window size; `Editor`: default_zoom/show_rulers; `RecentFiles`: empty), saves to the user path, and returns the parser.
- [`save_config(config)`](../utils.py) — writes the parser to the user config path; failures are printed, not raised.

### Resources

- [`resource_path(relative_path)`](../utils.py) — resolves against `sys._MEIPASS` under PyInstaller, else against the current directory.

### Recent files (MRU)

- [`add_recent_file(config, file_path)`](../utils.py) — ignores missing paths; moves duplicates to the front; caps the list at 5; rewrites the `RecentFiles` section as `file1…file5`. The caller ([`MainWindow.openFile()`](../main_window.py)) persists the config immediately after the call.
- [`get_recent_files(config)`](../utils.py) — returns up to 5 entries, filtered to files that still exist.

See [Configuration](configuration.md) for the full INI schema.

---

## 8. Cross-Module Interactions Summary

| Interaction | Mechanism |
|-------------|-----------|
| Menu action → edit operation | `MainWindow` handler → `currentEditor()` → `ImageEditor` method → command |
| Selection → status bar | `ImageEditorScene.selectionChanged` signal → `ImageEditor.updateStatusBar` slot |
| Dialog → live preview | Dialog widgets → `ImageEditor.preview_*` methods (snapshot-based) |
| Dialog → commit | Dialog → `ImageEditor.apply_*` → `Command` → `executeCommand()` |
| Floating paste → baked | Scene/editor mouse events → `fixMovableItem()` / `fixPastedItems()` → `FixPasteCommand` |
| Close → save prompt | `CustomMdiSubWindow.closeEvent` / `MainWindow.closeEvent` → `confirmSave()` → `saveFile()` |
| Config lifecycle | `main.py` load → `MainWindow` mutations → `closeEvent` → `save_config()` |
