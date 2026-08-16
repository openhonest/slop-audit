"""Attribute-level false-positive filters for the L1.18b finite-testability classifier.

state_bounds classifies each REFERENCE to a piece of state, then combines the categories
into a verdict. That is right for most state, but it conflates unbounded DATA with an
unbounded DECISION: a value indexed by an unbounded key, or carried through a builder, is
flagged even when no value derived from it ever reaches a branch. Decision space, not data
cardinality, is what bounds testability.

These filters run once per attribute, over all its references, and clear a finding to
NEUTRAL only when a shape is PROVABLY testable. They are conservative: any doubt keeps the
finding. Four shapes, each carrying at least one case the others cannot:

  write-once   assigned once (through ANY receiver), never mutated, never handed out whole
  memoization  a presence-gated, result-invariant cache whose stored value never reaches a
               branch condition
  carried      a value that appears in no test expression at all
  accumulator  a presence-gated counter or tally that is only ever written: no reference
               reads the stored value out, so nothing observable turns on it

The last two overlap on an UNGATED accumulator, which carried already clears. What only the
accumulator rule reaches is the gated form, `if k not in self._h: self._h[k] = 0`, where the
membership test does put a reference in a condition.

Two module-level guards sit in front of the rules and refuse a shape outright, because a
rule that argues from where a reference sits cannot see either of them:

  value-in-a-condition  the stored value is inspected in a branch, so presence or magnitude
                        is the answer and the cache is a decision
  open-key selection    the container is read at a key the class does not bound, so it
                        answers one way per key and the caller chooses which

Only memoization is allowed past the second guard, and only because a presence-gated,
result-invariant cache can be deleted without changing an answer. The guard is the fix for a
cross-language defect: `return self.cache[k]` cleared here while C reported the identical
shape promiscuous, because C has no filter to clear it with. tests/
test_finite_testability_cross_language.py is the comparison that now holds the two together.

Python only. The false positives and their proofs are Python (found and verified against
declaro-persistum). This is slop-audit's own code; the rules are the spec, ported to
tree-sitter, not a dependency.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer.lang_spec import LANG_SPEC

_PY = LANG_SPEC["python"]
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


# --- Guard: an open key selects among the stored values --------------------------
#
# The rules above all argue from where a reference SITS: assigned once, inside an `if`,
# written by a plain store. None of them asks the question the classifier already answered,
# which is what made the reference unbounded in the first place. A subscript by a key the
# class does not bound is itself the decision - the container answers one way per key, and
# the caller chooses the key - so the classes cannot be enumerated whether or not an `if`
# follows the read. Reading the decision off the KEYWORD rather than off the values is what
# let `return self.cache[k]` clear here while C reported the same shape promiscuous
# (tests/test_finite_testability_c.py, value-indexed-cache). C has no attribute-level filter,
# so it never lost the finding, and the two languages disagreed about identical runtime
# behaviour for as long as this rule has shipped.
#
# The guard is scoped to keys from OUTSIDE the class, and that scope is the whole of it. A
# key that is itself state here - `self._rows[self._i]` - already carries its own finding,
# bounded there by `self._i >= len(self._rows)`; charging the container for it as well counts
# one decision twice, which is the cursor false positive this module removed on purpose. A
# key that arrives as a parameter is carried by no other finding, so it lands here or nowhere.
#
# A store target is not a selection: `d[k] = v`, `d[k] += 1` and `del d[k]` put a value in
# rather than take one out, and the accumulator rule below argues separately about them.


def _unwrap_unary(node: Node | None) -> Node | None:
    """Peel unary operators off a key. `s[-1]` is the last element, one compile-time value,
    so the wrapper must not hide the literal underneath it."""
    while node is not None and node.type in _PY.get("unary_types", ()):
        named = node.named_children
        node = named[0] if named else None
    return node


def _is_state_of_this_class(node: Node) -> bool:
    """`self.x` / `cls.x`: state the enumerator reports separately, with its own verdict."""
    return node.type == "attribute" and _text(node.child_by_field_name("object")) in ("self", "cls")


def _is_open_key(key: Node | None) -> bool:
    """A single key the class does not bound. A SLICE is not a key and never reaches this
    rule: `self._hash[:4]` selects a contiguous run at a fixed width, and `self.alerts
    [-limit:]` selects a run at a caller's width, but neither picks one stored value out of
    unboundedly many, which is the argument the guard rests on. Measured on buckler/iam,
    where `self.e164_hash[:4].hex()` was flagged by an earlier draft of this rule: a slice
    bounded by the literal 4, called promiscuous because the `slice` node is not itself a
    literal node. Whatever a variable-width slice is worth, the carried-value rule below is
    what decided it before this guard existed and it decides it still."""
    if key is not None and key.type == "slice":
        return False
    key = _unwrap_unary(key)
    if key is None or key.type in _PY["literal_types"]:
        return False
    return not _is_state_of_this_class(key)


def _selects_on_an_open_key(refs: list[Node]) -> bool:
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type != "subscript" or parent.child_by_field_name("value") != ref:
            continue
        gp = parent.parent
        store = gp is not None and (
            (gp.type in ("assignment", "augmented_assignment") and gp.child_by_field_name("left") == parent)
            or gp.type == "delete_statement"
        )
        if not store and _is_open_key(parent.child_by_field_name("subscript")):
            return True
    return False


# --- Rule: write-only accumulator ------------------------------------------------
#
# A per-key counter or tally: `if k not in self._h: self._h[k] = 0` followed by
# `self._h[k] += 1`. It is not a memoization cache - the augmented assignment inspects and
# rewrites the stored value, which is exactly why _writes_are_plain_stores rejects it, and
# that rejection is correct. But nothing ever reads the count back out. The membership test
# gates a branch whose arms both fall through to the same augmented assignment, so no test
# can tell the arms apart and none needs to. State that cannot change an observable outcome
# cannot make anything harder to test.
#
# The rule has two halves and needs both. The first is that no reference reads the stored
# value into a condition; the module-level guard in is_false_positive already establishes
# that. The second is that no reference hands the value out. Dropping the second half would
# clear a counter whose count is returned and then branched on by the CALLER, which is the
# compositional hole the classifier guards everywhere else: the decision moves one frame up
# and the finding evaporates.
#
# Both halves are enforced by whitelisting the positions a reference may occupy. Every role
# below is a WRITE or a presence test; none of them yields the stored value to anything. A
# reference anywhere else - returned, passed as an argument, iterated, read by key into an
# expression, invoked - is not on the list, and the rule declines.

# In-place methods that only write. pop, popitem and setdefault also hand the stored value
# back to the caller, so they read as well as write and are excluded.
_PURE_WRITE_METHODS = _IN_PLACE - {"pop", "popitem", "setdefault"}


def _is_whole_rebind(ref: Node, parent: Node) -> bool:
    """`self.attr = {}` - the attribute itself is the assignment target."""
    return parent.child_by_field_name("left") == ref


def _is_presence_gate(ref: Node, parent: Node) -> bool:
    """`k in self.attr` - the container of a membership test, which reads no stored value."""
    return _is_membership_container(ref)


def _is_confined_subscript(ref: Node, parent: Node) -> bool:
    """`self.attr[k]` standing as a store target: `= v`, `+= 1`, or `del`. A keyed read in
    any other position carries the value somewhere this rule cannot follow."""
    if parent.child_by_field_name("value") != ref:
        return False
    gp = parent.parent
    if gp is None:
        return False
    if gp.type in ("assignment", "augmented_assignment"):
        return gp.child_by_field_name("left") == parent
    return gp.type == "delete_statement"


def _is_pure_write_call(ref: Node, parent: Node) -> bool:
    """`self.attr.add(k)` - an in-place method that returns no stored value."""
    if parent.child_by_field_name("object") != ref:
        return False
    gp = parent.parent
    called = gp is not None and gp.type == "call" and gp.child_by_field_name("function") == parent
    return called and _text(parent.child_by_field_name("attribute")) in _PURE_WRITE_METHODS


# The whitelist, keyed by the PARENT node type a reference sits under.
_CONFINED_ROLES = {
    "assignment": _is_whole_rebind,
    "comparison_operator": _is_presence_gate,
    "subscript": _is_confined_subscript,
    "attribute": _is_pure_write_call,
}


def _is_confined_reference(ref: Node) -> bool:
    parent = ref.parent
    if parent is None:
        return False
    role = _CONFINED_ROLES.get(parent.type)
    return role is not None and role(ref, parent)


def _is_attr_write_target(node: Node | None, attr: str) -> bool:
    """`self.attr` or `self.attr[k]`, as the left-hand side of a write."""
    if _is_keyed_read_of(node, attr):
        return True
    return node is not None and node.type == "attribute" and _text(node.child_by_field_name("attribute")) == attr


def _stmt_is_attr_assignment(node: Node, attr: str) -> bool:
    return _is_attr_write_target(node.child_by_field_name("left"), attr)


def _stmt_is_attr_delete(node: Node, attr: str) -> bool:
    return all(_is_attr_write_target(c, attr) for c in node.named_children)


def _stmt_is_attr_write_call(node: Node, attr: str) -> bool:
    fn = node.child_by_field_name("function")
    if fn is None or fn.type != "attribute":
        return False
    obj = fn.child_by_field_name("object")
    return _is_attr_write_target(obj, attr) and _is_pure_write_call(obj, fn)


_GATED_STATEMENTS = {
    "assignment": _stmt_is_attr_assignment,
    "augmented_assignment": _stmt_is_attr_assignment,
    "delete_statement": _stmt_is_attr_delete,
    "call": _stmt_is_attr_write_call,
}


def _writes_only_the_attribute(stmt: Node, attr: str) -> bool:
    """`stmt` writes `attr` and does nothing else the caller could observe."""
    inner = stmt.named_children[0] if stmt.type == "expression_statement" and stmt.named_children else stmt
    rule = _GATED_STATEMENTS.get(inner.type)
    return rule is not None and rule(inner, attr)


def _gate_branch(ref: Node) -> Node | None:
    """The `if` or `elif` whose condition this membership test is. None when the test sits
    somewhere with no block to read - a ternary, an assert, a comprehension guard - or in a
    condition the walk leaves without finding one."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        if parent.type in _FUNCTION_TYPES:
            return None
        if parent.type in ("if_statement", "elif_clause") and parent.child_by_field_name("condition") == cur:
            return parent
        cur = parent
    return None


def _gated_branches_converge(attr: str, refs: list[Node]) -> bool:
    """Every membership gate on the attribute guards branches that write only the attribute.
    Without this, `if k in self._seen: self._misses += 1` would clear: the presence decides
    something after all, just in a neighbouring slot rather than in a return value, and the
    module guard's result-invariance check only looks at returns."""
    for ref in refs:
        if not _is_membership_container(ref):
            continue
        gate = _gate_branch(ref)
        if gate is None:
            return False
        for block in (n for n in _descendants(gate) if n.type == "block"):
            if not all(_writes_only_the_attribute(s, attr) for s in block.named_children):
                return False
    return True


def _is_write_only_accumulator(attr: str, refs: list[Node]) -> bool:
    return all(_is_confined_reference(r) for r in refs) and _gated_branches_converge(attr, refs)


# --- entry point -----------------------------------------------------------------

def is_false_positive(key: str, refs: list[Node], verdict: str) -> bool:
    """True when the finding for this attribute is a provable false positive under one of
    the four rules, and should be reclassified NEUTRAL. Conservative: any doubt is False.

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
    # Memoization is settled BEFORE the open-key guard, and it is the one shape allowed past
    # it. A presence-gated, result-invariant cache answers the same for a key whether or not
    # that key is stored, so the partition its keyed read cuts belongs to the function being
    # memoised and not to the cache: delete the cache and every observable answer is
    # unchanged. No other rule can make that argument, which is why no other rule is exempt.
    if verdict == "promiscuous" and _is_memoization(cls, attr, refs):
        return True
    if _selects_on_an_open_key(refs):
        return False
    if _is_write_once(cls, attr, refs):
        return True                                   # immutable, read only in bounded ways
    if verdict == "promiscuous":
        return _drives_no_decision(refs) or _is_write_only_accumulator(attr, refs)
    return False
