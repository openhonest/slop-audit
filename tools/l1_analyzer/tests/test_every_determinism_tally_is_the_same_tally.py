"""Five languages counted their randomized runs, and the counting was written five times.

The rules that must not drift are four: refuse a run that timed out, refuse a suite that
never executed, refuse a count over no runs at all, band the rest. C# and Java were merged
into one tally in August. Go, JavaScript and Ruby were left out, with a note in the source
saying they are not the same shape and that forcing them in would need a callback per
message.

The note was half right and the half it got wrong cost a day. On 2026-09-01 every timeout
refusal in this package learned to name the seconds it allowed and the flag that raises
them, and that meant editing this one rule in five places by hand. A rule I have to edit
five times is a rule that will be edited four times next.

What the three actually needed was two things, not a callback per message. A word for what
a timed-out attempt is called, because "a randomized run timed out" and "a seed timed out"
are different sentences about the same event. And the reason a suite did not run, read from
the outcome rather than fixed in advance, because Ruby quotes the exit code and the first
line of what the runner printed. The second is the same kind of parameter the failure
summary already was.

Go's own extra rule went rather than moving. It refused when it held fewer outcomes than
runs requested, and its only caller stops early on exactly the two cases the loop above
already refuses, so the check could never fire.
"""

import ast
import inspect

import pytest
from l1_analyzer import (
    csharp_trace,
    go_trace,
    java_trace,
    js_trace,
    pytest_trace,
    ruby_trace,
)

_SHARING = [csharp_trace, go_trace, java_trace, js_trace, ruby_trace, pytest_trace]


@pytest.mark.parametrize("module", _SHARING, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_no_language_counts_its_own_runs(module):
    """A language holding its own loop can drift on any of the four rules. Asserted on the
    verdict function rather than by counting a token: the first version of this test
    elsewhere counted `if returncode == 124:` and expected three, and there were ten."""
    verdict = getattr(module, "_determinism_verdict", None)
    if verdict is None:
        pytest.skip(f"{module.__name__} has no determinism verdict of its own")
    tree = ast.parse(inspect.getsource(verdict))
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
    assert not loops, f"{module.__name__} still counts its own runs"


def test_the_word_for_a_timed_out_attempt_is_the_language_s_own():
    """Java randomizes by seed, so attempt three is seed three. `dotnet test` has no seed
    and varies by scheduler, so attempt three is just run three. A reader must not be told
    about seeds by a C# report, and that is why this is a word rather than a constant."""
    seeded = pytest_trace.determinism_tally(
        [(124, "")], {"unit": "seed", "timed_out": "a randomized run timed out",
                      "no_runs": "none made", "describe": "runs passed"},
        lambda _out: True, lambda _out: "", lambda _rc, _out: "nothing ran",
        timeout_seconds=300.0)
    assert "a randomized run timed out (seed 1)" in seeded["details"]

    scheduled = pytest_trace.determinism_tally(
        [(124, "")], {"unit": "run", "timed_out": "a run timed out",
                      "no_runs": "none made", "describe": "runs passed"},
        lambda _out: True, lambda _out: "", lambda _rc, _out: "nothing ran",
        timeout_seconds=300.0)
    assert "seed" not in scheduled["details"]


def test_the_reason_a_suite_did_not_run_is_read_from_the_outcome():
    """Ruby quotes the exit code and the first line the runner printed, which cannot be a
    fixed string. It is the same kind of parameter the failure summary already was."""
    said = pytest_trace.determinism_tally(
        [(2, "cannot load such file -- rspec")],
        {"unit": "seed", "timed_out": "a run timed out", "no_runs": "none made",
         "describe": "runs passed"},
        lambda _out: False, lambda _out: "",
        lambda rc, out: f"exit {rc}: {out.splitlines()[0]}",
        timeout_seconds=300.0)
    assert "exit 2: cannot load such file -- rspec" in said["details"]


def test_a_language_with_a_fixed_reason_says_the_same_thing_every_time():
    """Java and C# know why before they look. The reader takes the outcome and ignores it,
    which is a fact about that language rather than a hole in the parameter."""
    said = pytest_trace.determinism_tally(
        [(1, "COMPILATION ERROR")],
        {"unit": "seed", "timed_out": "a run timed out", "no_runs": "none made",
         "describe": "runs passed"},
        lambda _out: False, lambda _out: "",
        lambda _rc, _out: "no tests executed under openjdk 21",
        timeout_seconds=300.0)
    assert "no tests executed under openjdk 21" in said["details"]


@pytest.mark.parametrize("module", [go_trace, js_trace, ruby_trace],
                         ids=["go", "javascript", "ruby"])
def test_the_three_that_were_left_out_now_ask_the_shared_rule(module):
    assert module.determinism_tally is pytest_trace.determinism_tally
