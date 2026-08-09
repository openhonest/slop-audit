"""Attribute-level false-positive filters for the L1.18b finite-testability classifier.

state_bounds classifies each REFERENCE to a piece of state, then combines the categories
into a verdict. That is right for most state, but it conflates unbounded DATA with an
unbounded DECISION: a value indexed by an unbounded key, or carried through a builder, is
flagged even when no value derived from it ever reaches a branch. Decision space, not data
cardinality, is what bounds testability.

These filters run once per attribute, over all its references, and clear a finding to
NEUTRAL only when a shape is PROVABLY testable. They are conservative: any doubt keeps the
finding. Three non-overlapping shapes, each load-bearing on its own case:

  write-once   assigned once (through ANY receiver), never mutated, never handed out whole
  memoization  a presence-gated, result-invariant cache whose stored value never reaches a
               branch condition
  carried      a value that appears in no test expression at all

Python only. The false positives and their proofs are Python (found and verified against
declaro-persistum). This is slop-audit's own code; the rules are the spec, ported to
tree-sitter, not a dependency.
"""

from __future__ import annotations

from tree_sitter import Node

_FUNCTION_TYPES = frozenset({"function_definition", "lambda"})
# Method names that mutate a container in place (a superset of the classifier's, stated
# here so the filter's plain-store rule is self-contained).
_IN_PLACE = frozenset({
    "append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse",
    "update", "setdefault", "popitem", "add", "discard",
    "intersection_update", "difference_update", "symmetric_difference_update",
})
# Container reads that a memoization cache may use and that do not inspect a value's shape.
_CACHE_READS = frozenset({"pop", "clear", "get", "keys", "values", "items", "setdefault"})


def _text(node: Node | None) -> str:
    return "" if node is None or node.text is None else node.text.decode("utf8", errors="ignore")


def _attr(key: str) -> str:
    """The bare attribute name from a state key: `self._rows` -> `_rows`."""
    return key.rsplit(".", 1)[-1]


def _enclosing_class(ref: Node) -> Node | None:
    cur = ref.parent
    while cur is not None:
        if cur.type in ("class_definition", "class_declaration"):
            return cur
        cur = cur.parent
    return None


# --- Rule: appears in a real test expression (the drives-a-decision axis) --------

def _is_condition_position(parent: Node, child: Node) -> bool:
    """True when `child` is the test part of `parent`: an if/while/elif condition, a
    ternary condition, an assert test, or a comprehension guard."""
    ptype = parent.type
    if ptype in ("if_statement", "while_statement", "elif_clause"):
        return child == parent.child_by_field_name("condition")
    if ptype == "conditional_expression":            # a if <cond> else b
        named = parent.named_children
        return len(named) >= 2 and child == named[1]
    if ptype == "assert_statement":
        named = parent.named_children
        return bool(named) and child == named[0]
    return ptype == "if_clause"                      # comprehension guard: [x for x in xs if <cond>]


def _in_test(ref: Node) -> bool:
    """The reference sits inside a real test expression, nested to any depth
    (`if self._cfg.enabled`, `if len(self._items) > 3`), stopping at the function boundary."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        if parent.type in _FUNCTION_TYPES:
            return False
        if _is_condition_position(parent, cur):
            return True
        cur = parent
    return False


def _drives_no_decision(refs: list[Node]) -> bool:
    """Rule B (carried value): no reference appears in a test expression, so the attribute
    decides nothing. Unbounded data that never reaches a branch does not bound testability."""
    return not any(_in_test(r) for r in refs)


# --- Rule: write-once, receiver-aware --------------------------------------------

def _member_writes(cls: Node, attr: str) -> list[Node]:
    """Every assignment target `<recv>.attr` inside the class, through ANY receiver. A
    builder writes the attribute through another instance (new._q = self._q.f()), so a
    self-only scan is blind to it; over-approximating writes is the safe direction."""
    writes: list[Node] = []

    def walk(n: Node) -> None:
        if n.type == "assignment":
            left = n.child_by_field_name("left")
            if left is not None and left.type == "attribute" and _text(left.child_by_field_name("attribute")) == attr:
                writes.append(left)
        for c in n.children:
            walk(c)

    walk(cls)
    return writes


def _mutated_in_place(refs: list[Node], attr: str) -> bool:
    """Any `self.attr.<method>(...)` with an in-place method, `self.attr[k] = v`, or
    `del self.attr[k]` - a mutation route beyond the single assignment."""
    for ref in refs:
        parent = ref.parent
        if parent is None:
            continue
        # self.attr[...] as an assignment/del target
        if parent.type == "subscript" and parent.child_by_field_name("value") == ref:
            gp = parent.parent
            if gp is not None and (
                (gp.type == "assignment" and gp.child_by_field_name("left") == parent)
                or (gp.type in ("delete_statement", "augmented_assignment"))
            ):
                return True
        # self.attr.method(...) with an in-place method
        if parent.type == "attribute" and parent.child_by_field_name("object") == ref:
            gp = parent.parent
            called = gp is not None and gp.type == "call" and gp.child_by_field_name("function") == parent
            if called and _text(parent.child_by_field_name("attribute")) in _IN_PLACE:
                return True
        # augmented assignment straight to self.attr
        if parent.type == "augmented_assignment" and parent.child_by_field_name("left") == ref:
            return True
    return False


def _returned_whole(refs: list[Node]) -> bool:
    """`return self.attr` hands the object itself out; a caller can then mutate it.
    Returning a slice or a copy (`return self.attr[:]`, `list(self.attr)`) is fine."""
    return any(r.parent is not None and r.parent.type == "return_statement" for r in refs)


# Builtins that read or copy their argument without retaining or mutating it. Passing the
# bare attribute to one of these is safe; passing it anywhere else could let an unknown
# callee mutate it, so the finding stays.
_SAFE_ARG_BUILTINS = frozenset({
    "list", "tuple", "set", "frozenset", "dict", "sorted", "reversed", "len", "iter",
    "any", "all", "sum", "min", "max", "next", "bool", "str", "repr",
})


def _escapes(refs: list[Node]) -> bool:
    """The attribute is invoked as a callable (dynamic dispatch) or passed as a bare
    argument to a callee that is not a known read-only builtin. Either lets an unbounded or
    unknown context act on it, so the value does not provably stay bounded."""
    for ref in refs:
        parent = ref.parent
        if parent is None:
            continue
        if parent.type == "call" and parent.child_by_field_name("function") == ref:
            return True                               # self.attr(...) : dynamic dispatch
        if parent.type == "argument_list":
            call = parent.parent
            callee = call.child_by_field_name("function") if call is not None else None
            if _text(callee) not in _SAFE_ARG_BUILTINS:
                return True                           # passed to an unknown callee
    return False


def _is_write_once(cls: Node, attr: str, refs: list[Node]) -> bool:
    if len(_member_writes(cls, attr)) != 1:
        return False
    return not _mutated_in_place(refs, attr) and not _returned_whole(refs) and not _escapes(refs)


# --- Rule: presence-gated, result-invariant memoization cache --------------------

def _is_membership_container(ref: Node) -> bool:
    """`ref` (self.attr) is the container of a membership test: `k in self.attr` or
    `k not in self.attr`. The operator is a single `in` / `not in` token in this grammar."""
    parent = ref.parent
    if parent is None or parent.type != "comparison_operator":
        return False
    if not any(c.type in ("in", "not in") for c in parent.children):
        return False
    named = parent.named_children
    return bool(named) and named[-1] == ref


def _has_presence_gate(refs: list[Node]) -> bool:
    return any(_is_membership_container(r) for r in refs)


def _value_reaches_condition(refs: list[Node]) -> bool:
    """A stored value is inspected in a branch: `self.attr[k]` (a keyed READ, not the bare
    membership container) appears inside a test expression. This is condition 2, the
    load-bearing one - it keeps _first_failure_time (now - t >= 3600) flagged."""
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type != "subscript" or parent.child_by_field_name("value") != ref:
            continue                                  # only keyed reads of the value
        gp = parent.parent
        if gp is not None and gp.type == "assignment" and gp.child_by_field_name("left") == parent:
            continue                                  # a store, not a read
        if _in_test(parent):
            return True
    return False


def _writes_are_plain_stores(cls: Node, attr: str, refs: list[Node]) -> bool:
    """Writes are only `d[k] = v`, `del d[k]`, empty-dict rebind, or cache methods. An
    augmented assignment through the attribute (self.attr[k] += 1) fails - that inspects and
    rewrites the value, which is what a counter does."""
    for ref in refs:
        parent = ref.parent
        if parent is None:
            continue
        if parent.type == "subscript" and parent.child_by_field_name("value") == ref:
            gp = parent.parent
            if gp is not None and gp.type == "augmented_assignment":
                return False
        if parent.type == "attribute" and parent.child_by_field_name("object") == ref:
            gp = parent.parent
            called = gp is not None and gp.type == "call" and gp.child_by_field_name("function") == parent
            method = _text(parent.child_by_field_name("attribute"))
            if called and method in _IN_PLACE and method not in _CACHE_READS:
                return False
    # a whole-attribute rebind must be to an empty dict literal
    for w in _member_writes(cls, attr):
        assign = w.parent
        rhs = assign.child_by_field_name("right") if assign is not None else None
        if rhs is not None and not (rhs.type == "dictionary" and not rhs.named_children):
            return False
    return True


def _descendants(node: Node):
    for c in node.named_children:
        yield c
        yield from _descendants(c)


def _enclosing_function(ref: Node) -> Node | None:
    cur = ref.parent
    while cur is not None:
        if cur.type in _FUNCTION_TYPES:
            return cur
        cur = cur.parent
    return None


def _is_keyed_read_of(expr: Node | None, attr: str) -> bool:
    """`expr` is `self.attr[...]` - the cached value read out by key."""
    if expr is None or expr.type != "subscript":
        return False
    value = expr.child_by_field_name("value")
    return value is not None and value.type == "attribute" and _text(value.child_by_field_name("attribute")) == attr


def _result_invariant(attr: str, refs: list[Node]) -> bool:
    """The presence of a key does not change the answer. Scoped to the ACCESSOR methods -
    those that contain a membership test on the attribute - every return is the keyed value
    `self.attr[k]` or a bare return. A method that returns a different value by presence
    (`return None` on a miss, `return False` for a dedup) is result-VARIANT: the presence IS
    the answer, a genuine decision, and it stays flagged. A setter in a different method that
    returns the stored value is irrelevant - only the membership-gated method is checked."""
    for fn in {_enclosing_function(r) for r in refs if _is_membership_container(r)}:
        if fn is None:
            continue
        for ret in (n for n in _descendants(fn) if n.type == "return_statement"):
            val = ret.named_children[0] if ret.named_children else None
            if val is not None and not _is_keyed_read_of(val, attr):
                return False
    return True


def _is_memoization(cls: Node, attr: str, refs: list[Node]) -> bool:
    return _has_presence_gate(refs) and _writes_are_plain_stores(cls, attr, refs)


# --- entry point -----------------------------------------------------------------

def is_false_positive(key: str, refs: list[Node], verdict: str) -> bool:
    """True when the finding for this attribute is a provable false positive under one of
    the three rules, and should be reclassified NEUTRAL. Conservative: any doubt is False.

    The verdict gates which rules may fire. UNRESOLVED means the classifier could not decide
    the reaching set (dynamic dispatch, an unknown callee): that is a genuine fail-closed
    finding, so the carried-value rule (which only argues about decision space) must never
    clear it. Only write-once can clear an UNRESOLVED, and only when the value provably never
    escapes."""
    if not refs:
        return False
    cls = _enclosing_class(refs[0])
    if cls is None:
        return False
    attr = _attr(key)
    # The single guard that keeps every genuine finding: if the attribute drives a decision
    # whose answer depends on an unbounded value or key, it stays flagged, whatever else is
    # true of it. That is exactly the value-inspected magnitude test (_first_failure_time),
    # the dedup set, and the value-indexed lookup that returns None on a miss. Only once no
    # such decision exists is a shape eligible to clear.
    if _value_reaches_condition(refs) or not _result_invariant(attr, refs):
        return False
    if _is_write_once(cls, attr, refs):
        return True                                   # immutable, read only in bounded ways
    if verdict == "promiscuous":
        return _is_memoization(cls, attr, refs) or _drives_no_decision(refs)
    return False
