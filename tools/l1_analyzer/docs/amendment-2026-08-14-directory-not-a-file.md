# Amendment 2026-08-14: a directory is not an unreadable file

## What was wrong

Every scan in `indicators.py` walked the target with `repo.rglob(f"*{ext}")`, and `rglob` yields directories as well as files. A directory whose name ends in a source extension therefore reached the reader, raised `IsADirectoryError`, was caught by the `except OSError` arm, and was disclosed as `1 file(s) unreadable and excluded`.

The disclosure was false twice over: the path is not a file, and it is not unreadable. It reported a partial scan where the scan was complete, which is the opposite of what the skipped-count exists to do.

`node_modules/decimal.js` is such a directory and is common. On `~/dev/domx` the defect showed in L1.17:

- Before: `0/6 files >1k LOC, 0 >4k LOC; 1 >1k LOC scoped out (tests), 107 >1k LOC scoped out (vendored); 1 file(s) unreadable and excluded`
- After: `0/6 files >1k LOC, 0 >4k LOC; 1 >1k LOC scoped out (tests), 107 >1k LOC scoped out (vendored)`

The three readers named in the defect were `_read_source_bytes` (L1.15, L1.19 and the finite-testability path), `_read_text_files` (L1.16) and `_god_files` (L1.17). The architectural cause was wider: every scan site repeated `repo.rglob(...)` and each one had to remember on its own what `rglob` yields. Six sites, one of them a language detector that counted a directory named `decimal.js` as a JavaScript file.

## The fix

One boundary walker, `_rglob_files(repo, pattern)`, yields files only. All six scan sites go through it: `_repo_has_packages`, `_read_source_bytes`, `bucketed_paths`, `_read_text_files`, `detect_primary_language` and `_god_files`. No reader repeats `rglob` any more, so the next reader cannot reintroduce the defect by forgetting.

`Path.is_file()` follows symlinks, which keeps two behaviours intact:

- a symlinked source file is still read and measured;
- a file the process may not read still reaches the reader, still raises `OSError`, and is still counted and disclosed. That path is the honest one and it is untouched.

## The port

`tools/slop-audit-rs` is a certified-equivalent redistribution, so the same change lands there in the same commit. It carried the defect deliberately, to stay equal; the comments that said so are rewritten to describe the corrected behaviour.

`lib.rs` gains `is_file_entry(&DirEntry)`, the mirror of Python's `Path.is_file()`: walkdir reports the *link's* own type, so a bare `entry.file_type().is_file()` would drop a symlinked source file the reference reads. Every walk filters on it: `source_files`, `repo_has_packages`, `lang::detect_primary_language`, `god_files`, `type_escapes`, `decision_space`, `absolute_paths`. `min_depth(1)` stays, because `rglob` yields descendants only.

## Regression cover

`tools/l1_analyzer/tests/test_basic.py`:

- `test_directory_named_like_a_source_file_is_ignored_by_every_reader` — a `decimal.js` directory and a `pkg.py` directory beside one real file: `_read_source_bytes` and `_read_text_files` both report `skipped == 0` and return the file alone, and L1.17 reads `0/1 files >1k LOC, 0 >4k LOC` with no unreadable note.
- `test_a_directory_does_not_hide_a_genuinely_unreadable_file` — the same directories plus a `chmod 000` file: L1.17 discloses `1 file(s) unreadable and excluded`, and both readers report `skipped == 1`. Exactly one, the real file.

`tools/slop-audit-rs/src/indicators/god_files.rs`:

- `a_directory_named_like_a_source_file_is_skipped_in_silence`
- `a_genuinely_unreadable_file_is_still_disclosed`

Both pairs were run against the unfixed code first and both pairs failed there.

## Parity

Checked after the change, 16/16 indicators equal on each:

- the slop-audit worktree itself (python)
- `~/dev/domx` (javascript, the repo that carries the `node_modules/decimal.js` directory)
- the `c` corpus: `json-c/json-c` and `libuv/libuv`

## Note for Paper A

Any repository that holds a directory named like a source file loses a spurious "unreadable" note, and its `detect_primary_language` count for that extension drops by one such directory. Neither changes an indicator's value unless the directory was the tie-breaker in language detection. This is a defect correction, not a definitional change.
