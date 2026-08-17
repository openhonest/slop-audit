"""How ONE reference to a piece of state reads, in nine grammars.

state_bounds_filters argues about an attribute from the positions its references occupy: a
write, a presence test, a keyed read, a test expression. Those positions are the same
question in every language and a different set of node types in each, and the reading was
Python's node types written into the rules, which is why eight languages got no filtering at
all. This module is the reading, parameterised by LangSpec; the rules are next door.

Nothing here reaches a verdict or knows what a false positive is. Each function answers one
question about one node: is this reference a presence test, is the value it produces thrown
away, does this node name the attribute. The rules compose those answers.

Three divergences cost more than the rest, and each has a function of its own here so no
rule has to know about them:

  flat calls        Java and Ruby put receiver, method and arguments on ONE node, so a
                    predicate written as "parent is a member access, grandparent is a call"
                    reads them off by a level. `receiver_call` reconciles the two shapes.
  presence tests    an operator in Python, JavaScript and TypeScript; a method in Java, C#,
                    Ruby and Rust; a BINDING in Go, whose `_, ok := d[k]` is neither.
  attribute naming  a member access, a bare identifier, or a sigil, depending on how the
                    language reaches its own state.

C is present in every table and answers no to every presence question, which is the truth
about the language rather than a gap: C asks no membership question and grows no container.
"""

from __future__ import annotations

from collections.abc import Callable

from tree_sitter import Node

from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import is_lvalue as _is_lvalue
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import text as _text

# The absent case for a test position. It is the empty string, which no written row holds,
# so a miss is readable as a miss rather than as somebody's answer to a different input.
NO_TEST_SLOT = ""

# Every spelling of a membership operator, as tree-sitter TOKENISES it. `not in` is one token
# of type "not in", not a `not` wrapping an `in`, so matching only "in" misses the negated
# form entirely - which once inverted a whole verdict.
MEMBERSHIP_TOKENS = frozenset({"in", "not in"})


# --- naming the attribute --------------------------------------------------------

def named_as_member(node: Node, attr: str, sp: LangSpec) -> bool:
    """Python, Rust, JavaScript, TypeScript and Go reach state through a receiver."""
    return node.type in sp["member_types"] and _text(_field(node, sp["mem_attr"])) == attr


def named_as_identifier(node: Node, attr: str, sp: LangSpec) -> bool:
    """Java, C# and C name a field bare inside its own scope."""
    return node.type == "identifier" and _text(node) == attr


def named_as_ivar(node: Node, attr: str, sp: LangSpec) -> bool:
    """Ruby's sigil is part of the node's own text, so the key needs no receiver stripped."""
    return node.type == "instance_variable" and _text(node) == attr


_ATTR_SPELLINGS: dict[str, Callable[[Node, str, LangSpec], bool]] = {
    "member": named_as_member,
    "identifier": named_as_identifier,
    "ruby_ivar": named_as_ivar,
}


def names_the_attribute(node: Node | None, attr: str, sp: LangSpec) -> bool:
    """`node` denotes the attribute itself - `self.hits`, `this.hits`, `@hits`, `hits`,
    `s.hits`. The style is read off the same two spec keys the enumerator reads to FIND the
    references, so the two cannot disagree about what a reference looks like, and a spec
    declaring a style nobody wrote raises here rather than defaulting to one of the three."""
    if node is None:
        return False
    style = "ruby_ivar" if sp["instance_enum"] == "ruby_ivar" else sp["instance_ref_style"]
    return _ATTR_SPELLINGS[style](node, attr, sp)


# --- calls on the attribute, in flat and nested grammars -------------------------

def receiver_call(ref: Node, sp: LangSpec) -> Node | None:
    """The call whose RECEIVER this reference is: the `d.get(k)` node, given `d`. None when
    the reference is not a receiver.

    Java and Ruby put receiver, method and arguments on ONE node, so the reference's own
    parent is the call. The other seven nest a member access in between, and a predicate
    written for one shape reads the other off by a level - which is the whole reason this is
    a function and not four lines repeated in every predicate that needs it."""
    parent = ref.parent
    if parent is None:
        return None
    if sp["flat_call"]:
        if parent.type in sp["call_types"] and _same(_field(parent, sp["call_recv"]), ref):
            return parent
        return None
    if parent.type not in sp["member_types"] or not _same(_field(parent, sp["mem_object"]), ref):
        return None
    gp = parent.parent
    if gp is not None and gp.type in sp["call_types"] and _same(_field(gp, sp["call_fn"]), parent):
        return gp
    return None


def call_receiver(call: Node | None, sp: LangSpec) -> Node | None:
    """The receiver of a call: the inverse of `receiver_call`, for a walk that arrived at
    the call first. None when the call has no receiver at all, which is what a plain
    function call is."""
    if call is None or call.type not in sp["call_types"]:
        return None
    if sp["flat_call"]:
        return _field(call, sp["call_recv"])
    return _field(_field(call, sp["call_fn"]), sp["mem_object"])


def method_name(call: Node, sp: LangSpec) -> str:
    """The bare method name of a call on a receiver, without the receiver text a flat
    grammar would otherwise fold into it."""
    if sp["flat_call"]:
        return _text(_field(call, sp["call_name"]))
    return _text(_field(_field(call, sp["call_fn"]), sp["mem_attr"]))


def result_discarded(call: Node, sp: LangSpec) -> bool:
    """The call's result is thrown away. Java's `Map.put` and Rust's `HashMap::insert`
    return the value previously stored at the key, so they write and nothing more only where
    nobody reads the answer. Ruby declares no discard form - every Ruby expression is a value
    and only position decides whether anything reads it - so Ruby can never prove this, which
    is an honest decline rather than a stretched one."""
    parent = call.parent
    return parent is not None and parent.type in sp["discard_types"]


# --- test positions --------------------------------------------------------------

def test_slot_field(parent: Node, child: Node, sp: LangSpec) -> bool:
    """The test sits in the branch node's declared condition field."""
    return _same(_field(parent, sp["branch_cond"]), child)


def test_slot_first(parent: Node, child: Node, sp: LangSpec) -> bool:
    """The test is the first named child: `assert <test>`."""
    named = parent.named_children
    return bool(named) and _same(named[0], child)


def test_slot_second(parent: Node, child: Node, sp: LangSpec) -> bool:
    """The test is the second named child: Python's `a if <test> else b`, which carries no
    condition field at all."""
    named = parent.named_children
    return len(named) >= 2 and _same(named[1], child)


def test_slot_all(parent: Node, child: Node, sp: LangSpec) -> bool:
    """The whole node is a test: a comprehension guard is nothing else."""
    return True


_TEST_SLOTS: dict[str, Callable[[Node, Node, LangSpec], bool]] = {
    "field": test_slot_field,
    "first": test_slot_first,
    "second": test_slot_second,
    "all": test_slot_all,
}


def test_slot_of(parent: Node, sp: LangSpec) -> str:
    """How this construct holds its test, or NO_TEST_SLOT. Branch and elif nodes read their
    declared condition field; every other construct has to be declared in
    extra_test_positions, so a construct nobody wrote a rule for is a miss and not a row."""
    slot = sp["extra_test_positions"].get(parent.type, NO_TEST_SLOT)
    if slot != NO_TEST_SLOT:
        return slot
    if parent.type in sp["branch_types"] or parent.type in sp["elif_types"]:
        return "field"
    return NO_TEST_SLOT


def is_condition_position(parent: Node, child: Node, sp: LangSpec) -> bool:
    """True when `child` is the test part of `parent`: an if/while/elif condition, a ternary
    condition, an assert test, or a comprehension guard."""
    slot = test_slot_of(parent, sp)
    return slot != NO_TEST_SLOT and _TEST_SLOTS[slot](parent, child, sp)


def in_test(ref: Node, sp: LangSpec) -> bool:
    """The reference sits inside a real test expression, nested to any depth
    (`if self._cfg.enabled`, `if len(self._items) > 3`), stopping at the function boundary.

    JavaScript and TypeScript wrap every condition in a parenthesized_expression and C# in a
    prefix_unary_expression, so a direct child comparison against the condition field would
    never match. The walk carries the child up with it, which is what makes those wrappers
    cost nothing."""
    cur = ref
    while cur.parent is not None:
        parent = cur.parent
        if parent.type in sp["func_types"]:
            return False
        if is_condition_position(parent, cur, sp):
            return True
        cur = parent
    return False


# --- presence tests: three spellings across the nine -----------------------------
#
# Python, JavaScript and TypeScript ask with an operator. Java, C#, Ruby and Rust have no
# membership operator and ask with a method. Go asks with a BINDING - `_, ok := d[k]` - which
# is neither, and whose value half goes to the blank identifier. All three read no stored
# value out, which is the property the accumulator rule turns on, so all three are one
# question spelled three ways rather than three questions.


def container_of_comparison_in(ref: Node, parent: Node, sp: LangSpec) -> bool:
    """Python: `k in d` is a comparison_operator carrying an `in` / `not in` token, and the
    container is its last named operand."""
    if not any(c.type in MEMBERSHIP_TOKENS for c in parent.children):
        return False
    named = parent.named_children
    return bool(named) and _same(named[-1], ref)


def container_of_binary_in(ref: Node, parent: Node, sp: LangSpec) -> bool:
    """JavaScript and TypeScript: `k in o` is a binary_expression whose operator is `in`."""
    return _text(_field(parent, "operator")) == "in" and _same(_field(parent, "right"), ref)


def container_of_no_operator(ref: Node, parent: Node, sp: LangSpec) -> bool:
    """Java, C#, Ruby, Rust, Go and C have no membership operator. The decline is explicit:
    those six ask presence with a method or a binding, handled by the two predicates below,
    and reading their comparison nodes as membership would be an invention."""
    return False


_MEMBERSHIP_FORMS: dict[str, Callable[[Node, Node, LangSpec], bool]] = {
    "comparison_in": container_of_comparison_in,
    "binary_in": container_of_binary_in,
    "none": container_of_no_operator,
}


def is_membership_container(ref: Node, sp: LangSpec) -> bool:
    """`ref` is the container of a membership test written with an operator."""
    parent = ref.parent
    if parent is None or parent.type not in sp["comparison_types"]:
        return False
    return _MEMBERSHIP_FORMS[sp["membership"]](ref, parent, sp)


def is_presence_method_call(ref: Node, sp: LangSpec) -> bool:
    """`map.containsKey(k)`, `dict.ContainsKey(k)`, `@h.key?(k)`, `h.contains_key(&k)`: the
    method answers whether the key is there and hands no stored value back."""
    call = receiver_call(ref, sp)
    return call is not None and method_name(call, sp) in sp["presence_methods"]


def presence_binding(subscript: Node, sp: LangSpec) -> Node | None:
    """The binding a keyed read feeds, when the language spells presence that way. Go's
    `_, ok := d[k]` is a short_var_declaration, which is NOT one of Go's assign_types, so no
    other reader in the tree recognises it as anything. None for the other eight, which
    declare no presence_bind_types."""
    holder = subscript.parent
    wrapper = sp["lvalue_wrapper"]
    if holder is not None and wrapper and holder.type == wrapper:
        above = holder.parent
        if above is None or not _same(_field(above, sp["assign_right"]), holder):
            return None
        holder = above
    if holder is None or holder.type not in sp["presence_bind_types"]:
        return None
    return holder


def binding_targets(bind: Node, sp: LangSpec) -> list[Node]:
    """The names a binding writes, unwrapping the language's lvalue wrapper."""
    left = _field(bind, sp["assign_left"])
    if left is None:
        return []
    wrapper = sp["lvalue_wrapper"]
    return list(left.named_children) if wrapper and left.type == wrapper else [left]


def is_comma_ok_presence(ref: Node, sp: LangSpec) -> bool:
    """Go's `_, ok := d[k]`. The keyed read's VALUE goes to the blank identifier and only the
    presence flag is kept, so no stored value is read out. The other eight declare neither a
    presence binding nor a blank identifier, and decline here."""
    parent = ref.parent
    if parent is None or parent.type not in sp["subscript_types"]:
        return False
    if not _same(_sub_collection(parent, sp), ref):
        return False
    bind = presence_binding(parent, sp)
    if bind is None:
        return False
    targets = binding_targets(bind, sp)
    return len(targets) == 2 and _text(targets[0]) in sp["blank_idents"]


def is_presence_test(ref: Node, sp: LangSpec) -> bool:
    """The reference is asked whether it holds a key, in whichever of the three forms this
    language spells. Every form reads no stored value out, which is the whole of why they
    answer as one."""
    return (is_membership_container(ref, sp)
            or is_presence_method_call(ref, sp)
            or is_comma_ok_presence(ref, sp))


# --- keyed reads and removals ----------------------------------------------------

def is_deleted(node: Node, sp: LangSpec) -> bool:
    """`node` is the target of a key removal spelled as a STATEMENT. Only Python has one.
    Everywhere else a removal is a call that hands the removed value back, or - in
    JavaScript - a unary_expression that collides with a wrapper already declared
    transparent, so the eight declare no delete statement and decline here."""
    parent = node.parent
    return parent is not None and parent.type in sp["delete_stmt_types"]


def is_keyed_read_of(expr: Node | None, attr: str, sp: LangSpec) -> bool:
    """`expr` is `self.attr[...]` - the stored value addressed by key."""
    if expr is None or expr.type not in sp["subscript_types"]:
        return False
    return names_the_attribute(_sub_collection(expr, sp), attr, sp)


def keyed_value_read(ref: Node, sp: LangSpec) -> Node | None:
    """The node that yields a value stored under a key, or None when the reference is not
    such a read. A store target is not a read - `d[k] = v`, `d[k] += 1` and `del d[k]` put a
    value in rather than take one out - and neither is a presence test, which answers about
    the key and never about what is stored under it."""
    parent = ref.parent
    if parent is None:
        return None
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        if _is_lvalue(parent, sp) or is_deleted(parent, sp):
            return None
        return parent
    call = receiver_call(ref, sp)
    if call is None:
        return None
    name = method_name(call, sp)
    if name in sp["keyed_read"] and name not in sp["presence_methods"]:
        return call
    return None
