"""
L1.18b — state-bounds classifier (gated, additive refinement of L1.18).

L1.18 counts functions that read external mutable state. It cannot tell whether
that state is *bounded* (a bool, an enum -> finite behavior domain, exhaustively
testable) or *unbounded* (a growing dict/list, a str, an arbitrary-precision int
-> infinite behavior domain, per paper-c-amendment-l118-rationale.md: the
State(S) term is unbounded). This module makes that call so the "how many test
cases to fully cover it" answer can distinguish "impractically large but finite"
from "mathematically infinite".

Design guarantees:
  - This is ADDITIVE. It never touches L1.18's value/band. It runs only when the
    caller opts in (classify_state_bounds=True), which is off for the
    pre-registered experiments and on for the CLI and web tool.
  - Soundness is one-directional and conservative. We report UNBOUNDED only when
    we can point at an unbounded type/literal; BOUNDED only when every signal is
    bounded; otherwise UNDETERMINED. A perfect classifier is impossible (Rice's
    theorem), so "undetermined" is a first-class, honestly-labeled outcome.
  - Python only in this prototype. Other languages return n/a rather than guess.

Two signals are combined, per the two levels of the analysis:
  1. The *type* of the state (its annotation or assignment RHS).
  2. The *observed projection* — how the function reads it. A function that only
     asks `len(x)`, `k in x`, or `if x:` depends on a bounded feature of an
     otherwise-unbounded object, so that read is bounded. (Conservative v1: only
     these three unambiguous projections downgrade a read.)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from l1_analyzer.indicators import (
    _BODY_NODE_TYPES,
    _count_mutable_refs,
    _find_module_mutable_names,
    _get_parser,
    _read_source_bytes,
    _receiver_names,
    LANG_CFG,
)

UNBOUNDED = "unbounded"
BOUNDED = "bounded"
UNDETERMINED = "undetermined"

# Annotations / builtins whose value set is unbounded (infinite behavior domain).
_UNBOUNDED_TYPES = frozenset({
    "int", "str", "bytes", "bytearray", "list", "dict", "set", "tuple", "frozenset",
    "List", "Dict", "Set", "Tuple", "FrozenSet", "Sequence", "Mapping", "Iterable", "Any", "object",
})
# Annotations / builtins whose value set is finite (bounded behavior domain).
_BOUNDED_TYPES = frozenset({"bool", "float", "complex", "None", "NoneType"})
# Constructors that build an unbounded container/value.
_UNBOUNDED_CTORS = frozenset({
    "dict", "list", "set", "tuple", "frozenset", "defaultdict", "OrderedDict",
    "deque", "Counter", "bytearray", "bytes", "str",
})

_INT_RE = re.compile(r"-?\d[\d_]*$")
_FLOAT_RE = re.compile(r"-?\d[\d_]*\.\d*$|-?\.\d+$")


def _bucket_from_annotation(text: str) -> str:
    base = text.strip().split("[", 1)[0].strip()
    if base == "Literal":
        return BOUNDED
    if base in ("Optional", "Final", "Annotated", "Union"):
        # Bounded only if every argument inside the brackets is bounded.
        inner = text[text.find("[") + 1: text.rfind("]")] if "[" in text else ""
        args = [a.strip() for a in inner.split(",") if a.strip()]
        buckets = {_bucket_from_annotation(a) for a in args}
        if UNBOUNDED in buckets:
            return UNBOUNDED
        if buckets and buckets <= {BOUNDED, "None", "NoneType"}:
            return BOUNDED
        return UNDETERMINED
    if base in _BOUNDED_TYPES:
        return BOUNDED
    if base in _UNBOUNDED_TYPES:
        return UNBOUNDED
    return UNDETERMINED


def _bucket_from_rhs(text: str) -> str:
    text = text.strip()
    if text in ("True", "False"):
        return BOUNDED
    if text.startswith(("{", "[")):
        return UNBOUNDED  # dict/set/list display
    if text.startswith(("'", '"', "f'", 'f"', "b'", 'b"', "r'", 'r"')):
        return UNBOUNDED  # str/bytes literal
    ctor = text.split("(", 1)[0].strip()
    if ctor in _UNBOUNDED_CTORS:
        return UNBOUNDED
    if ctor in ("float", "complex"):
        return BOUNDED
    if ctor == "int":
        return UNBOUNDED
    if text in ("None",):
        return BOUNDED
    if _INT_RE.match(text):
        return UNBOUNDED  # Python ints are arbitrary precision
    if _FLOAT_RE.match(text):
        return BOUNDED
    return UNDETERMINED


def _combine(buckets: set[str]) -> str:
    """Honest lattice: demonstrate UNBOUNDED > fall back to UNDETERMINED > only
    call BOUNDED when every signal is bounded."""
    if not buckets:
        return UNDETERMINED
    if UNBOUNDED in buckets:
        return UNBOUNDED
    if UNDETERMINED in buckets:
        return UNDETERMINED
    return BOUNDED


def _decode(node: Any) -> str:
    return node.text.decode("utf8", errors="ignore") if node.text else ""


def _state_types(root: Any, module_mutables: set[str]) -> dict[str, str]:
    """Map each state key ("self.<attr>" or a module name) to its bucket, from
    annotations and assignment right-hand sides across the file."""
    seen: dict[str, set[str]] = {}

    def note(key: str, bucket: str) -> None:
        seen.setdefault(key, set()).add(bucket)

    def walk(n: Any) -> None:
        if n.type == "assignment":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            annot = n.child_by_field_name("type")
            if left is not None:
                lt = _decode(left)
                key = None
                if lt.startswith("self."):
                    key = "self." + lt[len("self."):].split(".", 1)[0].split("[", 1)[0].strip()
                elif lt in module_mutables:
                    key = lt
                if key is not None:
                    if annot is not None:
                        note(key, _bucket_from_annotation(_decode(annot)))
                    elif right is not None:
                        note(key, _bucket_from_rhs(_decode(right)))
        for c in n.children:
            walk(c)

    walk(root)
    return {key: _combine(buckets) for key, buckets in seen.items()}


def _is_bounded_projection(node: Any) -> bool:
    """True when this read of the state observes only a bounded feature of it:
    len(x), membership (k in x), or truthiness (if x:/while x:)."""
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "argument_list" and parent.parent is not None and parent.parent.type == "call":
        fn = parent.parent.child_by_field_name("function")
        if fn is not None and _decode(fn) == "len":
            return True
    if parent.type == "comparison_operator" and any(c.type == "in" for c in parent.children):
        return True
    if parent.type in ("if_statement", "while_statement") and parent.child_by_field_name("condition") is node:
        return True
    return False


def _function_reads(body: Any, module_mutables: set[str]) -> list[tuple[str, bool]]:
    """Every read of external mutable state in a function body, as
    (state_key, is_bounded_projection)."""
    reads: list[tuple[str, bool]] = []

    def walk(n: Any) -> None:
        key = None
        if n.type == "attribute":
            text = _decode(n)
            if text.startswith("self."):
                key = "self." + text[len("self."):].split(".", 1)[0].split("[", 1)[0].strip()
        elif n.type == "identifier" and _decode(n) in module_mutables:
            key = _decode(n)
        if key is not None:
            reads.append((key, _is_bounded_projection(n)))
        for c in n.children:
            walk(c)

    walk(body)
    return reads


def _function_analysis(reads: list[tuple[str, bool]], types: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Return (verdict, {state_key: bucket}). A read seen only through a bounded
    projection is recorded as bounded regardless of the state's own type."""
    per_key: dict[str, str] = {}
    for key, bounded_projection in reads:
        bucket = BOUNDED if bounded_projection else types.get(key, UNDETERMINED)
        # If a key is read both ways, the unbounded read wins (it is demonstrated).
        if key not in per_key or bucket == UNBOUNDED:
            per_key[key] = bucket
    return _combine(set(per_key.values())), per_key


def _func_name(node: Any) -> str:
    name = node.child_by_field_name("name")
    return _decode(name) if name is not None else "<anonymous>"


def _culprits(per_key: dict[str, str], verdict: str) -> list[str]:
    """The state keys that drove the verdict (what you would fix)."""
    if verdict == "bounded":
        return sorted(per_key)
    return sorted(k for k, b in per_key.items() if b == verdict)


def classify(repo: Path, lang: str) -> dict[str, Any]:
    """L1.18b breakdown. Additive; never consulted by L1.18 itself."""
    if lang != "python":
        return {
            "value": "n/a", "band": "n/a", "verdict": "n/a",
            "unbounded_funcs": 0, "bounded_funcs": 0, "undetermined_funcs": 0,
            "details": f"state-bounds classifier not implemented for {lang} yet (python only)",
        }
    cfg = LANG_CFG["python"]
    parser = _get_parser("python")
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    counts = {UNBOUNDED: 0, BOUNDED: 0, UNDETERMINED: 0}
    findings: list[dict[str, Any]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if repo in path.parents or path == repo else str(path)
        root = parser.parse(src).root_node
        module_mutables = _find_module_mutable_names(root, cfg)
        types = _state_types(root, module_mutables)

        def walk(n: Any, rel: str = rel, types: dict[str, str] = types, module_mutables: set[str] = module_mutables) -> None:
            if n.type in cfg["function_types"]:
                body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
                if body is not None:
                    receivers = _receiver_names(n, cfg)
                    # Gate on L1.18's own predicate so the L1.18b buckets sum to
                    # exactly L1.18's mutable-function count. A function L1.18
                    # flags whose specific state this classifier cannot locate is
                    # honestly UNDETERMINED, not silently dropped.
                    if _count_mutable_refs(body, cfg, module_mutables, receivers) > 0:
                        reads = _function_reads(body, module_mutables)
                        verdict, per_key = _function_analysis(reads, types) if reads else (UNDETERMINED, {})
                        counts[verdict] += 1
                        findings.append({
                            "file": rel,
                            "line": n.start_point[0] + 1,
                            "function": _func_name(n),
                            "verdict": verdict,
                            "state": _culprits(per_key, verdict),
                        })
            for c in n.children:
                walk(c)

        walk(root)

    # Most actionable first: unbounded (real infinity), then undetermined.
    _order = {UNBOUNDED: 0, UNDETERMINED: 1, BOUNDED: 2}
    findings.sort(key=lambda f: (_order[f["verdict"]], f["file"], f["line"]))
    verdict = "infinite" if counts[UNBOUNDED] else ("undetermined" if counts[UNDETERMINED] else "finite")
    return {
        "value": f"{counts[UNBOUNDED]} unbounded / {counts[BOUNDED]} bounded / {counts[UNDETERMINED]} undetermined",
        "band": "n/a",
        "verdict": verdict,
        "unbounded_funcs": counts[UNBOUNDED],
        "bounded_funcs": counts[BOUNDED],
        "undetermined_funcs": counts[UNDETERMINED],
        "findings": findings,
        "details": (
            f"of the functions that read external mutable state: {counts[UNBOUNDED]} read unbounded "
            f"state (infinite behavior domain), {counts[BOUNDED]} read only bounded state, "
            f"{counts[UNDETERMINED]} undetermined (python, conservative v1)"
        ),
    }
