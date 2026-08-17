"""The tree-sitter node accessors every analysis module needs.

They lived inside state_bounds, which meant a second module that wanted `_text` either
imported a private name across a module boundary or wrote its own copy. Both happened.
Two copies of a one-line accessor are harmless until one of them learns something the
other does not, and `_same` is exactly that case: node identity has a rule (compare ids,
never `is`) that a re-implementation gets wrong on the first try.

Nothing here knows what a state is or what a partition is. These read a parse tree.
"""

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from l1_analyzer.lang_spec import LangSpec


def refs(scope: Node, predicate: Callable[[Node], bool]) -> list[Node]:
    """Every node under `scope` matching `predicate`, in pre-order, which is source order."""
    out: list[Node] = []

    def walk(n: Node) -> None:
        if predicate(n):
            out.append(n)
        for c in n.children:
            walk(c)

    walk(scope)
    return out


def local_refs(scope: Node, predicate: Callable[[Node], bool], stop: tuple[str, ...]) -> list[Node]:
    """Like `refs`, but never descends into a nested record. An inner class owns its own
    fields and is analysed as its own scope, so the enclosing class must not harvest the
    inner class's state, which would count it twice."""
    out: list[Node] = []

    def walk(n: Node, is_root: bool) -> None:
        if not is_root and n.type in stop:
            return
        if predicate(n):
            out.append(n)
        for c in n.children:
            walk(c, False)

    walk(scope, True)
    return out


def text(node: Node | None) -> str:
    return node.text.decode("utf8", errors="ignore") if node is not None and node.text else ""


def field(node: Node | None, name: str | None) -> Node | None:
    return node.child_by_field_name(name) if node is not None and name else None


def same(a: Node | None, b: Node | None) -> bool:
    """Node identity by id. child_by_field_name returns a fresh wrapper each call, so `is`
    is unreliable; compare the stable node id instead."""
    return a is not None and b is not None and a.id == b.id


def first_named(node: Node | None) -> Node | None:
    return next((c for c in node.children if c.is_named), None) if node is not None else None


def arg_value(node: Node | None) -> Node | None:
    """Unwrap a C# `argument` wrapper to the expression it carries."""
    if node is not None and node.type == "argument":
        return first_named(node)
    return node


# --- readers that need one grammar's vocabulary ---------------------------------
#
# These still know nothing about state or partitions: they read a parse tree through a
# LangSpec, which is a table of node types and field names. They live here because two
# modules need them and state_bounds_filters cannot import state_bounds without a cycle.
# One copy of `is_lvalue` is the point: a re-implementation gets Go's expression_list
# wrapper wrong on the first try, and a wrong answer there reads a write as a read.


def sub_named(subscript: Node) -> list[Node]:
    return [c for c in subscript.children if c.is_named]


def sub_collection(subscript: Node, sp: LangSpec) -> Node | None:
    """The collection being indexed. Rust's index_expression has no fields, so the
    collection is the first named child; other grammars name it."""
    if sp["sub_positional"]:
        named = sub_named(subscript)
        return named[0] if named else None
    return field(subscript, sp["sub_value"])


def sub_key(subscript: Node, sp: LangSpec) -> Node | None:
    """The key/index node of a subscript. Rust indexes positionally (second named
    child); C# wraps the key in a bracketed_argument_list; others name it."""
    if sp["sub_positional"]:
        named = sub_named(subscript)
        return named[1] if len(named) > 1 else None
    idx = field(subscript, sp["sub_index"])
    if idx is not None and idx.type == "bracketed_argument_list":
        return arg_value(first_named(idx))
    return idx


def is_lvalue(node: Node | None, sp: LangSpec) -> bool:
    """True if `node` is the assigned lvalue of an assignment, unwrapping an optional
    lvalue wrapper (Go puts assignment targets inside an expression_list)."""
    if node is None:
        return False
    wrapper = sp["lvalue_wrapper"]
    p = node.parent
    if wrapper and p is not None and p.type == wrapper:
        node, p = p, p.parent
    return p is not None and p.type in sp["assign_types"] and same(field(p, sp["assign_left"]), node)
