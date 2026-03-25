# Improvements for `czkawka-core`, `czkawka-cli`, and `kalka`

Verified against the current source. Items marked ~~strikethrough~~ were previously listed but confirmed not to be issues.

## Summary

The three highest-value improvements are:
1. Fix Kalka scan lifecycle bugs (stop flow, stderr handling).
2. Define a stable CLI JSON results contract.
3. Add cross-crate integration tests for that contract.

## `czkawka-core`

- ~258 instances of `.unwrap()`/`panic!`/`.expect()` in non-test code, some in user-facing algorithm paths (`similar_images/core.rs:258,401,412,425`). Convert recoverable ones to typed errors.
- Explicit `TODO` at `similar_images/core.rs:523` — reference-folder verification is not trusted.
- Newer features (fuzzy-name matching, `--no-self-compare`, similar documents, reference paths) lack test coverage.

## `czkawka-cli`

- Per-command dispatcher in `main.rs` duplicates setup/save/exit/progress wiring for every tool.
- No integration tests for subcommand argument parsing, exit codes, or JSON output.
- Warnings and diagnostics are logged but not included in machine-readable output.

## `kalka`

- **Stop-scan bug** (`backend.py:456-465`): `_check_stop_cleanup()` hardcodes `finished.emit(ActiveTab.DUPLICATE_FILES, [])` regardless of the active tool. Corrupts UI state.
- **Lost stderr**: non-JSON stderr lines from czkawka_cli are silently dropped (`backend.py:153-156`). Permission errors, skipped files, etc. never reach the user.
- **Missing Similar Documents tab**: CLI has `similar-docs` but `models.py:ActiveTab` has no entry.
- **`QTreeWidget` scaling**: `results_view.py` rebuilds the entire tree on every `set_results()`. Works with batch insert + signal blocking, but won't scale to large result sets.
- **Scan-state flags**: `AppState` uses loose booleans (`scanning`, `processing`, `stop_requested`) instead of a state machine.

### Not an issue

- ~~CLI argument construction for repeated values.~~ Comma-joining paths works correctly — `clap` parses comma-separated values into `Vec<PathBuf>`.

---

## Roadmap

| Phase | Focus | Effort | Depends on |
|-------|-------|--------|------------|
| 1 | Stabilize Kalka lifecycle | 1–2 days | — |
| 2 | Stable CLI JSON contract | 3–5 days | — |
| 3 | Integration tests for CLI contract | 2–3 days | Phase 2 |
| 4 | Core runtime robustness | 3–5 days | — |
| 5 | Kalka scalability (QTreeView, new tabs) | 5–8 days | Phase 2 |

---

## Task List

### Quick wins (< 1 day each)

- [ ] **Fix stop-scan cleanup** — store the active tab at scan start, use it in `_check_stop_cleanup()` instead of hardcoded `DUPLICATE_FILES`. (`kalka/app/backend.py`)
- [ ] **Surface stderr diagnostics** — collect non-JSON stderr lines during scan, display them in the bottom panel on completion. (`kalka/app/backend.py`)
- [ ] **Add Similar Documents to Kalka** — new `ActiveTab` entry, `TAB_TO_CLI_COMMAND` mapping, column definitions. (`kalka/app/models.py`, `left_panel.py`)
- [ ] **Resolve reference-folder TODO** — investigate and either fix or document the limitation at `similar_images/core.rs:523`.

### Medium (1–3 days each)

- [ ] **Stable JSON results envelope** — add `schema_version`, `tool_type`, `messages` wrapper to CLI output. Optional `--json-results-stdout` mode. (`czkawka_cli/src/main.rs`)
- [ ] **CLI integration tests** — per-subcommand tests covering argument parsing, exit codes, and JSON output shape. (`czkawka_cli/tests/`)
- [ ] **Scan state machine** — replace `scanning`/`processing`/`stop_requested` booleans in `AppState` with an enum-based state machine (idle → scanning → stopping → idle). (`kalka/app/state.py`)
- [ ] **Strongly type settings** — convert `excluded_items`, `allowed_extensions`, `excluded_extensions` from raw strings to lists at the settings layer. (`kalka/app/models.py`, `backend.py`)

### Deep refactors (5+ days each)

- [ ] **Replace `QTreeWidget` with `QTreeView` + model** — implement `QAbstractItemModel` for results, move sorting/selection into model layer. (`kalka/app/results_view.py`)
- [ ] **Reduce CLI command dispatch duplication** — extract a trait/runner abstraction so tool setup, saving, exit handling, and progress wiring are defined once. (`czkawka_cli/src/main.rs`)
- [ ] **Audit and reduce runtime panics** — systematic pass over ~258 `unwrap`/`panic`/`expect` sites in `czkawka_core`, converting user-triggerable ones to typed errors. (`czkawka_core/src/`)
- [ ] **Standardize result metadata** — common serialized envelope across all core tools so consumers don't infer shape per-tool. (`czkawka_core/src/`)
