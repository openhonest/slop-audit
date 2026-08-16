#!/usr/bin/env bash
# feature-gate.sh — the function-point invariant: every function carries exactly one gherkin
# scenario (honest-gherkin §9). The scenario count is the directly-counted FP measure, so a
# function with no scenario (or a scenario with no function) is a real defect, gated like
# dishonest code.
#
# Ported from honest-framework/python/feature-gate.sh, which the Slop Audit had no equivalent
# of. The framework sits at 96% one-scenario-per-function because that gate refuses the next
# commit; this analyzer sat at 16% because nothing ever asked.
#
# Affected-only: checks just the modules whose source OR feature file is staged for commit.
# Bijection per module: the set of module-level function names in l1_analyzer/<m>.py must equal
# the set of scenario subjects in features/<m>.feature (counts equal, none missing, none extra).
#
# Plus one reserved scenario per file, `Scenario: undecidable ...`, excluded from the bijection
# and separately required. A measure that meets a construct it has no rule for must say so rather
# than return a verdict, and must offer the shape of what it could not read for collection. That
# is the whole finding of the L1.18 root-cause analysis: the meter returned 0.0 and Healthy for a
# closure it never looked at, because nothing obliged it to state the case where it decides
# nothing. Requiring the scenario is how the obligation becomes structural instead of remembered.
set -uo pipefail
root=$(git rev-parse --show-toplevel)
pkg="$root/tools/l1_analyzer/l1_analyzer"
featdir="$root/tools/l1_analyzer/features"

staged=$(git diff --cached --name-only --diff-filter=ACM)
mods=$(printf '%s\n' "$staged" | sed -nE \
  -e 's#^tools/l1_analyzer/l1_analyzer/([a-z_0-9]+)\.py$#\1#p' \
  -e 's#^tools/l1_analyzer/features/([a-z_0-9]+)\.feature$#\1#p' | sort -u)
[ -z "$mods" ] && exit 0

fail=0
for m in $mods; do
  src="$pkg/$m.py"
  [ -f "$src" ] || continue   # a feature whose module was deleted; the extra-scenario arm below is not reachable

  funcs=$(grep -hoE '^(async )?def [a-z_][a-z0-9_]*' "$src" | sed -E 's/^(async )?def //' | sort)
  nf=$(printf '%s\n' "$funcs" | grep -c .)

  feat="$featdir/$m.feature"
  if [ ! -f "$feat" ]; then
    [ "$nf" -eq 0 ] && continue   # a data-only module declares no function and needs no feature
    fail=1
    echo ""
    echo "feature-gate: $m — no feature file, and the module declares $nf functions."
    echo "  Create tools/l1_analyzer/features/$m.feature with one scenario per function:"
    echo "    Scenario: <function_name> <plain description>"
    continue
  fi

  all_scen=$(grep -hE '^  Scenario:' "$feat" | sed -E 's/^  Scenario: ([A-Za-z_][A-Za-z0-9_]*).*/\1/' | sort)
  nu=$(printf '%s\n' "$all_scen" | grep -cx 'undecidable')
  scen=$(printf '%s\n' "$all_scen" | grep -vx 'undecidable' | sort)
  ns=$(printf '%s\n' "$scen" | grep -c .)

  if [ "$nu" -ne 1 ]; then
    fail=1
    echo ""
    echo "feature-gate: $m — $nu undecidable scenarios, expected exactly 1."
    echo "  Every feature states what the module does when it meets a construct it has no rule"
    echo "  for, and what it offers the operator about it. Add, to features/$m.feature:"
    echo "    Scenario: undecidable <what this module cannot decide>"
    echo "  It must say that the module reports the case rather than returning a verdict, and"
    echo "  that the shape of what it could not read is offered for collection, opt-in per run,"
    echo "  node types only. See research/candidates/collecting-unmeasured-constructs.md."
  fi
  missing=$(comm -23 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
  extra=$(comm -13 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))

  if [ "$nf" != "$ns" ] || [ -n "$missing" ] || [ -n "$extra" ]; then
    fail=1
    echo ""
    echo "feature-gate: $m — the gherkin features do not match the code ($nf functions, $ns scenarios)."
    echo "  The rule: every function has exactly one scenario named after it, written as"
    echo "    Scenario: <function_name> <plain description>"
    echo "  in tools/l1_analyzer/features/$m.feature"
    if [ -n "$missing" ]; then
      echo "  ADD a scenario for each of these functions (it has none yet):"
      printf '    %s\n' $missing
    fi
    if [ -n "$extra" ]; then
      echo "  These scenarios name no function — the function was renamed or removed."
      echo "  DELETE the scenario, or correct its name to match the function:"
      printf '    %s\n' $extra
    fi
  else
    echo "feature-gate: $m OK ($nf functions = $ns scenarios)"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "feature-gate: commit blocked — make the features above match the code, then commit again." >&2
fi
exit "$fail"
