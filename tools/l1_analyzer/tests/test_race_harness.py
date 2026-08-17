"""The two pure pieces of the ThreadSanitizer harness: the command it would run, and the
one line it quotes back when the build fails.

Everything else in race_harness probes a toolchain or executes untrusted code, and the
behaviour-level cases live in tests/bdd. These two decide what the report SAYS - a wrong
flag makes the sanitizer silently no-op, and a wrong line makes an n/a reason useless -
so they are pinned here on values, with no process started and nothing patched.
"""

import pytest
from l1_analyzer.race_harness import _first_error, _rust_tsan_command

# --- the command ------------------------------------------------------------

def test_the_tsan_command_is_the_whole_invocation():
    """Pinned as a whole list, not by substring. Each element is load-carrying and the
    order is the invocation: `+nightly` selects the toolchain that has the sanitizer,
    `-Zbuild-std` rebuilds std with it (without which the instrumentation is partial),
    the explicit `--target` is what turns the instrumentation on at all, and everything
    after the bare `--` is passed to the test binary rather than to cargo."""
    assert _rust_tsan_command("aarch64-apple-darwin") == [
        "cargo", "+nightly", "test", "-Zbuild-std",
        "--target", "aarch64-apple-darwin",
        "--", "--test-threads=4",
    ]


def test_the_target_triple_lands_in_the_target_slot_and_nowhere_else():
    """The caller passes a triple discovered from `rustc -vV`. It must reach cargo as the
    value of --target; a triple that landed anywhere else would be read as a test filter."""
    cmd = _rust_tsan_command("x86_64-unknown-linux-gnu")
    assert cmd[cmd.index("--target") + 1] == "x86_64-unknown-linux-gnu"
    assert cmd.count("x86_64-unknown-linux-gnu") == 1


def test_the_test_binary_arguments_sit_after_the_bare_separator():
    """`--test-threads=4` is an argument to the compiled test harness, not to cargo. It
    has to sit behind the `--`, and the 4 is the contention the run depends on: a single
    test thread schedules nothing for TSan to catch."""
    cmd = _rust_tsan_command("t")
    assert cmd[cmd.index("--"):] == ["--", "--test-threads=4"]


def test_an_empty_target_is_passed_through_unchecked():
    """Real behaviour, pinned to say where the check lives rather than to bless the input.
    The function validates nothing; detect_races refuses to call it at all when
    _host_target() came back None, so the absent-target case is decided at the boundary
    and never inside here."""
    assert _rust_tsan_command("")[5] == ""


# --- the quoted build error -------------------------------------------------

def test_the_first_error_line_is_the_one_reported():
    """cargo prints the failures in order and then a summary. The first is the cause; the
    later ones are its consequences, so picking the first is what makes the n/a reason
    point at something a reader can act on."""
    output = ("   Compiling demo v0.1.0\n"
              "error[E0308]: mismatched types\n"
              "  --> src/lib.rs:4:9\n"
              "error: aborting due to 1 previous error\n")
    assert _first_error(output) == "error[E0308]: mismatched types"


def test_indentation_does_not_hide_an_error_line():
    """cargo indents errors nested under a build script. The line is stripped before the
    test and before it is returned, so the reason carries no leading run of spaces."""
    assert _first_error("        error: linking with `cc` failed\n") == "error: linking with `cc` failed"


@pytest.mark.parametrize("output", ["", "\n\n", "   Compiling demo v0.1.0\nwarning: unused `x`\n"])
def test_output_with_no_error_line_gets_a_named_fallback(output):
    """The caller has already decided the build failed - it reaches _first_error only after
    matching "error[" or "could not compile" in the output. When no single line carries the
    word, the reason says so instead of returning an empty string, which would print as a
    reason that trailed off after the colon."""
    assert _first_error(output) == "unknown build error"


def test_a_capitalised_error_line_is_not_matched():
    """Real behaviour, and it surprised the reading: the test is case-sensitive, so a
    linker's `Error:` falls through to the fallback. cargo and rustc both emit lowercase
    `error`, which is what the harness reads, and the fallback is honest about the miss
    rather than quoting an unrelated line."""
    assert _first_error("Error: could not find `Cargo.toml`\n") == "unknown build error"


def test_a_long_error_line_is_truncated_to_two_hundred_characters():
    """A rustc type-mismatch line can run for thousands of characters. The reason string is
    a report field, so the line is cut at 200 - the cut is what keeps one build failure
    from swallowing the finding it is attached to."""
    line = "error: " + "x" * 500
    got = _first_error(line)
    assert len(got) == 200
    assert got == line[:200]
