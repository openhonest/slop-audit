"""Diff the ported unreachable-statement scan against the Python reference, line by line.

This is category 1 of L1.12, the half decidable from syntax alone: a statement that follows a
return, a throw, a break or a continue in the same block. It is ported and compared on its
own, before the unreferenced-definition half it will sit beside, because a wrong answer here
is a claim that somebody's code cannot run.

    uv run validate_unreachable.py <repo> <lang>

Each row is a file and the line span of one unreachable statement. A file whose tree carries
an error is skipped on both sides: a tree the grammar could not parse cannot support a claim
about what it contains, and on one corpus repository the statements around the error nodes
read as unreachable, sixteen of them.

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

# One unreachable statement, as both sides name it: the file, and the lines it spans.
Row = tuple[str, int, int]


READER = """
import sys, json
from pathlib import Path
from l1_analyzer.dead_code import _unreachable_statements
from l1_analyzer.dead_code_grammars import _EXT_LANG, parser
from l1_analyzer.indicators import _read_source_bytes
from l1_analyzer.scope import PRODUCTION

repo, lang = Path(sys.argv[1]), sys.argv[2]
extensions = tuple(ext for ext, (_g, key) in _EXT_LANG.items() if key == lang)
sources, _unreadable = _read_source_bytes(repo, extensions, scope=PRODUCTION)
rows = []
for path, src in sources:
    rel = str(path.relative_to(repo)) if repo in path.parents else path.name
    grammar, _key = _EXT_LANG[path.suffix.lower()]
    root = parser(grammar).parse(src).root_node
    if root.has_error:
        continue
    for u in _unreachable_statements(root, lang):
        rows.append([rel, u["line"], u["end_line"]])
print(json.dumps(rows))
"""


@boundary
def reference_rows(repo: Path, lang: str) -> set[Row]:
    """The reference's unreachable statements, over its own production scope."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve()), lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return {(r[0], r[1], r[2]) for r in json.loads(out)}


@boundary
def ported_rows(repo: Path, lang: str) -> set[Row]:
    """The port's unreachable statements, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--unreachable", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, start, end = line.split("\t")
        rows.add((path, int(start), int(end)))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, with the port's own inventions first.

    A statement the port calls unreachable and the reference does not is a claim that
    somebody's code cannot run, made on no reference run's authority. One the port misses
    lowers a ratio, which is the safer direction of the two."""
    for label, rows in (("only the port calls unreachable", extra),
                        ("only the reference calls unreachable", missing)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for path, start, end in sorted(rows)[:shown]:
            print(f"   {path}:{start}-{end}")
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


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

    files = {row[0] for row in reference} | {row[0] for row in ported}
    print(f"{repo} ({lang}): {len(reference)} unreachable statement(s) in the reference, "
          f"{len(ported)} in the port, over {len(files)} file(s)")
    if not reference and not ported:
        # Nought differences out of nought statements. Not a difference, and not a pass
        # either: a repository with nothing unreachable in it proves nothing about a scan
        # that finds nothing anywhere.
        print("NOTHING TO COMPARE: neither side found one here, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, statement for statement")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
