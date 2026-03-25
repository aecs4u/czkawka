"""Tests for CLI command building in the backend.

These tests verify that ScanWorker._build_command() produces correct
CLI argument lists for each tool and setting combination, without
actually running any subprocess.
"""

import pytest
from app.models import (
    ActiveTab, AppSettings, ToolSettings,
    CheckingMethod, HashType, MusicSearchMethod,
    VideoCropMechanism, VideoCodec, VideoCropDetect,
)
from app.backend import ScanWorker


def _build(tab: ActiveTab, app_settings=None, tool_settings=None) -> list[str]:
    """Helper: build a CLI command list for the given tab."""
    s = app_settings or AppSettings()
    ts = tool_settings or ToolSettings()
    worker = ScanWorker(tab, s, ts)
    return worker._build_command()


# ── Common flags ─────────────────────────────────────────────────────


class TestCommonFlags:
    def test_basic_command_structure(self):
        cmd = _build(ActiveTab.DUPLICATE_FILES)
        assert cmd[0] == "czkawka_cli"
        assert cmd[1] == "dup"

    def test_included_directories(self):
        s = AppSettings()
        s.included_paths = ["/home/user", "/tmp"]
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-d" in cmd
        idx = cmd.index("-d")
        assert cmd[idx + 1] == "/home/user,/tmp"

    def test_excluded_directories(self):
        s = AppSettings()
        s.excluded_paths = ["/proc"]
        cmd = _build(ActiveTab.EMPTY_FOLDERS, app_settings=s)
        assert "-e" in cmd
        idx = cmd.index("-e")
        assert cmd[idx + 1] == "/proc"

    def test_not_recursive(self):
        s = AppSettings()
        s.recursive_search = False
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-R" in cmd

    def test_recursive_default_no_flag(self):
        cmd = _build(ActiveTab.EMPTY_FILES)
        assert "-R" not in cmd

    def test_disable_cache(self):
        s = AppSettings()
        s.use_cache = False
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-H" in cmd

    def test_thread_number(self):
        s = AppSettings()
        s.thread_number = 4
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-T" in cmd
        idx = cmd.index("-T")
        assert cmd[idx + 1] == "4"

    def test_thread_zero_no_flag(self):
        s = AppSettings()
        s.thread_number = 0
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-T" not in cmd

    def test_reference_paths(self):
        s = AppSettings()
        s.use_reference_folders = True
        s.reference_paths = ["/ref1", "/ref2"]
        cmd = _build(ActiveTab.DUPLICATE_FILES, app_settings=s)
        assert "-r" in cmd
        idx = cmd.index("-r")
        assert cmd[idx + 1] == "/ref1,/ref2"

    def test_reference_paths_disabled(self):
        s = AppSettings()
        s.use_reference_folders = False
        s.reference_paths = ["/ref1"]
        cmd = _build(ActiveTab.DUPLICATE_FILES, app_settings=s)
        assert "-r" not in cmd

    def test_ignore_other_filesystems(self):
        s = AppSettings()
        s.ignore_other_filesystems = True
        cmd = _build(ActiveTab.EMPTY_FILES, app_settings=s)
        assert "-X" in cmd

    def test_ignore_other_filesystems_default(self):
        cmd = _build(ActiveTab.EMPTY_FILES)
        assert "-X" not in cmd

    def test_allowed_extensions(self):
        s = AppSettings()
        s.allowed_extensions = ["jpg", "png"]
        cmd = _build(ActiveTab.DUPLICATE_FILES, app_settings=s)
        assert "-x" in cmd
        idx = cmd.index("-x")
        assert cmd[idx + 1] == "jpg,png"

    def test_excluded_extensions(self):
        s = AppSettings()
        s.excluded_extensions = ["log", "tmp"]
        cmd = _build(ActiveTab.DUPLICATE_FILES, app_settings=s)
        assert "-P" in cmd

    def test_excluded_items(self):
        s = AppSettings()
        s.excluded_items = ["*.tmp", "cache_*"]
        cmd = _build(ActiveTab.DUPLICATE_FILES, app_settings=s)
        assert "-E" in cmd


# ── Duplicate Files ──────────────────────────────────────────────────


class TestDuplicateFiles:
    def test_default_hash_method(self):
        cmd = _build(ActiveTab.DUPLICATE_FILES)
        assert "-s" in cmd
        idx = cmd.index("-s")
        assert cmd[idx + 1] == "HASH"

    def test_hash_type(self):
        ts = ToolSettings()
        ts.dup_hash_type = HashType.CRC32
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "-t" in cmd
        idx = cmd.index("-t")
        assert cmd[idx + 1] == "CRC32"

    def test_case_sensitive(self):
        ts = ToolSettings()
        ts.dup_name_case_sensitive = True
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "-l" in cmd

    def test_prehash(self):
        ts = ToolSettings()
        ts.dup_use_prehash = True
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "-u" in cmd

    def test_fuzzy_name_threshold(self):
        ts = ToolSettings()
        ts.dup_check_method = CheckingMethod.FUZZY_NAME
        ts.dup_name_similarity_threshold = 0.9
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "--name-similarity-threshold" in cmd
        idx = cmd.index("--name-similarity-threshold")
        assert cmd[idx + 1] == "0.9"

    def test_no_self_compare(self):
        ts = ToolSettings()
        ts.dup_no_self_compare = True
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "--no-self-compare" in cmd

    def test_no_self_compare_default_off(self):
        cmd = _build(ActiveTab.DUPLICATE_FILES)
        assert "--no-self-compare" not in cmd

    def test_min_size(self):
        ts = ToolSettings()
        ts.dup_min_size = "1024"
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "-m" in cmd
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "1024"

    def test_max_size(self):
        ts = ToolSettings()
        ts.dup_max_size = "999999"
        cmd = _build(ActiveTab.DUPLICATE_FILES, tool_settings=ts)
        assert "-i" in cmd


# ── Similar Images ───────────────────────────────────────────────────


class TestSimilarImages:
    def test_default_args(self):
        cmd = _build(ActiveTab.SIMILAR_IMAGES)
        assert "-g" in cmd  # hash alg
        assert "-z" in cmd  # filter
        assert "-c" in cmd  # hash size
        assert "-s" in cmd  # max diff

    def test_ignore_same_size(self):
        ts = ToolSettings()
        ts.img_ignore_same_size = True
        cmd = _build(ActiveTab.SIMILAR_IMAGES, tool_settings=ts)
        assert "-J" in cmd


# ── Similar Videos ───────────────────────────────────────────────────


class TestSimilarVideos:
    def test_default_args(self):
        cmd = _build(ActiveTab.SIMILAR_VIDEOS)
        assert "-t" in cmd  # tolerance
        assert "-U" in cmd  # skip forward
        assert "-B" in cmd  # crop detect
        assert "-A" in cmd  # duration

    def test_crop_detect_value(self):
        ts = ToolSettings()
        ts.vid_crop_detect = VideoCropDetect.NONE
        cmd = _build(ActiveTab.SIMILAR_VIDEOS, tool_settings=ts)
        idx = cmd.index("-B")
        assert cmd[idx + 1] == "none"


# ── Similar Music ────────────────────────────────────────────────────


class TestSimilarMusic:
    def test_tags_mode_default(self):
        cmd = _build(ActiveTab.SIMILAR_MUSIC)
        assert "-s" in cmd
        idx = cmd.index("-s")
        assert cmd[idx + 1] == "TAGS"

    def test_tags_selection(self):
        ts = ToolSettings()
        ts.music_title = True
        ts.music_artist = True
        ts.music_bitrate = False
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        assert "-z" in cmd
        idx = cmd.index("-z")
        assert "track_title" in cmd[idx + 1]
        assert "track_artist" in cmd[idx + 1]
        assert "bitrate" not in cmd[idx + 1]

    def test_approximate(self):
        ts = ToolSettings()
        ts.music_approximate = True
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        assert "-a" in cmd

    def test_content_mode(self):
        ts = ToolSettings()
        ts.music_search_method = MusicSearchMethod.CONTENT
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        idx = cmd.index("-s")
        assert cmd[idx + 1] == "CONTENT"
        assert "-Y" in cmd

    def test_min_segment_duration_content_mode(self):
        ts = ToolSettings()
        ts.music_search_method = MusicSearchMethod.CONTENT
        ts.music_min_segment_duration = 15.0
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        assert "-l" in cmd
        idx = cmd.index("-l")
        assert cmd[idx + 1] == "15.0"

    def test_min_segment_duration_not_in_tags_mode(self):
        ts = ToolSettings()
        ts.music_search_method = MusicSearchMethod.TAGS
        ts.music_min_segment_duration = 15.0
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        assert "-l" not in cmd

    def test_fuzzy_tag_comparison(self):
        ts = ToolSettings()
        ts.music_fuzzy_tag_comparison = True
        ts.music_tag_similarity_threshold = 0.9
        cmd = _build(ActiveTab.SIMILAR_MUSIC, tool_settings=ts)
        assert "--fuzzy-tag-comparison" in cmd
        assert "--tag-similarity-threshold" in cmd
        idx = cmd.index("--tag-similarity-threshold")
        assert cmd[idx + 1] == "0.9"

    def test_fuzzy_tag_off_by_default(self):
        cmd = _build(ActiveTab.SIMILAR_MUSIC)
        assert "--fuzzy-tag-comparison" not in cmd
        assert "--tag-similarity-threshold" not in cmd


# ── Big Files ────────────────────────────────────────────────────────


class TestBigFiles:
    def test_default_count(self):
        cmd = _build(ActiveTab.BIG_FILES)
        assert "-n" in cmd
        idx = cmd.index("-n")
        assert cmd[idx + 1] == "50"

    def test_smallest_mode(self):
        ts = ToolSettings()
        ts.big_files_mode = "smallest"
        cmd = _build(ActiveTab.BIG_FILES, tool_settings=ts)
        assert "-J" in cmd

    def test_biggest_mode_no_J(self):
        cmd = _build(ActiveTab.BIG_FILES)
        assert "-J" not in cmd


# ── Broken Files ─────────────────────────────────────────────────────


class TestBrokenFiles:
    def test_default_types(self):
        cmd = _build(ActiveTab.BROKEN_FILES)
        assert "-C" in cmd
        idx = cmd.index("-C")
        types_str = cmd[idx + 1]
        assert "AUDIO" in types_str
        assert "PDF" in types_str

    def test_only_video(self):
        ts = ToolSettings()
        ts.broken_audio = False
        ts.broken_pdf = False
        ts.broken_archive = False
        ts.broken_image = False
        ts.broken_video = True
        cmd = _build(ActiveTab.BROKEN_FILES, tool_settings=ts)
        idx = cmd.index("-C")
        assert cmd[idx + 1] == "VIDEO"


# ── Bad Names ────────────────────────────────────────────────────────


class TestBadNames:
    def test_default_checks(self):
        cmd = _build(ActiveTab.BAD_NAMES)
        assert "-u" in cmd  # uppercase ext
        assert "-j" in cmd  # emoji
        assert "-w" in cmd  # space
        assert "-n" in cmd  # non-ascii

    def test_restricted_charset(self):
        ts = ToolSettings()
        ts.bad_names_restricted_charset = "abc,def"
        cmd = _build(ActiveTab.BAD_NAMES, tool_settings=ts)
        # Note: bad_names uses -r for restricted charset, not reference dirs
        idx = cmd.index("-r")
        assert cmd[idx + 1] == "abc,def"


# ── Video Optimizer ──────────────────────────────────────────────────


class TestVideoOptimizer:
    def test_crop_mode_subcommand(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert cmd[1] == "video-optimizer"
        assert cmd[2] == "crop"

    def test_transcode_mode_subcommand(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert cmd[2] == "transcode"

    def test_crop_mechanism(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        ts.video_crop_mechanism = VideoCropMechanism.STATICCONTENT
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "staticcontent"

    def test_crop_reencode(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        ts.video_crop_reencode = True
        ts.video_crop_codec = VideoCodec.AV1
        ts.video_crop_quality = 30
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--target-codec" in cmd
        idx = cmd.index("--target-codec")
        assert cmd[idx + 1] == "av1"
        assert "--quality" in cmd
        q_idx = cmd.index("--quality")
        assert cmd[q_idx + 1] == "30"

    def test_crop_no_reencode_default(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--target-codec" not in cmd

    def test_crop_overwrite(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        ts.video_overwrite = True
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--overwrite-original" in cmd

    def test_crop_thumbnails(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        ts.video_thumbnail = True
        ts.video_thumbnail_percentage = 25
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "-t" in cmd
        idx = cmd.index("-V")
        assert cmd[idx + 1] == "25"

    def test_crop_thumbnail_grid(self):
        ts = ToolSettings()
        ts.video_opt_mode = "crop"
        ts.video_thumbnail_grid = True
        ts.video_thumbnail_grid_tiles = 4
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "-g" in cmd
        idx = cmd.index("-Z")
        assert cmd[idx + 1] == "4"

    def test_transcode_codec(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_codec = VideoCodec.VP9
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        idx = cmd.index("--target-codec")
        assert cmd[idx + 1] == "vp9"

    def test_transcode_fail_if_bigger(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_fail_if_bigger = True
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--fail-if-not-smaller" in cmd

    def test_transcode_overwrite(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_overwrite = True
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--overwrite-original" in cmd

    def test_transcode_limit_size(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_limit_size = True
        ts.video_max_width = 1280
        ts.video_max_height = 720
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--limit-video-size" in cmd
        assert "--max-width" in cmd
        idx = cmd.index("--max-width")
        assert cmd[idx + 1] == "1280"
        idx = cmd.index("--max-height")
        assert cmd[idx + 1] == "720"

    def test_transcode_limit_size_off(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_limit_size = False
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "--limit-video-size" not in cmd

    def test_transcode_thumbnails(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        ts.video_thumbnail = True
        ts.video_thumbnail_percentage = 50
        ts.video_thumbnail_grid = True
        ts.video_thumbnail_grid_tiles = 5
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "-t" in cmd
        idx = cmd.index("-V")
        assert cmd[idx + 1] == "50"
        assert "-g" in cmd
        idx = cmd.index("-Z")
        assert cmd[idx + 1] == "5"

    def test_excluded_codecs(self):
        ts = ToolSettings()
        ts.video_opt_mode = "transcode"
        cmd = _build(ActiveTab.VIDEO_OPTIMIZER, tool_settings=ts)
        assert "-c" in cmd
        idx = cmd.index("-c")
        assert "h265" in cmd[idx + 1]


# ── Similar Documents ────────────────────────────────────────────────


class TestSimilarDocuments:
    def test_default_args(self):
        cmd = _build(ActiveTab.SIMILAR_DOCUMENTS)
        assert "--similarity-threshold" in cmd
        assert "--num-hashes" in cmd
        assert "--shingle-size" in cmd

    def test_custom_threshold(self):
        ts = ToolSettings()
        ts.doc_similarity_threshold = 0.9
        cmd = _build(ActiveTab.SIMILAR_DOCUMENTS, tool_settings=ts)
        idx = cmd.index("--similarity-threshold")
        assert cmd[idx + 1] == "0.9"


# ── Unsupported tab ─────────────────────────────────────────────────


class TestUnsupportedTab:
    def test_settings_tab_returns_empty(self):
        cmd = _build(ActiveTab.SETTINGS)
        assert cmd == []

    def test_about_tab_returns_empty(self):
        cmd = _build(ActiveTab.ABOUT)
        assert cmd == []
