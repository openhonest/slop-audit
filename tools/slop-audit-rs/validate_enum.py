"""Diff the ported state enumerator against the Python reference, site by site, on one repo.

This is the CLASSIFIER'S walk, not the census. It reaches a conclusion about each
declaration it meets, so every row carries the key the site yielded and the empty string
where the walk read a declaration and declined it.

The declines are the half that matters and the half a total would hide. A port that
admitted everything and a port that read nothing can agree on how many sites they reached;
what separates them is which ones they ruled out, and ruling one out correctly is what
stops the census counting it as a site nobody looked at.

    uv run validate_enum.py <repo> [lang]

Exit 1 on any difference. Nothing is written anywhere.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
BINARY = HERE / "target" / "debug" / "slop-audit-rs"

# One candidate, as both sides name it: the file, then (kind, owner, name), then the state
# key the walk yielded, which is empty where it declined.
Row = tuple[str, str, str, str, str]


def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    The analyzer package declares its edges with a decorator of this name. This script sits
    beside that package rather than inside it, so it says the same thing in its own words
    rather than importing across the boundary between a Rust crate's helper and the Python
    tool it validates."""
    return fn


@boundary
def reference_sites(repo: Path, lang: str) -> set[Row]:
    """The reference's candidates, walked over the same files the census walks, so a
    scoping difference cannot masquerade as a reading difference."""
    script = (
        "import sys, json\n"
        "from pathlib import Path\n"
        "from l1_analyzer import state_census, state_enum\n"
        "from l1_analyzer.indicators import LANG_CFG, _read_source_bytes, parser_for\n"
        "from l1_analyzer.lang_spec import LANG_SPEC\n"
        "from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE\n"
        "from l1_analyzer.ts_nodes import refs as _refs\n"
        "_descend = lambda n: _refs(n, lambda x: True)\n"
        "repo, lang = Path(sys.argv[1]), sys.argv[2]\n"
        "cfg = LANG_CFG[lang]\n"
        "sp = LANG_SPEC[lang]\n"
        "files, _ = _read_source_bytes(repo, cfg['extensions'], "
        "scope=PRODUCTION_WITHOUT_CONFORMANCE)\n"
        "rows = []\n"
        "for path, src in files:\n"
        "    rel = str(path.relative_to(repo))\n"
        "    root = parser_for(path.suffix, lang).parse(src).root_node\n"
        "    cands = dict(state_enum.module_cands(root, sp, cfg))\n"
        "    for cls in [n for n in _descend(root) if n.type in sp['class_types']]:\n"
        "        for site, key in state_enum.instance_cands(cls, sp).items():\n"
        "            if site not in cands or key: cands[site] = key\n"
        "    if sp['scope_by_receiver']:\n"
        "        for slot in state_enum.go_slots(root):\n"
        "            site = slot['site']\n"
        "            if site not in cands or slot['state']: cands[site] = slot['state']\n"
        "    for (kind, owner, name), key in cands.items():\n"
        "        rows.append([rel, kind, owner, name, key])\n"
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
    """The port's candidates, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--enum", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, kind, owner, name, key = line.split("\t")
        rows.add((path, kind, owner, name, key))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, in both directions, with the worst-understood first.

    A candidate the port ADMITS where the reference declines is worse than the reverse: an
    extra decline shrinks what the classifier claims to have decided, which the silence
    index still reports, while an extra admission is a verdict about code nobody checked
    and it reaches a reader as a finding."""
    for label, rows in (("only the port reaches", extra), ("only the reference reaches", missing)):
        if not rows:
            continue
        print(f"\n{len(rows)} {label}:")
        for row in sorted(rows)[:shown]:
            print("   " + "  ".join(row))
        if len(rows) > shown:
            print(f"   ... and {len(rows) - shown} more")


@boundary
def binary_is_stale() -> str:
    """Why this run would report on code nobody is looking at, or the empty string.

    The port's Python arm read as failing for a whole parity sweep after it was written,
    and the cause was a binary older than the source. The harness compared an old build
    against a current reference and called the difference a defect in the port, which is
    the same failure the port exists to catch, committed by the thing checking it.

    Refused rather than rebuilt here. A harness that quietly rebuilds hides which build
    produced a number, and the answer a reader wants is "run cargo build", not a number
    from a binary they did not ask for."""
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
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    repo = Path(argv[1])
    lang = argv[2] if len(argv) == 3 else "auto"
    if lang == "auto":
        print("name the language; the enumerator reads one grammar per run")
        return 2
    stale = binary_is_stale()
    if stale:
        print(stale)
        return 2

    reference = reference_sites(repo, lang)
    ported = ported_sites(repo, lang)
    missing, extra = reference - ported, ported - reference

    files = {row[0] for row in reference} | {row[0] for row in ported}
    admits = sum(1 for row in reference if row[4])
    print(f"{repo} ({lang}): {len(reference)} candidates in the reference "
          f"({admits} admitted, {len(reference) - admits} declined), "
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
