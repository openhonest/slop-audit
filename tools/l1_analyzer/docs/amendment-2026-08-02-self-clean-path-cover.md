# Amendment 2026-08-02: self-clean CFG builder and I/O-boundary exclusion

Two changes so L1.18 is honest about instrumentation and about its own source.

## 1. The analyzer is now self-clean (bug fix)

L1.18 on the analyzer's own source reported 11.7% (9/77 functions). All nine were
in `path_cover.py`: a stateful `_CFG` class whose methods (`__init__`, `node`,
`edge`, `build_block`, `build_stmt`, `_if`, `arm`, `_loop`, `_match`) accumulated
into `self.edges` and `self._n`. That is exactly the mutable-instance-state pattern
L1.18 exists to flag, so the tool was failing its own audit. The fabricated
behavioural step hid it by asserting 0.0 unconditionally.

`_CFG` was refactored to module-level functions that thread the two accumulators
explicitly: `edges` (the edge list) and `counter` (an `itertools.count` id source).
Every builder takes them as parameters and binds no instance or module state. The
control-flow graph and every `function_cover` result are identical (the node-id
sequence and edge order are preserved), so `tests/test_path_cover.py` passes
unchanged. L1.18 on the analyzer's own source is now 0/N.

## 2. Declared I/O boundaries are excluded from L1.18

A function that declares itself an I/O boundary with a comment marker
(`# honest: boundary`, `// honest: boundary`) is excluded from the L1.18 ratio,
numerator and denominator. I/O at the boundary is where external state legitimately
lives; the interior is what should stay pure.

Recognition is by DECLARATION, never by guessing at function names or at which
calls perform I/O. An unmarked function is never excluded, so no repository's L1.18
number changes unless its authors opt in with the marker. This is the meter
honoring the gate's declaration, consistent with the finite-testability asymmetry
(the gate recognizes boundaries by declaration; the meter honors that declaration
when present and otherwise measures).

## Regression cover

`tests/test_path_cover.py` (unchanged results) plus new assertions in
`tests/test_basic.py`: the analyzer's own source scores 0.0 under L1.18, and a
`# honest: boundary` function touching a module global is excluded.

## Note for Paper A

The boundary exclusion is opt-in, so unmarked corpora are unaffected. The
self-clean refactor changes no L1.18 number for any audited repository; it only
changes the analyzer's own source, which is not part of the corpus.
