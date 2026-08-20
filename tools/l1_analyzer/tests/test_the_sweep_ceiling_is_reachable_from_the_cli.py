"""The operator can set the ceiling the sweep stops at.

A regression I introduced earlier today. `prove_coverage_repo` gained `max_attempts` to
bound what a whole-repository sweep may spend, defaulting to 5. The CLI never passes it, so
`--prove-coverage-repo` silently attempts at most five gaps and prints "STOPPED AT THE
CEILING: 5 of 157" with no flag that could change it.

Before the ceiling that path was bounded only per module, so this narrowed real behaviour
and left the operator no way back. A limit the person running the tool cannot see or set is
not a budget, it is a wall.

`--prove-max` is the other cap and means something different: how many gaps ONE MODULE may
offer. Both are needed. Five per module over forty modules is two hundred attempts, which
is what the run ceiling exists to bound.
"""

import inspect
import subprocess
import sys

from l1_analyzer import cli, coverage_prove, python_coverage_prove


def _flags() -> str:
    """The parser's own help, which is what an operator actually sees."""
    return subprocess.run([sys.executable, "-m", "l1_analyzer.cli", "--help"],
                          capture_output=True, text=True, check=False).stdout


def test_the_run_ceiling_has_a_flag():
    help_text = _flags()
    assert "--prove-max-total" in help_text, (
        "the whole-repository sweep is capped at its default with no flag to raise it, so "
        "an operator is told it stopped at a ceiling they cannot reach"
    )


def test_the_help_says_what_the_two_caps_mean():
    """Two numbers that both bound a sweep and bound different things. An operator reading
    one and setting the other spends nothing and learns nothing."""
    help_text = _flags()
    assert "module" in help_text.lower()
    assert "--prove-max" in help_text


def test_both_sweeps_are_handed_the_ceiling():
    """Read from the source, because reaching the real sweep needs a key and a toolchain."""
    source = inspect.getsource(cli.main)
    assert source.count("max_attempts=") == 2, (
        "one of the two language sweeps is still called without the run ceiling"
    )


def test_the_ceiling_still_defaults_where_no_operator_is_present():
    """A library caller that names no ceiling gets the documented 5 rather than an
    unbounded run. The flag is the operator's control, not a removal of the bound."""
    for sweep in (coverage_prove.prove_coverage_repo, python_coverage_prove.prove_coverage_repo):
        assert inspect.signature(sweep).parameters["max_attempts"].default == 5
