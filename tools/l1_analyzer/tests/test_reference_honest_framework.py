"""Reference test: the meter's verdict on honest-framework's reference server.

honest-framework (openhonest/honest-framework) is the reference implementation of the
Honest Framework - deliberately kept finitely testable. Its FastAPI entry point,
python/app.py, is the file that once surfaced a meter false positive: `app.get(path)
(handler)` (route registration in call form) was misread as dynamic dispatch on `app`
and flagged UNRESOLVED, downgrading the whole codebase from CAN to MIGHT.

This pins the correct answer against a vendored, verbatim snapshot of that file
(tests/reference/honest_framework_app.txt), so a future change to the classifier
cannot silently re-dirty the reference. It is a frozen snapshot on purpose: it guards
the METER, not honest-framework's own evolution. Refresh the snapshot deliberately if
the reference server changes in a way this should track.
"""

from pathlib import Path

from l1_analyzer import state_bounds

_FIXTURE = Path(__file__).parent / "reference" / "honest_framework_app.txt"


def test_meter_gives_honest_framework_reference_server_a_clean_bill(tmp_path):
    (tmp_path / "app.py").write_text(_FIXTURE.read_text())
    r = state_bounds.classify(tmp_path, "python")

    # The reference server is finitely testable: no unbounded state, nothing the meter
    # must fail-close on. The FastAPI app object is configuration, not a decision.
    assert r["counts"]["promiscuous"] == 0
    assert r["counts"]["unresolved"] == 0, (
        "the reference server must not fail-close: "
        + ", ".join(f"{f['state']}@{f['line']}" for f in r["findings"] if f["verdict"] == "unresolved")
    )
    assert r["verdict"] == "neutral"

    # Specifically, the app singleton and the templates object are neutral, not
    # dispatched - this is the exact false positive the fix removed.
    by_state = {f["state"]: f for f in r["findings"]}
    assert by_state["app"]["verdict"] == "neutral"
    assert by_state["templates"]["verdict"] == "neutral"
