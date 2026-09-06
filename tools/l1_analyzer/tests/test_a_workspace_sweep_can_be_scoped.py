"""A workspace with one target that will not build must not cost the whole sweep.

Reported on 2026-09-06 by the session auditing turso. One test target there links a library
with a relative `-L target/debug` baked into its build, and cargo-llvm-cov redirects output
to `target/llvm-cov-target/debug`, so the linker never finds the cdylib. One target that
will not link fails the whole workspace build, and the sweep had no way to say "read this
workspace but not that package". The only scoping lever was which directory you pointed at,
which is why `core/` worked and the repository root did not.

Cargo already has the words for this: `-p`, `--exclude`, `--workspace`. So the arguments go
through untouched rather than being reinvented here. The alternative considered was
degrading per package, and it is worse: the tool would pick which packages to drop on its
own and then report a share of a denominator nobody named.

What the run was scoped by is named in the report, because a coverage figure over part of a
workspace is a different number from one over all of it.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import rust_trace


def test_the_command_carries_the_arguments_it_was_given():
    built = rust_trace.llvm_cov_command(
        "cargo", Path("/tmp/cov.json"), ("--workspace", "--exclude", "turso_sqlite3"))
    assert built[:2] == ["cargo", "llvm-cov"]
    assert built[-3:] == ["--workspace", "--exclude", "turso_sqlite3"]


def test_the_command_with_no_arguments_is_what_it_always_was():
    """The other direction. Passing nothing must not change a run that scoped nothing, or
    every existing measurement moves for a reason nobody asked for."""
    assert rust_trace.llvm_cov_command("cargo", Path("/tmp/cov.json"), ()) == [
        "cargo", "llvm-cov", "--json", "--quiet", "--output-path", "/tmp/cov.json"]


def test_the_arguments_go_after_the_output_path_so_they_cannot_replace_it():
    """The report file is this reader's, not the caller's. A caller who passes their own
    --output-path gets both, and cargo takes the last, which is theirs: that is a way to
    lose the report. Worth knowing rather than guarding, since guarding would mean parsing
    cargo's option grammar here, which is the reinvention this pass-through avoids."""
    built = rust_trace.llvm_cov_command("cargo", Path("/tmp/cov.json"), ("--workspace",))
    assert built.index("--output-path") < built.index("--workspace")
