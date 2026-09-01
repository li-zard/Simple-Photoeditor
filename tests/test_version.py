"""Tests for the single-source versioning scheme (version.py).

version.py is the single source of APP_VERSION:
- About dialog and window title consume it in main_window.py
- build_windows.bat parses it and passes /DAppVersion to ISCC
- installer.iss uses it in OutputBaseFilename

This test guards the format so the bat parser (findstr + for /f)
never breaks silently.
"""
import re
from pathlib import Path

import pytest

from version import APP_VERSION, APP_NAME

ROOT = Path(__file__).resolve().parent.parent


class TestVersionSource:
    def test_version_semver_like(self):
        # digits and dots only, no spaces/quotes: safe for the bat parser
        # and for a filename inside OutputBaseFilename
        assert re.fullmatch(r"[0-9]+(\.[0-9]+)*", APP_VERSION), APP_VERSION

    def test_version_no_quotes_or_spaces(self):
        assert '"' not in APP_VERSION
        assert " " not in APP_VERSION

    def test_app_name_is_plain(self):
        assert APP_NAME == "Simple Photo Editor"

    def test_installer_uses_version_placeholder(self):
        iss = (ROOT / "installer" / "installer.iss").read_text(encoding="utf-8")
        # filename must be built from the define, not hardcoded
        assert "OutputBaseFilename=SimplePhotoEditor_Setup_v{#AppVersion}" in iss
        # hardcoded default must be guarded by #ifndef (manual ISCC runs only)
        assert "#ifndef AppVersion" in iss
        assert iss.count('#define AppVersion') == 1

    def test_build_script_parses_and_passes_version(self):
        bat = (ROOT / "build_windows.bat").read_text(encoding="utf-8")
        assert 'findstr /b "APP_VERSION" version.py' in bat
        assert "/DAppVersion=%VERSION%" in bat

    def test_about_dialog_uses_constants(self, qapp):
        from PyQt5.QtWidgets import QMainWindow
        from utils import load_config
        from main_window import MainWindow

        mw = MainWindow(load_config())
        try:
            # window title carries the version
            assert APP_VERSION in mw.windowTitle()
            assert APP_NAME in mw.windowTitle()
        finally:
            mw.close()
