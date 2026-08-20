"""Every knob that changes what a run costs is reachable from the command line.

I added `max_attempts` to bound what a whole-repository sweep may spend and did not give
the CLI a flag for it, so `--prove-coverage-repo` attempted five gaps and printed "STOPPED
AT THE CEILING: 5 of 157" with nothing an operator could set. A limit the person running
the tool cannot see or change is not a budget, it is a wall.

The rule that would have caught it, stated once: a parameter that bounds how much work a
run does, how long it may take, or how many model calls it may make is the operator's
decision. It belongs in the parser, not only in a default.

Callbacks and interpreters are not cost knobs. `progress` is how the caller receives
output, and `python_executable` already has `--python`; neither changes what a run spends.
"""

import inspect
import subprocess
import sys

import pytest
from l1_analyzer import cli, coverage_prove, python_coverage_prove

# The parameter and the flag that must reach it. Named as pairs rather than inferred,
# because a flag whose name resembles a parameter proves nothing about whether it arrives.
COST_KNOBS = [
    ("cap_per_module", "--prove-max"),
    ("max_attempts", "--prove-max-total"),
    ("repair_rounds", "--coverage-repair-rounds"),
    ("timeout_seconds", "--timeout"),
]


def _help() -> str:
    return subprocess.run([sys.executable, "-m", "l1_analyzer.cli", "--help"],
                          capture_output=True, text=True, check=False).stdout


@pytest.mark.parametrize(("knob", "flag"), COST_KNOBS)
@pytest.mark.parametrize("sweep", [coverage_prove.prove_coverage_repo,
                                   python_coverage_prove.prove_coverage_repo],
                         ids=["rust", "python"])
def test_each_cost_knob_is_a_parameter_of_both_sweeps(sweep, knob, flag):
    assert knob in inspect.signature(sweep).parameters, (
        f"{sweep.__module__} does not take {knob}, so {flag} has nothing to reach"
    )


@pytest.mark.parametrize(("knob", "flag"), COST_KNOBS)
def test_each_cost_knob_has_a_flag_an_operator_can_read(knob, flag):
    assert flag in _help(), f"{knob} bounds what a run costs and no flag sets it"


@pytest.mark.parametrize(("knob", "_flag"), COST_KNOBS)
def test_each_cost_knob_is_actually_handed_to_the_sweeps(knob, _flag):
    """A flag that parses and is never passed on is worse than no flag: it tells an
    operator they set something. Both language sweeps are called, so each knob appears
    twice in the source that calls them."""
    source = inspect.getsource(cli.main)
    assert source.count(f"{knob}=") >= 2, (
        f"{knob} reaches at most one of the two sweeps from the CLI"
    )


def test_a_callback_is_not_a_cost_knob():
    """The rule has an edge and it is worth stating: `progress` is how the caller receives
    output and changes nothing about what a run spends, so it is a parameter with no flag
    and that is correct."""
    assert "progress" in inspect.signature(coverage_prove.prove_coverage_repo).parameters
    assert "--progress" not in _help()
