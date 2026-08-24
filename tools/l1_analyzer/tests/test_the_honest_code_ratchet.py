"""L1.21 on this package's own commits, which nothing enforced until now.

The dogfood gate ran god-files, finite testability and the type-escape ratchet. It never
ran L1.21. The conformity number moved only when somebody remembered to type the command,
which is the condition under which a number drifts: nothing fails when it gets worse.

A ratchet rather than a bright line, because this package is not at a hundred per cent. The
baseline sits at the current count and a NEW finding fails the commit. Raising it is a
deliberate, reviewable change in the hook config, exactly as the type-escape ratchet works.

Slack is a defect too, and the existing `_slack` check is reused: a baseline looser than
reality lets the next violation in for free, so the gate says so and fails.
"""

import pathlib

from l1_analyzer import gate


def _gate(max_findings: int | None) -> int:
    return gate._run_gate(pathlib.Path(__file__).parent.parent, "python",
                         max_type_escapes=None, max_thread_exposed=None,
                         max_honest_code=max_findings)


def test_the_gate_ignores_the_clause_check_when_no_baseline_is_given():
    """Every other repository this tool gates. L1.21 is opt-in there and stays opt-in."""
    assert _gate(None) == 0


def test_a_baseline_at_the_current_count_passes():
    from l1_analyzer import honest_code

    now = len(honest_code.analyze(pathlib.Path(__file__).parent.parent, "python")["findings"])
    assert _gate(now) == 0


def test_a_baseline_below_the_current_count_fails():
    """What a new violation looks like: the count rises past the number in the config."""
    assert _gate(0) != 0


def test_a_baseline_above_the_current_count_fails_as_slack(capsys):
    """A baseline looser than reality is a free pass for the next violation, so it is
    reported rather than quietly honoured."""
    from l1_analyzer import honest_code

    now = len(honest_code.analyze(pathlib.Path(__file__).parent.parent, "python")["findings"])
    assert _gate(now + 5) != 0
    said = (capsys.readouterr().out + capsys.readouterr().err).lower()
    # The message rather than the word. It names the baseline, the real count, and how many
    # regressions the gap would let through unreported.
    assert "ratchet is set at" in said and str(now) in said
