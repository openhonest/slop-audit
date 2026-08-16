"""Reference test: the meter's verdict on honest-framework's reference server.

honest-framework (openhonest/honest-framework) is the reference implementation of the
Honest Framework - deliberately kept finitely testable. Its FastAPI entry point,
python/app.py, is the file that once surfaced a meter false positive: `app.get(path)
(handler)` (route registration in call form) was misread as dynamic dispatch on `app`
and flagged UNRESOLVED, downgrading the whole codebase from CAN to MIGHT.

This pins the correct answer, so a future change to the classifier cannot silently
re-dirty the reference.

The reference is ONE source: the capture at tests/reference/honest_framework_app.txt,
pinned below by its sha256. It used to be one of two, preferring the capture and falling
back to a sibling honest-framework checkout, and that shape cost three things. Nothing
detected drift, because neither path carried a hash. A red could not say whether the
classifier had changed or the reference had, because the resolver returned the text alone
and never the path it read. And where it mattered most it did not run: the capture is
gitignored, so a fresh clone with no sibling checkout took a skip, and a skip is
pass-shaped on exactly the machine where changes get merged.

So absence is now a red with a named cause, not a skip, and the capture and the meter are
two tests with two messages. If the capture is missing or its hash has moved, regenerate it
and update `_CAPTURED_SHA256` and `_CAPTURED_ON` in the same commit:

    cp ../honest-framework/python/app.py tools/l1_analyzer/tests/reference/honest_framework_app.txt
    shasum -a 256 tools/l1_analyzer/tests/reference/honest_framework_app.txt
"""

import hashlib
from pathlib import Path

from l1_analyzer import state_bounds

_REFERENCE = Path(__file__).parent / "reference" / "honest_framework_app.txt"

# The capture, pinned. These three lines are the record the file itself does not carry.
_CAPTURED_SHA256 = "11342d5f9678a83d5a6cc3bb58a64d053f1893e423320073424bd838b41860ee"
_CAPTURED_ON = "2026-08-16"
_CAPTURED_FROM = "openhonest/honest-framework, python/app.py"

# The miss, named. A string no source text a test wants can equal.
_ABSENT = "absent"

_MISSING = (
    f"the pinned reference capture is absent at {_REFERENCE}. It is gitignored, so a fresh "
    f"clone reaches this; regenerate it from {_CAPTURED_FROM} (see the module docstring) or "
    f"track the file, but do not let this test pass without reading it."
)


def _reference_text() -> str:
    """The captured reference source, or the named case `"absent"`.

    One path, resolved here and nowhere else. Absence is returned as a value the caller
    must handle, so no reader can mistake "the reference was not read" for "the reference
    was clean".
    """
    if not _REFERENCE.exists():
        return _ABSENT
    return _REFERENCE.read_text()


def _provenance(src: str) -> str:
    """What was read, and whether it is still the capture this file pins. Appended to every
    assertion message, so the reader never has to guess which source produced the red."""
    digest = hashlib.sha256(src.encode()).hexdigest()
    verdict = "matches the pin" if digest == _CAPTURED_SHA256 else "DOES NOT match the pin"
    return (f"[read {_REFERENCE.name}, sha256 {digest[:16]}, {verdict}; "
            f"captured {_CAPTURED_ON} from {_CAPTURED_FROM}]")


def test_the_pinned_reference_capture_is_unchanged():
    """The reference half of the guard. This red says the CAPTURE moved, and it is the only
    test that can say so, which is what makes the red below attributable to the meter."""
    src = _reference_text()
    assert src != _ABSENT, _MISSING
    assert hashlib.sha256(src.encode()).hexdigest() == _CAPTURED_SHA256, (
        f"the reference capture changed, not the meter. Upstream {_CAPTURED_FROM} moved, or "
        f"the file was edited in place. Re-verify the expectations below against the new "
        f"source, then update _CAPTURED_SHA256 and _CAPTURED_ON. {_provenance(src)}"
    )


def test_meter_gives_honest_framework_reference_server_a_clean_bill(tmp_path):
    """The meter half. Given the test above is green, every red here is the classifier."""
    src = _reference_text()
    assert src != _ABSENT, _MISSING
    (tmp_path / "app.py").write_text(src)
    r = state_bounds.classify(tmp_path, "python")
    where = _provenance(src)

    # The reference server is finitely testable: no unbounded state, nothing the meter
    # must fail-close on. The FastAPI app object is configuration, not a decision.
    assert r["counts"]["promiscuous"] == 0, f"the reference server has no promiscuous state {where}"
    assert r["counts"]["unresolved"] == 0, (
        "the reference server must not fail-close: "
        + ", ".join(f"{f['state']}@{f['line']}" for f in r["findings"] if f["verdict"] == "unresolved")
        + f" {where}"
    )
    assert r["verdict"] == "neutral", f"the reference server grades neutral {where}"

    # Specifically, the app singleton and the templates object are neutral, not
    # dispatched - this is the exact false positive the fix removed.
    by_state = {f["state"]: f for f in r["findings"]}
    assert by_state["app"]["verdict"] == "neutral", f"the app singleton is not dispatch {where}"
    assert by_state["templates"]["verdict"] == "neutral", f"the templates object is not dispatch {where}"
