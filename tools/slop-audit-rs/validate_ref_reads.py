"""Diff the ported position predicates against the Python reference, node by node, on one repo.

This is neither the census nor the classifier's walk. It is the layer under both rules:
given one node, is it a test expression, a presence test, a keyed read, a call whose result
nobody reads. Those readings are where the nine grammars diverge most, and every
false-positive filter is composed out of them, so a filter can only be as sound as they are.

    uv run validate_ref_reads.py <repo> <lang>

Seven of the ten predicates are compared. The three left out are the naming rules, which
take an attribute name this dump has none of: `names_the_attribute`, `is_keyed_read_of` and
the member spelling under them are covered by unit tests on the three styles instead. That
is a real gap in this harness and it is named here rather than left for a reader to work out
from what the rows do not carry.

A row is emitted only where at least one predicate fired. A row per node would bury the
divergence in a column of falses.

Exit 1 on any difference, 2 when there was nothing to compare. Nothing is written anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

# One reading, as both sides name it: the file, the node's byte span, its type, and the
# predicates that fired, sorted and joined.
Row = tuple[str, int, int, str, str]


def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    The analyzer package declares its edges with a decorator of this name. This script sits
    beside that package rather than inside it, so it says the same thing in its own words
    rather than importing across the boundary between a Rust crate's helper and the Python
    tool it validates."""
    return fn


READER = """
import sys, json
from pathlib import Path
from l1_analyzer import state_ref_reads as rr
from l1_analyzer.indicators import LANG_CFG, _read_source_bytes, parser_for
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.ts_nodes import refs as _refs

repo, lang = Path(sys.argv[1]), sys.argv[2]
cfg, sp = LANG_CFG[lang], LANG_SPEC[lang]
files, _ = _read_source_bytes(repo, cfg['extensions'], scope=PRODUCTION_WITHOUT_CONFORMANCE)
rows = []
for path, src in files:
    rel = str(path.relative_to(repo))
    root = parser_for(path.suffix, lang).parse(src).root_node
    for node in _refs(root, lambda n: True):
        flags = []
        if rr.in_test(node, sp): flags.append("in_test")
        if rr.is_membership_container(node, sp): flags.append("membership")
        if rr.is_presence_method_call(node, sp): flags.append("presence_method")
        if rr.is_comma_ok_presence(node, sp): flags.append("comma_ok")
        if rr.is_deleted(node, sp): flags.append("deleted")
        read = rr.keyed_value_read(node, sp)
        if read is not None: flags.append("keyed_read@%d" % read.start_byte)
        call = rr.receiver_call(node, sp)
        if call is not None:
            flags.append("call:%s" % rr.method_name(call, sp))
            if rr.result_discarded(call, sp): flags.append("discarded")
        recv = rr.call_receiver(node, sp)
        if recv is not None: flags.append("recv@%d" % recv.start_byte)
        if not flags: continue
        rows.append([rel, node.start_byte, node.end_byte, node.type, ",".join(sorted(flags))])
print(json.dumps(rows))
"""


@boundary
def reference_reads(repo: Path, lang: str) -> set[Row]:
    """The reference's readings, over the same files the census walks, so a scoping
    difference cannot masquerade as a reading difference."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve()), lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return {(r[0], r[1], r[2], r[3], r[4]) for r in json.loads(out)}


@boundary
def ported_reads(repo: Path, lang: str) -> set[Row]:
    """The port's readings, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--reads", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, start, end, kind, flags = line.split("\t")
        rows.add((path, int(start), int(end), kind, flags))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, in both directions, with the port's own inventions first.

    A reading the port makes and the reference does not is a claim about somebody's code
    that no reference run supports, and it reaches a reader as a finding. A reading the
    port misses shrinks what the filters can clear, which over-accuses rather than
    inventing, and that is the less dangerous direction of the two."""
    for label, rows in (("only the port reads", extra), ("only the reference reads", missing)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for row in sorted(rows)[:shown]:
            print(f"   {row[0]}  {row[1]}-{row[2]}  {row[3]}  {row[4]}")
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


@boundary
def binary_is_stale() -> str:
    """Why this run would report on code nobody is looking at, or the empty string.

    Refused rather than rebuilt. A harness that quietly rebuilds hides which build produced
    a number, and the answer a reader wants is "run cargo build", not a number from a binary
    they did not ask for."""
    if not BINARY.exists():
        return f"no binary at {BINARY}; run `cargo build` first"
    built = BINARY.stat().st_mtime
    newer = [path for path in (HERE / "src").rglob("*.rs") if path.stat().st_mtime > built]
    if newer:
        names = ", ".join(sorted(p.name for p in newer)[:3])
        return (f"{BINARY.name} is older than {len(newer)} source file(s) ({names}); "
                "run `cargo build` first, or this run reports on the previous build")
    return ""


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    repo, lang = Path(argv[1]), argv[2]
    stale = binary_is_stale()
    if stale:
        print(stale)
        return 2

    reference = reference_reads(repo, lang)
    ported = ported_reads(repo, lang)
    missing, extra = reference - ported, ported - reference

    files = {row[0] for row in reference} | {row[0] for row in ported}
    print(f"{repo} ({lang}): {len(reference)} readings in the reference, "
          f"{len(ported)} in the port, over {len(files)} files")
    if not reference and not ported:
        # Nought differences out of nought readings. The two agreed about nothing, and a
        # report that reads the same for "we agree" and "there was nothing to agree about"
        # is the exact defect this instrument exists to name, committed by its own
        # validator. Exit 2: not a difference, and not a pass either.
        print("NOTHING TO COMPARE: neither side read anything here, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, reading for reading")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
