"""Pool the per-state partition cardinalities over the sixteen repositories the
silence-index study measured, so the distribution behind UNORDERED_CLASS_BOUND can be
re-derived rather than re-remembered.

Checked in on 2026-08-18 because the published table did not reproduce and there was no
script to compare methods against: the run existed only in a session. Paths are the local
ones the study used, so this is reproducible on the measuring machine and nowhere else,
which is a limit worth fixing before any figure from it is published again.

    uv run python scripts/cardinality_distribution.py

Every run prints its provenance first: the analyzer commit, and each repository's HEAD
with a dirty marker. Ten of the sixteen are live working trees rather than pinned
checkouts, so without that header two runs of this script are not comparable and the
figures it prints cannot be re-derived later. That is not a caveat about the script, it
is the reason the 2026-08-15 figures could not be reproduced on 2026-08-18.
"""
import json
import pathlib
import subprocess
import sys
from collections import Counter

from l1_analyzer import state_bounds

H = pathlib.Path.home()
REPOS = [
 ("libuv", H/".cache/slop-audit-corpus/libuv__libuv", "c"),
 ("json-c", H/".cache/slop-audit-corpus/json-c__json-c", "c"),
 ("junit4", H/".cache/slop-audit-corpus/junit-team__junit4", "java"),
 ("gson", H/".cache/slop-audit-corpus/google__gson", "java"),
 ("RestSharp", H/".cache/slop-audit-corpus/restsharp__RestSharp", "csharp"),
 ("Newtonsoft.Json", H/".cache/slop-audit-corpus/JamesNK__Newtonsoft.Json", "csharp"),
 ("honest-framework", H/"dev/honest/open-honest/honest-framework", "python"),
 ("multicardz", H/"dev/multicardz", "python"),
 ("declaro", H/"dev/declaro", "python"),
 ("slop-audit", H/"dev/honest/open-honest/slop-audit", "python"),
 ("weights-watch", H/"dev/honest/open-honest/weights-watch", "python"),
 ("challenge", H/"dev/honest/open-honest/challenge", "python"),
 ("honest-starter", H/"dev/honest/open-honest/honest-starter", "python"),
 ("slop-audit-web", H/"dev/honest/open-honest/slop-audit-web", "python"),
 ("open-vrm-app", H/"dev/buckler/open-vrm-app", "python"),
 ("umbra", H/"dev/honest/open-honest/umbra", "python"),
]
def _head(path: pathlib.Path) -> str:
    """The repository's commit and whether its tree is dirty, or a marker saying we could
    not tell. A figure measured over an unrecorded working tree cannot be checked later."""
    try:
        sha = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=False).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain"],
                               capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        return "unknown"
    return f"{sha or 'unknown'}{'+dirty' if dirty else ''}"


ANALYZER = _head(pathlib.Path(__file__).resolve().parents[3])
print(f"analyzer {ANALYZER}")
unordered, ordered, per_repo = Counter(), Counter(), {}
for name, path, lang in REPOS:
    if not path.exists():
        print(f"MISSING {name} {path}", file=sys.stderr); continue
    r = state_bounds.classify(path, lang)
    u = o = 0
    for f in r.get("findings") or []:
        p = f.get("partition") or {}
        c = p.get("classes")
        if not c or not f.get("drives_decision"):
            continue
        if p.get("ordered"): ordered[c] += 1; o += 1
        else: unordered[c] += 1; u += 1
    per_repo[name] = (u, o)
    print(f"  {name:18s} {_head(path):18s} unordered={u:4d} ordered={o:4d}", flush=True)
print(f"\nUNORDERED n={sum(unordered.values())}")
print("  " + " ".join(f"{k}:{v}" for k, v in sorted(unordered.items())))
print(f"ORDERED n={sum(ordered.values())}  max={max(ordered) if ordered else '-'}")
print("  " + " ".join(f"{k}:{v}" for k, v in sorted(ordered.items())))
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("cardinality-distribution.json")
with OUT.open("w") as fh:
    json.dump({"analyzer": ANALYZER, "provenance": {n: _head(p) for n, p, _l in REPOS if p.exists()},
               "unordered": dict(unordered), "ordered": dict(ordered), "per_repo": per_repo}, fh, indent=1)
print(f"wrote {OUT}")
