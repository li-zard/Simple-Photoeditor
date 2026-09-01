@echo off
rem ============================================================
rem  Simple Photo Editor - Windows build chain (Roadmap stage 6)
rem  1) PyInstaller --onedir  ->  dist\SimplePhotoEditor\
rem  2) Inno Setup (ISCC)     ->  installer\Output\SimplePhotoEditor_Setup_v1.0.exe
rem
rem  Prerequisites:
rem    - venv with requirements-dev.txt installed (PyQt5 + pyinstaller).
rem      The script auto-uses .\venv (or the active VIRTUAL_ENV);
rem      a pre-flight check aborts early if PyQt5 is missing.
rem    - Inno Setup 6+ installed (ISCC.exe, or set ISCC env var)
rem    - version.py is the single source of APP_VERSION: it lands in
rem      the About dialog and, via /D, in the installer name/metadata.
rem ============================================================
setlocal

rem --- Locate Inno Setup compiler (override by setting ISCC env var) ---
if "%ISCC%"=="" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup compiler not found: "%ISCC%"
    echo         Install Inno Setup 6+ or set the ISCC environment variable.
    exit /b 1
)

rem --- Pick the interpreter: active venv, then .\venv, then PATH ---
rem     (plain "pyinstaller" may belong to another Python without PyQt5,
rem      which produces an exe failing with "no module named 'PyQt5'")
set "PY=python"
if defined VIRTUAL_ENV (
    set "PY=%VIRTUAL_ENV%\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY=%~dp0venv\Scripts\python.exe"
)

rem --- Pre-flight: Python must be 3.10-3.13 (pinned wheels; 3.14 has none) ---
echo === Using interpreter: "%PY%" ===
"%PY%" -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 (
    "%PY%" -c "import sys; print('[ERROR] Python %s.%s is not supported: pinned numpy/pillow wheels exist only for 3.10-3.13.' % sys.version_info[:2])"
    echo         Recreate the venv with Python 3.12:  py -3.12 -m venv venv
    exit /b 1
)

rem --- Pre-flight: PyQt5 must be importable by THIS interpreter ---
"%PY%" -c "import PyQt5" 2>nul
if errorlevel 1 (
    echo [ERROR] PyQt5 is not installed for the interpreter above.
    echo         Create a venv and run:  pip install -r requirements-dev.txt
    exit /b 1
)

rem --- Extract APP_VERSION from version.py (single source of truth) ---
rem     delims "== " splits on '=' and spaces; %%~v strips the quotes.
set "VERSION="
for /f "tokens=2 delims== " %%v in ('findstr /b "APP_VERSION" version.py') do set "VERSION=%%~v"
if not defined VERSION (
    echo [ERROR] Cannot parse APP_VERSION from version.py
    exit /b 1
)
echo === Building version: %VERSION% ===

rem --- 1. Freeze the application (onedir) ---
echo === PyInstaller (onedir) ===
"%PY%" -m PyInstaller main.py --onedir --windowed --icon=icons\icon.ico ^
    --name="SimplePhotoEditor" --noconfirm ^
    --hidden-import win32com --hidden-import pythoncom ^
    --add-data "icons;icons" --add-data "config.ini;."
if errorlevel 1 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

rem --- Post-check: PyQt5 must be inside the bundle ---
if not exist "dist\SimplePhotoEditor\_internal\PyQt5" (
    echo [ERROR] PyQt5 missing from dist\SimplePhotoEditor\_internal -
    echo         the build used a wrong Python. Remove build\ and dist\, then retry.
    exit /b 1
)

rem --- 2. Compile the installer ---
echo === Inno Setup ===
if not exist "installer\installer.iss" (
    echo [ERROR] installer\installer.iss not found on this machine.
    echo         Check that the installer\ folder is synced/present, then retry.
    exit /b 1
)
"%ISCC%" /DAppVersion=%VERSION% installer\installer.iss
if errorlevel 1 (
    echo [ERROR] ISCC failed. Run it manually for details:
    echo         "%ISCC%" installer\installer.iss
    exit /b 1
)

echo.
echo Done: installer\Output\SimplePhotoEditor_Setup_v%VERSION%.exe
endlocal
