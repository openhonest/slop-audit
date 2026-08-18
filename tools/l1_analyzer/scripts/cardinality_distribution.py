"""Pool the per-state partition cardinalities over the sixteen repositories the
silence-index study measured, so the distribution behind UNORDERED_CLASS_BOUND can be
re-derived rather than re-remembered.

Checked in on 2026-08-18 because the published table did not reproduce and there was no
script to compare methods against: the run existed only in a session. Paths are the local
ones the study used, so this is reproducible on the measuring machine and nowhere else,
which is a limit worth fixing before any figure from it is published again.

    uv run python scripts/cardinality_distribution.py
"""
import json, pathlib, sys
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
    print(f"  {name:18s} unordered={u:4d} ordered={o:4d}", flush=True)
print("\nUNORDERED n=%d" % sum(unordered.values()))
print("  " + " ".join(f"{k}:{v}" for k, v in sorted(unordered.items())))
print("ORDERED n=%d  max=%s" % (sum(ordered.values()), max(ordered) if ordered else "-"))
print("  " + " ".join(f"{k}:{v}" for k, v in sorted(ordered.items())))
json.dump({"unordered": dict(unordered), "ordered": dict(ordered), "per_repo": per_repo},
          open("/private/tmp/claude-501/-Users-adam-dev-honest-open-honest-slop-audit/ab4ac205-05dd-47f4-8d55-463405f143cc/scratchpad/dist.json","w"), indent=1)
