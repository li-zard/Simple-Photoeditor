# Building & Deployment

## 1. Requirements

**Python 3.10 – 3.13 is required (3.12 recommended).** The pinned binary dependencies (`numpy==2.2.3`, `pillow==11.1.0`) ship wheels only up to CPython 3.13; on 3.14 pip falls back to a source build that needs MSVC and fails. Create the venv with a supported interpreter, e.g. `py -3.12 -m venv venv`.

Runtime dependencies are pinned in [`requirements.txt`](../requirements.txt):

| Package | Version | Role |
|---------|---------|------|
| `PyQt5` | 5.15.11 | GUI framework (widgets, graphics view, print support) |
| `pillow` | 11.1.0 | Brightness/contrast/gamma enhancement pipeline |
| `numpy` | 2.2.3 | Pixel-array operations (autobalance, grayscale bridge) |
| `opencv-python-headless` | 4.11.0.86 | Grayscale conversion (optional at runtime) |
| `appdirs` | 1.4.4 | Per-user config directory resolution |
| `PyQt5-Qt5` | 5.15.16 (Linux) / 5.15.2 (Windows, macOS) | Bundled Qt binaries; newer builds are published for Linux only — selected via `platform_system` markers in [`requirements.txt`](../requirements.txt) |
| `PyQt5-Qt5` | 5.15.16 (Linux) / 5.15.2 (Windows, macOS) | Bundled Qt binaries; newer builds are published for Linux only — selected via `platform_system` markers in [`requirements.txt`](../requirements.txt) |

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

The official build is **onedir** (roadmap stage 6): a onefile build unpacks itself into a temp folder on every start (+1–3 s), which is pointless for an installed application — the installer already provides the single artifact.

```bash
pyinstaller main.py \
    --onedir \
    --windowed \
    --icon=icons/icon.ico \
    --name="SimplePhotoEditor" \
    --add-data "icons:icons" \
    --add-data "config.ini:."
```

> On **Windows**, separator syntax is `--add-data "icons;icons"` (semicolon instead of colon).

### Bundling data files

The application loads resources at runtime via [`resource_path()`](../utils.py:18), which resolves against `sys._MEIPASS` in a frozen app. In onedir builds `sys._MEIPASS` points to `dist/SimplePhotoEditor/_internal/`, so `icons/` and the default `config.ini` must be added explicitly (see the command above). Verified on Linux: the bundle contains `_internal/icons/` and `_internal/config.ini`, and the frozen executable starts and finds them.

### Hidden imports

- Scanning (`win32com.client`, `pythoncom`) is imported lazily inside [`scanImage()`](../main_window.py); on Windows builds PyInstaller usually detects it, but add `--hidden-import win32com --hidden-import pythoncom` if the frozen app cannot scan.
- `cv2` is normally auto-detected; add `--hidden-import cv2` if grayscale is unavailable in the executable.

### Output

- `dist/SimplePhotoEditor/` — the onedir bundle: the `SimplePhotoEditor` executable plus `_internal/` (Qt DLLs, `icons/`, default `config.ini`). This folder is what the installer packs.
- `build/` — intermediate files (safe to delete).
- `SimplePhotoEditor.spec` — generated spec; commit or regenerate as preferred.

### Windows installer (Inno Setup)

On Windows the whole chain is automated by [`build_windows.bat`](../build_windows.bat):

1. PyInstaller builds `dist\SimplePhotoEditor\` (onedir, windowed, icon, bundled data).
2. Inno Setup compiles [`installer/installer.iss`](../installer/installer.iss) via `ISCC.exe` (default location `%ProgramFiles(x86)%\Inno Setup 6\`, overridable through the `ISCC` environment variable).
3. Artifact: `installer\Output\SimplePhotoEditor_Setup_v1.0.exe` — Start-menu shortcut and uninstaller, optional desktop icon, optional "Open with" file associations (HKCU + `OpenWithProgids`), full registry cleanup on uninstall.

Acceptance checks for the installed app: [roadmap § 6.5](roadmap.md).

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
├── build_windows.bat     # Windows build chain: PyInstaller + Inno Setup
├── installer/            # installer.iss — Inno Setup script
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
| Frozen exe: `Failed to execute script 'main' — no module named 'PyQt5'` | PyInstaller ran under a Python **without** PyQt5 (e.g. a global `pyinstaller` outside the venv). Rebuild with the venv interpreter — [`build_windows.bat`](../build_windows.bat) does this automatically (`python -m PyInstaller` + pre/post checks). Delete `build\` and `dist\` before retrying |
| `pip install` fails building numpy/pillow: `meson ... ERROR: Unknown compiler(s)` | Python is 3.14 (or older than 3.10) — no prebuilt wheels for the pinned versions, so pip tries a source build without MSVC. Recreate the venv with Python 3.12/3.13: `py -3.12 -m venv venv`, then `pip install -r requirements-dev.txt` |
| ISCC prints banner then `The system cannot find the file specified.` | `installer\installer.iss` is missing on the build machine (e.g. not synced) — the script guards with a pre-check now; or the Inno Setup install lacks `Languages\Russian.isl` — the script falls back to an English-only wizard automatically |
| "WIA components are not installed" | Expected on non-Windows or without `pywin32`; scanning is Windows-only |
| "OpenCV (cv2) is not installed" | Install/repair `opencv-python-headless` or bundle `cv2` |
| Config not persisted | Check write permissions for the [user config dir](configuration.md#1-config-file-locations); errors are printed to stdout |
| App window opens 800×600 every time | `General` section missing/invalid — delete the user config to re-seed defaults |
| Grayscale output is null | Rare format edge case; the command reports it via a message box ([`GrayscaleCommand.execute()`](../commands.py)) |
