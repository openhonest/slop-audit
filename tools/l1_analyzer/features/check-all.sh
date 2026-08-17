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
nound=0
norph=0
tot_p=0

# A feature file whose module does not exist was invisible to this script until 2026-08-17,
# because the loop below walks SOURCE files and asks each one for its feature. A spec for
# deleted code is the mirror of code with no spec, and only one of the two was being caught.
# It is allowed, but only when declared: every scenario in it must carry @pending, which is
# what separates a specification waiting for its implementation from one nobody noticed had
# rotted.
for feat in "$featdir"/*.feature; do
  m=$(basename "$feat" .feature)
  [ -f "$pkg/$m.py" ] && continue
  total=$(grep -cE '^  Scenario:' "$feat")
  pending=$(grep -cE '^  @pending' "$feat")
  if [ "$total" -eq "$pending" ] && [ "$total" -gt 0 ]; then
    printf '%-26s %9s %9d   %s\n' "$m" "-" "$total" "spec only, $total pending implementation"
  else
    fail=1
    norph=$((norph + 1))
    printf '%-26s %9s %9d   %s\n' "$m" "-" "$total" "ORPHAN SPEC: $pending of $total tagged @pending"
  fi
done
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

  all_scen=$(grep -hE '^  Scenario:' "$feat" | sed -E 's/^  Scenario: ([A-Za-z_][A-Za-z0-9_]*).*/\1/' | sort)
  nu=$(printf '%s\n' "$all_scen" | grep -cx 'undecidable')
  scen=$(printf '%s\n' "$all_scen" | grep -vx 'undecidable' | sort)
  ns=$(printf '%s\n' "$scen" | grep -c .)
  tot_f=$((tot_f + nf))
  tot_s=$((tot_s + ns))
  # Scenario subjects carrying @pending on the line above them. An extra scenario is either
  # a specification waiting for its implementation or a leftover from deleted code, and until
  # 2026-08-17 this script called both MISMATCH and left a reader to guess which. Declaring
  # the first with a tag is what makes the second detectable.
  pend=$(awk '/^  @pending/{p=1;next} /^  Scenario:/{if(p){sub(/^  Scenario: /,"");sub(/ .*$/,"");print} p=0} {if($0 !~ /^  @/) p=0}' "$feat" | sort -u)
  missing=$(comm -23 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
  extra=$(comm -13 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
  extra=$(comm -23 <(printf '%s\n' "$extra" | grep . | sort -u) <(printf '%s\n' "$pend" | grep . | sort -u))
  npend=$(printf '%s\n' "$pend" | grep -c . )

  if [ "$nu" -ne 1 ]; then
    fail=1
    nound=$((nound + 1))
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" "NO UNDECIDABLE SCENARIO"
    continue
  fi

  ns=$((ns - npend))
  tot_s=$((tot_s - npend))
  tot_p=$((tot_p + npend))
  if [ "$nf" != "$ns" ] || [ -n "$missing" ] || [ -n "$extra" ]; then
    fail=1
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" "MISMATCH"
    [ -n "$missing" ] && printf '    missing: %s\n' "$(printf '%s ' $missing)"
    [ -n "$extra" ] && printf '    extra:   %s\n' "$(printf '%s ' $extra)"
  elif [ "$npend" -gt 0 ]; then
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" "OK ($npend pending implementation)"
  else
    printf '%-26s %9d %9d   %s\n' "$m" "$nf" "$ns" OK
  fi
done

echo ""
if [ "$tot_f" -gt 0 ]; then
  # Scenarios over functions was printing 101% while ten scenarios named functions that had
  # been deleted. A number above 100 is not a coverage figure, and a reader skims the last
  # line. Both counts are stated instead, and the rows above say which way any gap runs.
  printf 'TOTAL %d functions, %d function scenarios, %d pending implementation\n' "$tot_f" "$tot_s" "$tot_p"
fi
[ "$nound" -gt 0 ] && echo "$nound module(s) state no undecidable case"
[ "$norph" -gt 0 ] && echo "$norph feature file(s) specify a module that does not exist"
[ "$fail" -eq 0 ] && echo "every module holds one scenario per function and one undecidable scenario" || echo "coverage is incomplete; see the rows above"
exit "$fail"
