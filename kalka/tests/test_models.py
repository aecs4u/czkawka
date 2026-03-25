"""Tests for kalka.app.models dataclasses and enums."""

import pytest
from app.models import (
    ActiveTab, AppSettings, ToolSettings, ResultEntry, ScanProgress,
    TAB_TO_CLI_COMMAND, TAB_COLUMNS, GROUPED_TABS, TABS_WITH_SETTINGS,
    CheckingMethod, HashType, ImageHashAlg, ImageFilter,
    MusicSearchMethod, VideoCropDetect, VideoCropMechanism, VideoCodec,
    SelectMode, DeleteMethod,
)


# ── AppSettings defaults ─────────────────────────────────────────────


class TestAppSettingsDefaults:
    def test_default_included_paths_is_home(self):
        from pathlib import Path
        s = AppSettings()
        assert s.included_paths == [str(Path.home())]

    def test_default_reference_paths_empty(self):
        s = AppSettings()
        assert s.reference_paths == []
        assert s.use_reference_folders is False

    def test_default_booleans(self):
        s = AppSettings()
        assert s.recursive_search is True
        assert s.use_cache is True
        assert s.move_to_trash is True
        assert s.hide_hard_links is False
        assert s.low_priority_scan is False

    def test_new_settings_defaults(self):
        s = AppSettings()
        assert s.ignore_other_filesystems is False
        assert s.app_scale == 1.0
        assert s.show_only_icons is False
        assert s.save_window_geometry is True
        assert s.window_width == 1200
        assert s.window_height == 800
        assert s.window_x == -1
        assert s.window_y == -1
        assert s.notify_on_completion is False
        assert s.play_sound_on_completion is False

    def test_instances_are_independent(self):
        s1 = AppSettings()
        s2 = AppSettings()
        s1.included_paths.append("/tmp/test")
        assert "/tmp/test" not in s2.included_paths


# ── ToolSettings defaults ─────────────────────────────────────────────


class TestToolSettingsDefaults:
    def test_duplicate_defaults(self):
        ts = ToolSettings()
        assert ts.dup_check_method == CheckingMethod.HASH
        assert ts.dup_hash_type == HashType.BLAKE3
        assert ts.dup_no_self_compare is False

    def test_music_defaults(self):
        ts = ToolSettings()
        assert ts.music_search_method == MusicSearchMethod.TAGS
        assert ts.music_fuzzy_tag_comparison is False
        assert ts.music_tag_similarity_threshold == 0.85
        assert ts.music_min_segment_duration == 10.0

    def test_video_defaults(self):
        ts = ToolSettings()
        assert ts.video_crop_reencode is False
        assert ts.video_crop_codec == VideoCodec.H265
        assert ts.video_crop_quality == 23
        assert ts.video_thumbnail is False
        assert ts.video_thumbnail_percentage == 10
        assert ts.video_thumbnail_grid is False
        assert ts.video_thumbnail_grid_tiles == 3
        assert ts.video_limit_size is False
        assert ts.video_max_width == 1920
        assert ts.video_max_height == 1080

    def test_image_defaults(self):
        ts = ToolSettings()
        assert ts.img_hash_size == 16
        assert ts.img_filter == ImageFilter.NEAREST
        assert ts.img_hash_alg == ImageHashAlg.GRADIENT
        assert ts.img_max_difference == 5

    def test_doc_defaults(self):
        ts = ToolSettings()
        assert ts.doc_similarity_threshold == 0.7
        assert ts.doc_num_hashes == 128
        assert ts.doc_shingle_size == 3


# ── Enums ────────────────────────────────────────────────────────────


class TestEnums:
    def test_checking_method_values(self):
        assert CheckingMethod.HASH.value == "HASH"
        assert CheckingMethod.FUZZY_NAME.value == "FUZZY_NAME"

    def test_video_codec_values(self):
        assert VideoCodec.H264.value == "h264"
        assert VideoCodec.H265.value == "h265"
        assert VideoCodec.AV1.value == "av1"
        assert VideoCodec.VP9.value == "vp9"

    def test_active_tab_has_all_tools(self):
        expected = {
            "DUPLICATE_FILES", "EMPTY_FOLDERS", "BIG_FILES", "EMPTY_FILES",
            "TEMPORARY_FILES", "SIMILAR_IMAGES", "SIMILAR_VIDEOS",
            "SIMILAR_MUSIC", "INVALID_SYMLINKS", "BROKEN_FILES",
            "BAD_EXTENSIONS", "BAD_NAMES", "EXIF_REMOVER",
            "VIDEO_OPTIMIZER", "SIMILAR_DOCUMENTS", "SETTINGS", "ABOUT",
        }
        actual = {t.name for t in ActiveTab}
        assert expected == actual

    def test_select_mode_completeness(self):
        assert len(SelectMode) >= 11


# ── Tab mappings ─────────────────────────────────────────────────────


class TestTabMappings:
    def test_all_scanning_tabs_have_cli_command(self):
        non_scan = {ActiveTab.SETTINGS, ActiveTab.ABOUT}
        for tab in ActiveTab:
            if tab not in non_scan:
                assert tab in TAB_TO_CLI_COMMAND, f"{tab} missing CLI command"

    def test_all_scanning_tabs_have_columns(self):
        non_scan = {ActiveTab.SETTINGS, ActiveTab.ABOUT}
        for tab in ActiveTab:
            if tab not in non_scan:
                assert tab in TAB_COLUMNS, f"{tab} missing column defs"

    def test_grouped_tabs_subset(self):
        assert ActiveTab.DUPLICATE_FILES in GROUPED_TABS
        assert ActiveTab.SIMILAR_IMAGES in GROUPED_TABS
        assert ActiveTab.EMPTY_FILES not in GROUPED_TABS

    def test_cli_command_names(self):
        assert TAB_TO_CLI_COMMAND[ActiveTab.DUPLICATE_FILES] == "dup"
        assert TAB_TO_CLI_COMMAND[ActiveTab.SIMILAR_IMAGES] == "image"
        assert TAB_TO_CLI_COMMAND[ActiveTab.SIMILAR_DOCUMENTS] == "similar-docs"


# ── ResultEntry ──────────────────────────────────────────────────────


class TestResultEntry:
    def test_default_values(self):
        r = ResultEntry(values={"a": "b"})
        assert r.checked is False
        assert r.header_row is False
        assert r.group_id == 0

    def test_header_row(self):
        r = ResultEntry(values={}, header_row=True, group_id=5)
        assert r.header_row is True
        assert r.group_id == 5


# ── ScanProgress ─────────────────────────────────────────────────────


class TestScanProgress:
    def test_default_zeros(self):
        p = ScanProgress()
        assert p.current == 0
        assert p.total == 0
        assert p.bytes_checked == 0
        assert p.entries_checked == 0

    def test_custom_values(self):
        p = ScanProgress(step_name="Hashing", entries_checked=50, entries_to_check=100)
        assert p.step_name == "Hashing"
        assert p.entries_checked == 50
