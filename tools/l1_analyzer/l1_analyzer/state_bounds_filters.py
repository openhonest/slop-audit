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

WHICH RULES SERVE WHICH LANGUAGES. The accumulator rule and the two guards in front of it
read a LangSpec and serve all nine. The other three - write-once, memoization and carried -
still read Python node types directly and are gated to Python at the entry point. Widening
one rule at a time is deliberate: each widening is a claim about nine grammars, and the
cross-language conformance suite can only hold one claim at a time to the evidence. Their
false positives and proofs are Python (found and verified against declaro-persistum).

Leaving the open-key guard Python-only is safe rather than lucky, and the reason is worth
stating because it is what makes the staging possible. The guard refuses a container read at
a key the class does not bound. The accumulator's whitelist is strictly tighter: it admits
only writes, presence tests and a read written straight back, and a keyed read in any other
position is not on it. So a shape the guard would refuse, the whitelist refuses first.

A DEFECT FOUND AND SINCE FIXED. `_RUBY_MUTATING` carries the string `"<<"`, and Ruby parses
an append as a `binary` node rather than a call, so no method name is ever `"<<"` and that
entry could never match: the classifier read `@rows << x` as a value flowing on rather than
as a write. The operator form is now declared in `write_in_place_ops`, beside C#'s `n++`,
Java's `update_expression` and Go's `inc_statement`, because all four are one question the
table had never asked - which nodes write their operand where it stands. The accumulator rule
still declines the shape, for the reason it always did: Ruby can prove no discard.
"""

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from l1_analyzer import state_ref_reads as reads
from l1_analyzer.lang_spec import (
    _PY_IN_PLACE,
    COMPARISON_OPS,
    LANG_SPEC,
    LangSpec,
)
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_arg as _first_arg
from l1_analyzer.ts_nodes import is_lvalue as _is_lvalue
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import sub_key as _sub_key
from l1_analyzer.ts_nodes import text as _text

_PY = LANG_SPEC["python"]
# Method names that mutate a container in place. The docstring used to CLAIM this was a
# superset of the classifier's set and a hand-written list sat underneath, which drifted:
# `appendleft` was in _PY_MUTATING and not here, so a deque assigned once and then grown
# cleared as write-once. The claim is now the construction, so the two cannot part again,
# and the derivation itself moved to lang_spec, where python's write-only set is taken from
# it in the same breath.
_IN_PLACE = _PY_IN_PLACE
# Container reads that a memoization cache may use and that do not inspect a value's shape.
_CACHE_READS = frozenset({"pop", "clear", "get", "keys", "values", "items", "setdefault"})


def _is_python(sp: LangSpec) -> bool:
    """The three rules that still read Python node types directly fire only for Python.
    Stated as one predicate so the entry point says which rules are staged and why."""
    return sp is _PY


def _attr(key: str) -> str:
    """The bare attribute name from a state key: `self._rows` -> `_rows`. Ruby's sigil
    survives (`@hits` stays `@hits`), which is right: the sigil is part of the name the
    grammar puts in the node, and _names_the_attribute matches against that node."""
    return key.rsplit(".", 1)[-1]


def _enclosing(ref: Node, types: tuple[str, ...] | frozenset[str]) -> Node | None:
    """The nearest ancestor of `ref` whose type is one of `types`, or None."""
    cur = ref.parent
    while cur is not None:
        if cur.type in types:
            return cur
        cur = cur.parent
    return None


def _enclosing_class(ref: Node, sp: LangSpec) -> Node | None:
    """The class whose body a reference sits in. Go and C declare no class types at all, so
    this returns None for them; the two rules that need a class body to walk (write-once and
    memoization) are Python-only anyway, and the accumulator rule needs no scope node."""
    return _enclosing(ref, sp["class_types"])


def _enclosing_function(ref: Node, sp: LangSpec) -> Node | None:
    return _enclosing(ref, sp["func_types"])


def _drives_no_decision(refs: list[Node], sp: LangSpec) -> bool:
    """Rule B (carried value): no reference appears in a test expression, so the attribute
    decides nothing. Unbounded data that never reaches a branch does not bound testability."""
    return not any(reads.in_test(r, sp) for r in refs)


# --- Rule: write-once, receiver-aware --------------------------------------------

def _attribute_targets(left: Node | None) -> list[Node]:
    """Every `<recv>.attr` node an assignment target binds, unwrapping tuple and list
    patterns. A plain target yields itself; a pattern yields one node per element.
    """
    if left is None:
        return []
    if left.type == "attribute":
        return [left]
    return [n for n in left.children if n.type == "attribute"]


def _member_writes(cls: Node, attr: str) -> list[Node]:
    """Every assignment target `<recv>.attr` inside the class, through ANY receiver. A
    builder writes the attribute through another instance (new._q = self._q.f()), so a
    self-only scan is blind to it; over-approximating writes is the safe direction."""
    writes: list[Node] = []

    def walk(n: Node) -> None:
        if n.type == "assignment":
            left = n.child_by_field_name("left")
            # Every attribute IN the target, not the target itself. `self.a, self.b = m, m`
            # puts a pattern_list here, and reading only `left.type == "attribute"` counted
            # neither write, so an attribute written twice could still read as write-once.
            writes.extend(t for t in _attribute_targets(left)
                          if _text(t.child_by_field_name("attribute")) == attr)
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


# Nodes Python inserts between a reference and the argument list holding it. Reading only
# `argument_list` meant `f(*self.a)`, `f(**self.a)` and `f(rows=self.a)` each handed the bare
# container to an unmodelled callee without the walk seeing it leave. Written out as a table
# so a fourth spelling is a missing row here rather than a silent escape.
_ARGUMENT_WRAPPERS = frozenset({"list_splat", "dictionary_splat", "keyword_argument"})


def _argument_list_above(parent: Node) -> Node | None:
    """The argument list this reference is an argument of, through any wrapper, or None.

    Returns the node rather than a bool so the caller can still reach the callee, and None
    rather than raising because a reference that is not an argument is the ordinary case.
    """
    if parent.type == "argument_list":
        return parent
    if parent.type in _ARGUMENT_WRAPPERS and parent.parent is not None:
        return parent.parent if parent.parent.type == "argument_list" else None
    return None


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
        arglist = _argument_list_above(parent)
        if arglist is not None:
            call = arglist.parent
            callee = call.child_by_field_name("function") if call is not None else None
            if _text(callee) not in _SAFE_ARG_BUILTINS:
                return True                           # passed to an unknown callee
    return False


def _is_write_once(cls: Node, attr: str, refs: list[Node]) -> bool:
    if len(_member_writes(cls, attr)) != 1:
        return False
    return not _mutated_in_place(refs, attr) and not _returned_whole(refs) and not _escapes(refs)


def _has_presence_gate(refs: list[Node], sp: LangSpec) -> bool:
    return any(reads.is_presence_test(r, sp) for r in refs)


def _value_reaches_condition(refs: list[Node], sp: LangSpec) -> bool:
    """A stored value is inspected in a branch: a keyed READ of the attribute appears inside
    a test expression. This is condition 2, the load-bearing one - it keeps
    _first_failure_time (now - t >= 3600) flagged."""
    for ref in refs:
        read = reads.keyed_value_read(ref, sp)
        if read is not None and reads.in_test(read, sp):
            return True
    return False


# --- Rule: presence-gated, result-invariant memoization cache --------------------

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


def _result_invariant(attr: str, refs: list[Node], sp: LangSpec) -> bool:
    """The presence of a key does not change the answer. Scoped to the ACCESSOR methods -
    those that contain a presence test on the attribute - every return is the keyed value
    `self.attr[k]` or a bare return. A method that returns a different value by presence
    (`return None` on a miss, `return False` for a dedup) is result-VARIANT: the presence IS
    the answer, a genuine decision, and it stays flagged. A setter in a different method that
    returns the stored value is irrelevant - only the presence-gated method is checked."""
    for fn in {_enclosing_function(r, sp) for r in refs if reads.is_presence_test(r, sp)}:
        if fn is None:
            continue
        for ret in (n for n in _descendants(fn) if n.type in sp["return_types"]):
            val = ret.named_children[0] if ret.named_children else None
            if val is not None and not reads.is_keyed_read_of(val, attr, sp):
                return False
    return True


def _is_memoization(cls: Node, attr: str, refs: list[Node], sp: LangSpec) -> bool:
    return _has_presence_gate(refs, sp) and _writes_are_plain_stores(cls, attr, refs)


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
    while node is not None and node.type in _PY["unary_types"]:
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


def _selects_on_an_open_key(refs: list[Node], sp: LangSpec) -> bool:
    """A reference SELECTS on a key nobody bounded, so the attribute's answer depends on it.

    Read from the vocabulary since 2026-08-18. It hardcoded Python's `subscript`,
    `assignment` and `delete_statement`, and the carried-value rule it guards was widened
    to all nine on the same day. Widening the rule and not the guard dropped the guard for
    eight languages and turned thirty-seven cross-language conformance vectors red, which
    is what that suite is for.

    A STORE is not a select: writing at a key, or removing one, does not make the answer
    depend on the key. Removal has two spellings across the nine, a statement in Python,
    JavaScript and TypeScript, and a method everywhere else, and the method form is already
    covered by `mutating`."""
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type not in sp["subscript_types"] \
                or _sub_collection(parent, sp) != ref:
            continue
        gp = parent.parent
        store = gp is not None and (
            (gp.type in sp["assign_types"] and _field(gp, sp["assign_left"]) == parent)
            or gp.type in sp["key_removal_types"]
        )
        if not store and _is_open_key(_sub_key(parent, sp)):
            return True
    # THE METHOD FORM of a keyed read, which is how six of the nine spell it. Java asks
    # `d.get(k)` and C# `d.GetValueOrDefault(k)`, neither of which is a subscript, so a
    # guard reading only subscripts saw nothing and the carried-value rule cleared an
    # open-key read that the cross-language vector `open-key-read-returned` declares
    # promiscuous. Python's own `d.get(k)` was covered by the subscript spelling beside it
    # and this shape never came up while the rule was Python-only.
    for ref in refs:
        parent = ref.parent
        if parent is None or parent.type not in sp["member_types"]:
            continue
        attr_node = _field(parent, sp["mem_attr"])
        gp = parent.parent
        called = gp is not None and gp.type in sp["call_types"] and _field(gp, sp["call_fn"]) == parent
        if called and attr_node is not None and _text(attr_node) in sp["keyed_read"] \
                and _is_open_key(_first_arg(gp, sp)):
            return True
    return False


# --- Rule: write-only accumulator ------------------------------------------------
#
# A per-key counter or tally: `if k not in self._h: self._h[k] = 0` followed by
# `self._h[k] += 1`. It is not a memoization cache - the augmented assignment inspects and
# rewrites the stored value, which is exactly why _writes_are_plain_stores rejects it, and
# that rejection is correct. But nothing ever reads the count back out. The presence test
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
#
# The read-modify-write is where the nine grammars diverge furthest and mean the same thing.
# Python, C#, Ruby, Go, JavaScript and TypeScript write it as one compound-assignment node.
# Java has to spell it `h.put(k, h.get(k) + 1)` and Rust `*h.get_mut(&k).unwrap() += 1`, so
# in those two the read is a node of its own and the rule has to follow the value it produces
# to the write on the other side. Same runtime step, three notations.


def _is_whole_rebind(ref: Node, parent: Node, attr: str, sp: LangSpec) -> bool:
    """`self.attr = {}` - the attribute itself is the assignment target."""
    return _is_lvalue(ref, sp)


def _is_binding_declaration(ref: Node, parent: Node, attr: str, sp: LangSpec) -> bool:
    """`Map<String,Integer> hits = new HashMap<>();` - the reference is the DECLARED NAME of
    the field. A declaration binds the state, it does not consume it, so it is a write like
    any assignment target. The field is checked and not just the node type: `int y =
    hits.size();` puts `hits` under a variable_declarator too, in the value."""
    field = sp["binding_sites"][parent.type]
    return _same(_field(parent, field), ref)


def _is_presence_gate(ref: Node, parent: Node, attr: str, sp: LangSpec) -> bool:
    """`k in self.attr` - the container of a membership test, which reads no stored value."""
    return reads.is_membership_container(ref, sp)


def _is_confined_subscript(ref: Node, parent: Node, attr: str, sp: LangSpec) -> bool:
    """`self.attr[k]` standing as a store target: `= v`, `+= 1`, or `del`. A keyed read in
    any other position carries the value somewhere this rule cannot follow - except Go's
    comma-ok presence test, where the value half goes to the blank identifier and only the
    presence flag is kept."""
    if not _same(_sub_collection(parent, sp), ref):
        return False
    if _is_lvalue(parent, sp):
        # A CONDITIONAL ASSIGNMENT IS NOT A PLAIN STORE. `@cache[k] ||= compute(k)` evaluates
        # to the stored value, so the value leaves through the expression itself, and in Ruby
        # a method's tail expression is its return. That is the compositional hole this rule
        # guards everywhere else: the decision moves one frame up to the caller and the
        # finding evaporates. It admitted the shape anyway, and the result was a false green
        # on the commonest memoization cache in the language, where the same cache written as
        # a read plus a store came back promiscuous.
        #
        # It is admitted only where the language can PROVE the value is thrown away. Ruby
        # declares no discard_types, so in Ruby it never can, and the rule declines.
        if _text(_field(parent.parent, "operator")) in sp["read_write_assign_ops"]:
            return reads.result_discarded(parent.parent, sp)
        return True
    if reads.is_deleted(parent, sp):
        return True
    return reads.is_comma_ok_presence(ref, sp)


def _is_pure_write_call(ref: Node, sp: LangSpec) -> bool:
    """`self.attr.add(k)` - an in-place method that returns no stored value, whose result
    nobody reads. Two conditions, and both are needed: the name has to be one that writes,
    and where the write also hands back what was there before (Java's put, Rust's insert)
    the result has to be discarded."""
    call = reads.receiver_call(ref, sp)
    if call is None or reads.method_name(call, sp) not in sp["write_methods"]:
        return False
    return reads.result_discarded(call, sp)


def _is_arithmetic_host(parent: Node, sp: LangSpec) -> bool:
    """A binary node carrying an operator that is neither a comparison nor a membership
    test: `h.get(k) + 1`. The value it produces is derived, not decided on.

    Python is excluded by construction rather than by a special case: its comparison node
    carries no `operator` field, so the text is empty and no arithmetic reading is available.
    Python spells arithmetic with a different node type entirely, and one this rule has no
    need for."""
    op = _field(parent, "operator")
    if op is None:
        return False
    text = _text(op)
    return text not in COMPARISON_OPS and text not in reads.MEMBERSHIP_TOKENS


def _transparent_host(cur: Node, parent: Node, sp: LangSpec) -> Node | None:
    """The node the value moves to when its host neither consumes nor decides on it, or None
    when the host is neither. Three shapes: a declared passthrough wrapper (Rust's deref,
    a parenthesis), arithmetic, and a method that hands back the value it was given
    (Rust's `unwrap`, without which `get_mut(&k).unwrap()` cannot reach its assignment)."""
    if parent.type in sp["passthrough_types"]:
        return parent
    if parent.type in sp["comparison_types"] and _is_arithmetic_host(parent, sp):
        return parent
    call = reads.receiver_call(cur, sp)
    if call is not None and reads.method_name(call, sp) in sp["value_preserving_methods"]:
        return call
    return None


def _is_attribute_write_call(call: Node | None, attr: str, sp: LangSpec) -> bool:
    """`h.put(k, ...)` - a pure write whose receiver is the attribute itself."""
    recv = reads.call_receiver(call, sp)
    return (recv is not None and reads.names_the_attribute(recv, attr, sp)
            and _is_pure_write_call(recv, sp))


def _flows_back_into_the_attribute(read: Node, attr: str, sp: LangSpec) -> bool:
    """The value this read produced is written straight back into the attribute and reaches
    nothing else. Two endings: it is the target of an assignment (Rust's
    `*h.get_mut(&k).unwrap() += 1`), or it is an argument of a write on the same attribute
    (Java's `h.put(k, h.get(k) + 1)`). Anything else on the way up and the walk declines,
    which is the conservative direction: a value that escapes keeps the finding."""
    cur = read
    while True:
        parent = cur.parent
        if parent is None or parent.type in sp["func_types"]:
            return False
        if parent.type in sp["assign_types"]:
            return _is_lvalue(cur, sp)
        if parent.type in sp["arglist_types"]:
            return _is_attribute_write_call(parent.parent, attr, sp)
        nxt = _transparent_host(cur, parent, sp)
        if nxt is None:
            return False
        cur = nxt


def _is_keyed_read_written_back(ref: Node, attr: str, sp: LangSpec) -> bool:
    """A read-modify-write spelled with an explicit read. `h.get(k)` in Java and
    `h.get_mut(&k)` in Rust are the same runtime step Python writes as `h[k] += 1`: the
    value comes out and goes straight back in, so nothing observes it."""
    call = reads.receiver_call(ref, sp)
    if call is None:
        return False
    name = reads.method_name(call, sp)
    if name not in sp["keyed_read"] or name in sp["presence_methods"]:
        return False
    return _flows_back_into_the_attribute(call, attr, sp)


def _is_confined_method_use(ref: Node, parent: Node, attr: str, sp: LangSpec) -> bool:
    """Every method position the rule admits: a pure write, a presence test, or a keyed read
    written straight back. One predicate serves the flat-call grammars and the nested ones,
    because _receiver_call already reconciles the two shapes."""
    return (_is_pure_write_call(ref, sp)
            or reads.is_presence_method_call(ref, sp)
            or _is_keyed_read_written_back(ref, attr, sp))


ConfinedRole = Callable[[Node, Node, str, LangSpec], bool]


def _confined_roles(sp: LangSpec) -> dict[str, ConfinedRole]:
    """The whitelist for one language, keyed by the PARENT node type a reference sits under
    and built from that language's own declared vocabulary. A parent type with no row is a
    position the rule has no argument for, and the rule declines rather than guessing."""
    roles: dict[str, ConfinedRole] = {}
    for t in sp["assign_types"]:
        roles[t] = _is_whole_rebind
    if sp["lvalue_wrapper"]:
        roles[sp["lvalue_wrapper"]] = _is_whole_rebind
    for t in sp["binding_sites"]:
        roles[t] = _is_binding_declaration
    for t in sp["comparison_types"]:
        roles[t] = _is_presence_gate
    for t in sp["subscript_types"]:
        roles[t] = _is_confined_subscript
    for t in sp["member_types"]:
        roles[t] = _is_confined_method_use
    if sp["flat_call"]:
        for t in sp["call_types"]:
            roles[t] = _is_confined_method_use
    return roles


def _is_confined_reference(ref: Node, attr: str, sp: LangSpec) -> bool:
    parent = ref.parent
    if parent is None:
        return False
    role = _confined_roles(sp).get(parent.type)
    return role is not None and role(ref, parent, attr, sp)


def _is_attr_write_target(node: Node | None, attr: str, sp: LangSpec) -> bool:
    """`self.attr` or `self.attr[k]`, as the left-hand side of a write."""
    return reads.is_keyed_read_of(node, attr, sp) or reads.names_the_attribute(node, attr, sp)


def _stmt_is_attr_assignment(node: Node, attr: str, sp: LangSpec) -> bool:
    left = _field(node, sp["assign_left"])
    wrapper = sp["lvalue_wrapper"]
    if left is not None and wrapper and left.type == wrapper:
        named = left.named_children
        left = named[0] if len(named) == 1 else None
    return _is_attr_write_target(left, attr, sp)


def _stmt_is_attr_delete(node: Node, attr: str, sp: LangSpec) -> bool:
    return all(_is_attr_write_target(c, attr, sp) for c in node.named_children)


def _stmt_is_attr_write_call(node: Node, attr: str, sp: LangSpec) -> bool:
    recv = reads.call_receiver(node, sp)
    return (recv is not None and _is_attr_write_target(recv, attr, sp)
            and _is_pure_write_call(recv, sp))


StatementRule = Callable[[Node, str, LangSpec], bool]


def _gated_statement_rules(sp: LangSpec) -> dict[str, StatementRule]:
    """Which statements a gate's arm may hold, keyed by node type and built per language.
    Only Python declares a delete statement; everywhere else a key removal is a call that
    hands the removed value back, or a unary operator that collides with a wrapper already
    declared transparent, and the rule declines the shape rather than reading one as the
    other."""
    rules: dict[str, StatementRule] = {}
    for t in sp["assign_types"]:
        rules[t] = _stmt_is_attr_assignment
    for t in sp["delete_stmt_types"]:
        rules[t] = _stmt_is_attr_delete
    for t in sp["call_types"]:
        rules[t] = _stmt_is_attr_write_call
    return rules


def _writes_only_the_attribute(stmt: Node, attr: str, sp: LangSpec) -> bool:
    """`stmt` writes `attr` and does nothing else the caller could observe."""
    inner = stmt
    if stmt.type in sp["discard_types"] and stmt.named_children:
        inner = stmt.named_children[0]
    rule = _gated_statement_rules(sp).get(inner.type)
    return rule is not None and rule(inner, attr, sp)


def _gate_branch(ref: Node, sp: LangSpec) -> Node | None:
    """The branch whose test this presence check is. None when the test sits somewhere with
    no arm to read - a ternary, an assert, a comprehension guard - or in a position the walk
    leaves without finding one. Go's comma-ok sits in the `initializer` of its `if` rather
    than in the condition, which is why gate_fields is a tuple and not one name."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        if parent.type in sp["func_types"]:
            return None
        branch = parent.type in sp["branch_types"] or parent.type in sp["elif_types"]
        if branch and any(_same(_field(parent, f), cur) for f in sp["gate_fields"]):
            return parent
        cur = parent
    return None


def _gate_guarded_statements(gate: Node, sp: LangSpec) -> list[Node]:
    """Every statement the gate guards, with the gate's own test left out. Body containers
    are declared per language and expanded, so Java's constructor_body, Ruby's `then` and
    `else`, Go's statement_list and Python's else_clause all yield their statements instead
    of reading as one unrecognised node."""
    tests = [_field(gate, f) for f in sp["gate_fields"]]
    out: list[Node] = []
    for child in gate.named_children:
        if any(_same(t, child) for t in tests):
            continue
        if child.type in sp["gate_body_types"]:
            out.extend(_gate_guarded_statements(child, sp))
        else:
            out.append(child)
    return out


def _gated_branches_converge(attr: str, refs: list[Node], sp: LangSpec) -> bool:
    """Every presence gate on the attribute guards arms that write only the attribute.
    Without this, `if k in self._seen: self._misses += 1` would clear: the presence decides
    something after all, just in a neighbouring slot rather than in a return value, and the
    module guard's result-invariance check only looks at returns."""
    for ref in refs:
        if not reads.is_presence_test(ref, sp):
            continue
        gate = _gate_branch(ref, sp)
        if gate is None:
            return False
        if not all(_writes_only_the_attribute(s, attr, sp)
                   for s in _gate_guarded_statements(gate, sp)):
            return False
    return True


def _is_write_only_accumulator(attr: str, refs: list[Node], sp: LangSpec) -> bool:
    return (all(_is_confined_reference(r, attr, sp) for r in refs)
            and _gated_branches_converge(attr, refs, sp))


# --- entry point -----------------------------------------------------------------

def is_false_positive(key: str, refs: list[Node], verdict: str, sp: LangSpec) -> bool:
    """True when the finding for this attribute is a provable false positive under one of
    the four rules, and should be reclassified NEUTRAL. Conservative: any doubt is False.

    The verdict gates which rules may fire. UNRESOLVED means the classifier could not decide
    the reaching set (dynamic dispatch, an unknown callee): that is a genuine fail-closed
    finding, so the carried-value rule (which only argues about decision space) must never
    clear it. Only write-once can clear an UNRESOLVED, and only when the value provably never
    escapes."""
    if not refs:
        return False
    attr = _attr(key)
    # The single guard that keeps every genuine finding: if the attribute drives a decision
    # whose answer depends on an unbounded value or key, it stays flagged, whatever else is
    # true of it. That is exactly the value-inspected magnitude test (_first_failure_time),
    # the dedup set, and the value-indexed lookup that returns None on a miss. Only once no
    # such decision exists is a shape eligible to clear.
    if _value_reaches_condition(refs, sp) or not _result_invariant(attr, refs, sp):
        return False
    # CARRIED VALUE SERVES ALL NINE, since 2026-08-18. It is one line, `no reference sits
    # in a test expression`, and it delegates to `reads.in_test`, which is vocabulary-driven
    # and whose own docstring works through the JavaScript, TypeScript and C# condition
    # wrappers. It was language-independent already and sat inside the gate only because the
    # gate wraps three rules together.
    #
    # The guard above runs first and also serves all nine, so a value that DOES reach a
    # decision on an unbounded key is still flagged in every language.
    # Write-once, memoization and carried-value still run for Python and nobody else. Each
    # is a claim about nine grammars the cross-language suite has not been made to hold,
    # and widening one rule at a time is what lets the suite say which claim broke.
    #
    # CARRIED VALUE WAS TRIED ON 2026-08-18 AND PUT BACK. The rule itself is one line and
    # already vocabulary-driven, so it looked free. It is not, and the dependency chain is
    # the finding: it is only sound behind `_selects_on_an_open_key`, which was Python-only
    # too; widening that needs the subscript spelling AND the method spelling, because six
    # of the nine ask `d.get(k)` rather than `d[k]`; and with both of those the Ruby
    # conditional-assignment cache still clears when it must not. The guard below now reads
    # the vocabulary, which is the part of that work worth keeping.
    #
    # What a future attempt needs: `open-key-read-returned` in the cross-language vectors
    # declares this shape promiscuous and is the assertion to satisfy, and the Ruby
    # conditional-assignment cache is the second. Both were green before and after here.
    if _is_python(sp):
        cls = _enclosing_class(refs[0], sp)
        if cls is None:
            return False
        # Memoization is settled BEFORE the open-key guard, and it is the one shape allowed
        # past it. A presence-gated, result-invariant cache answers the same for a key
        # whether or not that key is stored, so the partition its keyed read cuts belongs to
        # the function being memoised and not to the cache: delete the cache and every
        # observable answer is unchanged. No other rule can make that argument, which is why
        # no other rule is exempt.
        if verdict == "promiscuous" and _is_memoization(cls, attr, refs, sp):
            return True
        if _selects_on_an_open_key(refs, sp):
            return False
        if _is_write_once(cls, attr, refs):
            return True                               # immutable, read only in bounded ways
        if verdict == "promiscuous" and _drives_no_decision(refs, sp):
            return True
    if verdict != "promiscuous":
        return False
    return _is_write_only_accumulator(attr, refs, sp)
