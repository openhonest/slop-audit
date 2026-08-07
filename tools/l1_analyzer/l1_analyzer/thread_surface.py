"""
Thread-safety SURFACE meter (additive, deterministic, zero-LLM).

What it is, and is not. This meter does NOT detect data races. Race detection is
undecidable statically without whole-program alias and happens-before reasoning; it
is a ThreadSanitizer job. Claiming "thread-safe" from a static pass would be the
exact silent-failure lie the audit exists to surface.

What it measures instead: the concurrency AUDIT SURFACE - every site where a
language's compiler-enforced thread-safety guarantee is overridden by hand or is
simply absent. Each finding is a fact about the syntax ("here is surface a human or
TSan must verify"), never a verdict that a race exists. This is the same honest move
as the finite-testability meter, which counts partitions, not bugs.

The motivating case is the turso free-threaded WAL bug: the meter would not have
caught the race, but it flags `unsafe impl Sync for MappedSharedWalCoordination` -
the struct whose hand-asserted thread-safety turned out to be wrong. It puts the
struct on the audit list; the human finds the missing guard inside it.

Verdicts (repo-level), worst site wins:
  EXPOSED - at least one hand-override of the thread-safety guarantee present
  REVIEW  - only lower-severity footguns (e.g. relaxed atomic ordering) present
  CLEAN   - a spec exists for the language and no surface was found
  n/a     - no spec for the language

Rust surface, first pass:
  EXPOSED  unsafe impl Send / unsafe impl Sync  - Send/Sync asserted by hand
  EXPOSED  static mut                            - global mutable state, no guard
  REVIEW   Ordering::Relaxed                     - no happens-before; the atomics footgun

The predicate ("where is the guarantee overridden") is language-neutral; the node
types are not. Languages are added one scanner at a time; a language with no scanner
returns n/a rather than guess.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.indicators import (
    LANG_CFG,
    _get_parser,
    _read_source_bytes,
    bucketed_paths,
)

# conformance/ and tests hold scaffolding and doubles, not production surface.
_IGNORE = ("tests", "test", "conformance")

EXPOSED = "exposed"
REVIEW = "review"
# candidate: a real hazard SHAPE, but measured low-precision (B1 non-atomic RMW fires
# on correct lock-free code by design). It never flips a headline verdict on its own and
# reads as "confirm with the prove stage", not as an accusation. Honest confidence tier.
CANDIDATE = "candidate"
CLEAN = "clean"


class Finding(TypedDict):
    """One concurrency-surface site. Fixed keys, so a TypedDict, not a bag."""
    kind: str
    symbol: str
    severity: str
    file: str
    line: int


class SurfaceResult(TypedDict):
    """The scan result. A TypedDict, not dict[str, Any]: the shape is fixed, and the
    tool must not escape its own type discipline to describe itself (`bucketed` is
    object-valued, not Any, so no # type: ignore / Any hatch is introduced)."""
    verdict: str
    value: str
    band: str
    counts: dict[str, int]
    findings: list[Finding]
    bucketed: dict[str, object]
    details: str


def _text(node: Node | None) -> str:
    return node.text.decode("utf8", errors="ignore") if node is not None and node.text else ""


def _walk(node: Node) -> list[Node]:
    out: list[Node] = []

    def go(n: Node) -> None:
        out.append(n)
        for c in n.children:
            go(c)

    go(node)
    return out


def _mk(kind: str, symbol: str, severity: str, rel: str, node: Node) -> Finding:
    # Collapse whitespace: a multi-line field access (self.\n  .field) must read as one
    # symbol, not carry the source's line breaks into the report.
    return {"kind": kind, "symbol": " ".join(symbol.split()), "severity": severity, "file": rel, "line": node.start_point[0] + 1}


# --------------------------------------------------------------------------
# Rust scanner.
#
# Category A (overridden guarantee: unsafe impl Send/Sync, static mut) and the
# relaxed-ordering footgun are whole-file node matches. Categories B1 (non-atomic
# read-modify-write) and B2 (check-then-act) are per-function shapes, restricted to
# self.-rooted receivers so we flag shared INSTANCE state and skip pure locals. Each
# B finding is a suspected race SHAPE to verify or prove, never a proven race.
# --------------------------------------------------------------------------

# B1: a load and a store on the same atomic in one function is a read-modify-write
# done non-atomically (fetch_add / compare_exchange would be the atomic form).
_ATOMIC_STORE = frozenset({"store", "swap"})
# B2: a collection read in a condition (check) then a mutation in the body (act).
_CHECK_METHODS = frozenset({"contains_key", "contains", "is_empty", "is_none", "is_some", "get", "get_mut", "len", "capacity"})
_MUTATE_METHODS = frozenset({"insert", "push", "push_back", "remove", "pop", "clear", "extend", "append", "set", "store", "swap"})


def _rust_method_receiver(call: Node) -> tuple[str, str] | None:
    """(method, receiver_text) for a `recv.method(..)` call, else None. The receiver
    text (e.g. `self.count`) is the shared-state key we match B1/B2 on."""
    if call.type != "call_expression":
        return None
    fn = call.child_by_field_name("function")
    if fn is None or fn.type != "field_expression":
        return None
    return _text(fn.child_by_field_name("field")), _text(fn.child_by_field_name("value"))


def _rust_receivers_by_method(scope: Node | None, methods: frozenset[str]) -> set[str]:
    """self.-rooted receivers of any call whose method is in `methods`, within scope."""
    out: set[str] = set()
    if scope is None:
        return out
    for n in _walk(scope):
        mr = _rust_method_receiver(n)
        if mr is not None and mr[0] in methods and mr[1].startswith("self."):
            out.add(mr[1])
    return out


def _rust_nonatomic_rmw(func: Node, rel: str) -> list[Finding]:
    """B1: the same self.-rooted atomic is both loaded and stored/swapped in one
    function - a read-modify-write that is not a single atomic op.

    A receiver that also uses compare_exchange / fetch_* in the same function is doing
    a real atomic protocol (a CAS loop, a single-writer fetch), not an unguarded RMW,
    so it is excluded. This is what keeps the shape off correct lock-free code."""
    loads: dict[str, Node] = {}
    stores: set[str] = set()
    atomic_protocol: set[str] = set()
    for n in _walk(func):
        mr = _rust_method_receiver(n)
        if mr is None or not mr[1].startswith("self."):
            continue
        method, recv = mr
        if method == "load":
            loads.setdefault(recv, n)
        elif method in _ATOMIC_STORE:
            stores.add(recv)
        elif method.startswith("fetch_") or method in ("compare_exchange", "compare_exchange_weak", "compare_and_swap"):
            atomic_protocol.add(recv)
    return [
        _mk("nonatomic_rmw", recv, CANDIDATE, rel, node)
        for recv, node in loads.items()
        if recv in stores and recv not in atomic_protocol
    ]


# C1: Relaxed ordering is fine for a counter/stat, but a Relaxed load whose value
# gates control flow has no acquire where one is needed. Comparison operators that,
# together with a branch, make a Relaxed load control-bearing.
_CMP_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})


def _call_uses_relaxed(call: Node) -> bool:
    args = call.child_by_field_name("arguments")
    return args is not None and any(
        n.type == "scoped_identifier" and _text(n).replace(" ", "").endswith("Ordering::Relaxed")
        for n in _walk(args)
    )


def _result_feeds_branch(call: Node) -> bool:
    """True if the call's result reaches a branch condition or a comparison, through a
    few transparent wrappers. The let-bound case (`let v = ..load(); if v`) is out of
    scope on purpose - only the directly-control-bearing shape, to stay high-precision."""
    node = call
    for _ in range(5):
        p = node.parent
        if p is None:
            return False
        if p.type in ("if_expression", "while_expression"):
            cond = p.child_by_field_name("condition")
            return cond is not None and cond.id == node.id
        if p.type == "binary_expression":
            return any(c.type in _CMP_OPS for c in p.children)
        if p.type in ("parenthesized_expression", "unary_expression", "reference_expression", "try_expression"):
            node = p
            continue
        return False
    return False


def _rust_check_then_act(func: Node, rel: str) -> list[Finding]:
    """B2: an `if` whose condition checks a self.-rooted collection and whose body
    mutates the same one - a check-then-act (TOCTOU) window."""
    findings: list[Finding] = []
    for n in _walk(func):
        if n.type != "if_expression":
            continue
        checked = _rust_receivers_by_method(n.child_by_field_name("condition"), _CHECK_METHODS)
        mutated = _rust_receivers_by_method(n.child_by_field_name("consequence"), _MUTATE_METHODS)
        mutated |= _rust_receivers_by_method(n.child_by_field_name("alternative"), _MUTATE_METHODS)
        for recv in sorted(checked & mutated):
            findings.append(_mk("check_then_act", recv, REVIEW, rel, n))
    return findings


def _scan_rust(root: Node, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    for n in _walk(root):
        # unsafe impl Send/Sync for T : the Send/Sync guarantee is hand-asserted.
        if n.type == "impl_item" and any(c.type == "unsafe" for c in n.children):
            trait = _text(n.child_by_field_name("trait"))
            if trait in ("Send", "Sync"):
                target = _text(n.child_by_field_name("type"))
                findings.append(_mk(f"unsafe_impl_{trait.lower()}", target, EXPOSED, rel, n))
            continue
        # static mut NAME : global mutable state with no compiler guard.
        if n.type == "static_item" and any(c.type == "mutable_specifier" for c in n.children):
            findings.append(_mk("static_mut", _text(n.child_by_field_name("name")), EXPOSED, rel, n))
            continue
        # The remaining shapes (Relaxed ordering, B1, B2) are not production concurrency
        # surface in test files.
        if _is_test_file(rel):
            continue
        # C1: a Relaxed atomic op. A Relaxed LOAD whose value gates control flow is a
        # review-level missing-acquire (relaxed_guard); every other Relaxed use is the
        # low-precision candidate tier (Relaxed is correct for counters/stats).
        if n.type == "call_expression":
            mr = _rust_method_receiver(n)
            if mr is not None and _call_uses_relaxed(n):
                if mr[0] == "load" and _result_feeds_branch(n):
                    findings.append(_mk("relaxed_guard", mr[1], REVIEW, rel, n))
                else:
                    findings.append(_mk("relaxed_ordering", mr[1], CANDIDATE, rel, n))
        # B1 / B2: per-function race shapes on shared instance state.
        elif n.type == "function_item":
            findings.extend(_rust_nonatomic_rmw(n, rel))
            findings.extend(_rust_check_then_act(n, rel))

    return findings


def _is_test_file(rel: str) -> bool:
    low = rel.lower()
    return low.endswith(("tests.rs", "test.rs")) or "/tests/" in low or "/test/" in low


# --------------------------------------------------------------------------
# Python scanner (free-threading surface). Python has no compiler thread-safety
# guarantee, so the surface is shared mutable state that cp314t makes concurrent,
# not a hand-override. The module-scoped heuristic is conservative and disclosed:
# a module container is only surfaced when the file itself uses a concurrency
# primitive, and it is downgraded to REVIEW when any lock is present in the file.
# --------------------------------------------------------------------------

# RHS node types / constructors that bind a mutable container.
_PY_MUTABLE_LITERALS = frozenset({
    "dictionary", "list", "set",
    "dictionary_comprehension", "list_comprehension", "set_comprehension",
})
_PY_MUTABLE_CTORS = frozenset({"dict", "list", "set", "defaultdict", "OrderedDict", "Counter", "deque"})

# Modules / names whose presence means the file runs work concurrently.
_PY_CONCURRENCY_MODULES = frozenset({"threading", "multiprocessing", "concurrent"})
_PY_CONCURRENCY_CALLS = frozenset({"Thread", "Process", "ThreadPoolExecutor", "ProcessPoolExecutor"})
# Names whose presence means some synchronization exists in the file.
_PY_LOCK_NAMES = frozenset({"Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition", "Barrier"})


def _py_rhs_is_mutable(rhs: Node | None) -> bool:
    if rhs is None:
        return False
    if rhs.type in _PY_MUTABLE_LITERALS:
        return True
    if rhs.type == "call":
        return _text(rhs.child_by_field_name("function")) in _PY_MUTABLE_CTORS
    return False


def _py_imported_modules(root: Node) -> set[str]:
    """Top-level module names the file imports (import X / from X import ...)."""
    mods: set[str] = set()
    for n in root.children:
        if n.type == "import_statement":
            for c in n.children:
                if c.type in ("dotted_name", "aliased_import"):
                    mods.add(_text(c).split(".")[0].split(" ")[0])
        elif n.type == "import_from_statement":
            mod = n.child_by_field_name("module_name")
            if mod is not None:
                mods.add(_text(mod).split(".")[0])
    return mods


def _py_uses_concurrency(root: Node, nodes: list[Node]) -> bool:
    if _py_imported_modules(root) & _PY_CONCURRENCY_MODULES:
        return True
    # A direct Thread(...) / ThreadPoolExecutor(...) call, however imported.
    for n in nodes:
        if n.type == "call":
            fn = n.child_by_field_name("function")
            name = _text(fn).rsplit(".", 1)[-1] if fn is not None else ""
            if name in _PY_CONCURRENCY_CALLS:
                return True
    return False


def _py_has_lock(nodes: list[Node]) -> bool:
    for n in nodes:
        if n.type == "identifier" and _text(n) in _PY_LOCK_NAMES:
            return True
        # `x.acquire()` : a lock is being taken somewhere in the file.
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn is not None and fn.type == "attribute" and _text(fn.child_by_field_name("attribute")) == "acquire":
                return True
    return False


def _scan_python(root: Node, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    nodes = _walk(root)

    # Mutable default arguments: shared across calls, always decidable, race under
    # free-threading. A REVIEW-level footgun regardless of concurrency imports.
    for n in nodes:
        if n.type in ("default_parameter", "typed_default_parameter") and _py_rhs_is_mutable(n.child_by_field_name("value")):
            findings.append(_mk("mutable_default_arg", _text(n.child_by_field_name("name")), REVIEW, rel, n))

    # Module-level mutable containers, only when the file actually runs concurrently.
    if not _py_uses_concurrency(root, nodes):
        return findings
    guarded = _py_has_lock(nodes)
    for stmt in root.children:
        assign = stmt.children[0] if (stmt.type == "expression_statement" and stmt.children) else stmt
        if assign.type != "assignment":
            continue
        left = assign.child_by_field_name("left")
        if left is None or left.type != "identifier":
            continue
        if _py_rhs_is_mutable(assign.child_by_field_name("right")):
            if guarded:
                findings.append(_mk("possibly_unguarded_shared_state", _text(left), REVIEW, rel, assign))
            else:
                findings.append(_mk("unguarded_shared_state", _text(left), EXPOSED, rel, assign))

    return findings


_SCANNERS: dict[str, Callable[[Node, str], list[Finding]]] = {
    "rust": _scan_rust,
    "python": _scan_python,
}


def _na(lang: str) -> SurfaceResult:
    return {
        "verdict": "n/a",
        "value": "n/a",
        "band": "n/a",
        "counts": {EXPOSED: 0, REVIEW: 0, CANDIDATE: 0},
        "findings": [],
        "bucketed": {"counts": {}, "paths": []},
        "details": f"thread-safety surface meter has no scanner for {lang} yet",
    }


def scan(repo: Path, lang: str) -> SurfaceResult:
    """The concurrency-surface distribution for a repo. Additive; a fact about the
    syntax, never a claim that a race exists (a race is a ThreadSanitizer job)."""
    if lang not in _SCANNERS:
        return _na(lang)
    scanner = _SCANNERS[lang]
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=_IGNORE)
    bucketed = bucketed_paths(repo, cfg["extensions"], _IGNORE)

    findings: list[Finding] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        findings.extend(scanner(parser.parse(src).root_node, rel))

    counts = {EXPOSED: 0, REVIEW: 0, CANDIDATE: 0}
    for f in findings:
        counts[f["severity"]] += 1

    if counts[EXPOSED]:
        verdict = EXPOSED
    elif counts[REVIEW]:
        verdict = REVIEW
    elif counts[CANDIDATE]:
        verdict = CANDIDATE
    else:
        verdict = CLEAN

    _order = {EXPOSED: 0, REVIEW: 1, CANDIDATE: 2}
    findings.sort(key=lambda f: (_order[f["severity"]], f["file"], f["line"]))

    return {
        "verdict": verdict,
        "value": f"{counts[EXPOSED]} exposed / {counts[REVIEW]} review / {counts[CANDIDATE]} candidate",
        "band": "n/a",
        "counts": counts,
        "findings": findings,
        "bucketed": bucketed,
        "details": (
            f"thread-safety surface: {counts[EXPOSED]} hand-overrides of the thread-safety "
            f"guarantee, {counts[REVIEW]} lower-severity footguns, {counts[CANDIDATE]} "
            f"low-precision candidate shape(s) across {len(findings)} sites"
        ),
    }
