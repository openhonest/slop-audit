# Advisory: the portable binary omits six indicators without saying so

**Date: 2026-08-14. Affects: the `slop-audit-rs` portable binary, including every asset published under release v0.2.0. Does not affect the Python `l1_analyzer`.**

If you have run the portable binary and drawn any conclusion about finite testability from its output, that conclusion is void and the run should be repeated with the Python tool. This is the whole advisory; the rest is evidence.

## What the binary does

On the same repository the Python tool reports 21 `L1.*` keys and the binary reports 15. For the six it does not compute, it emits **no row at all**:

| Missing key | What it is | Why it is missing |
|---|---|---|
| L1.12 | dead-code ratio | needs `vulture`, not ported |
| L1.13 | duplication | needs `jscpd`, not ported |
| L1.14 | secret scan | needs `gitleaks`, not ported |
| **L1.18** | **mutable-state ratio** | **not ported** |
| **L1.18b** | **finite-testability classification** | **not ported** |
| L1.20 | test-execution outcome | needs a test run |

There is no `n/a`, no `not implemented`, and no reason string anywhere in the Rust source. The row is simply absent, so a scorecard from the binary reads as complete while missing L1.18, which is the headline indicator and the thing finite testability means.

The tool already knows the correct shape. L1.19 **is** present in the binary's output, carrying `not run by this reference implementation`. Six indicators had that pattern available in the same output routine and did not use it.

## What is wrong underneath, which is worse than the omission

The binary has no declared coverage manifest. Its output is assembled from whatever happened to compute, so three different facts collapse into one observable:

- this indicator is not implemented
- the external tool it needs is absent
- it ran and found nothing to report

All three are silence. A consumer cannot distinguish them, and neither can a maintainer, which is why a release shipping a superseded classifier is undetectable from its own output.

This is the input-side silent-failure shape the Honest Framework exists to name, sitting in our own instrument. Tracked as `slop-audit-t17`, priority 1.

Note that the README's coverage table was accurate throughout: it said "not yet" against exactly these indicators. The documentation told the truth and the instrument did not, and a consumer reads the instrument.

**Fixed on `main`.** The canonical indicator set is now declared as data in `tools/slop-audit-rs/src/coverage.rs`, and every run emits one row per member. An indicator the binary does not compute prints `not measured` in both the value and band columns, plus the reason it was not measured, and the three reasons stay distinguishable from each other:

- `not ported to the portable binary` — L1.18, L1.18b, and the three additive checks
- `requires <tool>, which the single-file binary does not bundle` — L1.12, L1.13, L1.14
- `requires executing the target's own test suite` — L1.20

Three tests hold the two implementations to the same key set: every canonical indicator gets a row, every indicator the binary computes is declared canonical (so porting L1.18 without declaring it would fail rather than compute the right answer and print nothing), and everything declared measured actually appears in a real run.

The parity differ had the same blind spot and is fixed with it. It compared only the intersection of the two key sets, which is how it reported 16/16 for weeks across a set that excluded L1.18. It now reports unmeasured indicators as explicit `GAP` lines, fails on any reference indicator the binary omits entirely, and says "16/16 **compared** indicators equal" rather than implying a complete audit.

## What to do instead

Clone `main` and run the Python implementation, which is what the README's install path already specifies:

```
git clone https://github.com/openhonest/slop-audit && cd slop-audit/tools/l1_analyzer
uv sync --extra dev
uv run slop-audit-l1 /path/to/repo
```

`--no-exec` skips the two indicators that run the target's own suite.

## Release v0.2.0 is separately out of date

Independently of the coverage defect, v0.2.0 predates four fixes to the L1.18b classifier. `git tag --contains` returns empty for all four: `c132f40`, `2aff645`, `41dfae0`, `606043a`. Those fixes are on `main` and are not in any published artifact.

## How this was found

An external adopter reported three defects in L1.18b against two production codebases. All three were real and all three are fixed on `main`. Chasing them meant diffing the two implementations key by key rather than trusting the parity number, and the parity number was 16/16 throughout — across a key set that silently excluded L1.18. Nothing compared the key sets themselves, so the check intended to prove the implementations agree could not see what it was not comparing.

The nine-repository validation corpus surfaced none of the four. Two real codebases surfaced all of them.
