"""Diff the ported state census against the Python reference, site by site, on one repo.

The census counts declaration sites of state-bearing constructs. It is the denominator
every self-disclosure number in this instrument is measured against, so a port that gets it
wrong makes the classifier's blind spots invisible rather than merely miscounting them.

Two counts that agree in total can disagree about every site. This compares the sets, so a
port that drops one site and invents another reads as two differences and not as equal.

    uv run validate_census.py <repo> [lang]

Exit 1 on any difference, so it can gate a commit. Nothing is written anywhere.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from parity_harness import binary_is_stale, boundary

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

# One site, as both sides name it: the file it sits in, then (kind, owner, name).
Row = tuple[str, str, str, str]


@boundary
def reference_sites(repo: Path, lang: str) -> set[Row]:
    """The reference's sites, asked for through its own walk so the file scoping is the
    reference's too. A port that reads a different set of FILES and the same sites in each
    is a different defect from one that reads the same files differently, and merging the
    two questions would hide both."""
    script = (
        "import sys, json\n"
        "from pathlib import Path\n"
        "from l1_analyzer import state_census\n"
        "rows = []\n"
        "for path, sites in state_census._walk(Path(sys.argv[1]), sys.argv[2]).items():\n"
        "    for kind, owner, name in sites:\n"
        "        rows.append([path, kind, owner, name])\n"
        "print(json.dumps(rows))\n"
    )
    out = subprocess.run(
        ["uv", "run", "python", "-c", script, str(repo.resolve()), lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    import json
    return {tuple(row) for row in json.loads(out)}


@boundary
def ported_sites(repo: Path, lang: str) -> set[Row]:
    """The port's sites, from the binary's own census dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--census", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, kind, owner, name = line.split("\t")
        rows.add((path, kind, owner, name))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, in both directions, with the worst-understood first.

    A site the port INVENTS is worse than one it drops: a dropped site shrinks a
    denominator and reads as higher confidence, which the silence floor can still catch,
    while an invented one reads as a declaration nothing visited and sends a reader looking
    for a blind spot that is not there."""
    for label, rows in (("only the port counts", extra), ("only the reference counts", missing)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for row in sorted(rows)[:shown]:
            print("   " + "  ".join(row))
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    repo = Path(argv[1])
    lang = argv[2] if len(argv) == 3 else "auto"
    if lang == "auto":
        print("name the language; the census reads one grammar per run")
        return 2
    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2

    reference = reference_sites(repo, lang)
    ported = ported_sites(repo, lang)
    missing, extra = reference - ported, ported - reference

    files = {row[0] for row in reference} | {row[0] for row in ported}
    print(f"{repo} ({lang}): {len(reference)} sites in the reference, "
          f"{len(ported)} in the port, over {len(files)} files")
    if not reference and not ported:
        # Nought differences out of nought sites. The two agreed about nothing, and a
        # report that reads the same for "we agree" and "there was nothing to agree about"
        # is the exact defect this instrument exists to name, committed by its own
        # validator. Exit 2: not a difference, and not a pass either.
        print("NOTHING TO COMPARE: neither side found a site here, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, site for site")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
