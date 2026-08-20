# Amendment 2026-08-19 — scope `scripts/`+`seed/` dirs; and an open question: the call-target fail-close penalises Honest-Code composition

Context: measured against a real, fully ADR-007 / Honest-Code-converted production repo (TraileAI/iam). Part 1 is implemented in this commit. Part 2 is an RFC — a methodology decision for the tool author, not a change made here.

## Part 1 — Implemented: `scripts/` and `seed/` are tooling directories

`_bucket_reason` already treats a **loose root** `.py` sitting beside packages as a dev/entry-point script — "not the code under test" (`card.py` `scoped.why`) — but only at the repo root. A conventional **`scripts/`** directory is the same thing organised into a folder (nightly monitors, ops/benchmark/entry-point scripts); **`seed`/`seeds`** hold data-population scripts. They were being analysed as if they were the library under audit.

Change: `_TOOLING_DIRS = {"scripts", "seed", "seeds"}`; `_bucket_reason` returns reason `"scripts"` for any file under one; `bucketed_paths` **discloses** them (never a silent skip). General and structural; references no project. Directory-level parallel to the existing root-script rule and to how `tests/` is already scoped.

Effect on the reference repo: eliminated **all 6 promiscuous drivers** (every one was in `scripts/nightly/*` / `scripts/performance-benchmark.py`), moving the L1.18b verdict from **cannot → might**.

## Part 2 — RFC: the call-target fail-close penalises the composition Honest Code prescribes

### The rule
L1.18b fail-closes to `UNRESOLVED` on a state value passed as an argument to an opaque (non-builtin, non-effect) call target. Documented (`state_bounds` docstring: *"Fail-close (UNRESOLVED) only on a value passed to an unbounded call target"*) and tested:
- `test_module_global_that_itself_escapes_stays_unresolved`: `h = build(); def q(): return serialize(h)` → `h` is **unresolved** ("handed to an unknown callee. Real finding.")
- `test_passed_to_unknown_callee_keeps_write_once_but_escapes`: `helper(self._b)` → **unresolved** ("could mutate it").

### The rationale (sound, as far as it goes)
In Python an opaque callee can **mutate or retain** a mutable argument passed by reference, so the value's future is not bounded by the current scope. Correct when the callee is unknown **and** the argument is mutable.

### The tension
Honest Code **Ch4** (pure functions — data in, data out) and **Ch6** (compose flat) *prescribe* decomposing logic into small pure functions. A codebase that follows this routes state through exactly such helpers — and every one of those calls trips the fail-close. **The more Honest-Code-compliant a repo is, the worse it scores on L1.18b for the composed-out state.** The meter and the methodology it measures against pull in opposite directions here.

### Evidence
The reference repo, after the full ADR-007 conversion + every meter-legitimate in-repo fix, has ~16 `unresolved` drivers. **Every single one** is `helper(self.<immutable column>)` or `f(<one-owner singleton>)` where the call **result is observe-only** (returned / assigned / displayed) — none is a mutation-through-callee:

| driver | site | arg kind |
|---|---|---|
| `self.email_hash`, `self.firebase_uid_hash` | `hash_prefix(self.email_hash)` in `__repr__` | `bytes` (immutable) — display only |
| `self.permissions` | `json.loads(self.permissions)` returned | `str` (immutable) |
| `self.is_deleted` | `self._ensure_utc(self.is_deleted)` → duration | `datetime` (immutable) |
| `_cache_service`, `_audit_queue_service` | `build_audit_queue_handle(_cache_service)` assigned | one-owner resource handed to a builder |
| `_engine`, `_async_engine`, `security_handler`, `app`, middleware caches | passed to setup/builders, result stored | one-owner framework resources (Honest Code Ch2 blesses these) |

None can be mutated through the callee (immutable args) or is a genuine escape (one-owner resource whose builder result is stored). The fail-close is a false-positive against Honest Code for all of them.

### Options (author's call)
- **A. Immutable-arg exception.** When the passed value is provably immutable (a literal, a const-typed value, or a known-immutable builtin kind — `bytes`/`str`/`int`/`float`/`datetime`/`frozenset`/tuple), the callee cannot mutate it → follow the call result compositionally. Sound (immutability defeats the mutation concern), lowest-risk, no interprocedural analysis. **Recommended.**
- **B. Repo-pure-callee exception.** A function defined in-repo whose body never mutates its parameters (`param.x = …`, `param[…] = …`, or a mutating method on `param`) is pure w.r.t. that arg → follow the result. Fuller, one-level interprocedural, still conservative.
- **C. Result-observe-only narrowing (alone: unsound).** Follow the result only when it is observe-only in the host. I implemented and tested this — **your suite correctly rejects it** (it ignores mutation). Only sound combined with A or B.
- **D. Status quo + relabel.** Accept the tension as intended and add a distinct sub-label (e.g. `unresolved: composed-out`) so composition-opaque state is not conflated with genuinely-undecidable state, and a reader can see the difference.

### Why it matters
The Slop Audit measures against Honest Code. If the meter flags the exact pure-function composition Honest Code prescribes, a maximally-honest repo cannot reach an A **without inlining its pure helpers** — de-composing to satisfy the meter, the opposite of the methodology. Closing the immutable-arg / pure-callee gap (A or B) would let honest composition score as the finite-testability it actually is.
