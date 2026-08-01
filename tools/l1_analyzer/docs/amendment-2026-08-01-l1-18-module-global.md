# Amendment 2026-08-01 — fix L1.18 module-global false positives (Python)

Filed in response to a bug report (`l1-18-module-global-extraction-bug.md`) reproduced against `openhonest/umbra` at `31c044b`, analyzer at `493f2eb`.

## What was wrong

`_find_module_mutable_names` extracted the binding name by decoding each candidate assignment to text, splitting on `=`, and taking the last token to the left. On umbra this registered 36 "module-level mutable globals," **none of which were module-level mutable globals**, and missed the one that was. Four compounding defects:

1. **Binds the annotation tail, not the name.** `SITE_LABELS: dict[str, str] = {...}` splits to `... str]` → `str`. This is what put `str`, `bool`, `None` and truncated fragments into the mutable set. Every function annotating a local `str` was then counted.
2. **The uppercase-constant guard tested the wrong token,** so it inverted: it protected annotated tables it was not meant to and excluded the genuine accumulator `RETAINED_PROOFS_BY_AUDIT`.
3. **Multi-line string literals were scanned as source,** harvesting identifiers out of embedded JS/CSS/SQL and even prose containing an `=`.
4. **Type aliases counted as mutable state.** `FunctionNode = ast.FunctionDef | ...` and TypedDict/Protocol names were registered.

The bias was not random: annotated dispatch tables and module-level type aliases are exactly the constructs the Honest Framework prescribes, so the instrument scored the prescribed style as mutable-state-heavy.

## The fix

`_find_module_mutable_names` now reads the binding from the assignment's `left` field for Python (behind a `field_based_globals` flag in `LANG_CFG`). This kills defects 1 and 3 outright: a string literal is not an assignment node, and an annotation is not the `left` field. Added on top:

- **Type-alias skip (defect 4):** the binding is skipped when its right-hand side is a pure type expression (a name, a dotted name, a subscript, or a `|` union of those) or the annotation is `TypeAlias`.
- **Accumulator rule (defect 2):** an uppercase name stays a constant unless it is seeded with an empty container (`CACHE = {}`, `BUF = []`), which is a mutable accumulator, the pattern the indicator exists to catch. This also catches the genuine `RETAINED_PROOFS_BY_AUDIT = {}` the old code missed.
- **Dunder exclusion:** `__all__`, `__version__`, and other module metadata are not state.

The frozen convention is otherwise preserved: a lowercase module binding is mutable, an uppercase scalar binding is a constant. `tests/test_module_globals.py` locks all of this by asserting on the registered NAME SET, not only the ratio.

## Scope

**Python only.** The eight other languages keep the legacy text heuristic, so their L1.18 values are byte-for-byte unchanged (no unvalidated cross-language regression). The same defect pattern exists there and should be migrated to field-based extraction per language, with per-grammar validation, in a later amendment.

## Measured impact (umbra)

| | L1.18 | Functions flagged | Module globals detected |
|---|---|---|---|
| Before (buggy) | 4.9% | 49 / 1001 | 36, all false |
| After (this fix) | 0.5% | 5 / 1001 | 1: `RETAINED_PROOFS_BY_AUDIT` |

The 5 are genuine: 2 in `StdioSamplingRequester` (receiver arm, always correct) and 3 real readers of the `RETAINED_PROOFS_BY_AUDIT` accumulator. This is higher than the bug report's minimal "corrected value" of 0.2% (2/1001) precisely because this fix also closes defect 2, so the one true mutable global is now counted rather than missed.

## Pre-registration note

This changes L1.18 for Python repositories that use annotated module bindings, type aliases, or embedded program/prose strings — the change is a correction of near-total false positives, not a redefinition of the indicator. **Any Paper A data collected with the pre-fix extractor is inflated on this axis** and should be recomputed or carry a documented correction before it is relied on; the production Paper A analyzer needs the same fix, filed before further data collection. L1.18b, L1.15, L1.17 and the other indicators are unaffected.
