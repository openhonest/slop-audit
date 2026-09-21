"""Diff the ported false-positive filters against the Python reference, state by state.

These rules only ever CLEAR a finding the classifier already reached. A port that gets one
wrong therefore reports MORE than it measured, which is the single direction this instrument
must not fail in, so the four rules and the two guards are compared one answer at a time
rather than through whatever verdict a repository happened to produce.

    uv run validate_filters.py <repo> <lang>

Each row carries nine answers in a fixed order: the value-in-a-condition guard, result
invariance (y / n / - where no method gates on presence), memoization, accumulator, the
open-key guard, write-once, carried value, and the entry point itself under each of the two
verdicts a rule can act on.

TWO OF THE THREE ROUTES the classifier walks are here: module-level state, and instance
state inside a class. Go's receiver-grouped slots are the third and are not, because the
enumerator hands those back as byte offsets rather than nodes. Go's package-level state
still goes through the module route, so the grammar is exercised and the gap is narrower
than a language.

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

# One state, as both sides name it: the file, the scope's start byte (nought for module
# scope), the state key, how many references were found, and the nine answers.
Row = tuple[str, int, str, int, str]


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
from l1_analyzer import state_bounds_filters as f, state_enum
from l1_analyzer.indicators import LANG_CFG, _read_source_bytes, parser_for
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.state_partition import PROMISCUOUS, UNRESOLVED
from l1_analyzer.state_refs import bound_to
from l1_analyzer.ts_nodes import local_refs, refs as _refs, text as _text

repo, lang = Path(sys.argv[1]), sys.argv[2]
cfg, sp = LANG_CFG[lang], LANG_SPEC[lang]

def yn(answer):
    return "y" if answer else "n"

def state_refs(scope, key):
    stop = sp["class_types"]
    if sp["instance_enum"] == "ruby_ivar":
        return local_refs(scope, lambda n: n.type == "instance_variable" and _text(n) == key, stop)
    if sp["instance_ref_style"] == "member":
        return local_refs(scope, lambda n: n.type in sp["member_types"] and _text(n) == key, stop)
    hits = local_refs(scope, lambda n: n.type == "identifier" and _text(n) == key, stop)
    return bound_to(hits, key, sp)

def answers(cls, key, rs):
    attr = f._attr(key)
    invariant = f._result_invariant(attr, rs, sp)
    memo = cls is not None and f._is_memoization(cls, attr, rs, sp)
    once = cls is not None and f._is_write_once(cls, attr, rs, sp)
    return "".join([
        yn(f._value_reaches_condition(rs, sp)),
        "-" if invariant is None else yn(invariant),
        yn(memo),
        yn(f._is_write_only_accumulator(attr, rs, sp)),
        yn(f._selects_on_an_open_key(rs, sp)),
        yn(once),
        yn(f._drives_no_decision(rs, sp)),
        yn(f.is_false_positive(key, rs, PROMISCUOUS, sp)),
        yn(f.is_false_positive(key, rs, UNRESOLVED, sp)),
    ])

files, _ = _read_source_bytes(repo, cfg['extensions'], scope=PRODUCTION_WITHOUT_CONFORMANCE)
rows = []
for path, src in files:
    rel = str(path.relative_to(repo))
    root = parser_for(path.suffix, lang).parse(src).root_node
    module = state_enum.module_cands(root, sp, cfg)
    for key in state_enum.keys_of(module):
        named = [n for n in _refs(root, lambda n: True)
                 if n.type == "identifier" and _text(n) == key]
        rs = bound_to(named, key, sp)
        if not rs:
            continue
        rows.append([rel, 0, key, len(rs), answers(None, key, rs)])
    for cls in [n for n in _refs(root, lambda n: True) if n.type in sp["class_types"]]:
        cands = state_enum.instance_cands(cls, sp)
        for key in state_enum.keys_of(cands):
            rs = state_refs(cls, key)
            if not rs:
                continue
            rows.append([rel, cls.start_byte, key, len(rs), answers(cls, key, rs)])
print(json.dumps(rows))
"""


@boundary
def reference_states(repo: Path, lang: str) -> set[Row]:
    """The reference's answers, over the same files the census walks, so a scoping
    difference cannot masquerade as a reading difference."""
    out = subprocess.run(
        ["uv", "run", "python", "-c", READER, str(repo.resolve()), lang],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    return {(r[0], r[1], r[2], r[3], r[4]) for r in json.loads(out)}


@boundary
def ported_states(repo: Path, lang: str) -> set[Row]:
    """The port's answers, from the binary's own dump."""
    out = subprocess.run(
        [str(BINARY), str(repo.resolve()), "--filters", "--lang", lang],
        capture_output=True, text=True, check=True,
    ).stdout
    rows: set[Row] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        path, scope, key, count, flags = line.split("\t")
        rows.add((path, int(scope), key, int(count), flags))
    return rows


@boundary
def report(missing: set[Row], extra: set[Row], shown: int) -> None:
    """What differs, paired up by the state it is about, so a reader sees two answers and
    not two lists.

    A row present on one side only is a scoping difference and says so; a row on both sides
    with different answers is a reading difference, which is what this harness is for."""
    by_state: dict[tuple[str, int, str], list[str | None]] = {}
    for row in missing:
        by_state.setdefault(row[:3], [None, None])[0] = f"{row[3]} refs {row[4]}"
    for row in extra:
        by_state.setdefault(row[:3], [None, None])[1] = f"{row[3]} refs {row[4]}"
    print(f"\n{len(by_state)} state(s) the two read differently:")
    for state, (ref, port) in sorted(by_state.items())[:shown]:
        path, scope, key = state
        print(f"   {path}  @{scope}  {key}")
        print(f"      reference: {ref or 'no such state'}")
        print(f"      port:      {port or 'no such state'}")
    if len(by_state) > shown:
        print(f"   ... and {len(by_state) - shown} more")


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

    reference = reference_states(repo, lang)
    ported = ported_states(repo, lang)
    missing, extra = reference - ported, ported - reference

    files = {row[0] for row in reference} | {row[0] for row in ported}
    cleared = sum(1 for row in reference if row[4].endswith("yn") or row[4].endswith("yy"))
    print(f"{repo} ({lang}): {len(reference)} states in the reference "
          f"({cleared} cleared under a promiscuous verdict), {len(ported)} in the port, "
          f"over {len(files)} files")
    if not reference and not ported:
        # Nought differences out of nought states. The two agreed about nothing, and a
        # report that reads the same for "we agree" and "there was nothing to agree about"
        # is the exact defect this instrument exists to name, committed by its own
        # validator. Exit 2: not a difference, and not a pass either.
        print("NOTHING TO COMPARE: neither side found a state here, so this run proves nothing")
        return 2
    if not missing and not extra:
        print("EQUAL, answer for answer")
        return 0
    report(missing, extra, shown=20)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
