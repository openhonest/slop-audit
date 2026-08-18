"""Whether a state is settled at one value before any reach is read.

Two rules, one question. A declaration the language marks immutable AND binds to a
literal has a one-value domain. A Python name assigned once from an immutable
construction has one too, which takes following the constructor a level to see.

Split out of state_bounds.py on 2026-08-18, the third time that module crossed the
thousand-line god-file threshold this repository publishes. Splitting by responsibility
rather than shaving lines to pass the gate is the rule the methodology gives an adopter.

The declared rule replaced a `sp is LANG_SPEC["python"]` identity check in `_finding`,
which is the language conditional welded into shared code that this project objects to
elsewhere. Both rules are declared per language now, by `immutable_modifiers` and
`immutable_ctor_rule`.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer.lang_spec import _PY_MUTATING, LangSpec
from l1_analyzer.state_partition import NEUTRAL
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_named as _first_named
from l1_analyzer.ts_nodes import is_lvalue as _is_lvalue
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import is_write_target as _is_write_target
from l1_analyzer.ts_nodes import text as _text
from l1_analyzer.ts_nodes import unwrap_unary as _unwrap_unary


IMMUTABLE_WRAPPERS = frozenset({"MappingProxyType", "frozenset", "tuple", "bytes"})


def rhs_is_immutable(rhs: Node | None, immutable_ctors: set[str]) -> bool:
    if rhs is None:
        return False
    if rhs.type in ("tuple", "true", "false", "none", "integer", "float", "string", "concatenated_string"):
        return True
    if rhs.type == "call":
        fn = _text(_field(rhs, "function"))
        return fn in IMMUTABLE_WRAPPERS or fn in immutable_ctors
    return False


def returns_immutable(func_node: Node) -> bool:
    returns = _refs(func_node, lambda n: n.type == "return_statement")
    if not returns:
        return False
    for r in returns:
        val = _first_named(r)
        if not rhs_is_immutable(val, frozenset()):
            return False
    return True


def collect_immutable_ctors(root: Node) -> set[str]:
    out: set[str] = set()
    for fn in _refs(root, lambda n: n.type == "function_definition"):
        name = _field(fn, "name")
        if name is not None and returns_immutable(fn):
            out.add(_text(name))
    return out


def reaches_decision(refs: list[Node], sp: LangSpec) -> bool:
    for r in refs:
        p = r.parent
        if p is None or p.type in sp["return_types"]:
            continue
        if _is_write_target(r, p, sp):
            continue
        return True
    return False


def immutable_const_verdict(refs: list[Node], immutable_ctors: set[str], sp: LangSpec) -> tuple[str, bool] | None:
    """(NEUTRAL, drives) if the state is an immutable constant: assigned exactly once
    from an immutable construction, never mutated, never called. Else None."""
    assigns: list[Node] = []
    for r in refs:
        p = r.parent
        if p is None:
            continue
        if p.type == "assignment" and _same(_field(p, "left"), r):
            assigns.append(p)
            continue
        if p.type == "augmented_assignment" and _same(_field(p, "left"), r):
            return None  # S += ... : reassignment
        if p.type == "subscript" and _same(_field(p, "value"), r):
            gp = p.parent
            if gp is not None and gp.type in ("assignment", "augmented_assignment") and _same(_field(gp, "left"), p):
                return None  # S[k] = v : mutation
        if p.type == "call" and _same(_field(p, "function"), r):
            return None  # called: dynamic dispatch, not a constant
        if p.type == "attribute" and _same(_field(p, "object"), r):
            gp = p.parent
            if _text(_field(p, "attribute")) in _PY_MUTATING and gp is not None and gp.type == "call" and _same(_field(gp, "function"), p):
                return None  # mutating method
    if len(assigns) != 1:
        return None
    if not rhs_is_immutable(_field(assigns[0], "right"), immutable_ctors):
        return None
    return NEUTRAL, reaches_decision(refs, sp)


def declared_constant(refs: list[Node], sp: LangSpec) -> bool:
    """Whether the language's own declaration settles this state at ONE literal value.

    `private static final int PEEKED = 11;` and `private const int Peeked = 11;` have a
    one-value domain. They were enumerated as state, came back unresolved, and the blame
    fell on the place they are READ -- a case label -- rather than on the declaration that
    settles them. Nineteen sites in gson alone.

    BOTH halves are required, and the second half is the one that took a failing test to
    learn. A modifier alone buys binding immutability, not value immutability: JavaScript's
    `const arr = []` forbids reassigning `arr` and permits `arr.push(1)`, and Java's
    `final List<X> L = new ArrayList<>()` is the same trap in a stricter language. Only a
    LITERAL initialiser closes the domain, which is the same premise Python's
    immutable-construction rule checks before it clears anything.

    L1.18 has carried `immutable_modifiers` since it was written and mutable_state.py reads
    it; L1.18b had no notion of immutability outside Python. Two readers of one property,
    the same shape as the borrow wrapper that sat in the passthrough list while the key
    predicate ignored it. A language declaring no modifiers answers False for every state.
    """
    mods = sp["immutable_modifiers"]
    if not mods:
        return False
    for ref in refs:
        node = ref
        for _ in range(4):
            node = node.parent
            if node is None:
                break
            # One level deeper as well: Java gathers `private static final` into a
            # `modifiers` node, so the keyword is a grandchild, while C# hangs `const` and
            # `readonly` directly off the declaration.
            declared = any(c.type in mods or _text(c) in mods
                           or any(g.type in mods or _text(g) in mods for g in c.children)
                           for c in node.children)
            if declared and literal_initialiser(node, sp):
                return True
    return False


def literal_initialiser(declaration: Node, sp: LangSpec) -> bool:
    """Whether every value bound in this declaration is a literal.

    A declaration binding several names is settled only if all of them are, and a
    declaration binding none, such as an enum member with no initialiser, is not settled
    here at all: this rule reads what was written, and nothing was."""
    values = []
    for slots in sp["local_binding"].values():
        _name_field, value_field = slots
        for node in _refs(declaration, lambda n: n.type in sp["local_binding"]):
            value = _field(node, value_field) if value_field else (
                node.named_children[-1] if len(node.named_children) > 1 else None)
            if value is not None:
                values.append(value)
        break
    return bool(values) and all(_unwrap_unary(v, sp).type in sp["literal_types"] for v in values)
