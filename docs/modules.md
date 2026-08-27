# Modules Reference

This document describes every module of Simple Photo Editor in detail: its classes, key methods, attributes, and how they interact.

---

## 1. [`main.py`](../main.py) — Entry Point

The application bootstrap script. Runs only under `if __name__ == "__main__":`.

### Startup sequence

1. Configure logging: level from the `PHOTOEDITOR_LOGLEVEL` environment variable (default `WARNING`), format `время уровень [имя] сообщение`.
2. Create [`QApplication(sys.argv)`](../main.py) and set the window icon from `icons/icon.ico` (resolved via [`resource_path()`](../utils.py)).
4. Enable High-DPI attributes (`AA_EnableHighDpiScaling`, `AA_UseHighDpiPixmaps`) **before** creating the application — without them the UI (including MDI title bars) renders small and gets stretched blurry on scaled displays.
5. Load configuration with [`load_config()`](../utils.py).
6. Initialize the theme via [`theme.init_theme(app, config)`](../theme.py) (`General.theme`: `system`/`light` → system palette, `dark` → dark palette + inverted icons).
7. Instantiate [`MainWindow(config)`](../main_window.py).
8. Read persisted window geometry from the `General` section (`window_width`, `window_height`, defaulting to 800×600) and resize the window.
9. Show the window.
10. Open the initial image via [`window.openFile(path)`](../main_window.py): a command-line argument if one was given and exists, otherwise `General.last_opened_file` from the previous session (when the file still exists).
11. Enter the Qt event loop with `app.exec_()`.

### CLI usage

```bash
python main.py                    # reopens General.last_opened_file, if any
python main.py picture.png        # start and open picture.png
```

---

## 2. [`main_window.py`](../main_window.py) — Main Application Window

> All action icons are created through [`theme.icon(name)`](../theme.py) (each action also gets `objectName = "act_icon_<name>"`), so icons re-render — inverted in the dark theme — on live theme switches.

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
- [`closeEvent()`](../main_window.py) — persists `General.window_width/height`, `General.last_opened_file` (the active sub-window's path), `Editor.show_rulers` (the active editor's ruler state), and all `LastImageSettings` values, calls [`save_config()`](../utils.py), then iterates all MDI sub-windows; for each modified image shows a Save/Discard/Cancel prompt ([`confirmSave()`](../main_window.py)). Cancel aborts the shutdown.

#### Actions, menus, toolbars

[`createActions()`](../main_window.py) builds one `QAction` per operation with shortcut, icon, and tooltip:

| Group | Actions (shortcut) |
|-------|--------------------|
| File | New (Ctrl+N), Open (Ctrl+O), Save (Ctrl+S), Save As (Ctrl+Shift+S), Print (Ctrl+P), Scan (Ctrl+Shift+N), Exit (Ctrl+Q) |
| Edit | Undo (Ctrl+Z), Redo (Ctrl+Y), Cut (Ctrl+X), Copy (Ctrl+C), Paste (Ctrl+V), Crop (Ctrl+R), Select All (Ctrl+A) |
| View | Zoom In (Ctrl++), Zoom Out (Ctrl+-), Fit to Screen (Ctrl+0), Actual Size (Ctrl+1), Show Rulers |
| Settings | Theme → System / Light / Dark (radio group) |
| Image | Rotate 90° CW / CCW / 180°, Rotate… (precise), Crop, Resize…, Flip Horizontal/Vertical, Grayscale, Adjustments… |
| Window | Tile, Cascade, Next (Ctrl+Tab), Previous (Ctrl+Shift+Tab) |
| Tools | Selection Tool |
| Help | About |

[`createMenus()`](../main_window.py) arranges these into File / Edit / View / Image (with **Rotate** and **Flip** submenus) / Settings (with the **Theme** radio submenu) / Window / Help menus and inserts the Recent Files submenu into File.

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

#### Theme switching

- [`switchTheme(theme_name)`](../main_window.py) — live-switches the theme via [`theme.apply_theme()`](../theme.py), persists `General.theme` immediately, and refreshes the menu check marks.
- [`update_theme_menu_actions()`](../main_window.py) — syncs the Settings → Theme radio group with the config value.

#### Module-level helper

Icons and other resources are resolved via [`resource_path()`](../utils.py) imported from [`utils.py`](../utils.py) — see [Utilities layer](#9-utilspy--utilities). Action icons go through [`theme.icon()`](../theme.py) instead, which adds dark-theme inversion and caching.

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

- [`executeCommand(command)`](../editor.py) — runs `command.execute()`, appends to `undo_stack`, clears `redo_stack`, sets `is_modified = True`, then trims the stack to the class constant `UNDO_LIMIT` (20 commands, oldest dropped) to bound memory use.
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
- [`resizeImage(new_width, new_height, keep_aspect=True)`](../editor.py) — builds a [`ResizeCommand`](../commands.py) and runs it through [`executeCommand()`](../editor.py); the scaling itself happens inside the command's `execute()`.
- [`convertToGrayscale()`](../editor.py) — pushes a [`GrayscaleCommand`](../commands.py).
- [`cut(fill_color=None)`](../editor.py) — pushes a [`CutCommand`](../commands.py) with an optional fill color (white by default).
- [`paste()`](../editor.py) — reads the clipboard image, converts to `ARGB32`, pushes a [`PasteCommand`](../commands.py).

#### Live-preview mechanism (used by dialogs)

- [`start_preview()`](../editor.py) — snapshots `current_image` into `image_before_preview`.
- [`preview_rotation(angle)`](../editor.py) — shows a rotated preview without touching history.
- [`preview_adjustments(brightness, contrast, gamma, autobalance)`](../editor.py) — calls [`apply_adjustments_pipeline()`](../imageops.py) — the exact code path used by [`AdjustmentsCommand.execute()`](../commands.py) — on the pre-preview snapshot and shows the result without touching history.
- [`apply_rotation(degrees)`](../editor.py) / [`apply_adjustments(...)`](../editor.py) — commit the dialog result as a real command based on the pre-preview snapshot, then clear it.
- [`cancel_preview()`](../editor.py) — restores the snapshot.

#### Pasted items

- [`fixPastedItems()`](../editor.py) — builds a [`FixPasteCommand`](../commands.py) over the current floating items and runs it through [`executeCommand()`](../editor.py); the baking itself happens inside the command's `execute()`.
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

Module constant: `CV2_AVAILABLE` — whether OpenCV imported successfully (grayscale requires it). The shared corrections pipeline is imported from [`imageops.py`](../imageops.py).

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
| [`ResizeCommand(editor, new_width, new_height, keep_aspect=True)`](../commands.py) | Target size; `old_image` is snapshotted lazily on first `execute()` | Scales the current image via `QImage.scaled` (smooth; `KeepAspectRatio`/`IgnoreAspectRatio` from `keep_aspect`) and applies it through `_apply()` ([`setImage()`](../editor.py) + `fitInViewWithRulers`) | `undo()` re-applies `old_image`; `redo()` re-applies `new_image` — both refit the view |
| [`FixPasteCommand(editor, pasted_items)`](../commands.py) | The floating items and their positions; `old_image` is snapshotted lazily on first `execute()` | Bakes every item's pixmap into `current_image` with a `QPainter`, removes the items from the scene and from `editor.pasted_items` | `undo()` restores the old image and re-adds the items at their recorded positions; `redo()` re-runs `execute()` |

Design notes:

- Most commands snapshot the image **at construction time**, so undo is O(1) image swap. The exceptions are `ResizeCommand` and `FixPasteCommand`, which capture `old_image` lazily on the first `execute()` (Roadmap stage 3 contract: all mutation happens inside `execute()`).
- `original_image_override` lets the live-preview dialogs pass the pre-preview snapshot so that committing a dialog result doesn't double-apply previewed changes.
- Status-bar feedback is emitted from inside commands via `editor.window().statusBar()`.

Full behavior contracts are described in [Undo/Redo System](undo-redo.md).

---

## 6. [`imageops.py`](../imageops.py) — Shared Image-Processing Pipeline

A leaf module (imports only NumPy, PyQt5, and Pillow), introduced during Roadmap stage 3 to deduplicate ~100 lines of corrections code that previously existed in parallel copies in `commands.py` and `editor.py`.

### `apply_adjustments_pipeline(image, brightness=0.0, contrast=0.0, gamma=1.0, autobalance=False)`

Applies the corrections chain to a `QImage` and returns a **new** `QImage`; the input is never modified and the result is an independent copy in `Format_RGBA8888` (whose in-memory byte order R,G,B,A is platform-independent):

1. Convert to `Format_RGBA8888`.
2. `autobalance` — per-channel histogram stretching with a 5% clip threshold ([`_autobalance_rgba8888()`](../imageops.py)); the alpha channel is untouched.
3. Brightness / contrast — PIL `ImageEnhance` with factor `1.0 + value`.
4. Gamma — true power curve `((px/255) ** (1/gamma)) * 255` through a 256-entry NumPy LUT ([`_apply_gamma()`](../imageops.py)); alpha untouched.

Callers: [`AdjustmentsCommand.execute()`](../commands.py) (commit) and [`ImageEditor.preview_adjustments()`](../editor.py) (live preview) — a single implementation guarantees that the preview matches the committed result.

### Conversion helpers

- [`_qimage_to_ndarray_rgba(qimg)`](../imageops.py) — `QImage` → `ndarray (h, w, 4)`, dropping per-line padding.
- [`_qimage_to_pil(qimg)`](../imageops.py) / [`_pil_to_qimage(pil_img)`](../imageops.py) — lossless QImage ↔ PIL round-trip pinned to RGBA.

---

## 7. [`theme.py`](../theme.py) — Theme Management

Global theme state (light / dark; `system` resolves to light) with live switching and dark-aware icons.

### Functions

- [`init_theme(app, config)`](../theme.py) — startup entry point; reads `General.theme` and delegates to `apply_theme()`.
- [`apply_theme(app, name)`](../theme.py) — switches the `QApplication` palette (dark palette built by [`_dark_palette()`](../theme.py), light = the style's standard palette), then refreshes every action icon via [`_refresh_all_icons()`](../theme.py) and repaints all top-level widgets.
- [`icon(name)`](../theme.py) — returns a `QIcon` for `icons/<name>.png`; in the dark theme the pixels are inverted by [`_invert_image()`](../theme.py) (RGB → `255 - v`, alpha untouched) so dark icons stay readable on a dark background. Results are cached per `(name, theme)`.
- [`current_theme()`](../theme.py) / [`is_dark()`](../theme.py) — accessors for the global state.

### Icon refresh mechanism

Every themed action carries `objectName = "act_icon_<name>"` (set in [`createActions()`](../main_window.py)); on a theme switch `_refresh_all_icons()` walks all top-level widgets, finds these actions, and re-set their icons — no restart needed.

---

## 8. [`widgets.py`](../widgets.py) — Custom Widgets & Dialogs

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

- Constructor stores `main_window`, creates an [`EditorContainer`](../editor.py) as its widget, sets minimum size 200×150, and sizes itself to the MDI viewport minus a 50 px margin. It then applies the persisted `Editor.show_rulers` config value: when `true`, rulers are toggled on for the new sub-window via [`EditorContainer.toggleRulers()`](../editor.py).
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

## 9. [`utils.py`](../utils.py) — Utilities

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

## 10. Cross-Module Interactions Summary

| Interaction | Mechanism |
|-------------|-----------|
| Menu action → edit operation | `MainWindow` handler → `currentEditor()` → `ImageEditor` method → command |
| Selection → status bar | `ImageEditorScene.selectionChanged` signal → `ImageEditor.updateStatusBar` slot |
| Dialog → live preview | Dialog widgets → `ImageEditor.preview_*` methods (snapshot-based) |
| Dialog → commit | Dialog → `ImageEditor.apply_*` → `Command` → `executeCommand()` |
| Shared corrections pipeline | `AdjustmentsCommand.execute()` and `ImageEditor.preview_adjustments()` both call `imageops.apply_adjustments_pipeline()` |
| Floating paste → baked | Scene/editor mouse events → `fixMovableItem()` / `fixPastedItems()` → `FixPasteCommand` |
| Close → save prompt | `CustomMdiSubWindow.closeEvent` / `MainWindow.closeEvent` → `confirmSave()` → `saveFile()` |
| Config lifecycle | `main.py` load → `MainWindow` mutations → `closeEvent` → `save_config()` |

---

## 11. [`tests/`](../tests) — Test Suite (Stage 4)

Headless pytest suite; run with `python3 -m pytest` from the project root (configured by [`pytest.ini`](../pytest.ini)).

### [`conftest.py`](../tests/conftest.py) — fixtures & helpers

- Sets `QT_QPA_PLATFORM=offscreen` **before** importing PyQt5 — no X server required (CI-friendly).
- Adds the project root to `sys.path` so application modules import cleanly.
- [`make_gradient(w, h)`](../tests/conftest.py:24) — deterministic RGB gradient (`Format_RGB32`); R/G span the full 0–255 range so autobalance provably changes pixels.
- [`make_solid_image(w, h, rgb)`](../tests/conftest.py:42) — flat-color rectangle for paste tests.
- [`image_bytes(image)`](../tests/conftest.py:49) — pixel bytes in `Format_RGBA8888` (stride-aware) for exact byte-level image comparison.
- [`qapp`](../tests/conftest.py:66) — session-scoped `QApplication`.
- [`editor`](../tests/conftest.py:79) — `ImageEditor` with the gradient loaded, hosted in a bare `QMainWindow` (commands call `editor.window().statusBar()`); `updateWindowTitle()` exits early because the parent is not a `CustomMdiSubWindow`.

### [`test_commands.py`](../tests/test_commands.py) — undo/redo contracts

Every command is exercised through the full execute → undo → redo cycle with byte-level assertions:

- `CropCommand` — cropped bytes equal the source rect; undo restores exact bytes.
- `TransformCommand` — 90° rotation swaps W↔H and maps corner pixels correctly; horizontal flip; undo restores bytes.
- `AdjustmentsCommand` — brightness/contrast/gamma/autobalance each change the image and restore on undo; **redo is idempotent** (recomputed from the stored `original_image`).
- `CutCommand` — clipboard image equals the cut region; the hole is filled with `fill_color`; selection rect and handles are removed from the scene; no-op without a selection.
- `PasteCommand` — into selection (pixels replaced, no floating items) and as a floating `MovableImageItem` (canvas untouched, item at (10,10)); undo/redo manage `pasted_items`.
- `ResizeCommand` / `FixPasteCommand` — Stage-3 `execute()` contract: exact sizes, `keep_aspect` behavior, baking floating items and restoring them (with movable flags) on undo.
- `TestEditorHistory` — `executeCommand()` stack semantics, `UNDO_LIMIT = 20` eviction, new command clears the redo stack.

### [`test_utils.py`](../tests/test_utils.py) — MRU list

`add_recent_file()` / `get_recent_files()`: insertion order (most recent first), dedup (reopening moves to top), 5-entry cap (oldest evicted), non-existent and empty paths ignored, `file1…file5` key layout.
