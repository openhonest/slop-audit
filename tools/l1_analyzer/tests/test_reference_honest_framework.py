"""Reference test: the meter's verdict on honest-framework's reference server.

honest-framework (openhonest/honest-framework) is the reference implementation of the
Honest Framework - deliberately kept finitely testable. Its FastAPI entry point,
python/app.py, is the file that once surfaced a meter false positive: `app.get(path)
(handler)` (route registration in call form) was misread as dynamic dispatch on `app`
and flagged UNRESOLVED, downgrading the whole codebase from CAN to MIGHT.

This pins the correct answer, so a future change to the classifier cannot silently
re-dirty the reference. The source is a local snapshot at tests/reference/
honest_framework_app.txt, which is gitignored (a committed copy of another repo's file
invites confusion); when it is absent the test reads the sibling honest-framework
checkout instead, and skips if neither is present (a fresh clone or CI without the
sibling). Regenerate the local snapshot with:

    cp ../honest-framework/python/app.py tools/l1_analyzer/tests/reference/honest_framework_app.txt
"""

from pathlib import Path

import pytest
from l1_analyzer import state_bounds

_FIXTURE = Path(__file__).parent / "reference" / "honest_framework_app.txt"
# slop-audit and honest-framework are siblings under .../open-honest/.
_SIBLING = Path(__file__).resolve().parents[4] / "honest-framework" / "python" / "app.py"


def _reference_source() -> str | None:
    for path in (_FIXTURE, _SIBLING):
        if path.exists():
            return path.read_text()
    return None


def test_meter_gives_honest_framework_reference_server_a_clean_bill(tmp_path):
    src = _reference_source()
    if src is None:
        pytest.skip("honest-framework reference not available (gitignored snapshot and sibling checkout both absent)")
    (tmp_path / "app.py").write_text(src)
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
