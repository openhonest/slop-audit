"""
L1.18b - finite-testability classifier (gated, additive refinement of L1.18).

Implements the shared predicate in
~/dev/honest/open-honest/honest-framework/specs/finite-testability.md:

  A piece of state is testability-neutral iff the production decisions reaching it
  partition its domain into a statically-enumerable finite set of equivalence
  classes. PARTITION-COUNT, not value-count: an int that only meets comparisons
  against constants is cheap; a value used as an unbounded lookup key is not.

Every piece of state resolves to exactly one of three verdicts, and to whether it
drives a decision, so the coverage matrix (spec section 7) can be published:

  NEUTRAL     - reaching partition is a statically-enumerable finite set (or empty)
  PROMISCUOUS - reaching partition is provably unbounded (a proven finding)
  UNRESOLVED  - reaching-set undecidable within scope; fail-closed, disclosed

Design guarantees:
  - Additive. Never touches L1.18's value/band. Runs only when the caller opts in
    (classify_state_bounds=True), off for the pre-registered experiments.
  - Analysis scope is the class or module, not the function (spec section 4):
    instance state is analysed across all methods of its class.
  - Returns are output, not promiscuity. Fail-close (UNRESOLVED) only on a value
    passed to an unbounded call target or reflective/dynamic access.
  - Python only in this prototype. Other languages return n/a rather than guess.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from l1_analyzer.indicators import (
    LANG_CFG,
    _find_module_mutable_names,
    _get_parser,
    _read_source_bytes,
)

NEUTRAL = "neutral"
PROMISCUOUS = "promiscuous"
UNRESOLVED = "unresolved"

# Per-reference categories (internal): how one use of a state value is consumed.
_WRITE = "write"          # target of an assignment / mutating method: not a decision
_OUTPUT = "output"        # returned or otherwise handed to the caller: compositional
_FINITE = "finite"        # reaches a decision whose reaching partition is enumerable
_UNBOUNDED = "unbounded"  # reaches a decision whose reaching partition is provably unbounded
_UNDECIDABLE = "undecidable"  # reaches a context whose reaching-set cannot be decided

_MUTATING_METHODS = frozenset({
    "append", "add", "update", "extend", "insert", "pop", "remove", "discard",
    "clear", "setdefault", "popitem", "sort", "appendleft",
})
# Builtins that read a bounded feature of their argument (the value flows onward).
_BOUNDED_BUILTINS = frozenset({"len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"})
# Builtins that consume a value as an effect/assertion, not a partitioning decision.
_EFFECT_CALLS = frozenset({"print", "repr", "str", "format", "log", "logging"})
_LITERAL_TYPES = frozenset({"string", "integer", "float", "true", "false", "none", "concatenated_string"})


def _text(node: Any) -> str:
    return node.text.decode("utf8", errors="ignore") if node is not None and node.text else ""


def _field(node: Any, name: str) -> Any:
    return node.child_by_field_name(name)


def _same(a: Any, b: Any) -> bool:
    """Node identity by id. child_by_field_name returns a fresh wrapper each call,
    so `is` is unreliable; compare the stable node id instead."""
    return a is not None and b is not None and a.id == b.id


# --------------------------------------------------------------------------
# Closed-set detection: a name bound to a frozenset / set-or-tuple of literals.
# --------------------------------------------------------------------------

def _rhs_is_closed_set(rhs: Any) -> bool:
    if rhs is None:
        return False
    if rhs.type in ("set", "tuple", "list"):
        return all(c.type in _LITERAL_TYPES for c in rhs.named_children)
    if rhs.type == "call":
        fn = _field(rhs, "function")
        return _text(fn) in ("frozenset", "set")
    return False


def _collect_closed_sets(root: Any) -> set[str]:
    """Names (bare) bound anywhere to a closed set of literals: MODES = frozenset(...),
    TABLE = {'a', 'b'}. Both `NAME` and `self.NAME`/`Cls.NAME` reference them."""
    names: set[str] = set()

    def walk(n: Any) -> None:
        if n.type == "assignment":
            left, rhs = _field(n, "left"), _field(n, "right")
            if left is not None and _rhs_is_closed_set(rhs):
                if left.type == "identifier":
                    names.add(_text(left))
                elif left.type == "attribute":
                    attr = _field(left, "attribute")
                    if attr is not None:
                        names.add(_text(attr))
        for c in n.children:
            walk(c)

    walk(root)
    return names


def _is_closed_set(node: Any, closed_sets: set[str]) -> bool:
    if node is None:
        return False
    if _rhs_is_closed_set(node):
        return True
    if node.type == "identifier":
        return _text(node) in closed_sets
    if node.type == "attribute":
        attr = _field(node, "attribute")
        return attr is not None and _text(attr) in closed_sets
    return False


def _is_unbounded_value(node: Any) -> bool:
    """A value used as a lookup key / index. Literals are bounded; anything else
    (a parameter, a variable) ranges over an unbounded domain."""
    return node is not None and node.type not in _LITERAL_TYPES


# --------------------------------------------------------------------------
# Membership helpers.
# --------------------------------------------------------------------------

def _membership_operands(cmp_node: Any) -> tuple[Any, Any] | None:
    """(left, right) for an `in` / `not in` comparison, else None."""
    if cmp_node.type != "comparison_operator":
        return None
    if not any(c.type == "in" for c in cmp_node.children):
        return None
    named = [c for c in cmp_node.children if c.is_named]
    if len(named) < 2:
        return None
    return named[0], named[-1]


# --------------------------------------------------------------------------
# Per-reference categorisation.
# --------------------------------------------------------------------------

def _is_write_target(ref: Any, parent: Any) -> bool:
    if parent.type in ("assignment", "augmented_assignment") and _same(_field(parent, "left"), ref):
        return True
    # S[k] = v  -> ref (S) is the value of a subscript that is the assignment target
    if parent.type == "subscript" and _same(_field(parent, "value"), ref):
        gp = parent.parent
        if gp is not None and gp.type in ("assignment", "augmented_assignment") and _same(_field(gp, "left"), parent):
            return True
    return False


def _categorize(ref: Any, closed_sets: set[str]) -> str:
    """How this single reference to a state value is consumed."""
    parent = ref.parent
    if parent is None:
        return _OUTPUT

    if _is_write_target(ref, parent):
        return _WRITE

    # S(...) : the state is the call target -> dynamic dispatch, unbounded callee.
    if parent.type == "call" and _same(_field(parent, "function"), ref):
        return _UNDECIDABLE

    # S[x] read : indexed by x. Unbounded key -> unbounded partition.
    if parent.type == "subscript" and _same(_field(parent, "value"), ref):
        idx = _field(parent, "subscript")
        return _UNBOUNDED if _is_unbounded_value(idx) else _FINITE

    # S.attr : mutating method -> write; otherwise the derived value flows onward.
    if parent.type == "attribute" and _same(_field(parent, "object"), ref):
        attr = _text(_field(parent, "attribute"))
        gp = parent.parent
        if attr in _MUTATING_METHODS and gp is not None and gp.type == "call" and _same(_field(gp, "function"), parent):
            return _WRITE
        return _flow(parent, closed_sets)

    # f(..., S, ...) : argument to a call.
    if parent.type == "argument_list":
        call = parent.parent
        fname = _text(_field(call, "function")) if call is not None and call.type == "call" else ""
        if fname in _BOUNDED_BUILTINS:
            return _flow(call, closed_sets)     # bounded projection: value flows onward
        if fname in _EFFECT_CALLS:
            return _OUTPUT                       # consumed as an effect, not a partition
        return _UNDECIDABLE                      # unknown callee: reaching-set undecidable

    return _flow(ref, closed_sets)


def _flow(node: Any, closed_sets: set[str]) -> str:
    """Categorise how a value derived from the state (node) reaches a decision."""
    parent = node.parent
    if parent is None:
        return _OUTPUT
    if parent.type == "return_statement":
        return _OUTPUT
    if parent.type in ("parenthesized_expression", "not_operator", "boolean_operator"):
        return _flow(parent, closed_sets)
    if parent.type == "comparison_operator":
        mem = _membership_operands(parent)
        if mem is not None:
            left, right = mem
            if _same(node, right):         # x in S : S is the container, keyed by x
                return _UNBOUNDED if _is_unbounded_value(left) else _FINITE
            return _FINITE if _is_closed_set(right, closed_sets) else _UNBOUNDED  # S in Y
        return _FINITE                     # S <cmp> other : two classes
    if parent.type in ("if_statement", "while_statement") and _same(_field(parent, "condition"), node):
        return _FINITE                     # truthiness: two classes
    if parent.type == "elif_clause" and _same(_field(parent, "condition"), node):
        return _FINITE
    if parent.type == "argument_list":
        call = parent.parent
        fname = _text(_field(call, "function")) if call is not None and call.type == "call" else ""
        if fname in _BOUNDED_BUILTINS:
            return _flow(call, closed_sets)
        if fname in _EFFECT_CALLS:
            return _OUTPUT
        return _UNDECIDABLE
    if parent.type == "subscript" and _same(_field(parent, "value"), node):
        idx = _field(parent, "subscript")
        return _UNBOUNDED if _is_unbounded_value(idx) else _FINITE
    return _OUTPUT


def _verdict(categories: list[str]) -> tuple[str, bool]:
    """Combine per-reference categories into (verdict, drives_decision)."""
    if _UNDECIDABLE in categories:
        return UNRESOLVED, True
    if _UNBOUNDED in categories:
        return PROMISCUOUS, True
    if _FINITE in categories:
        return NEUTRAL, True
    return NEUTRAL, False   # observe-only or output-only: empty reaching-set


# --------------------------------------------------------------------------
# State enumeration and file analysis.
# --------------------------------------------------------------------------

def _instance_state(class_node: Any) -> set[str]:
    """`self.<attr>` names assigned anywhere in the class."""
    attrs: set[str] = set()

    def walk(n: Any) -> None:
        if n.type in ("assignment", "augmented_assignment"):
            left = _field(n, "left")
            if left is not None and left.type == "attribute":
                obj = _field(left, "object")
                if obj is not None and _text(obj) == "self":
                    attrs.add(_text(_field(left, "attribute")))
        for c in n.children:
            walk(c)

    walk(class_node)
    return attrs


def _refs(scope: Any, predicate: Any) -> list[Any]:
    out: list[Any] = []

    def walk(n: Any) -> None:
        if predicate(n):
            out.append(n)
        for c in n.children:
            walk(c)

    walk(scope)
    return out


def _finding(key: str, refs: list[Any], rel: str, closed_sets: set[str]) -> dict[str, Any]:
    cats = [_categorize(r, closed_sets) for r in refs]
    verdict, drives = _verdict(cats)
    line = min((r.start_point[0] + 1 for r in refs), default=1)
    return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel, "line": line}


def _analyze_file(root: Any, rel: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    closed_sets = _collect_closed_sets(root)
    module_mutables = _find_module_mutable_names(root, cfg)
    findings: list[dict[str, Any]] = []

    for name in module_mutables:
        refs = _refs(root, lambda n, nm=name: n.type == "identifier" and _text(n) == nm)
        if refs:
            findings.append(_finding(name, refs, rel, closed_sets))

    for cls in _refs(root, lambda n: n.type == "class_definition"):
        for attr in _instance_state(cls):
            key = f"self.{attr}"
            refs = _refs(cls, lambda n, k=key: n.type == "attribute" and _text(n) == k)
            if refs:
                findings.append(_finding(key, refs, rel, closed_sets))

    return findings


def _na(lang: str) -> dict[str, Any]:
    return {
        "verdict": "n/a", "value": "n/a", "band": "n/a",
        "counts": {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0},
        "coverage": {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)},
        "resolvable_fraction": "n/a",
        "findings": [],
        "details": f"finite-testability classifier not implemented for {lang} yet (python only)",
    }


def classify(repo: Path, lang: str) -> dict[str, Any]:
    """L1.18b: the finite-testability verdict distribution. Additive; never
    consulted by L1.18 itself."""
    if lang != "python":
        return _na(lang)
    cfg = LANG_CFG["python"]
    parser = _get_parser("python")
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    findings: list[dict[str, Any]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        findings.extend(_analyze_file(parser.parse(src).root_node, rel, cfg))

    counts = {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0}
    coverage = {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)}
    for f in findings:
        counts[f["verdict"]] += 1
        coverage[f["verdict"]]["drives_decision" if f["drives_decision"] else "observe_only"] += 1

    total = sum(counts.values())
    if counts[PROMISCUOUS]:
        verdict = PROMISCUOUS
    elif counts[UNRESOLVED]:
        verdict = UNRESOLVED
    elif total:
        verdict = NEUTRAL
    else:
        verdict = "n/a"
    resolvable = round((counts[NEUTRAL] + counts[PROMISCUOUS]) / total, 3) if total else 1.0

    _order = {PROMISCUOUS: 0, UNRESOLVED: 1, NEUTRAL: 2}
    findings.sort(key=lambda f: (_order[f["verdict"]], not f["drives_decision"], f["file"], f["line"]))

    return {
        "verdict": verdict,
        "value": f"{counts[NEUTRAL]} neutral / {counts[PROMISCUOUS]} promiscuous / {counts[UNRESOLVED]} unresolved",
        "band": "n/a",
        "counts": counts,
        "coverage": coverage,
        "resolvable_fraction": resolvable,
        "findings": findings,
        "details": (
            f"finite-testability: {counts[NEUTRAL]} neutral, {counts[PROMISCUOUS]} promiscuous, "
            f"{counts[UNRESOLVED]} unresolved across {total} pieces of state; "
            f"resolvable fraction {resolvable}"
        ),
    }
