"""
L1.18 - mutable-state ratio (the "any language" indicator) and the module-mutable /
instance-field enumeration the finite-testability meter reuses.

Split out of indicators.py to keep that module under the god-file line the meter
enforces on itself. Depends only on the shared primitives in indicators (LANG_CFG,
the parser, the boundary readers, band); it never imports back the indicator
computations, so the two modules do not form a cycle.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tree_sitter import Node

from l1_analyzer.indicators import (
    LANG_CFG,
    L1Result,
    _BODY_NODE_TYPES,
    _get_parser,
    _read_source_bytes,
    _with_skipped,
    band,
)

# ---------------------------------------------------------------------------
# L1.18 Mutable state ratio (the key "any language" indicator, using tree-sitter)
# Simplified reference implementation. Full production version lives in the
# Paper A replication package with all the bound-literal logic etc.
# ---------------------------------------------------------------------------

# Container literals/constructors whose empty form seeds an accumulator.
# Constructors of MUTABLE containers whose empty form is an accumulator seed.
# frozenset/tuple/bytes are immutable and cannot accumulate, so they are excluded:
# `X = frozenset()` is a constant, not mutable state.
_PY_CONTAINER_CTORS = frozenset({
    "dict", "list", "set", "defaultdict", "OrderedDict", "deque", "Counter", "bytearray",
})


def _py_is_type_expression(n: Node) -> bool:
    """A pure type expression: a bare name, a dotted name, a subscript
    (Iterable[X]), or a `|` union of those. No call, no container literal."""
    if n.type in ("identifier", "attribute", "subscript"):
        return True
    if n.type == "binary_operator":
        op = n.child_by_field_name("operator")
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        return (op is not None and op.text == b"|" and left is not None and right is not None
                and _py_is_type_expression(left) and _py_is_type_expression(right))
    return False


def _py_is_type_alias(node: Node, rhs: Node | None) -> bool:
    annot = node.child_by_field_name("type")
    if annot is not None and annot.text.decode("utf8", errors="ignore").split("[", 1)[0].strip() == "TypeAlias":
        return True
    return rhs is not None and _py_is_type_expression(rhs)


def _py_is_empty_container(rhs: Node | None) -> bool:
    """An accumulator seed: {}, [], or set()/dict()/list()/... with no elements."""
    if rhs is None:
        return False
    if rhs.type in ("dictionary", "list"):
        return not rhs.named_children
    if rhs.type == "call":
        fn = rhs.child_by_field_name("function")
        args = rhs.child_by_field_name("arguments")
        if fn is not None and fn.type == "identifier" and fn.text.decode("utf8", errors="ignore") in _PY_CONTAINER_CTORS:
            return args is None or not args.named_children
    return False


def _module_mutables_python(candidates: list[Node], this_idents: set[str]) -> set[str]:
    """Field-based module-global detection for Python. The binding name is read
    from the assignment's `left` field, so string literals and annotation tails
    are never scanned as source. Type aliases are skipped. An uppercase name is a
    constant by convention, unless it is seeded with an empty container, which is
    an accumulator (e.g. `CACHE = {}`), the pattern the indicator exists to catch."""
    mutables: set[str] = set()
    for node in candidates:
        left = node.child_by_field_name("left")
        if left is None or left.type != "identifier":  # skip subscripts, tuples, attributes
            continue
        name = left.text.decode("utf8", errors="ignore")
        # Dunders (__all__, __version__, ...) are module metadata, not state.
        if name in this_idents or (name.startswith("__") and name.endswith("__")):
            continue
        rhs = node.child_by_field_name("right")
        if _py_is_type_alias(node, rhs):
            continue
        if name.isupper():
            if _py_is_empty_container(rhs):
                mutables.add(name)
        else:
            mutables.add(name)
    return mutables


def _module_mutables_by_specifier(candidates: list[Node]) -> set[str]:
    """Rust-style: a top-level binding is mutable state iff its declaration carries
    a `mut` specifier (`static mut counter: i32 = 0`). The name is the declaration's
    `identifier` child, read structurally so the type token is never mistaken for
    the name. `const` and plain `static` are immutable and excluded."""
    mutables: set[str] = set()
    for node in candidates:
        if not any(c.type == "mutable_specifier" for c in node.children):
            continue
        name = next((c.text.decode("utf8", errors="ignore") for c in node.children if c.type == "identifier"), None)
        if name:
            mutables.add(name)
    return mutables


def _find_module_mutable_names(root: Node, cfg: dict[str, Any]) -> set[str]:
    """Detect top-level names that are likely mutable module state.

    Candidate assignments are collected structurally; for Python the binding name
    is read from the assignment's fields, never by splitting the node's text
    (which harvested annotation tails and identifiers out of string literals).
    Languages not yet migrated keep the legacy text heuristic."""
    assign_types = cfg["module_level_assign"]
    this_idents = cfg["this_ident"]

    # Top-level assignments, allowing one wrapper: Python nests `x = 0` inside an
    # `expression_statement`, so the `assignment` node is a child of a root child.
    candidates: list[Node] = []
    for node in root.children:
        if node.type in assign_types:
            candidates.append(node)
        else:
            candidates.extend(c for c in node.children if c.type in assign_types)

    if cfg.get("field_based_globals"):
        return _module_mutables_python(candidates, this_idents)

    if cfg.get("mutable_specifier_globals"):
        return _module_mutables_by_specifier(candidates)

    # Legacy text heuristic (unchanged), for languages not yet migrated.
    const_keywords = cfg.get("const_keywords", ("const ", "final ", "readonly ", "let ", "val "))
    mutables: set[str] = set()
    for node in candidates:
        text = node.text.decode("utf8", errors="ignore")
        for line in text.splitlines():
            if "=" in line and not any(kw in line.lower() for kw in const_keywords):
                parts = line.split("=")[0].strip().split()
                if parts:
                    name = parts[-1].strip("()[]:,")
                    if name and name not in this_idents and not name.isupper():
                        mutables.add(name)
    return mutables

def _count_mutable_refs(body: Node, cfg: dict[str, Any], module_mutables: set[str], receiver_names: set[str]) -> int:
    """Count references inside a function body to external mutable state.

    Handles, per-language via cfg: receiver/member access (self./this./<go
    receiver>.field), Ruby @instance / $global variables, module-level mutable
    globals referenced by bare identifier, and Rust/C raw patterns.

    Simplified reference implementation; the production version (Paper A) adds
    bound-literal exclusion and full per-language field resolution.
    """
    count = 0
    member_type = cfg["member_access"]
    instance_field_types = cfg.get("instance_field_types", ())
    raw_mut_patterns = cfg.get("raw_mut_patterns", ())

    def walk(n: Node):
        nonlocal count
        if n.type == member_type and receiver_names:
            text = n.text.decode("utf8", errors="ignore")
            if any(text.startswith(r + ".") for r in receiver_names):
                count += 1
        if n.type in instance_field_types:
            count += 1
        if n.type == "identifier" and n.text.decode("utf8", errors="ignore") in module_mutables:
            count += 1
        # Raw-text mutable patterns are language-scoped (Rust only). Running them
        # for every language flagged any source that merely contained the strings.
        if raw_mut_patterns:
            txt = n.text.decode("utf8", errors="ignore") if n.text else ""
            if any(p in txt for p in raw_mut_patterns):
                count += 1
        for c in n.children:
            walk(c)
    walk(body)
    return count

def _receiver_names(func_node: Node, cfg: dict[str, Any]) -> set[str]:
    """Names that denote the enclosing instance for this function. For self/this
    languages it is the fixed keyword set; for Go it is the method receiver
    identifier, parsed from the receiver parameter list."""
    fixed = set(cfg["this_ident"])
    if fixed:
        return fixed
    names: set[str] = set()
    if func_node.type == "method_declaration":  # Go: `func (r *Foo) Bar(...)`
        for child in func_node.children:
            if child.type == "parameter_list":
                for decl in child.children:
                    if decl.type == "parameter_declaration":
                        for part in decl.children:
                            if part.type == "identifier":
                                names.add(part.text.decode("utf8", errors="ignore"))
                break  # first parameter_list is the receiver
    return names

_BOUNDARY_MARKER = "honest: boundary"


def _is_declared_boundary(func_node: Node) -> bool:
    """True when a function carries an explicit boundary declaration: a comment
    containing `honest: boundary` (`# honest: boundary`, `// honest: boundary`).

    A declared boundary is where I/O legitimately touches external state, so L1.18
    excludes it from the ratio entirely, numerator and denominator. Recognition is
    by DECLARATION, never by guessing at function names or I/O calls: an unmarked
    function is never excluded, so no repository's number moves unless its authors
    opt in with the marker (the meter honoring the gate's declaration, per the
    finite-testability asymmetry)."""
    def find(n: Node) -> bool:
        if "comment" in n.type and n.text and _BOUNDARY_MARKER in n.text.decode("utf8", errors="ignore").lower():
            return True
        return any(find(c) for c in n.children)

    return find(func_node)


def _count_file_functions(root: Node, cfg: dict[str, Any], module_mutables: set[str]) -> tuple[int, int]:
    """Pure per-file walk: return (total functions, functions touching external
    mutable state). Module-level (not a loop closure) so it binds no caller state.
    Functions declared as I/O boundaries are excluded from both counts."""
    totals = [0, 0]  # [total, mutable]

    def find_functions(n: Node):
        if n.type in cfg["function_types"] and not _is_declared_boundary(n):
            totals[0] += 1
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers) > 0:
                    totals[1] += 1
        for c in n.children:
            find_functions(c)

    find_functions(root)
    return totals[0], totals[1]

def analyze_mutable_state(repo: Path, lang: str) -> L1Result:
    """L1.18: percentage of functions that reference external mutable state."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    total_funcs = 0
    mutable_funcs = 0
    for _path, src in files:
        root = parser.parse(src).root_node
        module_mutables = _find_module_mutable_names(root, cfg)
        file_total, file_mutable = _count_file_functions(root, cfg, module_mutables)
        total_funcs += file_total
        mutable_funcs += file_mutable

    ratio = (mutable_funcs / total_funcs * 100) if total_funcs > 0 else 0.0
    return {
        "value": round(ratio, 1),
        "band": band(ratio, 15, 40, higher_is_better=False),
        "details": _with_skipped(f"{mutable_funcs}/{total_funcs} functions reference external mutable state ({lang})", skipped),
    }


def _file_mutable_names(root: Node, cfg: dict[str, Any], module_mutables: set[str]) -> list[str]:
    """Names of the functions in one file that L1.18 counts as touching external
    mutable state. Same predicate as _count_file_functions (module-level so it
    binds no caller state), only it keeps the names instead of a tally."""
    names: list[str] = []

    def find(n: Node) -> None:
        if n.type in cfg["function_types"] and not _is_declared_boundary(n):
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers) > 0:
                    nm = n.child_by_field_name("name")
                    if nm is not None and nm.text:
                        names.append(nm.text.decode("utf8", errors="ignore"))
        for c in n.children:
            find(c)

    find(root)
    return names


def mutable_function_names(repo: Path, lang: str) -> list[str]:
    """L1.18's culprits by name: functions that reference external mutable state.

    Additive, read-only. A name appears here iff analyze_mutable_state counts that
    function (identical _count_mutable_refs predicate), so this never moves L1.18's
    value/band or the pre-registered number. Exists so the behavioural suite can
    assert *which* function is flagged instead of fabricating the answer."""
    if lang not in LANG_CFG:
        return []
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))
    names: list[str] = []
    for _path, src in files:
        root = parser.parse(src).root_node
        module_mutables = _find_module_mutable_names(root, cfg)
        names.extend(_file_mutable_names(root, cfg, module_mutables))
    return names


def module_mutable_names(repo: Path, lang: str) -> set[str]:
    """The module-level bindings L1.18 treats as mutable state. A binding is a
    *bound literal* (a constant, a frozen dispatch table) exactly when it is
    absent from this set. Additive, read-only; never affects L1.18's number."""
    if lang not in LANG_CFG:
        return set()
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))
    out: set[str] = set()
    for _path, src in files:
        root = parser.parse(src).root_node
        out |= _find_module_mutable_names(root, cfg)
    return out
