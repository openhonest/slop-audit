#!/usr/bin/env bash
# Build a repository-by-window panel of L1 indicator values.
#
# The measurement half, kept separate from decompose.py so the statistics can be rerun
# without remeasuring. One row per repository-window; columns are indicator values.
#
#   ./build_panel.sh 2015 2025 L1.5 L1.7 L1.4 > panel.tsv
#
# Repositories come from the parity corpus manifest, tools/slop-audit-rs/corpus.toml,
# cloned by validate_corpus.py into $SLOP_AUDIT_CORPUS or ~/.cache/slop-audit-corpus.
# A window is one calendar year, which was chosen for convenience rather than for
# constant sample size; a commit-count window would hold the denominator fixed and is the
# better choice if the effect of window definition is itself in question.
set -euo pipefail
FROM=${1:?first year}; TO=${2:?last year}; shift 2
INDICATORS=("$@")
CACHE=${SLOP_AUDIT_CORPUS:-$HOME/.cache/slop-audit-corpus}
ANALYZER=$(cd "$(dirname "$0")/../l1_analyzer" && pwd)

printf 'repository\twindow'; printf '\t%s' "${INDICATORS[@]}"; printf '\n'
for repo in "$CACHE"/*/; do
  name=$(basename "$repo")
  for year in $(seq "$FROM" "$TO"); do
    uv run --project "$ANALYZER" slop-audit-l1 "$repo" \
        --since "$year-01-01" --until "$year-12-31" --no-exec --format json 2>/dev/null \
      | INDICATORS="${INDICATORS[*]}" NAME="$name" YEAR="$year" python3 -c '
import json, os, sys
try:
    results = json.load(sys.stdin)["results"]
except Exception:
    sys.exit(0)
wanted = os.environ["INDICATORS"].split()
values = []
for key in wanted:
    entry = results.get(key, {})
    if entry.get("band") == "n/a" and not isinstance(entry.get("value"), (int, float)):
        sys.exit(0)          # a window with no commits contributes no row
    values.append(entry.get("value"))
print(os.environ["NAME"], os.environ["YEAR"], *values, sep="\t")
'
  done
done
