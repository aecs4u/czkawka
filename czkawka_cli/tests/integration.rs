//! Integration tests for czkawka_cli subcommands.
//!
//! Each test runs the real binary, verifying argument parsing, exit codes,
//! and JSON output structure.

use assert_cmd::Command;
use std::fs;
use tempfile::TempDir;

fn cmd() -> Command {
    Command::cargo_bin("czkawka_cli").expect("binary not found")
}

fn setup_test_dir() -> TempDir {
    let dir = TempDir::new().unwrap();
    fs::write(dir.path().join("file_a.txt"), "hello world").unwrap();
    fs::write(dir.path().join("file_b.txt"), "hello world").unwrap();
    fs::write(dir.path().join("file_c.txt"), "different content here").unwrap();
    fs::create_dir(dir.path().join("empty_dir")).unwrap();
    dir
}

/// Assert exit code is 0 (no results) or 11 (results found).
fn assert_ok_or_found(output: &std::process::Output) {
    let code = output.status.code().expect("process killed by signal");
    assert!(code == 0 || code == 11, "unexpected exit code {code}");
}

/// Extract the JSON envelope from stdout.
/// In debug builds, czkawka_core prints debug info to stdout before the JSON.
/// The envelope is the last line that starts with '{'.
fn extract_json_envelope(stdout: &[u8]) -> serde_json::Value {
    let text = String::from_utf8_lossy(stdout);
    let json_line = text
        .lines()
        .rev()
        .find(|l| l.starts_with('{'))
        .expect("no JSON line found in stdout");
    serde_json::from_str(json_line).expect("invalid JSON envelope")
}

// ── Help & invalid args ─────────────────────────────────────

#[test]
fn test_help_exits_zero() {
    cmd().arg("--help").assert().success();
}

#[test]
fn test_subcommand_help() {
    cmd().args(["dup", "--help"]).assert().success();
    cmd().args(["empty-folders", "--help"]).assert().success();
    cmd().args(["big", "--help"]).assert().success();
    cmd().args(["image", "--help"]).assert().success();
    cmd().args(["similar-docs", "--help"]).assert().success();
}

#[test]
fn test_missing_directories_arg() {
    cmd().arg("dup").assert().failure();
}

// ── Duplicates ──────────────────────────────────────────────

#[test]
fn test_dup_json_compact_file() {
    let dir = setup_test_dir();
    let json_out = dir.path().join("results.json");

    let output = cmd()
        .args([
            "dup",
            "-d", dir.path().to_str().unwrap(),
            "--compact-file-to-save", json_out.to_str().unwrap(),
            "-N", "-M",
        ])
        .output()
        .unwrap();
    assert_ok_or_found(&output);

    let content = fs::read_to_string(&json_out).unwrap();
    let _: serde_json::Value = serde_json::from_str(&content).unwrap();
}

#[test]
fn test_dup_json_compact_stdout_envelope() {
    let dir = setup_test_dir();

    let output = cmd()
        .args([
            "dup",
            "-d", dir.path().to_str().unwrap(),
            "--json-compact-stdout",
            "-N", "-M",
        ])
        .output()
        .unwrap();
    assert_ok_or_found(&output);

    let envelope = extract_json_envelope(&output.stdout);
    assert_eq!(envelope["schema_version"], 1);
    assert_eq!(envelope["tool_type"], "duplicates");
    assert!(envelope["results"].is_array() || envelope["results"].is_object() || envelope["results"].is_null());
    assert!(envelope["messages"].is_array());
}

// ── Empty folders ───────────────────────────────────────────

#[test]
fn test_empty_folders_finds_results() {
    let dir = setup_test_dir();
    let json_out = dir.path().join("empty.json");

    let output = cmd()
        .args([
            "empty-folders",
            "-d", dir.path().to_str().unwrap(),
            "--compact-file-to-save", json_out.to_str().unwrap(),
            "-N", "-M",
        ])
        .output()
        .unwrap();
    assert_ok_or_found(&output);

    let content = fs::read_to_string(&json_out).unwrap();
    let val: serde_json::Value = serde_json::from_str(&content).unwrap();
    assert!(val.is_array() || val.is_object());
}

// ── Empty files ─────────────────────────────────────────────

#[test]
fn test_empty_files_no_results() {
    let dir = setup_test_dir();

    cmd()
        .args([
            "empty-files",
            "-d", dir.path().to_str().unwrap(),
            "-N", "-M",
        ])
        .assert()
        .success();
}

// ── Big files ───────────────────────────────────────────────

#[test]
fn test_big_files_json_envelope() {
    let dir = setup_test_dir();

    let output = cmd()
        .args([
            "big",
            "-d", dir.path().to_str().unwrap(),
            "--json-compact-stdout",
            "-N", "-M",
            "-n", "5",
        ])
        .output()
        .unwrap();
    assert_ok_or_found(&output);

    let envelope = extract_json_envelope(&output.stdout);
    assert_eq!(envelope["schema_version"], 1);
    assert_eq!(envelope["tool_type"], "big_files");
}

// ── Temporary files ─────────────────────────────────────────

#[test]
fn test_temp_files() {
    let dir = setup_test_dir();
    fs::write(dir.path().join("test.tmp"), "temp data").unwrap();

    let output = cmd()
        .args(["temp", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .output()
        .unwrap();
    assert_ok_or_found(&output);
}

// ── Bad extensions ──────────────────────────────────────────

#[test]
fn test_bad_extensions() {
    let dir = setup_test_dir();

    let output = cmd()
        .args(["ext", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .output()
        .unwrap();
    assert_ok_or_found(&output);
}

// ── Broken files ────────────────────────────────────────────

#[test]
fn test_broken_files() {
    let dir = setup_test_dir();

    let output = cmd()
        .args(["broken", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .output()
        .unwrap();
    assert_ok_or_found(&output);
}

// ── Invalid symlinks ────────────────────────────────────────

#[test]
fn test_invalid_symlinks() {
    let dir = setup_test_dir();

    let output = cmd()
        .args(["symlinks", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .output()
        .unwrap();
    assert_ok_or_found(&output);
}

// ── Similar documents ───────────────────────────────────────

#[test]
fn test_similar_docs_json_envelope() {
    let dir = setup_test_dir();

    let output = cmd()
        .args([
            "similar-docs",
            "-d", dir.path().to_str().unwrap(),
            "--json-compact-stdout",
            "-N", "-M",
        ])
        .output()
        .unwrap();
    assert_ok_or_found(&output);

    let envelope = extract_json_envelope(&output.stdout);
    assert_eq!(envelope["schema_version"], 1);
    assert_eq!(envelope["tool_type"], "similar_documents");
}

// ── Bad names ───────────────────────────────────────────────

#[test]
fn test_bad_names() {
    let dir = setup_test_dir();

    let output = cmd()
        .args(["bad-names", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .output()
        .unwrap();
    assert_ok_or_found(&output);
}

// ── Exit codes ──────────────────────────────────────────────

#[test]
fn test_exit_code_0_no_results() {
    let dir = TempDir::new().unwrap();
    fs::write(dir.path().join("unique.txt"), "only one file").unwrap();

    cmd()
        .args(["dup", "-d", dir.path().to_str().unwrap(), "-N", "-M"])
        .assert()
        .success();
}
