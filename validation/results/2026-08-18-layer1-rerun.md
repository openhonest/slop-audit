# Layer 1 re-run after ten classifier rules, 2026-08-18

**Status:** re-run of the 2026-08-17 pair against a changed analyzer. Layer 1 only. Layers 2 and 3 are human audits and still have never been performed.
**Analyzer commit:** `f40c9e6`, against `0d10039` for the run being checked.
**Controls:** `idd` at `honest-conversion`, tip `0a430d8a` (positive), and `Iddadvisor` at `main`, tip `1239d08` (negative). Cloned, not checked out; both source repositories were verified to be on their own unrelated branches before and after.

## Bottom line

The separation survives. Positive 2 of 17 slop signals, negative 10 of 17, which are the counts the 2026-08-17 run published. Ten classifier rules landed between the two runs and the headline result did not move.

One band moved, and it moved against the positive control: L1.12 goes 0.84 Healthy to 2.54 Not Healthy. That is the dead-code work of 2026-08-18 finding fifteen unreferenced definitions the old rule excused, and it is the direction that matters. A change to a measure that only ever flatters the codebase it was developed against is the change to distrust.

## The one that moved

| indicator | positive 2026-08-17 | positive today | negative 2026-08-17 | negative today |
|---|---|---|---|---|
| L1.12 | 0.84 / Healthy | **2.54 / Not Healthy** | 1.02 / Not Healthy | 1.15 / Not Healthy |

Two rules did it. A name mentioned in prose no longer exempts a definition from the dead-code count, and a module nothing imports no longer certifies its own contents. Fifteen unreferenced definitions in the positive control, twenty-four in the negative.

Every other indicator holds its band on both controls. The full panel is unchanged from `2026-08-17-negative-control.md` except that row.

## The negative control is now refused a grade, and the reason is ours

Its silence index is 0.682 against a floor of 0.52, so no grade is issued for it. Ten of its fifteen silent states are `unmodeled_construct`: TypeScript shapes the classifier has no rule for.

That refusal is honest and it is also a limit worth stating plainly. The floor was re-derived today from the eight pinned corpus repositories, which are C, C#, Java and Python. **The corpus holds no TypeScript at all**, so a number calibrated on four languages is being applied to a fifth. The positive control, which is Python, sits at 0.276 and grades normally. Tracked as slop-audit-gho.

## What this does and does not establish

It establishes that today's ten classifier rules did not break the Layer 1 separation on this pair, and that the one band they moved moved toward accusing the codebase the instrument was developed on.

It does not establish anything the 2026-08-17 run did not. One positive and one negative is a demonstration, not a validation study. L1.13 is n/a for want of jscpd on this machine. L1.19 and L1.20 are still n/a because the run used `--no-exec`, which is the re-run with a test-execution trace that slop-audit-uef has been asking for since 2026-08-15 and that this is not.

## Method

`git clone --single-branch` into a temporary directory, then `--no-exec --format json`, which is the method the run being checked used. Both source repositories were on unrelated branches with their own uncommitted work before and after, and were not touched.
