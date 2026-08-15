# L1.18a, a corrected mutable-state ratio alongside a frozen L1.18 (REJECTED)

**Status: rejected 2026-08-15, the same day it was written. Superseded by `tools/l1_analyzer/docs/amendment-2026-08-15-l1-18-corrected-ratio.md`, which corrects L1.18 in place.**

## What was proposed

Freeze L1.18 at its published definition, mark it deprecated, and publish the corrected ratio under a new code, L1.18a. The argument was reproducibility: a pre-registered 200-repository study measured L1.18, and moving the number would break that study.

## Why it was rejected

**The reproducibility argument does not hold.** A deposited study stays reproducible because the analyzer commit is pinned, which this project already does and documents. The indicator's name never carried that guarantee, so renaming buys nothing a pinned commit does not already give.

**The project already corrects indicators in place, and has already corrected this one.** Ten dated amendments sit in `tools/l1_analyzer/docs/`. `amendment-2026-08-14-csharp-test-scope.md` changed what counts as a test directory and says in its own text that it moved L1.15, L1.17, L1.19, **L1.18**, L1.18b and the absolute-path check on every C# repository — a wider blast radius than the four corrections at issue here. Nobody created an L1.15a. The amendment record, not a new code, is how a moved number is disclosed here.

**Two codes for one question is the cost, not the saving.** L1.18 and L1.18a would both have been emitted, both been chartable, and differed by up to 12.7 points in a direction decided by the language. That is a reading hazard created to avoid one that a dated amendment already handles.

## What survives

Everything except the split. The four defects were real, were verified, and are fixed: the inert I/O boundary exclusion (withdrawn, with the evidence that it cannot be done by analysis), the shared immutability vocabulary that made TypeScript `let` immutable, the unreachable Java and C# fields, and the ratio's blindness to bounded state. The measured movement, per repository and per language, is in the amendment.
