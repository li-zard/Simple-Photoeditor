# Configuration

Simple Photo Editor stores its settings in an INI file managed by [`configparser`](../utils.py) and the `appdirs` library.

## 1. Config File Locations

| Priority | Location | Purpose |
|----------|----------|---------|
| 1 (user) | `appdirs.user_config_dir("Photoed", "YourCompany") + "/config.ini"` | Live settings, created on first run |
| 2 (bundled) | `config.ini` next to the executable / project root | Seed defaults when no user config exists |

Typical user paths:

- **Linux**: `~/.config/Photoed/YourCompany/config.ini`
- **Windows**: `%APPDATA%\YourCompany\Photoed\config.ini`
- **macOS**: `~/Library/Application Support/Photoed/YourCompany/config.ini`

The directory is created on demand by [`get_user_config_path()`](../utils.py).

> Note: the repository's [`config.ini`](../config.ini) is effectively empty (a single space) — all defaults are seeded in code by [`load_config()`](../utils.py).

## 2. Loading & Saving

### [`load_config()`](../utils.py) — startup

1. If the **user config** exists → read it and return.
2. Otherwise → try to read the **bundled** `config.ini` (resolved via [`resource_path()`](../utils.py), which works under PyInstaller through `sys._MEIPASS`).
3. Ensure required sections exist, injecting defaults:

| Section | Defaults injected |
|---------|-------------------|
| `General` | `theme = dark`, `window_width = 800`, `window_height = 600` |
| `Editor` | `default_zoom = 1.0`, `show_rulers = true` |
| `RecentFiles` | *(empty)* |

4. Save the seeded config to the user path so subsequent runs read step 1.

### [`save_config(config)`](../utils.py) — shutdown

Writes the parser to the user config path. I/O errors are caught and printed; they never abort application shutdown.

### When settings are written

The in-memory `config` object is mutated during the session (e.g. MRU updates in [`add_recent_file()`](../utils.py)) but persisted **only once**, in [`MainWindow.closeEvent()`](../main_window.py), which first updates:

- `General.window_width` / `General.window_height` — current window size
- `LastImageSettings.*` — last New Image dialog values

## 3. INI Schema

### `[General]`

| Key | Type | Default | Written by | Used by |
|-----|------|---------|------------|---------|
| `theme` | str | `dark` | seeded only | *(reserved, not currently read)* |
| `window_width` | int | `800` | [`closeEvent()`](../main_window.py) | [`main.py`](../main.py) initial window size |
| `window_height` | int | `600` | [`closeEvent()`](../main_window.py) | [`main.py`](../main.py) initial window size |
| `last_opened_file` | str | *(empty)* | *(legacy)* | read by [`main.py`](../main.py) but not applied |

### `[Editor]`

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `default_zoom` | float | `1.0` | Seeded; not currently read back |
| `show_rulers` | bool | `true` | Seeded; ruler state is per-session, not persisted |

### `[LastImageSettings]`

Restored into `MainWindow.last_image_settings` at startup ([`__init__`](../main_window.py)) and used to pre-fill the New Image dialog; refreshed after each accepted dialog and saved on close.

| Key | Type | Default |
|-----|------|---------|
| `width` | str | `800` |
| `height` | str | `600` |
| `dpi` | int | `150` |
| `units` | str | `Pixels` |

### `[RecentFiles]`

MRU list maintained by [`add_recent_file()`](../utils.py) / [`get_recent_files()`](../utils.py):

| Key | Value |
|-----|-------|
| `file1` … `file5` | Absolute paths, most recent first |

Behavior:

- Max **5** entries; re-opening an existing entry moves it to position 1.
- Entries pointing to non-existent files are filtered out on read (but not pruned from the file).
- Updates are held in memory; the file is written at shutdown.

## 4. Example Config

```ini
[General]
theme = dark
window_width = 1024
window_height = 768

[Editor]
default_zoom = 1.0
show_rulers = true

[LastImageSettings]
width = 800
height = 600
dpi = 150
units = Pixels

[RecentFiles]
file1 = /home/user/pictures/scan001.png
file2 = /home/user/pictures/photo.jpg
```

## 5. Resource Resolution

A single helper is used everywhere:

- [`utils.resource_path()`](../utils.py) — checks `sys._MEIPASS` (PyInstaller extraction dir) and falls back to the current directory. [`main_window.py`](../main_window.py) and [`main.py`](../main.py) import it from [`utils`](../utils.py).

Under PyInstaller, data files (icons, default config) must be bundled (e.g. `--add-data`) for these lookups to succeed — see [Building & Deployment](building.md).
