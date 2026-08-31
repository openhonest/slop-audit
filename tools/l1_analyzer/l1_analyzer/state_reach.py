"""How ONE reference to a piece of state reaches a decision.

Given `self.sessions` at one site, this answers what the surrounding syntax does with it:
selects an arm, writes into it, hands it out, keys a lookup with it, or nothing this reader
has a rule for. Every verdict L1.18b publishes is a roll-up of these per-reference answers,
so a construct with no rule here is a construct the whole measure goes silent on.

Split out of state_bounds.py on 2026-08-31, when teaching the reader to follow a method
chain pushed that module past the thousand-line god-file threshold this repository
publishes. Splitting by responsibility rather than shaving lines to pass the gate is the
rule the methodology gives an adopter, and it applies here first. The seam is real: this
decides one reference, and what is left decides a file.

The dispatch ends in a total row that says a construct has no rule rather than reaching a
verdict, and that placement is the point. Every row above it has declined by the time it is
reached, so an unhandled shape comes out unmeasured by construction rather than by whoever
remembered to check.
"""

from __future__ import annotations

from tree_sitter import Node

from l1_analyzer import (
    state_partition,
)
from l1_analyzer.lang_spec import COMPARISON_OPS, LangSpec
from l1_analyzer.state_cells import cell_key as _cell_key
from l1_analyzer.state_cells import is_closed_set as _is_closed_set
from l1_analyzer.state_cells import is_unbounded_value as _is_unbounded_value
from l1_analyzer.state_cells import keyed_read as _keyed_read
from l1_analyzer.state_cells import membership_operands as _membership_operands
from l1_analyzer.state_partition import (
    DYNAMIC_DISPATCH,
    NEUTRAL,
    PROMISCUOUS,
    UNRESOLVED,
    Partition,
    Reach,
)
from l1_analyzer.ts_nodes import bare_condition as _bare_condition
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_arg as _first_arg
from l1_analyzer.ts_nodes import is_lvalue as _is_lvalue
from l1_analyzer.ts_nodes import is_opaque_unary as _is_opaque_unary
from l1_analyzer.ts_nodes import is_write_target as _is_write_target
from l1_analyzer.ts_nodes import local_refs as _local_refs
from l1_analyzer.ts_nodes import mutable_alias_value as _mutable_alias_value
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import sub_collection as _sub_collection
from l1_analyzer.ts_nodes import sub_key as _sub_key
from l1_analyzer.ts_nodes import text as _text
from l1_analyzer.ts_nodes import unwrap_unary as _unwrap_unary
from l1_analyzer.ts_nodes import written_in_place as _written_in_place

# Builtins that read a bounded feature of their argument (the value flows onward).
_BOUNDED_BUILTINS = frozenset({"len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"})


# Builtins that consume a value as an effect/assertion, not a partitioning decision.
_EFFECT_CALLS = frozenset({"print", "repr", "str", "format", "log", "logging"})


def _callee_name(call: Node | None, sp: LangSpec) -> str:
    if call is None or call.type not in sp["call_types"]:
        return ""
    return _text(_field(call, sp["call_name"] if sp["flat_call"] else sp["call_fn"]))


# Every spelling of a membership operator, as tree-sitter TOKENISES it. `not in` is one
# token of type "not in", not a `not` wrapping an `in`, so matching only "in" missed the
# negated form entirely. It then fell through to the comparison arm and was graded finite
# and ORDERED, which inverted the verdict: `key in store` graded the repository F and
# `key not in store` graded it A. One word, semantics unchanged, and no disclosure.
def _is_comparison(node: Node | None, sp: LangSpec) -> bool:
    """Whether this node compares two things. An absent node compares nothing.

    It declared that it takes one and asked it for its type on the next line."""
    if node is None:
        return False
    if node.type == "comparison_operator":       # Python: always a comparison
        return True
    return _text(_field(node, "operator")) in COMPARISON_OPS


def _reads_its_own_target(ref: Node, sp: LangSpec) -> bool:
    """The reference is the target of an assignment whose operator reads it before writing.

    Only the conditional operators, not the arithmetic ones. `x += 1` also reads x, but its
    read is of the whole value and is already carried by the accumulator rule; a conditional
    assignment's read is a PRESENCE test on a key, which is what decides a cache.
    """
    node = ref
    while node.parent is not None and node.parent.type not in sp["assign_types"]:
        if node.parent.type not in sp["subscript_types"] and node.parent.type not in sp["member_types"]:
            return False
        node = node.parent
    parent = node.parent
    if parent is None or not _same(_field(parent, sp["assign_left"]), node):
        return False
    return _text(_field(parent, "operator")) in sp["read_write_assign_ops"]


def _categorize_read(ref: Node, sp: LangSpec, closed_sets: dict[str, int | None], cells: int | None) -> Reach:
    """How the READ half of a conditional assignment reaches a decision.

    A keyed target is a keyed read, so an open key is unbounded exactly as it is on the
    right-hand side. A bare name is the value itself meeting a presence test, which is the
    two-class split any truthiness test makes.
    """
    parent = ref.parent
    if parent is not None and parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        return _keyed_read(_sub_key(parent, sp), sp, cells)
    return state_partition.finite(2, True, "truthy")


def _out_argument_local(call: Node | None, sp: LangSpec) -> Node | None:
    """The local an `out` argument of this call binds, or None.

    Takes the absence, because the caller hands it a field lookup and a node with nothing
    above it binds no argument. It already answers None for a call that has none.

    `_d.Remove(k, out var v)` hands the stored value back through `v`. `Remove` is a
    mutating method, so the reference read as a write and stopped, and the value leaving
    through the out argument was never followed: the dictionary came back neutral and
    observe-only on a source that branches on the removed value.

    A rule watching the invocation's own value cannot see it, because the invocation
    returns a bool. The value goes out through a declaration_expression inside the
    argument, which binds a local, and following a local is machinery this module has.

    C# alone of the nine spells this; the other eight declare an empty vocabulary."""
    kinds = sp["out_argument_types"]
    if not kinds or call is None:
        return None
    for node in _refs(call, lambda n: n.type in kinds):
        # The NAME, not the first named child. `out var v` parses as an implicit_type
        # `var` followed by the identifier, so taking the first named child took the type
        # and the rule silently did nothing.
        for child in node.named_children:
            if child.type == "identifier":
                return child
    return None


def _local_binding_name(ref: Node, sp: LangSpec) -> Node | None:
    """The local this reference is being bound INTO, or None.

    `var entries = _entries;` binds the state's value to a local. Every grammar in the
    table carries the link: Java, JavaScript, TypeScript name a `value` field beside
    `name`, Python, Ruby and Go use left/right, Rust and C name a pattern or declarator,
    and C# alone leaves the initialiser unnamed as the last named child. The vocabulary
    records which, so `None` for the value field means "the last named child" rather than
    "not available".

    Returns the NAME node, so the caller can look for what the function does with it. Only
    a plain identifier counts: a destructuring pattern binds several names and none of them
    is this value on its own."""
    parent = ref.parent
    if parent is None:
        return None
    slots = sp["local_binding"].get(parent.type)
    if slots is None:
        return None
    name_field, value_field = slots
    value = _field(parent, value_field) if value_field else (
        parent.named_children[-1] if parent.named_children else None)
    if value is None or not _same(value, ref):
        return None
    name = _field(parent, name_field)
    return name if name is not None and name.type == "identifier" else None


def _bound_to_the_discard(value: Node, sp: LangSpec) -> bool:
    """Whether this value is bound by a declaration that names nothing to bind it to.

    `let _ = f();` in Rust: the value goes nowhere and nobody reads it.

    Told apart from destructuring by whether the pattern is a NAMED node. Rust spells the
    wildcard as an anonymous token, so `_` is present in the tree and carries no name, while
    `(a, b)` is a named tuple pattern. The first draft of this asked whether the pattern was
    absent and found it present, which is why the distinction is written down rather than
    assumed: destructuring takes the value apart and is a question this reader leaves to the
    total row, and the discard is not that question."""
    parent = value.parent
    if parent is None:
        return False
    slots = sp["local_binding"].get(parent.type)
    if slots is None:
        return False
    name_field, value_field = slots
    bound = _field(parent, value_field) if value_field else (
        parent.named_children[-1] if parent.named_children else None)
    name = _field(parent, name_field)
    return _same(bound, value) and name is not None and not name.is_named


def _follow_local(ref: Node, name: Node, sp: LangSpec, closed_sets: dict[str, int | None],
                  cells: int | None, depth: int) -> Reach:
    """What the state reaches THROUGH a local it was copied into.

    The largest family of unread constructs in the corpus, 194 sites, and it needed a row
    rather than a new kind of silence. The tree carries the binding and this module already
    finds references inside a scope; following a local is that same walk bounded to the
    enclosing function.

    What the tree does NOT carry is whether the copy aliases: `var e = _m` shares the
    object for a reference type and copies it for a value type, and no types are resolved
    here. That matters only for a WRITE through the local reaching the state, so a write
    keeps its own refusal and is not folded into the reads below.

    `depth` bounds the walk. `a = b; b = a` inside one function would otherwise recurse
    forever, and a chain longer than a few hops is not a chain a reader is following either.
    """
    if depth <= 0:
        return state_partition.silence_kind(ref, sp)
    # `scope`, declared as what it becomes: the walk assigns the parent to it and a parent
    # can be nothing, which the line below already tests for and the declaration denied.
    scope: Node | None = ref
    while scope is not None and scope.type not in sp["func_types"]:
        scope = scope.parent
    if scope is None:
        return state_partition.output()   # module level: the binding is its own state
    key = _text(name)
    uses = [n for n in _local_refs(scope, lambda n: n.type == "identifier" and _text(n) == key, ())
            if not _same(n, name)]
    if not uses:
        return state_partition.output()   # bound and never read: the value came to rest
    reaches = [_categorize(u, sp, closed_sets, cells, depth - 1) for u in uses]
    kinds = [r["kind"] for r in reaches]
    if state_partition.UNDECIDED in kinds:
        return next(r for r in reaches if r["kind"] == state_partition.UNDECIDED)
    if state_partition.UNBOUNDED in kinds:
        return state_partition.unbounded()
    finite = [r for r in reaches if r["kind"] == state_partition.FINITE]
    if finite:
        # The widest of them, and that is a stated limit rather than a roll-up. `_categorize`
        # answers with ONE reach per reference, so several uses of one local collapse into
        # one here and the narrower ones are lost. Taking the widest under-counts the state's
        # partition, which is the direction this module takes when it cannot say more.
        return max(finite, key=lambda r: r["classes"])
    return state_partition.output()


def _switch_partition(subject: Node, switch: Node, arm_type: str) -> Reach:
    """The partition a switch cuts in its subject: one class per arm, plus one for the
    values that match no arm when there is no default.

    Unordered on purpose. There is no value "just above" a case label, so limit testing
    buys nothing here and every class costs its own test. That is the distinction the D
    tier rests on, and counting these arms is what lets a switch contribute to it: before
    this the subject was an unread construct and a state whose whole job is selecting
    behaviour contributed no classes at all.

    The key is the switch's own span, so the same switch read twice is one discriminator
    and two different switches on one state are two."""
    arms = [n for n in _refs(switch, lambda n: n.type == arm_type)]
    has_default = any("default" in _text(a).split(":", 1)[0] for a in arms)
    classes = len(arms) + (0 if has_default else 1)
    return state_partition.finite(classes, False, f"switch:{switch.start_byte}")


# How far a value is followed from the state it came from to the decision it reaches.
# Three, because a fourth hop has never changed a verdict on the corpus and the walk is
# quadratic in the reference count.
_REACH_DEPTH = 3


def _categorize(ref: Node, sp: LangSpec, closed_sets: dict[str, int | None], cells: int | None, depth: int) -> Reach:
    """How this single reference to a state value is consumed."""
    parent = ref.parent
    if parent is None:
        return state_partition.output()

    if _is_write_target(ref, parent, sp):
        # A CONDITIONAL ASSIGNMENT IS BOTH HALVES. `@cache[k] ||= compute(k)` tests what is
        # stored at k and stores only if it is absent, so the target is read as surely as it
        # is written. Reading it as a write alone was a false green: the same cache written
        # `@cache[k] = compute(k) unless @cache.key?(k)` came back promiscuous and had to earn
        # its clear through the memoization rule's premises, while this spelling was handed
        # neutral with no premise checked. One operation, two notations, opposite verdicts,
        # and the clean one was the commonest shape in the language.
        #
        # Declared per language because the operators are: Ruby has `||=` and `&&=`,
        # JavaScript and TypeScript add `??=`, C# has `??=` alone, and the rest have none and
        # say so with an empty row rather than by omission.
        if _reads_its_own_target(ref, sp):
            return _categorize_read(ref, sp, closed_sets, cells)
        return state_partition.write()

    # S AS THE NAME HALF OF A MEMBER ACCESS: `other.V = s`, `o.v`, `o->v`. In the three
    # languages whose class state is keyed by a bare identifier, C, C# and Java, a field is
    # enumerated as `v`, so a read of it off ANOTHER receiver puts that identifier on the
    # right of the dot. Every row here was written for the state as the RECEIVER, so the
    # name half fell off the bottom into the unmodeled-construct terminal. It was the
    # largest single shape in the corpus's silence: 173 sites in C# and 142 in Java.
    #
    # The member access IS the reference, so this re-enters the same dispatch one node up
    # rather than deciding anything new. A write to it is a write; anything else flows on
    # exactly as a bare read of the field would. Languages whose state is keyed by the
    # member itself (`self.v`) declare no name field and never reach this row, because for
    # them the member access is what was matched in the first place.
    name_field = sp["member_name_field"]
    if (name_field is not None and parent.type in sp["member_types"]
            and _same(_field(parent, name_field), ref)):
        if _is_write_target(parent, parent.parent, sp):
            return state_partition.write()
        return _flow(parent, sp, closed_sets, cells, depth)

    # THE STATE COPIED INTO A LOCAL. `var entries = _entries;` and then whatever the method
    # does with `entries`. 194 sites in the corpus came out as constructs with no rule, and
    # the rule they needed is this one: follow the local. Sits above the terminal and below
    # the write row, so a local that is itself written keeps the write verdict.
    local = _local_binding_name(ref, sp)
    if local is not None:
        return _follow_local(ref, local, sp, closed_sets, cells, depth)

    # THE STATE IS A SWITCH SUBJECT. Its value selects one arm, and the arms are countable
    # from the tree, so this is the one row here that produces CLASSES rather than merely
    # reading a construct. Java wraps the subject in parentheses, which the value-wrapper
    # peel handles, so the comparison is against the unwrapped node.
    for switch_type, (subject_field, arm_type) in sp["switch_types"].items():
        holder = ref.parent
        while holder is not None and holder.type != switch_type:
            if holder.type not in sp["value_wrapper_types"]:
                holder = None
                break
            holder = holder.parent
        if holder is not None and _same(_unwrap_unary(_field(holder, subject_field), sp), ref):
            return _switch_partition(ref, holder, arm_type)

    # ITERATING THE STATE reads every cell it holds, so its reach is the cell set and
    # nothing wider. `for k := range s.m` had no row anywhere and came back as a construct
    # with no rule, which inflated Go's silence on the plainest loop the language has.
    if parent.type in sp["iterate_types"]:
        if cells is not None:
            return state_partition.finite(cells + 1, False, "cells")
        return state_partition.unbounded()

    # S(...) : the state supplies WHAT RUNS. No arm selector reads its value, so call-target
    # position is compositional exactly as return position is, and the meter neither
    # fail-closes nor assumes: it follows the call RESULT like any other call result (spec
    # section 4). `return S(x)` is output; `if S(x):` is the host's own two arms. The premise
    # checks that make this a proof rather than an assumption are per-attribute, and live in
    # _injected_slot_premise_fails.
    if not sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), ref):
        return _flow(parent, sp, closed_sets, cells, depth)

    # S[x] read : indexed by x. Unbounded key -> unbounded partition.
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        return _keyed_read(_sub_key(parent, sp), sp, cells)

    # S.attr : mutating method -> write; keyed map read -> subscript-like; else flows on.
    # Nested-call languages only; flat-call languages (Java, Ruby) handle receiver.method
    # in the branch below, where the member access and the call are one node.
    through_member = _member_reach(ref, parent, sp, closed_sets, cells, depth)
    if through_member is not None:
        return through_member

    # S.method(args) flattened (Java method_invocation / Ruby call with a receiver).
    if sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_recv"]), ref):
        name = _text(_field(parent, sp["call_name"]))
        if name in sp["dispatch_methods"]:
            return state_partition.undecided(DYNAMIC_DISPATCH)
        if name in sp["mutating"]:
            return state_partition.write()
        if name in sp["keyed_read"]:
            return _keyed_read(_first_arg(parent, sp), sp, cells)
        return _flow(parent, sp, closed_sets, cells, depth)

    # f(..., S, ...) : argument to a call.
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in sp["writing_builtins"]:
            return state_partition.write()      # `delete(m, k)`: removes and returns nothing
        if fname in _BOUNDED_BUILTINS or fname in sp["extra_bounded"]:
            return _flow(parent.parent, sp, closed_sets, cells, depth)
        if fname in _EFFECT_CALLS:
            return state_partition.output()
        return state_partition.silence_kind(parent.parent, sp)

    # Not a write, a call target, a subscript, a member access or an argument: the parent
    # does not CONSUME the value, so the reference is the value itself and the question
    # moves to where that value goes. This is a row of the table, not a fallthrough - the
    # row that says "the host construct is transparent, follow the flow" - and `_flow`
    # below is where the table ends. It matters which of the two is the last one, because
    # only the last one can be the total handler and only one of them can be it.
    return _flow(ref, sp, closed_sets, cells, depth)


def _member_reach(value: Node, parent: Node, sp: LangSpec, closed_sets: dict[str, int | None],
                  cells: int | None, depth: int) -> Reach | None:
    """How a value reaches on when a member access is taken off it, or None when this shape
    is not that.

    `S.attr`: a mutating method is a write, a keyed map read is subscript-like, anything
    else flows on. Nested-call languages only; flat-call languages spell the member access
    and the call as one node and are handled by their own row.

    Read from BOTH ends of a method chain, which is why it is a function. It lived inline in
    `_categorize`, so it decided the first link of `self.map.entry(k).or_default().push(v)`
    and nothing decided the rest: a call RESULT reached through another member access had no
    row anywhere, and every chain longer than one call fell to the total row and came back
    as a construct with no rule.

    That is not a missing case, it is the second half of every chain. A production run over
    a public Rust crate on 2026-08-30 published 88% of read state finitely testable beside
    its own note that 290 of 392 state-keeping places were unread, and this shape was most
    of them.
    """
    if sp["flat_call"] or parent.type not in sp["member_types"]:
        return None
    if not _same(_field(parent, sp["mem_object"]), value):
        return None
    attr = _text(_field(parent, sp["mem_attr"]))
    gp = parent.parent
    called = gp is not None and gp.type in sp["call_types"] and _same(_field(gp, sp["call_fn"]), parent)
    if called and attr in sp["dispatch_methods"]:
        return state_partition.undecided(DYNAMIC_DISPATCH)   # a stored callable: unbounded target
    if called and attr in sp["mutating"]:
        # A mutating call can still hand the value OUT. `_d.Remove(k, out var v)` writes the
        # dictionary AND returns the removed value through `v`, so a rule that stops at the
        # write never sees the branch on it.
        out_local = _out_argument_local(gp, sp)
        if out_local is not None:
            return _follow_local(value, out_local, sp, closed_sets, cells, depth)
        return state_partition.write()
    if called and attr in sp["keyed_read"]:
        return _keyed_read(_first_arg(gp, sp), sp, cells)
    if called:
        return _flow(gp, sp, closed_sets, cells, depth)   # result flows on (.clone(), .len(), an accessor)
    return _flow(parent, sp, closed_sets, cells, depth)   # plain field access: self.x.y


def _flow(node: Node | None, sp: LangSpec, closed_sets: dict[str, int | None], cells: int | None, depth: int) -> Reach:
    """Categorise how a value derived from the state (node) reaches a decision.

    An absent node reaches no decision, and that is the same answer as a node with nothing
    above it: the value goes out of the function. This declared that it takes an absent node
    and asked it for its parent on the next line."""
    if node is None:
        return state_partition.output()
    parent = node.parent
    if parent is None:
        return state_partition.output()
    if parent.type in sp["return_types"]:
        return state_partition.output()
    # The value comes to rest. Either the language DISCARDS it - `app.add_middleware(x)` as a
    # statement, whose result nobody reads - or the language hands it back with no keyword,
    # which is what the tail expression of a Ruby body and of a Rust block is. Both reach no
    # arm selector, which is the conclusion the row above draws for a spelled `return`, so
    # they sit together. Written as a row because the total handler below exposed that this
    # was one of four rules the old fallthrough was carrying without being asked.
    if parent.type in sp["sink_types"]:
        return state_partition.output()
    # A PATTERN TESTED AGAINST THIS VALUE, which binds on success: `if let Some(v) = x`. The
    # pattern matches or it does not, which is the same two-class split this reader draws
    # for a plain condition, so it shares that key. The branch's own condition field holds
    # the let-condition node rather than the value inside it, so the truthiness row below
    # never sees this and thirteen sites on crates/buzz-acp came back with no rule.
    if parent.type in sp["binding_condition_types"]:
        return state_partition.finite(2, True, "truthy")
    # THE VALUE COMES TO REST in a shape that is not an assignment: `Reply { body: x }`. The
    # assignment row further down draws this conclusion for a value stored in a binding, and
    # a record literal stores it just as finally.
    if parent.type in sp["resting_types"]:
        return state_partition.output()
    # A SWITCH SUBJECT REACHED BY A DERIVED VALUE: `match self.child.id() { .. }`. The
    # categoriser has this rule for the state itself and nothing had it for a value derived
    # from the state, which is the commoner of the two: five sites on that crate, and the
    # arms are countable from the tree either way.
    for switch_type, (subject_field, arm_type) in sp["switch_types"].items():
        if parent.type == switch_type and _same(_unwrap_unary(_field(parent, subject_field), sp), node):
            return _switch_partition(node, parent, arm_type)
    # The state value itself is invoked as a callable, possibly through a wrapper:
    # `(self.f)(x)` in Rust reaches the call via a parenthesized_expression. Same rule as
    # direct `S(x)` in _categorize: follow the call result, do not fail-close.
    # A call RESULT being invoked is method-chaining, not state dispatch: `app.get(p)
    # (handler)` (the decorator idiom in call form) calls what app.get returns,
    # not app - so exclude nodes that are themselves a call.
    if (not sp["flat_call"] and node.type not in sp["call_types"]
            and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), node)):
        return _flow(parent, sp, closed_sets, cells, depth)
    # A MEMBER ACCESS TAKEN OFF THIS VALUE, which is the other half of every method chain.
    # The row above walks from a field access to the call it supplies; this walks from a
    # call result to the next field access, and without it a chain of two calls had a rule
    # for its first link and none for its second. The same rule decides both, so it is asked
    # here rather than written twice: a mutating method is a write wherever it appears, and
    # a keyed read asks about one cell whether it is the first link or the fourth.
    #
    # It sits above the rows that store, alias and pass through, because those ask what
    # happens to a value and this asks what is taken off it, and a chain is the second
    # question before it is ever the first.
    through_member = _member_reach(node, parent, sp, closed_sets, cells, depth)
    if through_member is not None:
        return through_member
    # THE TWO ROWS THE COMMENT ABOVE PROMISED AND NOBODY WROTE. It excludes the call form
    # deliberately and correctly, but excluding a shape from one row is not the same as
    # handling it, and until 2026-08-17 both forms fell through to the total row. That is why
    # the honest-framework reference server came back unresolved on its own route table:
    # `@app.get("/")` is the whole of what that server does with `app`.
    #
    # Both spellings reach the same conclusion. The state is consumed by the inner call, and
    # what comes back is a registrar applied to a definition. `app` never reaches an arm
    # selector: nothing branches on it, compares it, or keys a lookup with it. Registration is
    # an effect, which is the conclusion `sink_types` already draws for `app.add_middleware(x)`
    # written as a bare statement.
    if parent.type in sp["decorator_types"]:      # @app.get("/")
        return state_partition.output()
    if (not sp["flat_call"] and node.type in sp["call_types"]        # app.get(p)(handler)
            and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), node)):
        return state_partition.output()
    # THE VALUE IS STORED. `n._qs = self._qs.filter(**kw)`: a derived value comes to rest in a
    # binding, reaching no arm selector at this site. That is the same conclusion `sink_types`
    # draws for a value the language discards, and the difference between "stored" and
    # "discarded" is not one this row has to settle: neither selects an arm.
    #
    # Read through `assign_right`, which every language has declared since the spec was
    # written and which nothing read until now. That is why this row was missing rather than
    # wrong: the walk had a field for the value half of an assignment and no rule that used
    # it, so it reached the total row and reported `call in assignment` honestly.
    #
    # Whether the attribute as a whole then clears is not decided here. It is the carried-value
    # rule in state_bounds_filters that reads every reference together, and it needs this site
    # to resolve rather than to fail closed, because an unresolved site suppresses the whole
    # attribute regardless of what the other references say.
    # A DESTRUCTURING TARGET is excluded, and finding out why cost a red test. `first, *rest =
    # self.row` takes the value APART rather than storing it, and a starred target takes an
    # unbounded slice of it, so the two are not the same question. This row first claimed that
    # shape as clean and broke test_unmeasured_constructs, which exists to hold exactly this
    # line: a construct with no rule must read as unmeasured, never as clean. Destructuring
    # forms are declared per language and an unlisted one falls to the total row, which is the
    # honest direction to be wrong in.
    left = _field(parent, sp["assign_left"])
    if (parent.type in sp["assign_types"] and _same(_field(parent, sp["assign_right"]), node)
            and (left is None or left.type not in sp["destructuring_types"])):
        return state_partition.output()
    # THE VALUE IS HANDED OUT UNDER ANOTHER NAME, and that name can be written through:
    # `let r = &mut self.v; r.push(1);`. Every rule below and every rule in
    # state_bounds_filters argues from where this state's OWN references sit, and from this
    # line on there is a write that none of them contains. So the walk stops and says so.
    #
    # It sits ABOVE the wrapper row because Rust's reference_expression is on the wrapper
    # list, correctly: `&self.v` is a shared borrow and cannot be written through. Only the
    # mutability marker separates the two, so the order here is the rule.
    #
    # An UNRESOLVED verdict is also what keeps the clearing rules off it. Write-once is the
    # only rule allowed to clear an UNRESOLVED, and it is Python-only; when it is widened to
    # a language that spells a mutable alias, the alias check is the premise it needs.
    if _same(_mutable_alias_value(parent, sp), node):
        return state_partition.undecided(state_partition.MUTABLE_ALIAS)
    # A DERIVED VALUE BOUND TO A LOCAL: `var n = _m.Count;`. The row in _categorize catches
    # the state bound straight to a local; this catches it bound after passing through
    # something, which is the commoner half. Both hand off to the same walk.
    local = _local_binding_name(node, sp)
    if local is not None:
        return _follow_local(node, local, sp, closed_sets, cells, depth)
    # BOUND TO NOTHING: `let _ = self.deadline.take()`. The grammar hangs no pattern on that
    # declaration at all, so the reader above answers None and cannot say whether the value
    # went into a name it could follow or into the discard. An ABSENT pattern is the
    # discard; a pattern that is present and is not a plain name is destructuring, which
    # takes the value apart and is a different question this reader leaves to the total row.
    if _bound_to_the_discard(node, sp):
        return state_partition.output()

    # THE OPERAND IS NOT READ. `sizeof(state)` and `typeof(state)` ask about the TYPE at
    # compile time and never look at the value, so the state reaches no decision through
    # them and costs no test. Reporting them as unread said we could not tell, when there
    # is nothing there to tell.
    if parent.type in sp["unread_operand_types"]:
        return state_partition.output()

    # A transparent wrapper, EXCEPT where the operator consumes rather than wraps. Go spells
    # a channel receive `<-ch`, which is a unary_expression exactly as `-x` is, and
    # unary_expression is on the wrapper list. So a receive read as the channel flowing on
    # untouched, when what happens is that an element leaves the channel. Dropping the node
    # type from the list would take `-x` with it, so the operator is what decides.
    if parent.type in sp["passthrough_types"] and not _is_opaque_unary(parent, sp):
        return _flow(parent, sp, closed_sets, cells, depth)
    # The host WRITES this value where it stands: `n++`, `c.n++`, `@xs << x`. The host is
    # transparent for the flow, because it also produces a value and that value may still
    # reach a decision - `if (n++ > 3)` is a comparison whichever way the counter moves. The
    # row below settles what happens when nothing reads what the host produced.
    if _same(_written_in_place(parent, sp), node):
        return _flow(parent, sp, closed_sets, cells, depth)
    if parent.type in sp["comparison_types"]:
        mem = _membership_operands(parent, sp)
        if mem is not None:
            left, right = mem
            if _same(node, right):          # x in S : node is the container
                # The container is asked whether it holds one value: two classes, and no
                # boundary between "holds it" and "does not". A closed container answers the
                # same way, so the size of the container is not what is being split here.
                if _is_closed_set(node, closed_sets) or not _is_unbounded_value(left, sp):
                    # SAME discriminator as the subscript read of that key. `"a" in S` and
                    # `S["a"]` ask about one cell: one asks whether it is there, the other
                    # what is in it, and both cut the partition at that key and nowhere else.
                    # Keying them apart made `if "a" in S: return S["a"]`, the commonest
                    # table idiom there is, count every key twice: two keys read both ways
                    # reported five classes where three is the count.
                    #
                    # The merge is by key TEXT, so distinct keys stay distinct cuts. It is
                    # wrong for a sequence, where `1 in xs` asks about a value and `xs[1]`
                    # about a position, and merging those under-counts. That direction is
                    # the one this module already declares safe for a measure that only
                    # accuses, and the over-count it replaces was not.
                    return state_partition.finite(2, False, _cell_key(left))
                return state_partition.unbounded()
            if _is_closed_set(right, closed_sets):                                 # S in FIXED
                return state_partition.membership_reach(right, closed_sets)
            return state_partition.unbounded()
        if _is_comparison(parent, sp):
            # S <cmp> constant: the constant is a cut in an ordered domain, and n distinct
            # cuts leave n+1 intervals that boundary values reach. Keyed on the comparison
            # text so the same cut written twice is one cut, not two.
            return state_partition.finite(2, True, f"cmp:{_text(parent)}")
        return _flow(parent, sp, closed_sets, cells, depth)   # arithmetic / logical: derived value flows on
    # Truthiness is the SAME two-class split wherever it is written, so every site shares
    # one key: `if S:` in fifty methods is two classes, not fifty-one.
    if parent.type in sp["branch_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return state_partition.finite(2, True, "truthy")
    if parent.type in sp["elif_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return state_partition.finite(2, True, "truthy")
    # The same two-class split, in a branch that names no condition field. Go's `for` holds
    # its condition as a bare first child, so the row above reads nothing there whatever the
    # node type says, and `for p.running {}` was a loop on a bool field that came back as a
    # construct with no rule. It is the same discriminator and shares the same key.
    if _same(_bare_condition(parent, sp), node):
        return state_partition.finite(2, True, "truthy")
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in sp["writing_builtins"]:
            return state_partition.write()      # `delete(m, k)`: removes and returns nothing
        if fname in _BOUNDED_BUILTINS or fname in sp["extra_bounded"]:
            return _flow(parent.parent, sp, closed_sets, cells, depth)
        if fname in _EFFECT_CALLS:
            return state_partition.output()
        return state_partition.silence_kind(parent.parent, sp)
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), node):
        return _keyed_read(_sub_key(parent, sp), sp, cells)
    # THE VALUE AN IN-PLACE WRITE PRODUCED, WHICH NOTHING READS. Every row above has now been
    # offered it and declined, so `c.n++` standing alone as a statement, and `@xs << x` in a
    # modifier arm, are writes and nothing more. This sits at the bottom rather than beside
    # the transparent-host row on purpose: putting it higher would swallow `if (n++ > 3)`,
    # where the produced value is exactly what the branch decides on.
    if _written_in_place(node, sp) is not None:
        return state_partition.write()
    # THE TOTAL ROW. Every row above declined, so no rule in this table describes how this
    # construct consumes the value, and the handler says exactly that and stops. It used to
    # be `output()`, which is a verdict: compositional, reaches no decision, costs no tests.
    # That is how a `match` on a piece of state, a walrus in a condition and a comprehension
    # source came back neutral with an empty silence field - not unhandled, cleared. The
    # handler is handed two node types and nothing else, so it has no verdict available to
    # reach for; see state_partition.unmeasured for why that placement is the point.
    return state_partition.unmeasured(node.type, parent.type)


def _is_call_target(ref: Node, sp: LangSpec) -> bool:
    """This reference supplies what runs at a call site: `S(...)`, `await S(...)`."""
    parent = ref.parent
    if parent is None or sp["flat_call"]:
        return False
    return parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), ref)


def _written_through(ref: Node, sp: LangSpec) -> bool:
    """The host reaches INTO the value: `S.attr = v`, or a mutating method on S. Either way
    the host depends on the collaborator's internal shape, which it cannot enumerate."""
    parent = ref.parent
    if parent is None or parent.type not in sp["member_types"] or not _same(_field(parent, sp["mem_object"]), ref):
        return False
    if _is_lvalue(parent, sp):
        return True                                   # S.attr = v
    gp = parent.parent
    called = gp is not None and gp.type in sp["call_types"] and _same(_field(gp, sp["call_fn"]), parent)
    return called and _text(_field(parent, sp["mem_attr"])) in sp["mutating"]


def _injected_slot_premise_fails(refs: list[Node], sp: LangSpec, instance: bool) -> bool:
    """Call-target position is compositional only while the value at the call site is
    provably the value that was injected (spec section 4). Three constructs defeat that
    proof, and all three are per-attribute, so none can be seen one reference at a time.

    Not instance state: a module-level invoked slot (a C function pointer, a module global
    holding a callable) has a writer set that is not enumerable at all - any translation
    unit can assign it. Only instance state has the property the spec's scope rule relies
    on, that its writers are the methods of its own class. Rebinding: more than one binding
    site means which callee is live at the call depends on invisible history, the runtime
    rebinding of dispatch that honest-test section 4.8 rejects. Reaching in: writing through
    the slot means the collaborator is no longer a black box behind its contract."""
    if not any(_is_call_target(r, sp) for r in refs):
        return False
    if not instance:
        return True
    if sum(1 for r in refs if _is_lvalue(r, sp)) > 1:
        return True
    return any(_written_through(r, sp) for r in refs)


def _verdict(reaches: list[Reach], refs: list[Node]) -> tuple[str, bool, str, str, Partition, int]:
    """Combine per-reference reaches into (verdict, drives_decision, silence, construct,
    partition).

    `refs` is required. It defaulted to None, the one production caller always passes it,
    and no test took the default: a second path kept alive by its own signature, and the
    one where the silence reason has no reference to point at.

    The silence reason reported is the FIRST undecided reference in source order, not the
    worst of them by some ranking.

    Its LINE travels with it too, and that was missing. The construct was picked from this
    reference while the site published the state's binding line, so the report named a shape
    at a line that does not hold it. The paragraph below already says why they must agree;
    the finding simply carried the wrong one of the two. Any ranking would be invented here, and the reader's next
    move is to open the site, so the site that comes first is the one to send them to. The
    construct travels with that same reference for the same reason: it names the shape at
    the site the reader is being sent to, and picking it from a different reference would
    send them to one place and describe another."""
    kinds = [r["kind"] for r in reaches]
    silent = [(i, r) for i, r in enumerate(reaches) if r["kind"] == state_partition.UNDECIDED]
    if silent:
        index, reach = silent[0]
        line = refs[index].start_point[0] + 1 if refs is not None and index < len(refs) else 0
        return UNRESOLVED, True, reach["silence"], reach["construct"], state_partition.UNKNOWN, line
    if state_partition.UNBOUNDED in kinds:
        return PROMISCUOUS, True, "", "", state_partition.UNKNOWN, 0
    if state_partition.FINITE in kinds:
        return NEUTRAL, True, "", "", state_partition.roll_up(reaches), 0
    # observe-only or output-only: empty reaching-set, so one class and nothing to cover
    return NEUTRAL, False, "", "", state_partition.EMPTY, 0
