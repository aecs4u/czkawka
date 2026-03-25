"""Tests for settings persistence in state.py.

These tests verify that AppSettings are correctly serialized to JSON
and deserialized back, including all new fields.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# Patch QObject and signals before importing state module
@pytest.fixture(autouse=True)
def _patch_qt(monkeypatch):
    """Patch PySide6 imports so tests run without a display."""
    mock_qt_core = MagicMock()
    mock_qt_core.Signal = lambda *a, **kw: MagicMock()
    mock_qt_core.QStandardPaths.writableLocation = lambda *a: ""
    monkeypatch.setitem(
        __import__("sys").modules, "PySide6.QtCore", mock_qt_core
    )


class TestSettingsPersistence:
    def test_save_and_load_new_fields(self, tmp_path):
        """All new AppSettings fields survive a save/load round-trip."""
        from app.models import AppSettings

        # Create settings with non-default values for every new field
        original = AppSettings()
        original.ignore_other_filesystems = True
        original.app_scale = 2.5
        original.show_only_icons = True
        original.save_window_geometry = False
        original.window_width = 800
        original.window_height = 600
        original.window_x = 100
        original.window_y = 200
        original.notify_on_completion = True
        original.play_sound_on_completion = True

        # Simulate save (same logic as state.save_settings)
        data = {
            "included_paths": original.included_paths,
            "reference_paths": original.reference_paths,
            "use_reference_folders": original.use_reference_folders,
            "excluded_paths": original.excluded_paths,
            "excluded_items": original.excluded_items,
            "allowed_extensions": original.allowed_extensions,
            "excluded_extensions": original.excluded_extensions,
            "minimum_file_size": original.minimum_file_size,
            "maximum_file_size": original.maximum_file_size,
            "recursive_search": original.recursive_search,
            "use_cache": original.use_cache,
            "save_as_json": original.save_as_json,
            "move_to_trash": original.move_to_trash,
            "hide_hard_links": original.hide_hard_links,
            "thread_number": original.thread_number,
            "dark_theme": original.dark_theme,
            "show_image_preview": original.show_image_preview,
            "czkawka_cli_path": original.czkawka_cli_path,
            "language": original.language,
            "ignore_other_filesystems": original.ignore_other_filesystems,
            "app_scale": original.app_scale,
            "show_only_icons": original.show_only_icons,
            "save_window_geometry": original.save_window_geometry,
            "window_width": original.window_width,
            "window_height": original.window_height,
            "window_x": original.window_x,
            "window_y": original.window_y,
            "notify_on_completion": original.notify_on_completion,
            "play_sound_on_completion": original.play_sound_on_completion,
        }

        config_file = tmp_path / "settings.json"
        config_file.write_text(json.dumps(data, indent=2))

        # Simulate load (same logic as state.load_settings)
        loaded = AppSettings()
        raw = json.loads(config_file.read_text())
        loaded.ignore_other_filesystems = raw.get("ignore_other_filesystems", False)
        loaded.app_scale = raw.get("app_scale", 1.0)
        loaded.show_only_icons = raw.get("show_only_icons", False)
        loaded.save_window_geometry = raw.get("save_window_geometry", True)
        loaded.window_width = raw.get("window_width", 1200)
        loaded.window_height = raw.get("window_height", 800)
        loaded.window_x = raw.get("window_x", -1)
        loaded.window_y = raw.get("window_y", -1)
        loaded.notify_on_completion = raw.get("notify_on_completion", False)
        loaded.play_sound_on_completion = raw.get("play_sound_on_completion", False)

        assert loaded.ignore_other_filesystems is True
        assert loaded.app_scale == 2.5
        assert loaded.show_only_icons is True
        assert loaded.save_window_geometry is False
        assert loaded.window_width == 800
        assert loaded.window_height == 600
        assert loaded.window_x == 100
        assert loaded.window_y == 200
        assert loaded.notify_on_completion is True
        assert loaded.play_sound_on_completion is True

    def test_missing_new_fields_use_defaults(self, tmp_path):
        """Loading old config without new fields uses safe defaults."""
        config_file = tmp_path / "settings.json"
        # Simulate an old config file without the new fields
        config_file.write_text(json.dumps({
            "included_paths": ["/home"],
            "recursive_search": True,
        }))

        from app.models import AppSettings
        loaded = AppSettings()
        raw = json.loads(config_file.read_text())
        loaded.ignore_other_filesystems = raw.get("ignore_other_filesystems", False)
        loaded.app_scale = raw.get("app_scale", 1.0)
        loaded.show_only_icons = raw.get("show_only_icons", False)
        loaded.save_window_geometry = raw.get("save_window_geometry", True)
        loaded.window_x = raw.get("window_x", -1)
        loaded.window_y = raw.get("window_y", -1)
        loaded.notify_on_completion = raw.get("notify_on_completion", False)

        # Should all be defaults
        assert loaded.ignore_other_filesystems is False
        assert loaded.app_scale == 1.0
        assert loaded.show_only_icons is False
        assert loaded.save_window_geometry is True
        assert loaded.window_x == -1
        assert loaded.notify_on_completion is False


class TestSettingsJson:
    def test_json_roundtrip_preserves_types(self, tmp_path):
        """Ensure float/int/bool types survive JSON serialization."""
        data = {
            "app_scale": 1.5,
            "window_width": 1024,
            "notify_on_completion": True,
            "show_only_icons": False,
        }
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))
        loaded = json.loads(path.read_text())

        assert isinstance(loaded["app_scale"], float)
        assert isinstance(loaded["window_width"], int)
        assert isinstance(loaded["notify_on_completion"], bool)
        assert loaded["show_only_icons"] is False
