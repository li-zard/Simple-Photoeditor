# Approach 1: Resizable pasted items (resize handles on MovableImageItem)

Goal: when pasting from clipboard, the floating item gets 8 resize handles so the
user can scale it before fixing it onto the canvas. Primary use case: gluing two
scanned documents — paste the second scan, stretch it to match the first, fix.

## Current state (verified in code)

- Paste creates a floating [`MovableImageItem`](../scene.py:225) — movable only, no resize.
- Position is hard-clamped to `sceneRect()` in [`MovableImageItem.mouseMoveEvent()`](../scene.py:235).
- Selection already has an 8-handle mechanic: [`createHandles()`](../scene.py:36) + drag in [`ImageEditorScene.mouseMoveEvent()`](../scene.py:159).
- Baking is done by [`FixPasteCommand`](../commands.py:282) via `painter.drawPixmap(pos, pixmap)` — ignores any scale.
- [`PasteCommand.undo()`](../commands.py:188) restores items but not their transforms.

## Design decisions

- **Scale representation:** keep `pixmap()` at native resolution; store visual size in
  `item.setData(2, QSizeF)` and apply via `setScale()` (uniform) — crisp baking, no
  intermediate resamples. Non-uniform scale (Shift) uses `setTransform()`.
- **Handles owned by the scene**, created when a `MovableImageItem` becomes selected
  (reuse pattern of `createHandles()`), removed on deselect. Handles are children of
  the scene, z=300 (above items z=100, selection handles z=200).
- **Clamping relaxed:** item may extend beyond canvas edges (negative pos allowed),
  but at least 10% must remain inside so it stays grabbable. Baking clips to canvas.
- **Min size:** 8 px; **max size:** 4× canvas dimension (protects from runaway drags).
- **Aspect:** locked by default; Shift = free resize (matches common UX).
- **Baking:** `FixPasteCommand` draws `pixmap().scaled(target_rect)` with
  `Qt.SmoothTransformation`; undo restores old image + re-adds items with saved
  pos/scale (extend existing undo which already restores positions).

## Implementation steps

1. **scene.py — `MovableImageItem`**
   - Add `createResizeHandles()` / `updateResizeHandles()` (8 handles, reuse visual
     style from `createHandles()`; handle size adapts to view zoom via
     `views()[0].transform().m11()`).
   - `itemChange(ItemSelectedChange)` → show/hide handles.
   - `hoverMoveEvent` → `SizeFDiagCursor`/`SizeBDiagCursor`/`SizeHorCursor`/`SizeVerCursor`.
   - Relax clamping in `mouseMoveEvent()` (≥10% inside canvas).

2. **scene.py — `ImageEditorScene`**
   - In `mousePressEvent`: if click hits a resize handle of a `MovableImageItem` →
     start item-resize mode (store anchor corner + start rect), skip selection logic.
   - In `mouseMoveEvent`: item-resize branch — compute new size from cursor pos,
     apply aspect lock (unless Shift), min/max limits, `setScale()`/`setTransform()`,
     update handles, keep the opposite corner anchored.
   - In `mouseReleaseEvent`: finish item-resize.
   - Keep existing behavior: click on empty area fixes pasted items (via
     [`ImageEditor.mousePressEvent`](../editor.py:112) → `fixPastedItems()`).

3. **commands.py — `FixPasteCommand`**
   - Bake with scale: `target = QRectF(item.pos(), scaled size).toRect()`;
     `painter.drawPixmap(target, pixmap.scaled(target.size(), KeepAspectRatio, Smooth))`.
   - `undo()`: also restore saved scale/transform per item.

4. **commands.py — `PasteCommand`**
   - `undo()`: restore saved transforms of re-added items (pos already restored;
     add scale).

5. **Status bar feedback** (editor.py)
   - During item resize show `W×H px` in status bar (like selection).

6. **Tests** (tests/test_commands.py + new tests/test_scene_resize.py)
   - Paste → scale item 2× → fix → canvas pixels changed; undo → item back with
     original scale; redo.
   - Aspect lock math: diagonal handle drag keeps ratio.
   - Min/max clamp boundaries.

7. **Docs**
   - docs/modules.md: paste section — mention resize handles, Shift behavior.
   - docs/undo-redo.md: FixPasteCommand now stores scale.

## Risks / edge cases

- Handle size vs zoom: handles must stay visible at fit-zoom of large scans
  (scale handle rect by `1/zoom`).
- Interaction with selection tool: when a pasted item exists, starting a new rubber-
  band selection fixes it first (existing behavior, keep).
- `FixPasteCommand.undo()` re-adds items — must re-apply transforms, else undo of a
  scaled bake looks wrong.
- Baking a hugely upscaled item (4×) on a 4000×3000 canvas: one-time cost, acceptable.

## Not in scope (approach 2 candidates)

- Auto canvas expansion, auto-resize to match neighbor, drag-window gluing.
