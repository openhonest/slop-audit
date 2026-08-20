"""No test replaces a name inside the package it is testing.

The same class of defect landed three times: a function reaching for a collaborator
instead of taking one. `_prove_one` fixed it first and wrote the reason at its site,
`prove_hazard` fixed it second, `model_call.call` third. Each was found by hand, and each
time the tell was the same: a test could only reach the path by overwriting a name in the
module under test.

Three of one class means the shape is permitted rather than unlucky, so it is worth
detecting rather than repairing a fourth. `monkeypatch.setattr` against anything in
`l1_analyzer` is the mechanical signature, and it is a symptom with one cause: something
the code reaches for should have been handed in.

The 2026-08-17 fixture sweep deleted a set of tests for exactly this and said why: a test
that reaches in to replace what it is testing asserts against its own fixture. It passes
when the real thing is broken, because the real thing is not there.

The ENVIRONMENT is not in scope. `setenv` and `delenv` set the state of the machine, which
is what a boundary is supposed to read, and there is nothing to hand in instead: the
absence of an API key is a fact about where the process is running.
"""

import pathlib
import re

TESTS = pathlib.Path(__file__).parent

# `setattr` against a module or object of the package under test. `setenv` and `delenv` are
# environment, and `sys.argv` or a stdlib name is not this package's own contract.
_PATCHES_THE_PACKAGE = re.compile(
    r"monkeypatch\.setattr\(\s*(?:l1_analyzer|"
    r"(?:cli|card|report|indicators|prove|coverage_prove|python_coverage_prove|model_call|"
    r"dead_code|secret_scan|clone_detect|vacuity|state_bounds|mutable_state|thread_surface|"
    r"race_harness|live_sweep|scope|pytest_trace|rust_trace|js_trace|go_trace|java_trace|"
    r"ruby_trace|c_trace|csharp_trace)\b)"
)


def _offenders() -> list[str]:
    found = []
    for path in sorted(TESTS.rglob("*.py")):
        # This file carries the pattern's own examples, so it matches itself. Excluded by
        # name rather than by weakening the pattern: a check that cannot spell the shape it
        # looks for is worth less than the false positive it avoids.
        if path.name == pathlib.Path(__file__).name:
            continue
        for number, line in enumerate(path.read_text().split("\n"), start=1):
            code = line.split("#", 1)[0]
            if _PATCHES_THE_PACKAGE.search(code):
                found.append(f"{path.relative_to(TESTS)}:{number}")
    return found


def test_no_test_patches_a_name_inside_the_package():
    assert not _offenders(), (
        "these tests replace a name in the module they are testing: "
        f"{_offenders()}. That is a symptom with one cause - something the code reaches "
        "for should be handed in - and it is how three defects in this package hid."
    )


def test_the_check_would_notice_one():
    """A guard nobody can see fail is a guard nobody should trust. This proves the pattern
    matches the shape it is written for, without leaving one in the suite to be matched."""
    assert _PATCHES_THE_PACKAGE.search('monkeypatch.setattr(model_call, "_import_client", x)')
    assert _PATCHES_THE_PACKAGE.search("monkeypatch.setattr(l1_analyzer.prove, 'generate', x)")
    assert _PATCHES_THE_PACKAGE.search("monkeypatch.setattr(indicators, '_get_parser', x)")


def test_the_check_leaves_the_environment_alone():
    """Setting an environment variable is not replacing a collaborator. A boundary is
    supposed to read the machine's state, and the absence of an API key is a fact about
    where the process is running rather than a thing to hand in."""
    for line in ('monkeypatch.setenv("ANTHROPIC_API_KEY", "x")',
                 'monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)',
                 'monkeypatch.setattr(sys, "argv", ["prog"])'):
        assert not _PATCHES_THE_PACKAGE.search(line), line
