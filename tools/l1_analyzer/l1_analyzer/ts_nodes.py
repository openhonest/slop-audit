"""The tree-sitter node accessors every analysis module needs.

They lived inside state_bounds, which meant a second module that wanted `text` either
imported a private name across a module boundary or wrote its own copy. Both happened.
Two copies of a one-line accessor are harmless until one of them learns something the
other does not, and `same` is exactly that case: node identity has a rule (compare ids,
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


def written_in_place(node: Node | None, sp: LangSpec) -> Node | None:
    """The operand `node` writes where it stands, or None when `node` writes nothing.

    `n++`, `++n`, `c.n++` and `@xs << x` are one runtime step spelled four ways, and not one
    of them involves an assignment node, so `assign_types` cannot reach any of them. The
    reference is mutated in place and the node also PRODUCES a value, which is why this
    returns the operand rather than a verdict: the caller decides what the produced value
    then does.

    The operator is checked and not only the node type, because two grammars reuse the node
    for things that write nothing: C# spells the null-forgiving `x!` as a
    postfix_unary_expression and `!b` as a prefix one, and Ruby spells every binary operator
    it has as `binary`. A node type carrying an operator this language did not declare comes
    back None, so a shift into a variable is not read as an append.

    The operand is the declared assignment TARGET field where the node has one (Ruby's
    `binary` names `left`) and the first named child where it does not (nothing else in the
    table names a field). Both reach the same place; the field is preferred because a
    grammar that named it meant it."""
    if node is None or node.type not in sp["write_in_place_ops"]:
        return None
    ops = sp["write_in_place_ops"][node.type]
    if not any(not c.is_named and text(c) in ops for c in node.children):
        return None
    return field(node, sp["assign_left"]) or first_named(node)


def is_opaque_unary(node: Node | None, sp: LangSpec) -> bool:
    """`node` is a unary operator this language does NOT let a value pass through.

    Go's `<-ch` is a `unary_expression`, exactly as `-x` and `!b` are, and unary_expression
    is declared a transparent wrapper. So a channel receive walked through as if the channel
    itself flowed onward, when what actually happens is that an element is consumed. Only the
    operator separates the two, which is why the whole node type cannot simply be dropped
    from the wrapper list: that would take `-x` with it."""
    if node is None or node.type not in sp["unary_types"]:
        return False
    return text(field(node, "operator")) in sp["opaque_unary_ops"]


def bare_condition(node: Node | None, sp: LangSpec) -> Node | None:
    """The condition of a branch that holds it POSITIONALLY, or None.

    Go's `for` is the only one in the table. It gives its condition no field at all -
    `for_statement` names only `body` - so reading `branch_cond` there returns nothing
    however the node type is declared, and `for p.running {}` was a loop on a bool field that
    no row could see. The condition is the first named child that is not one of the types the
    spec excludes, which is what tells the three real forms apart: `for {}` has only a body,
    `for k := range m {}` has a range clause, and `for i := 0; c; i++ {}` has a for_clause
    that names its own condition field."""
    if node is None or node.type not in sp["bare_cond_types"]:
        return None
    excluded = sp["bare_cond_types"][node.type]
    return next((c for c in node.named_children if c.type not in excluded), None)


def mutable_alias_value(node: Node | None, sp: LangSpec) -> Node | None:
    """The value `node` hands out as a MUTABLE alias, or None when it hands out none.

    `let r = &mut self.v; r.push(1);` writes the field through a local whose name has no
    relation to it. Every rule in this analyzer argues from where a piece of state's OWN
    references sit, and from that line on there is a write those references do not contain,
    so no such rule is sound about it any more.

    The marker is checked and not the node type, and that is the whole of the reading: Rust's
    `reference_expression` is on the transparent-wrapper list because `&self.v` genuinely is
    a wrapper - a shared borrow cannot be written through. Only the `mutable_specifier`
    separates the two, and it is a child rather than a field."""
    if node is None or node.type not in sp["alias_types"]:
        return None
    if not any(c.type == sp["alias_marker"] for c in node.children):
        return None
    return field(node, sp["alias_types"][node.type])


def hidden_names(scope: Node, sp: LangSpec) -> frozenset[str]:
    """Every name that appears inside a region this grammar leaves unparsed, under `scope`.

    Rust's `macro_invocation` swallows its arguments into a `token_tree`:
    `format!("{}", self.v.len())` holds no field_expression and no call_expression, and the
    flat token sequence does not even keep the field name attached to `self`. So a walk that
    looks for references finds none there, and a state used only inside macros reads as state
    nothing touches - an invisible reference reported as an absence, which is the failure
    this analyzer exists to name.

    Names, not references, because names are all that survive: the tokens carry `self`, `v`
    and `len` as three unrelated identifiers. Matching a state's bare name against them
    over-refuses - a local called `v` inside a macro refuses a field called `v` - and that is
    the direction to be wrong in, because the alternative is to clear a state on a reading
    that skipped part of it. A language whose grammar parses everything declares no region
    type and gets the empty set without a walk."""
    if not sp["opaque_region_types"]:
        return frozenset()
    names: set[str] = set()
    for region in refs(scope, lambda n: n.type in sp["opaque_region_types"]):
        names.update(text(n) for n in refs(region, lambda n: n.is_named and not n.children))
    return frozenset(names)


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


def is_binding_site(ref: Node, parent: Node, sp: LangSpec) -> bool:
    """The reference is the DECLARED NAME in a declaration: `String[] stack;`,
    `static int cache[4];`, `public int N { get; set; }`.

    A declaration binds the state, it does not consume it, which is what an assignment
    target does too - so this is the same row as `is_write_target`, spelled the way a
    grammar with declarations spells it. It is a separate predicate only because the node
    is not an assignment in any of the nine and would never match `assign_types`.

    Two facts make this a rule rather than a convenience. The enumerators ALREADY find state
    by these very nodes (`field_decl_types`, and the census's FIELD_DECLARATION and
    PROPERTY_DECLARATION site kinds), so the classifier reaching a declaration it cannot
    name is the reader failing to recognise the site it arrived through. And the field is
    checked, not just the node type: `int y = stack.length;` puts `stack` under a
    variable_declarator too, in the VALUE, where it is read and not bound."""
    # Named `binding_field` and not `field`: this module's own accessor is called `field`,
    # and the alias this body carried in from state_bounds was rewritten onto it, so the
    # local was shadowing the function it then tried to call.
    binding_field = sp["binding_sites"].get(parent.type)
    return binding_field is not None and same(field(parent, binding_field), ref)


def is_write_target(ref: Node, parent: Node, sp: LangSpec) -> bool:
    if is_lvalue(ref, sp) or is_binding_site(ref, parent, sp):
        return True
    # S[k] = v  -> ref (S) is the collection of a subscript that is the assign target
    return parent.type in sp["subscript_types"] and same(sub_collection(parent, sp), ref) and is_lvalue(parent, sp)


def unwrap_unary(node: Node | None, sp: LangSpec) -> Node | None:
    """Peel the wrappers that leave a value's identity alone, so none of them can hide a
    literal underneath.

    A unary operator over a literal is itself one compile-time value (`-1` is the last
    element, `+1` the second). So is a borrow, a parenthesis and a cast: `&1`, `(1)` and
    `(int)1` each name the same single constant that `1` names. Unwrapping rather than
    whitelisting the wrapper is what keeps `-x` and `&k` unbounded, because both peel to
    an identifier, which is no literal. The loop handles a stack of them.

    The vocabulary is `value_wrapper_types` and is deliberately NOT the flow walker's
    `passthrough_types`, though the two overlap. Passthrough answers "does the value flow
    onward through this node", which is true of `boolean_operator`, `not_operator`,
    `try_expression`, `await` and `expression_list`. None of those preserves a literal's
    identity: `s[1 or x]` is not a constant index, and folding it would be a false green
    rather than the false RED this function was fixing. Reusing passthrough wholesale was
    the tempting shortcut and it is the wrong set.

    The borrow is why this was worth a second pass. `reference_expression` was already in
    Rust's passthrough set, so the flow walker read the borrow as transparent while this
    predicate did not, and two walks disagreeing about one wrapper is what let the defect
    survive the unary fix. In Rust it is not an edge case: `map.contains_key(&1)` is what
    real code writes, and it graded F where the unidiomatic spelling graded neutral.

    The operator token is unnamed in every grammar in the table, so the first named child
    is the operand."""
    while node is not None and node.type in sp["value_wrapper_types"]:
        node = first_named(node)
    return node
