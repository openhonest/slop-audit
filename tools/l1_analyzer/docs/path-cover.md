# path_cover — minimum end-to-end path cover (provenance note)

Added 2026-07-31. Gated and additive, the same as L1.18b.

## What it computes

For a repo that is finitely testable, the theoretical end-to-end figure (2 ** decisions) is honest but useless: a clean codebase comes back as a number with dozens of digits, which reads as "untestable" when it is the opposite. This gives the attainable number instead: the minimum count of runs, each following control flow from an entry to an exit, that together walk every branch at least once. Not the number of distinct paths (that multiplies), but the fewest walks that cover every edge.

The number is a minimum flow with a lower bound of 1 on every control-flow edge: each branch must be walked once, and we minimize how many entry-to-exit walks that takes. A function whose graph is balanced covers in one run.

## Guarantees

- Additive and gated. Emitted under `path_cover`, only when `classify_state_bounds=True` (on for CLI and web, off for the pre-registered experiments). Off-mode output is unchanged; the frozen-equivalence golden still holds.
- Verified against hand-checked answers: straight line 1, if/else 2, nested if 3, three-way switch 3, sequential ifs pair to 2. See `tests/test_path_cover.py`.

## Scope and honest limits

- Python only, v0. Other languages return n/a.
- **Intraprocedural.** It builds one control-flow graph per function and sums the per-function covers. The whole-program version, which links calls into one interprocedural graph so a run threads through callees (fewer, longer runs), is the next stage. It needs the call-graph resolution described in `~/dev/HONEST-reject-unbounded-call-constructions.md`, and a repo with unbounded call targets would come back with an unbounded graph, which is the honest answer for it.
- The CFG builder handles if/elif/else, while, for, break, continue, return, and match. try/with are entered as sequences. Unhandled compound statements are treated as straight line, which can undercount; extend the builder before trusting the number on heavy metaprogramming.
- Edge coverage is the floor. A single run through a non-empty loop covers both the enter-edge and the exit-edge, so the count does not force a separate empty-loop test. It is the minimum, not a full test plan.
