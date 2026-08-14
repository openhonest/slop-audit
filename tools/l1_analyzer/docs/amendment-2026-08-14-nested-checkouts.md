# Amendment 2026-08-14: a nested checkout is a different repository

The scan walked into any repository nested inside the one under audit and reported its code as part of the parent. Both tools now skip it.

## How it surfaced

The repository's own pre-commit gate blocked a commit with "type escapes (L1.15): 11 Any / # type: ignore hatches, over the ratchet of 0". No such escape existed in the tree being committed. All eleven were in `.claude/worktrees/agent-aa0b273070eedae58/`, a git worktree holding an older checkout of this same repository, created by a background agent and left behind when that agent was stopped.

The gate was reading code from a different commit and attributing it to this one. It is the same failure in either direction: a nested checkout can hide a real finding as easily as it can invent one.

## Why `.gitignore` did not help

The directory was gitignored. The analyzer never reads `.gitignore`; it walks the filesystem, and `_IGNORE_DIRS` is a fixed list of vendoring and tooling directory names. Nothing in it expresses "this subtree is a different repository".

## The rule

A directory below the root that carries its own `.git` is not part of this repository. Its files are neither measured nor counted.

`.git` is a directory in a clone and a **file** in a git worktree, so the test is existence rather than `is_dir`. The worktree case is the one that produced the false reading, and a rule that only recognised the directory form would have missed it.

The root's own `.git` is never consulted. Consulting it would prune every scan to nothing.

This covers all three shapes of the problem with one rule: a submodule working copy, a vendored clone committed with its history, and a git worktree.

## What it changes

Nothing on a repository with no nested checkout, which is the common case and includes all six corpus entries and every local repository used for parity. A repository that does carry one will now report smaller counts, correctly: the code it drops belongs to another repository with its own history and its own audit.

Verified end to end by recreating the exact failure: with a worktree of an older commit placed under `.claude/worktrees/`, the gate reports 0 of 0 type escapes and both tools still agree 16 of 16.

## Where it lives

Python: inside `_rglob_files`, the single boundary walker every reader already goes through, so all six scan sites inherit it. The ancestor test is memoised per call, so each directory is stat-ed once however many files it holds.

Rust: a new `walk_repo` in `lib.rs`, which every walk now uses. Seven hand-rolled `WalkDir::new` loops across the crate became one, which is the second half of this change: the reason the defect could exist in seven places at once is that the walk had been written seven times.

`filter_entry` prunes the whole subtree, so the walk never descends into a nested checkout at all.

## Regression cover

Python, `tests/test_bucketing.py`: a nested clone is not measured; a worktree whose `.git` is a file is not measured; the root repository is still measured in full.

Rust, `src/lib.rs`: one test covering the clone and the worktree shapes together.

The Python tests were run against the unfixed code and fail there, so they measure the fix rather than the fixture.

## Standing hazard

An agent worktree under the repository root is created by tooling, not by the author, and can outlive the process that made it. The measurement is now correct whether or not one is present, but a stale worktree is still worth removing: `git worktree list`, then `git worktree remove`, then `git worktree prune`.
