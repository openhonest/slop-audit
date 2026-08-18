"""How wide a keyed access is: the cell-domain rules for subscripted state.

One question, asked from several places in the classifier: given `S[k]`, how many
distinct behaviours of the program can S's value distinguish? The answer turns on the
key, on what the file declares closed, and, since 2026-08-18, on the writes.

Split out of state_bounds.py when adding the write-side bound pushed that module past
the thousand-line god-file threshold this repository publishes. Splitting by
responsibility rather than shaving lines to pass the gate is the rule the methodology
gives an adopter, and it applies here first.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer import state_partition
from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.state_partition import Reach
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import is_write_target as _is_write_target
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import sub_key as _sub_key
from l1_analyzer.ts_nodes import text as _text
from l1_analyzer.ts_nodes import unwrap_unary as _unwrap_unary


def is_unbounded_value(node: Node | None, sp: LangSpec) -> bool:
    """A value used as a lookup key / index. Literals are bounded; anything else
    (a parameter, a variable) ranges over an unbounded domain."""
    node = _unwrap_unary(node, sp)
    return node is not None and node.type not in sp["literal_types"]


def keyed_read(key_node: Node | None, sp: LangSpec, cells: int | None) -> Reach:
    """`S[k]` read. An unbounded key ranges over an unbounded domain; a literal key cuts
    one more class out of it, and whether that class has a neighbour is the whole
    ordered/unordered distinction: `S[3]` sits between `S[2]` and `S[4]`, `S["beta"]` sits
    between nothing. Distinct literals are distinct discriminators, so d of them leave
    d+1 classes."""
    if is_unbounded_value(key_node, sp):
        # An open key over a bounded cell set reaches the cells and nothing else: the ones
        # the writes can create, plus absent. Every such read splits on the SAME cell set,
        # so they share one discriminator key rather than counting once per read site.
        if cells is not None:
            return state_partition.finite(cells + 1, False, "cells")
        return state_partition.unbounded()
    key = _unwrap_unary(key_node, sp)
    return state_partition.finite(2, key is not None and key.type in state_partition.ORDERED_LITERALS, cell_key(key))


def guarded_by_closed_set(key_node: Node | None, sp: LangSpec, closed_sets: dict[str, int | None]) -> int | None:
    """How many values an enclosing membership test confines this key to, or None.

    `if k in KINDS: CACHE[k] = v` writes only under a key KINDS holds, so the store can
    reach at most two cells however wide `k`'s type is. The bound is the DECLARED set's
    cardinality, which is why only a set the file declares immutable counts: a mutable
    list bounds nothing, because a later append moves the number.

    Only the consequence is read. A store on the else branch is reached by keys the test
    REJECTED, which the set does not bound, so walking up from it must find nothing."""
    if key_node is None:
        return None
    name = _text(key_node)
    node = key_node
    while node.parent is not None and node.parent.type not in sp["func_types"]:
        parent = node.parent
        if parent.type in sp["branch_types"]:
            cond = _field(parent, sp["branch_cond"])
            consequence = _field(parent, "consequence")
            mem = membership_operands(cond, sp)
            if (mem is not None and _text(mem[0]) == name and is_closed_set(mem[1], closed_sets)
                    and consequence is not None and contains(consequence, key_node)):
                size = closed_sets.get(_text(mem[1]))
                if size is not None:
                    return size
        node = parent
    return None


def contains(scope: Node, node: Node) -> bool:
    """Whether `node` sits inside `scope`, by byte span."""
    return scope.start_byte <= node.start_byte and node.end_byte <= scope.end_byte


def write_key_bound(refs: list[Node], sp: LangSpec, closed_sets: dict[str, int | None]) -> int | None:
    """How many distinct cells the subscript STORES to this state can create, or None
    when nothing bounds them.

    This is the rule the classifier had no way to express, and its absence was a false
    proof rather than a missed refinement. Every reference used to be judged alone, so a
    read with an open key reported the state provably unbounded even when every write
    into it went through a two-member frozenset. A read cannot observe a cell no write
    created, so the write side is what bounds the state and the read side never was.

    None means the rule declines, not that the state is fine: a state with no subscript
    store at all is outside its scope, and one store with an open key reopens the whole
    cell set however narrow every other store is. Both come back None and leave the
    per-reference verdict exactly as it was."""
    cells = 0
    saw_store = False
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type not in sp["subscript_types"] or not _same(_sub_collection(parent, sp), ref):
            continue
        if not _is_write_target(parent, parent.parent, sp):
            continue
        saw_store = True
        key = _sub_key(parent, sp)
        if not is_unbounded_value(key, sp):
            cells += 1
            continue
        guarded = guarded_by_closed_set(key, sp, closed_sets)
        if guarded is None:
            return None
        cells += guarded
    return cells if saw_store else None


MEMBERSHIP_TOKENS = frozenset({"in", "not in"})


def membership_operands(node: Node | None, sp: LangSpec) -> tuple[Node, Node] | None:
    """(left, right) for an `in` / `not in` membership test, else None."""
    style = sp["membership"]
    if style == "comparison_in" and node.type == "comparison_operator":
        if not any(c.type in MEMBERSHIP_TOKENS for c in node.children):
            return None
        named = [c for c in node.children if c.is_named]
        return (named[0], named[-1]) if len(named) >= 2 else None
    if style == "binary_in" and node.type == "binary_expression" and _text(_field(node, "operator")) == "in":
        return _field(node, "left"), _field(node, "right")
    return None


def is_closed_set(node: Node | None, closed_sets: dict[str, int | None]) -> bool:
    if node is None:
        return False
    if node.type in ("set", "tuple", "list"):
        return True
    if node.type == "call" and _text(_field(node, "function")) in ("frozenset", "set"):
        return True
    if node.type == "identifier":
        return _text(node) in closed_sets
    if node.type == "attribute":
        attr = _field(node, "attribute")
        return attr is not None and _text(attr) in closed_sets
    return False


def collect_closed_sets(root: Node) -> dict[str, int | None]:
    names: dict[str, int | None] = {}

    def walk(n: Node) -> None:
        if n.type == "assignment":
            left, rhs = _field(n, "left"), _field(n, "right")
            if left is not None and is_immutable_collection(rhs):
                if left.type == "identifier":
                    names[_text(left)] = state_partition.literal_size(rhs)
                elif left.type == "attribute":
                    attr = _field(left, "attribute")
                    if attr is not None:
                        names[_text(attr)] = state_partition.literal_size(rhs)
        for c in n.children:
            walk(c)

    walk(root)
    return names


def is_immutable_collection(rhs: Node | None) -> bool:
    if rhs is None:
        return False
    if rhs.type == "tuple":
        return True
    if rhs.type == "call":
        return _text(_field(rhs, "function")) == "frozenset"
    return False


# name -> member count, with None for a collection that is provably fixed and not countable.


def cell_key(key_node: Node | None) -> str:
    """The discriminator identity of one cell of a keyed state.

    Both spellings of a question about a literal key share it, so `"a" in S` and `S["a"]`
    cut the partition once between them rather than twice. It exists as a function rather
    than an f-string at each site because the two sites are in different modules and drifted
    apart: one wrote holds:"a" and the other key:"a" for the same cell."""
    return f"cell:{_text(key_node)}"
