# A negative control that works, 2026-08-17

**Status:** second Layer 1 run of the day. Supersedes the negative half of `2026-08-17-layer1.md`, which does not supersede its positive half.
**Analyzer commit:** `0d10039`
**New negative control:** `Iddadvisor` at `main`, tip `1239d08`, 2026-04-13. Cloned, not checked out; the source repository was verified untouched and still on its own branch.

## Bottom line

The instrument separates a structured codebase from an unstructured one. That could not be said this morning.

| control | slop signals of 17 | share |
|---|---|---|
| `idd honest-conversion` (positive) | 2 | 12% |
| `idd develop` (first negative attempt) | 5 | 29% |
| **`Iddadvisor main` (negative)** | **10** | **59%** |

The spec's high-confidence threshold is eleven or more of twenty, or 55%, with n/a indicators excluded from both halves of the fraction. Three came back n/a here, so the denominator is 17 and the bar is 10 or more. The new negative control reaches it. The first attempt did not, and that was a fact about `develop` rather than about the instrument.

## The panel, all three side by side

| indicator | positive | old negative | new negative |
|---|---|---|---|
| L1.1 | 16.2 / Healthy | 11.4 / Healthy | 0.3 / Slop |
| L1.2 | 47.5 / Healthy | 54.4 / Healthy | 87.9 / Slop |
| L1.3 | 15.4 / Healthy | 21.9 / Healthy | 2.4 / Slop |
| L1.4 | 21.7 / Not Healthy | 15.9 / Not Healthy | 2.0 / Slop |
| L1.5 | 74.7 / Healthy | 23.9 / Slop | 46.0 / Not Healthy |
| L1.6 | 17.2 / Healthy | 19.0 / Healthy | 15.8 / Healthy |
| L1.7 | 45.2 / Healthy | 44.5 / Healthy | 52.0 / Healthy |
| L1.8 | 0.96 / Healthy | 0.81 / Healthy | 0.0 / Slop |
| L1.9 | present / Healthy | present / Healthy | absent / Slop |
| L1.10 | 5 / Healthy | 12 / Healthy | 0 / Slop |
| L1.11 | present / Healthy | present / Healthy | absent / Slop |
| L1.12 | 0.84 / Healthy | 5.87 / Slop | 1.02 / Not Healthy |
| L1.13 | n/a | n/a | n/a |
| L1.14 | 6 / Slop | 6 / Slop | 0 / Healthy |
| L1.15 | 17.64 / Slop | 18.8 / Slop | 6.14 / Slop |
| L1.16 | 0.0 / Healthy | 0.01 / Healthy | 1.89 / Not Healthy |
| L1.17 | 0.85 / Not Healthy | 3.27 / Slop | 3.57 / Slop |
| L1.18 | 15.1 / Not Healthy | 35.6 / Not Healthy | 5.2 / Healthy |
| L1.19 | 515 / n/a | 7137 / n/a | 2286 / n/a |
| L1.20 | not run | not run | not run |

## What carries the separation, and what does not

The whole structured-process cluster fires at once on the new control. L1.9 pre-commit hooks, L1.10 CI pipelines and L1.11 containerisation are all **absent** where both idd branches have them present and parameterised. That block of three is the clearest signal in the panel, and it is exactly what the methodology says it measures: process discipline, not code taste.

The git-history indicators follow. L1.1, L1.2, L1.3, L1.4 and L1.8 are all Slop on the new control and Healthy on both idd branches.

**Two indicators run the other way, and honesty requires saying so.** L1.14 reads 0 on the new negative control and 6 on both idd branches, so on secrets the "unstructured" codebase is the clean one. L1.18 reads 5.2 Healthy against the positive control's 15.1 Not Healthy, so on unbounded mutable state it is also the better of the two. Neither is a defect in the instrument. They are a reminder that an aggregate of twenty indicators is not a ranking, and that a codebase can be undisciplined about process while being tidy about state.

## What this does and does not establish

It establishes that the instrument distinguishes a structured codebase from an unstructured one on Layer 1, on one pair, in Python and TypeScript.

It does not establish a calibrated threshold, a false-positive rate, or anything about Layers 2 and 3. Three indicators returned n/a. The sample is one positive and one negative, which is a demonstration and not a validation study.

## A defect this run found

The audit did not finish in ten minutes on the first attempt, and the cause was the analyzer rather than the repository. `secret_scan`'s generic-credential rule was quadratic in line length on a bundled stylesheet whose longest line is 285,769 characters, and its binary test ran after each file had already been read whole, so 45,303 committed PNGs were read and discarded. Both are fixed in `0d10039`. The secret scan went from not finishing to 17 seconds and the full panel now runs in 65.

That is the argument for validating against real repositories rather than a pinned corpus. Neither defect was reachable from the six repositories the thresholds were measured on.

## Method

`git clone --single-branch` into a temporary directory. The source repository was checked before and after and remained on its own unrelated branch with its own uncommitted work. The analyzer ran at `0d10039` with `--no-exec --format json`, so L1.19 and L1.20 were not executed.

## Owed

Layers 2 and 3 for all three repositories. A run with test execution so L1.19 and L1.20 carry values. L1.13 needs jscpd on the measuring machine. And the protocol's expected outcomes should be re-derived from more than one pair before any of these numbers is quoted as a calibration.
