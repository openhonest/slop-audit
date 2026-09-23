"""Diff the ported dead-code corpus against the reference, one name occurrence at a time.

The corpus is where every name in the repository is written, and it is what decides whether a
definition nothing calls is dead or merely unreachable from the source. A name recorded as a
hard reference in one implementation and as a word in the other produces a different verdict
for the definition that carries it, with no difference in any count.

    uv run validate_corpus_names.py <repo>

The dump is per name and file with an occurrence count rather than per byte offset. The
offsets matter to the driver's own-file rule and will be compared there; a byte-for-byte dump
of them is a wall nobody reads.

Exit 1 on any difference, 2 when there was nothing to compare. Nothing is written anywhere.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from parity_harness import binary_is_stale, boundary

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

READER = """
import sys, collections
from pathlib import Path
from l1_analyzer.dead_code_corpus import _read_corpus

repo = Path(sys.argv[1])
corpus = _read_corpus(repo)
rows = []
for name, uses in corpus["hard"].items():
    by_file = collections.Counter(relpath for relpath, _offset in uses)
    for relpath, count in by_file.items():
        rows.append("hard\\t%s\\t%s\\t%d" % (name, relpath, count))
for bucket, found in corpus["words"].items():
    for word in found:
        rows.append("word\\t%s\\t%s" % (bucket, word))
print("\\n".join(rows))
"""


@boundary
def reference_rows(repo: Path) -> set[str]:
    """The reference's corpus, from its own reader."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve())],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return {line for line in out.splitlines() if line.strip()}


@boundary
def ported_rows(repo: Path) -> set[str]:
    """The port's corpus, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--corpus"],
        capture_output=True, text=True, check=True,
    ).stdout
    return {line for line in out.splitlines() if line.strip()}


@boundary
def report(missing: set[str], extra: set[str], shown: int) -> None:
    """What differs, with the port's own additions first.

    A name the port records and the reference does not SPARES a definition the reference would
    call dead, which is the direction that hides a finding."""
    for label, rows in (("only the port records", extra),
                        ("only the reference records", missing)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for row in sorted(rows)[:shown]:
            print("   " + row.replace("\t", "  "))
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo = Path(argv[1])
    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2

    reference = reference_rows(repo)
    ported = ported_rows(repo)
    missing, extra = reference - ported, ported - reference
    hard = sum(1 for row in reference if row.startswith("hard\t"))
    print(f"{repo}: {len(reference)} corpus row(s) in the reference "
          f"({hard} hard reference sites), {len(ported)} in the port")
    if not reference and not ported:
        print("NOTHING TO COMPARE: neither side recorded anything, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, occurrence for occurrence")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
