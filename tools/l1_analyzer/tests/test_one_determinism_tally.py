"""C# and Java tally their determinism runs with one function, not two identical ones.

The two `_determinism_verdict` bodies were the same statement for statement: compared with
every string literal blanked and the parameter renamed, they are byte-identical. What
differs is vocabulary, and the difference is real. Java randomizes by seed, so run three is
seed three; `dotnet test` has no seed CLI and varies by scheduler, so run three is just run
three. A reader must not be told about seeds by a C# report.

L1.13 found this. It compares the SHAPE of code with identifiers and literals normalized,
which is exactly the difference between these two, and it was the first measurement of
this package ever taken because the indicator had shelled out to a tool nobody had.

The other three tallies, Go, JavaScript and Ruby, are NOT the same shape and are left
alone. Forcing them into one function would need a callback per message, which is
machinery invented to solve a problem the right shape does not have.
"""

import pytest
from l1_analyzer import csharp_trace, java_trace, pytest_trace


def test_both_languages_tally_through_one_function():
    """Asserted on the rules rather than on the wrappers: each language keeps a thin
    function holding its own words, and both hand the counting to the same place."""
    for module in (csharp_trace, java_trace):
        assert module.determinism_tally is pytest_trace.determinism_tally


@pytest.mark.parametrize("module", [csharp_trace, java_trace], ids=["csharp", "java"])
def test_neither_language_keeps_a_loop_of_its_own(module):
    """The rules that must not drift are the loop's: refuse a timeout, refuse a suite that
    never ran, refuse a zero denominator, band the rest. A language holding its own loop is
    a language that can drift on any of the four, so each of these two now holds words and
    no control flow at all.

    Asserted on the function rather than by counting a token across the package. The first
    version of this test counted `if returncode == 124:` and expected three; there are ten,
    because the coverage verdicts refuse a timeout too. A test whose number is a guess
    passes for the wrong reason as easily as it fails."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(module._determinism_verdict))
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
    assert not loops, f"{module.__name__} still counts its own runs"


@pytest.mark.parametrize(("module", "word", "absent"), [
    (csharp_trace, "run", "seed"),
    (java_trace, "seed", "scheduler"),
])
def test_each_language_keeps_its_own_word_for_a_run(module, word, absent):
    """A timed-out attempt is reported in the vocabulary of the thing that varied."""
    result = module._determinism_verdict(iter([(124, "")]), "toolchain 1.0")
    assert result["band"] == "n/a"
    assert word in result["details"], result["details"]
    assert absent not in result["details"], result["details"]


@pytest.mark.parametrize("module", [csharp_trace, java_trace])
def test_no_runs_at_all_refuses_rather_than_banding_healthy(module):
    """Zero clean out of zero satisfies "every run passed" and would band Healthy, which is
    the zero-denominator lie this package exists to refuse."""
    result = module._determinism_verdict(iter([]), "toolchain 1.0")
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"


@pytest.mark.parametrize("module", [csharp_trace, java_trace])
def test_a_suite_that_never_ran_is_not_a_failing_run(module):
    result = module._determinism_verdict(iter([(0, "no tests here")]), "toolchain 1.0")
    assert result["band"] == "n/a"
    assert "did not run" in result["details"]


@pytest.mark.parametrize(("module", "output"), [
    (csharp_trace, "Passed!  - Failed: 0, Passed: 3"),
    (java_trace, "Tests run: 3, Failures: 0, Errors: 0, Skipped: 0"),
])
def test_all_clean_runs_band_healthy(module, output):
    result = module._determinism_verdict(iter([(0, output)] * 5), "toolchain 1.0")
    assert result["value"] == "5/5"
    assert result["band"] == "Healthy"
