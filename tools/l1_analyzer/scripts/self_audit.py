"""Run the whole Layer 1 panel against this repository and ratchet the slop count.

The pre-commit gate runs THREE checks: god-files, finite-testability and the type-escape
ratchet. The panel is twenty indicators. Until 2026-08-18 nothing ran the other
seventeen against our own tree, and one run of them produced two findings the gate could
not see: a credential in a specification reported as production code, and six git
indicators publishing a band with no counts behind it.

Why this is a ratchet and not a gate. The three the gate enforces are bright lines, pass
or fail. The other seventeen are graded, and this repository is Slop on L1.5 and L1.6
today, honestly: it adds far more than it deletes. A gate demanding zero would block
every commit; a gate demanding nothing would keep missing what this found. So the
baseline records what is true today and the build fails when it gets WORSE.

    uv run python scripts/self_audit.py            # compare against the baseline
    uv run python scripts/self_audit.py --record   # accept today's panel as the baseline

Recording is deliberate and separate, so a regression cannot be absorbed by the same
command that detects it.
"""

from __future__ import annotations

import json
import pathlib
import sys

from l1_analyzer import indicators, vacuity

REPO = pathlib.Path(__file__).resolve().parents[3]
BASELINE = pathlib.Path(__file__).resolve().parent / "self-audit-baseline.json"


def panel(repo: pathlib.Path) -> dict[str, str]:
    """Every indicator's band, keyed by indicator. `--no-exec`, so L1.19 and L1.20 are
    n/a: executing an arbitrary test suite is not something a ratchet should do."""
    results = indicators.compute_git_indicators(repo, None, None)
    results.update(indicators.compute_config_indicators(repo))
    results.update(indicators.compute_source_indicators(
        repo, lang="auto", exec_tests=False, timeout_seconds=60, classify_state_bounds=False))
    return {k: str(v.get("band")) for k, v in sorted(results.items())
            if k.startswith("L1.") and isinstance(v, dict)}


def slop_keys(bands: dict[str, str]) -> list[str]:
    return [k for k, b in bands.items() if b == "Slop"]


def vacuous_paths() -> int:
    """How many vacuous paths `vacuity.check` finds in the analyzer package.

    vacuity.py is 892 lines that only its own test imports, which L1.12 reports as
    test-only. It is not dead: it found the L1.4 and L1.5 empty-denominator defect on
    2026-08-18, a false Slop published over any range that added nothing. A checker that
    finds real defects and that nothing runs is a gate nobody wired, so it is wired here.

    Counted rather than gated, and ratcheted with the panel rather than given its own
    hook, for the same reason: it reports ten today, so a bar demanding zero would fail
    every commit and teach everyone to pass --no-verify."""
    return len(vacuity.check(REPO / "tools" / "l1_analyzer" / "l1_analyzer")["findings"])


def main(argv: list[str]) -> int:
    bands = panel(REPO)
    slop = slop_keys(bands)
    measured = len([b for b in bands.values() if b != "n/a"])
    vacuous = vacuous_paths()
    print(f"slop signals: {len(slop)} of {measured} measured  ({', '.join(slop) or 'none'})")
    print(f"vacuous paths: {vacuous}")

    if "--record" in argv:
        BASELINE.write_text(json.dumps({"slop": slop, "bands": bands, "vacuity": vacuous},
                                       indent=1, sort_keys=True) + "\n")
        print(f"recorded {BASELINE.name}")
        return 0

    if not BASELINE.is_file():
        print(f"no baseline at {BASELINE}; run with --record", file=sys.stderr)
        return 2

    was = json.loads(BASELINE.read_text())
    new = sorted(set(slop) - set(was["slop"]))
    gone = sorted(set(was["slop"]) - set(slop))
    for k in gone:
        print(f"  improved: {k} is no longer Slop")
    for k in new:
        print(f"  REGRESSED: {k} is now Slop (was {was['bands'].get(k)})", file=sys.stderr)
    was_vacuous = was.get("vacuity")
    if was_vacuous is not None and vacuous > was_vacuous:
        print(f"  REGRESSED: {vacuous} vacuous paths, was {was_vacuous}", file=sys.stderr)
        new = new + ["vacuity"]
    elif was_vacuous is not None and vacuous < was_vacuous:
        print(f"  improved: {vacuous} vacuous paths, was {was_vacuous}")
        gone = gone + ["vacuity"]
    if new:
        print("\nThe panel got worse. Fix it, or run --record in the same commit that "
              "explains why the new reading is the honest one.", file=sys.stderr)
        return 1
    if gone:
        print("\nThe panel improved. Run --record to hold the gain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
