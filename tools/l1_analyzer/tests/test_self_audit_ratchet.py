"""The self-audit ratchet compares a panel against its baseline (dogfood).

The pre-commit gate runs three checks and the panel is twenty. One run of the other
seventeen produced two findings the gate could not see, so the panel needs to run
somewhere. It cannot be a gate: this repository is honestly Slop on L1.5 and L1.6, so a
bar demanding zero would block every commit and a bar demanding nothing would keep
missing what the run found. It is a ratchet on the COUNT.

These test the comparison, not the panel. Running twenty indicators over this repository
takes minutes and belongs in CI; deciding whether a panel got worse is arithmetic and
belongs here.
"""

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "self_audit.py"
BASELINE = SCRIPT.parent / "self-audit-baseline.json"


def test_the_baseline_is_committed_and_names_todays_slop_signals():
    """Without a committed baseline the ratchet has nothing to compare against, and a CI
    job that silently passes because it found no baseline is worse than no job."""
    assert BASELINE.is_file(), "no baseline; the CI job would have nothing to ratchet against"
    d = json.loads(BASELINE.read_text())
    assert set(d) == {"slop", "bands", "vacuity"}
    assert d["slop"], "a baseline claiming zero slop signals for this repository is wrong"
    assert all(d["bands"][k] == "Slop" for k in d["slop"]), "baseline disagrees with itself"


def test_slop_keys_reads_the_bands_it_is_given():
    sys.path.insert(0, str(SCRIPT.parent))
    import self_audit

    bands = {"L1.1": "Healthy", "L1.5": "Slop", "L1.13": "n/a", "L1.17": "Not Healthy"}
    assert self_audit.slop_keys(bands) == ["L1.5"]


def test_the_script_refuses_rather_than_passing_when_no_baseline_exists(tmp_path):
    """A missing baseline must be an error. The failure mode this guards is a CI job that
    goes green because the file it compares against was never written."""
    stub = tmp_path / "self_audit.py"
    stub.write_text(SCRIPT.read_text().replace(
        'BASELINE = pathlib.Path(__file__).resolve().parent / "self-audit-baseline.json"',
        f'BASELINE = pathlib.Path({str(tmp_path / "absent.json")!r})'))
    # check=False deliberately: a non-zero exit is the thing being asserted, so raising
    # on it would turn the assertion into a crash.
    r = subprocess.run([sys.executable, str(stub)], capture_output=True, text=True,
                       cwd=SCRIPT.parents[1], check=False)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no baseline" in r.stderr


def test_the_baseline_ratchets_the_vacuity_count_too():
    """`vacuity.py` is 892 lines that only its own test imports. It is not dead: it found
    the L1.4 and L1.5 empty-denominator defect on 2026-08-18, which shipped as a false
    Slop over any range that added nothing. A checker that finds real defects and that
    nothing runs is a gate nobody wired, so it is wired here rather than deleted.

    It joins the existing ratchet instead of getting its own gate, for the same reason
    the panel did: it reports ten vacuous paths in this package today, so a bar demanding
    zero would fail every commit."""
    d = json.loads(BASELINE.read_text())
    assert "vacuity" in d, "the baseline does not ratchet vacuity, so nothing runs it"
    assert isinstance(d["vacuity"], int) and d["vacuity"] >= 0
