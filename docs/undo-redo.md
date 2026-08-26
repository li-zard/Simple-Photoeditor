# Undo/Redo System

Simple Photo Editor implements unlimited (per-stack) undo/redo using the **Command design pattern** with two stacks held by each [`ImageEditor`](../editor.py) instance.

## 1. Core Idea

Every image mutation is encapsulated in a command object that knows how to:

1. **execute** — apply the change,
2. **undo** — restore the pre-change state,
3. **redo** — re-apply the change (usually by re-running `execute()`).

Commands snapshot the image data **at construction time**, which makes undo a constant-time image swap regardless of how expensive the operation was.

## 2. The Stacks

Defined in [`ImageEditor.__init__`](../editor.py):

```python
self.undo_stack = []   # executed commands, most recent last
self.redo_stack = []   # undone commands awaiting redo
```

### Executing a command — [`executeCommand()`](../editor.py)

```
editor.executeCommand(command)
    ├─ command.execute()
    ├─ undo_stack.append(command)
    ├─ redo_stack.clear()          # a new branch invalidates the redo history
    └─ is_modified = True
```

### Undo — [`undo()`](../editor.py)

```
editor.undo()
    ├─ command = undo_stack.pop()
    ├─ redo_stack.append(command)
    ├─ command.undo()
    ├─ is_modified = bool(undo_stack)   # clean only when history is empty
    └─ refresh title / scene / viewport + status message
```

### Redo — [`redo()`](../editor.py)

```
editor.redo()
    ├─ command = redo_stack.pop()
    ├─ undo_stack.append(command)
    ├─ command.redo()
    ├─ is_modified = True
    └─ refresh title / scene / viewport + status message
```

Both are triggered from the Edit menu / toolbar via [`MainWindow.undo()`](../main_window.py) and [`MainWindow.redo()`](../main_window.py), which delegate to the active editor.

## 3. Command Catalog

All commands live in [`commands.py`](../commands.py) and derive from the [`Command`](../commands.py) base class (no-op `execute`/`undo`).

| Command | Trigger | What `execute()` does | What `undo()` restores |
|---------|---------|----------------------|------------------------|
| [`CropCommand`](../commands.py) | Edit → Crop (Ctrl+R) | Crops to the selection rect via `QImage.copy(rect)` | Full original image |
| [`AdjustmentsCommand`](../commands.py) | Image → Adjustments… (OK) | Autobalance + brightness/contrast/gamma pipeline | Pre-adjustment image |
| [`TransformCommand`](../commands.py) | Rotate/Flip menu items, Rotation dialog (OK) | `QTransform` rotation (smooth) or `mirrored()` flip | Pre-transform image |
| [`GrayscaleCommand`](../commands.py) | Image → Grayscale | OpenCV `RGBA2GRAY` → `GRAY2RGBA` | Color image |
| [`CutCommand`](../commands.py) | Edit → Cut (Ctrl+X) | Copies selection to clipboard, fills it with white, clears selection UI | Original image (selection is not re-created) |
| [`PasteCommand`](../commands.py) | Edit → Paste (Ctrl+V) | Into selection: paints clipboard image. No selection: adds a floating [`MovableImageItem`](../scene.py) | Selection case: original image. Floating case: removes the item and restores prior floating items + image |
| [`ResizeCommand`](../commands.py) | Image → Resize… (OK) | *(applied by the editor before pushing)* | Swaps back `old_image`, restores scene rect, refits view |
| [`FixPasteCommand`](../commands.py) | Clicking empty canvas / saving with floating items | *(applied by the editor)* | Restores old image and re-adds the floating items at their recorded positions |

## 4. Interaction with Live Preview

Dialogs (Adjustments, Rotation) preview non-destructively before committing:

```
Dialog opens            → editor.start_preview()      # snapshot into image_before_preview
Slider/spinbox changes  → editor.preview_*()          # display-only, no command, no history
OK                      → editor.apply_*()            # command built from the SNAPSHOT
                                                        (original_image_override=...)
Cancel                  → editor.cancel_preview()     # snapshot restored
```

The `original_image_override` parameter (see e.g. [`AdjustmentsCommand.__init__`](../commands.py)) is essential: without it, committing would apply the adjustment on top of the already-previewed pixels, double-applying the effect.

## 5. Modified Flag & Titles

- `is_modified` is set to `True` by [`executeCommand()`](../editor.py) and `redo()`, recomputed as `bool(undo_stack)` after `undo()` and after Paste/Cut undos.
- The flag drives:
  - the `*` marker in sub-window titles ([`updateWindowTitle()`](../editor.py)),
  - save prompts in [`CustomMdiSubWindow.closeEvent()`](../widgets.py) and [`MainWindow.closeEvent()`](../main_window.py),
  - clearing on successful save ([`saveFile()`](../main_window.py)).

## 6. History Lifecycle

| Event | Effect on stacks |
|-------|------------------|
| Image opened ([`openImage()`](../editor.py)) | Both stacks cleared |
| New command executed | Pushed to undo; redo cleared |
| Undo | Moves top of undo → redo |
| Redo | Moves top of redo → undo |
| Resize ([`resizeImage()`](../editor.py)) | Undo stack capped at 10 entries (oldest dropped) |
| Image replaced via [`setImage()`](../editor.py) (outside a command) | Stacks **not** cleared automatically — commands still hold valid snapshots |

## 7. Extension Guide: Adding a New Edit Operation

1. Create a subclass of [`Command`](../commands.py) in [`commands.py`](../commands.py):

```python
class MyEffectCommand(Command):
    def __init__(self, editor):
        self.editor = editor
        self.original_image = editor.getCurrentImage().copy()  # snapshot!

    def execute(self):
        result = ...  # compute from self.original_image
        self.editor.setImage(result)

    def undo(self):
        self.editor.setImage(self.original_image)

    def redo(self):
        self.execute()
```

2. Add a factory method on [`ImageEditor`](../editor.py):

```python
def applyMyEffect(self):
    if not self.current_image:
        return
    from commands import MyEffectCommand   # local import avoids cycles
    self.executeCommand(MyEffectCommand(self))
```

3. Expose it in the UI: create a `QAction` in [`createActions()`](../main_window.py), add it to a menu/toolbar, and have the handler call `editor.applyMyEffect()` via [`currentEditor()`](../main_window.py).

Rules of thumb:

- Always snapshot in `__init__`, never in `execute()` (redo may run multiple times).
- Make `redo()` idempotent by deriving the result from the snapshot.
- If the operation interacts with scene items (like paste), record and restore their state too.
- Use `original_image_override` when the change originates from a previewing dialog.
