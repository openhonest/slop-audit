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
- **A. Immutable-arg exception — IMPLEMENTED in this branch** (`state_bounds_filters._is_immutable_typed` + the `unresolved`-clear rule). When the state attribute's annotation names only provably-immutable value types (`bytes`/`str`/`int`/`float`/`datetime`/`frozenset`/tuple…, seen through `Mapped[T]`/`Optional`/`None`), the callee cannot mutate it, so the escape is harmless → the finding clears. Sound; the full suite stays green (incl. `test_passed_to_unknown_callee_keeps_write_once_but_escapes`, whose arg is untyped → still escapes). On the reference repo it cleared the ORM composition set (`email_hash`, `firebase_uid_hash`, `permissions`, `is_deleted`), 16 → 12 undetermined.
- **B. Repo-pure-callee exception (open).** A function defined in-repo whose body never mutates its parameters is pure w.r.t. that arg → follow the result. One-level interprocedural; would also clear immutable-value cases that are held on *unannotated* attributes.
- **C. Result-observe-only narrowing (rejected: unsound).** Follow the result whenever it is observe-only. Tried and the suite correctly rejects it — it ignores mutation. Only sound combined with A or B.

### Still open after A — the Ch2 one-owner resource question
After A, the reference repo's residual undetermined is **12 (→10 if two immutable configs, `int`/`str`, are given class annotations)**, and they are all **mutable one-owner framework resources**: SQLAlchemy `_engine`/`_async_engine`/`security_handler`, the FastAPI `app` + a middleware's `_fastapi_app`, the app-lifespan `_cache_service`/`_audit_queue_service` handles, injected middleware `cache_service`, the Redis `_rotate_script`. These are *mutable*, so A does not (and should not) clear them, and they escape to callees, so the fail-close is technically correct.

**But Honest Code Ch2 explicitly blesses stateful resources with exactly one owner** (connections, engines, the app object) — the meter flags the very pattern the framework sanctions. A write-once one-owner resource is the honest shape here, yet `test_passed_to_unknown_callee_keeps_write_once_but_escapes` deliberately keeps write-once-that-escapes `unresolved`. So this is a genuine methodology decision only the author can make: **does the Slop Audit treat a write-once one-owner resource (Honest Code Ch2) as bounded, or as a fail-closed escape?** Until that is decided, a maximally-Honest-Code service cannot reach verdict-CAN on account of its own framework resources — which is the last mile between this repo's measured **D** and **A**.

### Why it matters
The Slop Audit measures against Honest Code. If the meter flags the exact pure-function composition Honest Code prescribes, a maximally-honest repo cannot reach an A **without inlining its pure helpers** — de-composing to satisfy the meter, the opposite of the methodology. Closing the immutable-arg / pure-callee gap (A or B) would let honest composition score as the finite-testability it actually is.
