# Building & Deployment

## 1. Requirements

Python 3.8+ is recommended. Runtime dependencies are pinned in [`requirements.txt`](../requirements.txt):

| Package | Version | Role |
|---------|---------|------|
| `PyQt5` | 5.15.11 | GUI framework (widgets, graphics view, print support) |
| `pillow` | 11.1.0 | Brightness/contrast/gamma enhancement pipeline |
| `numpy` | 2.2.3 | Pixel-array operations (autobalance, grayscale bridge) |
| `opencv-python-headless` | 4.11.0.86 | Grayscale conversion (optional at runtime) |
| `appdirs` | 1.4.4 | Per-user config directory resolution |

Build-time dependencies (`pyinstaller`, `altgraph`, `packaging`, `pyinstaller-hooks-contrib`, `setuptools`) live in [`requirements-dev.txt`](../requirements-dev.txt), which also includes `-r requirements.txt`.

Optional (Windows scanning only): `pywin32` providing `win32com` / `pythoncom` for WIA. When absent, the Scan action shows a warning instead of failing ([`WIA_AVAILABLE`](../main_window.py)).

## 2. Running from Source

```bash
# 1. Virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Dependencies
pip install -r requirements.txt

# 3. Run
python main.py                    # optionally: python main.py image.png
```

Platform notes:

- **Linux**: PyQt5 may need system libraries (`libxcb-*`, etc.) — install your distro's `pyqt5` dependencies if the app fails to start.
- **Windows**: everything works from pip, including scanning when `pywin32` is installed.
- **Grayscale** requires `cv2`; without it the action warns ([`CV2_AVAILABLE`](../commands.py)).

### Troubleshooting: `Cannot mix incompatible Qt library (5.15.x) with this library (5.15.y)`

The pip wheel `PyQt5-Qt5` bundles its own copy of Qt. On Linux with a system Qt installed (e.g. Arch's `qt5-base`), the bundled image-format plugin `libqpdf.so` depends on `libQt5Pdf.so.5`, which is **not shipped in the wheel** — the dynamic linker then resolves it to the system Qt, and two different Qt builds end up loaded in one process. Qt detects this and aborts (`core dumped`) right after loading image-format plugins.

Fix — quarantine the plugin (PDF image loading is not needed by this app):

```bash
mkdir -p venv/_disabled_plugins
mv venv/lib/python3.12/site-packages/PyQt5/Qt5/plugins/imageformats/libqpdf.so \
   venv/_disabled_plugins/
```

Re-apply after every `pip install --force-reinstall PyQt5-Qt5` / venv rebuild. Alternative: use the distro's PyQt5 package instead of the pip wheel (it links against the single system Qt and has no such conflict).

## 3. Packaging with PyInstaller

The official build command (see [`GEMINI.md`](../GEMINI.md)):

```bash
pyinstaller main.py \
    --onefile \
    --windowed \
    --icon=icons/icon.ico \
    --name="SimplePhotoEditor_v1.0"
```

### Bundling data files

The application loads resources at runtime via [`resource_path()`](../main_window.py), which resolves against `sys._MEIPASS` in a frozen app. The `icons/` directory and the default `config.ini` must therefore be added explicitly:

```bash
pyinstaller main.py \
    --onefile --windowed \
    --icon=icons/icon.ico \
    --name="SimplePhotoEditor_v1.0" \
    --add-data "icons:icons" \
    --add-data "config.ini:."
```

> On **Windows**, separator syntax is `--add-data "icons;icons"` (semicolon instead of colon).

### Hidden imports

- Scanning (`win32com.client`, `pythoncom`) is imported lazily inside [`scanImage()`](../main_window.py); on Windows builds PyInstaller usually detects it, but add `--hidden-import win32com --hidden-import pythoncom` if the frozen app cannot scan.
- `cv2` is normally auto-detected; add `--hidden-import cv2` if grayscale is unavailable in the executable.

### Output

- `dist/SimplePhotoEditor_v1.0` (onefile: a single executable) — the artifact to distribute.
- `build/` — intermediate files (safe to delete).
- `SimplePhotoEditor_v1.0.spec` — generated spec; commit or regenerate as preferred.

## 4. First-Run Behavior in Packaged Builds

1. [`load_config()`](../utils.py) finds no user config → seeds defaults → writes the user config (see [Configuration](configuration.md)).
2. Icons resolve from the bundled `icons/` folder inside `sys._MEIPASS`.
3. The user config lives outside the executable, so settings survive re-installs.

## 5. Project Layout

```
Simple-Photoeditor/
├── main.py               # entry point
├── main_window.py        # MainWindow: menus, toolbars, MDI, file I/O
├── editor.py             # ImageEditor (QGraphicsView) + EditorContainer
├── scene.py              # ImageEditorScene + MovableImageItem
├── commands.py           # Command pattern implementations
├── widgets.py            # RulerWidget, CustomMdiSubWindow, dialogs
├── utils.py              # config, resource paths, recent files
├── config.ini            # bundled default config (seed)
├── requirements.txt      # pinned dependencies
├── icons/                # toolbar/menu icons + app icons
├── docs/                 # this documentation
├── README.md             # project overview
├── ARCHITECTURE.md       # legacy architecture notes (Russian)
├── GEMINI.md             # agent-oriented project summary
└── LICENSE               # MIT
```

## 6. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| Icons missing in frozen app | `icons/` not bundled — add `--add-data` (section 3) |
| "WIA components are not installed" | Expected on non-Windows or without `pywin32`; scanning is Windows-only |
| "OpenCV (cv2) is not installed" | Install/repair `opencv-python-headless` or bundle `cv2` |
| Config not persisted | Check write permissions for the [user config dir](configuration.md#1-config-file-locations); errors are printed to stdout |
| App window opens 800×600 every time | `General` section missing/invalid — delete the user config to re-seed defaults |
| Grayscale output is null | Rare format edge case; the command reports it via a message box ([`GrayscaleCommand.execute()`](../commands.py)) |
