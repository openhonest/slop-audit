"""Diff the ported dead-code definition collectors against the reference, one definition at a time.

Nine collectors, one per language, each deciding for every named definition whether the
reference scan may judge it: a CANDIDATE it may call dead, an UNDECIDABLE it must not judge
because something outside a syntactic scan's reach can name it, or an EXCLUDED the language
or a runner binds by convention.

    uv run validate_defs.py <repo> <lang>

THE STATUS IS THE HALF THAT MATTERS. Two collectors that find the same definitions and
disagree about one status produce the same count and a different number, and the direction is
the dangerous one: a candidate where the reference says undecidable is a claim that somebody's
code is dead, made where the reference refuses to claim anything.

A file whose tree carries an error is skipped on both sides, as the driver skips it: a tree
the grammar could not parse cannot support a claim about what it contains.

Exit 1 on any difference, 2 when there was nothing to compare. Nothing is written anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from parity_harness import binary_is_stale, boundary

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

# One definition, as both sides name it: the file, the name, the kind, the lines it spans,
# the status, and the reason the status carries.
Row = tuple[str, str, str, int, int, str, str]


READER = """
import sys, json
from pathlib import Path
from l1_analyzer.dead_code import COLLECTORS, _repo_facts
from l1_analyzer.dead_code_grammars import _EXT_LANG, parser
from l1_analyzer.indicators import _read_source_bytes
from l1_analyzer.scope import PRODUCTION

repo, lang = Path(sys.argv[1]), sys.argv[2]
facts = _repo_facts(repo, lang)
extensions = tuple(ext for ext, (_g, key) in _EXT_LANG.items() if key == lang)
sources, _unreadable = _read_source_bytes(repo, extensions, scope=PRODUCTION)
rows = []
for path, src in sources:
    rel = str(path.relative_to(repo)) if repo in path.parents else path.name
    grammar, _key = _EXT_LANG[path.suffix.lower()]
    root = parser(grammar).parse(src).root_node
    if root.has_error:
        continue
    for d in COLLECTORS[lang](root, src, rel, facts):
        rows.append([rel, d["name"], d["kind"], d["line"], d["end_line"],
                     d["status"], d["reason"]])
print(json.dumps(rows))
"""


@boundary
def reference_rows(repo: Path, lang: str) -> set[Row]:
    """The reference's definitions, over its own production scope."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve()), lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return {tuple(r) for r in json.loads(out)}


@boundary
def ported_rows(repo: Path, lang: str) -> set[Row]:
    """The port's definitions, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--defs", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, name, kind, start, end, status, reason = line.split("\t", 6)
        rows.add((path, name, kind, int(start), int(end), status, reason))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, and a status disagreement separately from a missing definition.

    A definition on both sides with two statuses is the dangerous difference and is listed
    first: the count is unchanged and the number is not. One side finding a definition the
    other does not is a collector difference, which moves the denominator."""
    def key(row: Row) -> tuple[str, str, int]:
        return (row[0], row[1], row[3])

    ref_by_key = {key(r): r for r in missing}
    port_by_key = {key(r): r for r in extra}
    shared = sorted(set(ref_by_key) & set(port_by_key))
    if shared:
        print(f"\n{len(shared)} definition(s) both sides found and judged differently:")
        for k in shared[:shown]:
            path, name, line = k
            print(f"   {path}:{line}  {name}")
            print(f"      reference: {ref_by_key[k][5]}  {ref_by_key[k][6]}")
            print(f"      port:      {port_by_key[k][5]}  {port_by_key[k][6]}")
        if len(shared) > shown:
            print(f"   ... and {len(shared) - shown} more")
    for label, rows in (("only the port finds", extra), ("only the reference finds", missing)):
        only = [r for r in rows if key(r) not in (set(ref_by_key) & set(port_by_key))]
        if not only:
            continue
        print(f"\n{len(only)} {label}:")
        for row in sorted(only)[:shown]:
            print(f"   {row[0]}:{row[3]}  {row[1]}  {row[2]}  {row[5]}")
        if len(only) > shown:
            print(f"   ... and {len(only) - shown} more")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    repo, lang = Path(argv[1]), argv[2]
    stale = binary_is_stale(BINARY, HERE / "src")
    if stale:
        print(stale)
        return 2

    reference = reference_rows(repo, lang)
    ported = ported_rows(repo, lang)
    missing, extra = reference - ported, ported - reference

    by_status: dict[str, int] = {}
    for row in reference:
        by_status[row[5]] = by_status.get(row[5], 0) + 1
    print(f"{repo} ({lang}): {len(reference)} definition(s) in the reference "
          f"({by_status}), {len(ported)} in the port")
    if not reference and not ported:
        print("NOTHING TO COMPARE: neither side found one here, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, definition for definition")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
