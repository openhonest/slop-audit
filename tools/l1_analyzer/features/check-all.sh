#!/usr/bin/env bash
# check-all.sh — the whole-repository form of feature-gate.sh.
#
# feature-gate.sh is affected-only by design: it checks the modules whose source or feature file
# is staged, so a commit is not slowed by modules it did not touch. That is right for a hook and
# wrong for a sweep, because it can never tell you the state of the tree as a whole. This walks
# every module and prints the bijection, so "one scenario per function" is a number rather than
# a belief.
#
# Exit 0 only when every module with functions has a feature file whose scenario subjects are
# exactly its function names.
set -uo pipefail
root=$(git rev-parse --show-toplevel)
pkg="$root/tools/l1_analyzer/l1_analyzer"
featdir="$root/tools/l1_analyzer/features"

fail=0
tot_f=0
tot_s=0
printf '%-26s %9s %9s   %s\n' module functions scenarios status
for src in "$pkg"/*.py; do
  m=$(basename "$src" .py)
  funcs=$(grep -hoE '^(async )?def [a-z_][a-z0-9_]*' "$src" | sed -E 's/^(async )?def //' | sort)
  nf=$(printf '%s\n' "$funcs" | grep -c .)
  feat="$featdir/$m.feature"

  if [ ! -f "$feat" ]; then
    if [ "$nf" -eq 0 ]; then
      printf '%-26s %9d %9s   %s\n' "$m" 0 "-" "data only, no feature needed"
      continue
    fi
    fail=1
    tot_f=$((tot_f + nf))
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" 0 "NO FEATURE FILE"
    continue
  fi

  scen=$(grep -hE '^  Scenario:' "$feat" | sed -E 's/^  Scenario: ([A-Za-z_][A-Za-z0-9_]*).*/\1/' | sort)
  ns=$(printf '%s\n' "$scen" | grep -c .)
  tot_f=$((tot_f + nf))
  tot_s=$((tot_s + ns))
  missing=$(comm -23 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
  extra=$(comm -13 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))

  if [ "$nf" != "$ns" ] || [ -n "$missing" ] || [ -n "$extra" ]; then
    fail=1
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" "MISMATCH"
    [ -n "$missing" ] && printf '    missing: %s\n' "$(printf '%s ' $missing)"
    [ -n "$extra" ] && printf '    extra:   %s\n' "$(printf '%s ' $extra)"
  else
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" OK
  fi
done

echo ""
if [ "$tot_f" -gt 0 ]; then
  printf 'TOTAL %d functions, %d scenarios, %d%% covered\n' "$tot_f" "$tot_s" $(( tot_s * 100 / tot_f ))
fi
[ "$fail" -eq 0 ] && echo "every module holds one scenario per function" || echo "coverage is incomplete; see the rows above"
exit "$fail"
