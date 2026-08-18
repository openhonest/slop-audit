"""
L1.18b - finite-testability classifier (gated, additive refinement of L1.18).

Implements the shared predicate in
~/dev/honest/open-honest/honest-framework/specs/finite-testability.md:

  A piece of state is testability-neutral iff the production decisions reaching it
  partition its domain into a statically-enumerable finite set of equivalence
  classes. PARTITION-COUNT, not value-count: an int that only meets comparisons
  against constants is cheap; a value used as an unbounded lookup key is not.

Every piece of state resolves to exactly one of three verdicts, and to whether it
drives a decision, so the coverage matrix (spec section 7) can be published:

  NEUTRAL     - reaching partition is a statically-enumerable finite set (or empty)
  PROMISCUOUS - reaching partition is provably unbounded (a proven finding)
  UNRESOLVED  - reaching-set undecidable within scope; fail-closed, disclosed

Design guarantees:
  - Additive. Never touches L1.18's value/band. Runs only when the caller opts in
    (classify_state_bounds=True), off for the pre-registered experiments.
  - Analysis scope is the class or module, not the function (spec section 4):
    instance state is analysed across all methods of its class.
  - Returns are output, not promiscuity. Fail-close (UNRESOLVED) only on a value
    passed to an unbounded call target or reflective/dynamic access.

The predicate is language-neutral; the AST node types that express it are not. A
per-language LANG_SPEC maps the shared vocabulary (assignment, subscript, member
access, membership, dynamic dispatch) onto each grammar's node types, so the same
partition-count reasoning runs over Python, TypeScript, Java and C#. Immutable-
constant and closed-set recognition (frozenset / MappingProxyType machines) remain
Python-only refinements; the other languages simply resolve fewer states to NEUTRAL
by that route, which is conservative (never a false green). Languages with no spec
return n/a rather than guess.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer import (
    record_state,
    state_bounds_filters,
    state_census,
    state_enum,
    state_partition,
)
from l1_analyzer.indicators import (
    LANG_CFG,
    LangCfg,
    _get_parser,
    _read_source_bytes,
    bucketed_paths,
)
from l1_analyzer.lang_spec import _PY_MUTATING, COMPARISON_OPS, LANG_SPEC, LangSpec
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.state_cells import collect_closed_sets as _collect_closed_sets
from l1_analyzer.state_cells import is_closed_set as _is_closed_set
from l1_analyzer.state_cells import is_unbounded_value as _is_unbounded_value
from l1_analyzer.state_cells import keyed_read as _keyed_read
from l1_analyzer.state_cells import membership_operands as _membership_operands
from l1_analyzer.state_cells import write_key_bound as _write_key_bound
from l1_analyzer.state_partition import (
    DYNAMIC_DISPATCH,
    INJECTED_SLOT,
    Partition,
    Reach,
)
from l1_analyzer.state_sites import Site
from l1_analyzer.ts_nodes import arg_value as _arg_value
from l1_analyzer.ts_nodes import bare_condition as _bare_condition
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_named as _first_named
from l1_analyzer.ts_nodes import hidden_names as _hidden_names
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
from l1_analyzer.ts_nodes import written_in_place as _written_in_place

NEUTRAL = "neutral"
PROMISCUOUS = "promiscuous"
UNRESOLVED = "unresolved"

# Builtins that read a bounded feature of their argument (the value flows onward).
_BOUNDED_BUILTINS = frozenset({"len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"})
# Builtins that consume a value as an effect/assertion, not a partitioning decision.
_EFFECT_CALLS = frozenset({"print", "repr", "str", "format", "log", "logging"})
# Comparison operators: a state value meeting one is split into finitely many classes. The
# set moved to lang_spec so state_bounds_filters can read the same one; the name stays here
# so every call site below reads as it did.
_COMPARISON_OPS = COMPARISON_OPS


class Finding(TypedDict):
    """One piece of state and its verdict. Fixed keys, so a TypedDict, not a bag.

    `silence` carries why the reaching-set could not be decided, and is the empty string
    on every decided finding. It is on the finding rather than in a parallel list because
    a silent site and its verdict are one fact, and two lists drift. `construct` names the
    syntax shape when the reason is that no dispatch row covered it, and is empty for every
    other reason: a missing rule the reader cannot name is a complaint, not a backlog."""
    state: str
    verdict: str
    drives_decision: bool
    file: str
    line: int
    silence: str
    construct: str
    partition: Partition


def _first_arg(call: Node | None, sp: LangSpec) -> Node | None:
    return _arg_value(_first_named(_field(call, sp["call_args"])))


def _callee_name(call: Node | None, sp: LangSpec) -> str:
    if call is None or call.type not in sp["call_types"]:
        return ""
    return _text(_field(call, sp["call_name"] if sp["flat_call"] else sp["call_fn"]))


# --------------------------------------------------------------------------
# Closed-set detection (Python only). Membership `x in S` is a finite partition
# when S is a statically fixed collection. Element *values* are irrelevant to the
# count: a tuple of symbolic constants bounds the partition exactly as literals do.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Membership and comparison helpers.
# --------------------------------------------------------------------------

# Every spelling of a membership operator, as tree-sitter TOKENISES it. `not in` is one
# token of type "not in", not a `not` wrapping an `in`, so matching only "in" missed the
# negated form entirely. It then fell through to the comparison arm and was graded finite
# and ORDERED, which inverted the verdict: `key in store` graded the repository F and
# `key not in store` graded it A. One word, semantics unchanged, and no disclosure.
def _is_comparison(node: Node | None, sp: LangSpec) -> bool:
    if node.type == "comparison_operator":       # Python: always a comparison
        return True
    return _text(_field(node, "operator")) in _COMPARISON_OPS


# --------------------------------------------------------------------------
# Per-reference categorisation.
# --------------------------------------------------------------------------

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


def _categorize(ref: Node, sp: LangSpec, closed_sets: dict[str, int | None], cells: int | None) -> Reach:
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

    # S(...) : the state supplies WHAT RUNS. No arm selector reads its value, so call-target
    # position is compositional exactly as return position is, and the meter neither
    # fail-closes nor assumes: it follows the call RESULT like any other call result (spec
    # section 4). `return S(x)` is output; `if S(x):` is the host's own two arms. The premise
    # checks that make this a proof rather than an assumption are per-attribute, and live in
    # _injected_slot_premise_fails.
    if not sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), ref):
        return _flow(parent, sp, closed_sets, cells)

    # S[x] read : indexed by x. Unbounded key -> unbounded partition.
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        return _keyed_read(_sub_key(parent, sp), sp, cells)

    # S.attr : mutating method -> write; keyed map read -> subscript-like; else flows on.
    # Nested-call languages only; flat-call languages (Java, Ruby) handle receiver.method
    # in the branch below, where the member access and the call are one node.
    if not sp["flat_call"] and parent.type in sp["member_types"] and _same(_field(parent, sp["mem_object"]), ref):
        attr = _text(_field(parent, sp["mem_attr"]))
        gp = parent.parent
        called = gp is not None and gp.type in sp["call_types"] and _same(_field(gp, sp["call_fn"]), parent)
        if called and attr in sp.get("dispatch_methods", frozenset()):
            return state_partition.undecided(DYNAMIC_DISPATCH)   # a stored callable: unbounded target
        if called and attr in sp["mutating"]:
            return state_partition.write()
        if called and attr in sp["keyed_read"]:
            return _keyed_read(_first_arg(gp, sp), sp, cells)
        if called:
            return _flow(gp, sp, closed_sets, cells)     # method result flows on (.clone(), .len(), an accessor)
        return _flow(parent, sp, closed_sets, cells)     # plain field access: self.x.y

    # S.method(args) flattened (Java method_invocation / Ruby call with a receiver).
    if sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_recv"]), ref):
        name = _text(_field(parent, sp["call_name"]))
        if name in sp.get("dispatch_methods", frozenset()):
            return state_partition.undecided(DYNAMIC_DISPATCH)
        if name in sp["mutating"]:
            return state_partition.write()
        if name in sp["keyed_read"]:
            return _keyed_read(_first_arg(parent, sp), sp, cells)
        return _flow(parent, sp, closed_sets, cells)

    # f(..., S, ...) : argument to a call.
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets, cells)
        if fname in _EFFECT_CALLS:
            return state_partition.output()
        return state_partition.silence_kind(parent.parent, sp)

    # Not a write, a call target, a subscript, a member access or an argument: the parent
    # does not CONSUME the value, so the reference is the value itself and the question
    # moves to where that value goes. This is a row of the table, not a fallthrough - the
    # row that says "the host construct is transparent, follow the flow" - and `_flow`
    # below is where the table ends. It matters which of the two is the last one, because
    # only the last one can be the total handler and only one of them can be it.
    return _flow(ref, sp, closed_sets, cells)


def _flow(node: Node | None, sp: LangSpec, closed_sets: dict[str, int | None], cells: int | None) -> Reach:
    """Categorise how a value derived from the state (node) reaches a decision."""
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
    # The state value itself is invoked as a callable, possibly through a wrapper:
    # `(self.f)(x)` in Rust reaches the call via a parenthesized_expression. Same rule as
    # direct `S(x)` in _categorize: follow the call result, do not fail-close.
    # A call RESULT being invoked is method-chaining, not state dispatch: `app.get(p)
    # (handler)` (the decorator idiom in call form) calls what app.get returns,
    # not app - so exclude nodes that are themselves a call.
    if (not sp["flat_call"] and node.type not in sp["call_types"]
            and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), node)):
        return _flow(parent, sp, closed_sets, cells)
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
    # A transparent wrapper, EXCEPT where the operator consumes rather than wraps. Go spells
    # a channel receive `<-ch`, which is a unary_expression exactly as `-x` is, and
    # unary_expression is on the wrapper list. So a receive read as the channel flowing on
    # untouched, when what happens is that an element leaves the channel. Dropping the node
    # type from the list would take `-x` with it, so the operator is what decides.
    if parent.type in sp["passthrough_types"] and not _is_opaque_unary(parent, sp):
        return _flow(parent, sp, closed_sets, cells)
    # The host WRITES this value where it stands: `n++`, `c.n++`, `@xs << x`. The host is
    # transparent for the flow, because it also produces a value and that value may still
    # reach a decision - `if (n++ > 3)` is a comparison whichever way the counter moves. The
    # row below settles what happens when nothing reads what the host produced.
    if _same(_written_in_place(parent, sp), node):
        return _flow(parent, sp, closed_sets, cells)
    if parent.type in sp["comparison_types"]:
        mem = _membership_operands(parent, sp)
        if mem is not None:
            left, right = mem
            if _same(node, right):          # x in S : node is the container
                # The container is asked whether it holds one value: two classes, and no
                # boundary between "holds it" and "does not". A closed container answers the
                # same way, so the size of the container is not what is being split here.
                if _is_closed_set(node, closed_sets) or not _is_unbounded_value(left, sp):
                    return state_partition.finite(2, False, f"holds:{_text(left)}")
                return state_partition.unbounded()
            if _is_closed_set(right, closed_sets):                                 # S in FIXED
                return state_partition.membership_reach(right, closed_sets)
            return state_partition.unbounded()
        if _is_comparison(parent, sp):
            # S <cmp> constant: the constant is a cut in an ordered domain, and n distinct
            # cuts leave n+1 intervals that boundary values reach. Keyed on the comparison
            # text so the same cut written twice is one cut, not two.
            return state_partition.finite(2, True, f"cmp:{_text(parent)}")
        return _flow(parent, sp, closed_sets, cells)   # arithmetic / logical: derived value flows on
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
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets, cells)
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


def _verdict(reaches: list[Reach]) -> tuple[str, bool, str, str, Partition]:
    """Combine per-reference reaches into (verdict, drives_decision, silence, construct,
    partition).

    The silence reason reported is the FIRST undecided reference in source order, not the
    worst of them by some ranking. Any ranking would be invented here, and the reader's next
    move is to open the site, so the site that comes first is the one to send them to. The
    construct travels with that same reference for the same reason: it names the shape at
    the site the reader is being sent to, and picking it from a different reference would
    send them to one place and describe another."""
    kinds = [r["kind"] for r in reaches]
    silent = [r for r in reaches if r["kind"] == state_partition.UNDECIDED]
    if silent:
        return UNRESOLVED, True, silent[0]["silence"], silent[0]["construct"], state_partition.UNKNOWN
    if state_partition.UNBOUNDED in kinds:
        return PROMISCUOUS, True, "", "", state_partition.UNKNOWN
    if state_partition.FINITE in kinds:
        return NEUTRAL, True, "", "", state_partition.roll_up(reaches)
    # observe-only or output-only: empty reaching-set, so one class and nothing to cover
    return NEUTRAL, False, "", "", state_partition.EMPTY


# --------------------------------------------------------------------------
# State enumeration and file analysis.
# --------------------------------------------------------------------------

# Node types whose subtree is a module path rather than a value: `from app.auth import X`
# names a package, not the variable `app` defined below it. Matching on identifier text
# alone made the two the same state.
_IMPORT_PATH_TYPES = ("import", "using_directive", "package_declaration", "package_clause")


def _under_import_path(node: Node) -> bool:
    """True when the identifier is part of an import or package path, so it binds nothing
    here and is not a reference to same-named state."""
    parent = node.parent
    while parent is not None:
        if any(marker in parent.type for marker in _IMPORT_PATH_TYPES):
            return True
        parent = parent.parent
    return False


def _shadowing_scope(node: Node, key: str, sp: LangSpec) -> Node | None:
    """The nearest enclosing function that BINDS `key` itself, or None.

    A parameter named `app` and a module variable named `app` are different objects, and
    the classifier treated them as one because their text matched. A reference inside a
    function whose own parameter list declares that name belongs to the parameter, so it
    is not evidence about the module variable. Ablation that isolated this: renaming the
    parameter, and changing nothing else, flipped the file's verdict.

    Only the parameter list is consulted. A local assignment shadows too, in Python and
    in most of the nine, but the rules diverge per language (Python's `global`, Ruby's
    block scoping), and a parameter is unambiguous everywhere. Narrow on purpose."""
    parent = node.parent
    while parent is not None:
        if parent.type in sp["func_types"]:
            for params in parent.children:
                if params.type not in sp.get("arglist_types", ()) and "param" not in params.type:
                    continue
                for declared in _refs(params, lambda n: n.type == "identifier"):
                    if _text(declared) == key:
                        return parent
        parent = parent.parent
    return None


def _bound_to(refs: list[Node], key: str, sp: LangSpec) -> list[Node]:
    """The references that actually denote `key`, dropping the two ways a matching name
    does not: it names a package, or a nearer parameter binds it.

    Both collection sites go through this. Module state and class state used to collect
    references separately, so a filter applied to one silently missed the other."""
    return [n for n in refs
            if not _under_import_path(n) and _shadowing_scope(n, key, sp) is None]


def _state_refs(scope: Node, key: str, sp: LangSpec) -> list[Node]:
    stop = sp["class_types"]
    if sp["instance_enum"] == "ruby_ivar":
        return _local_refs(scope, lambda n: n.type == "instance_variable" and _text(n) == key, stop)
    if sp["instance_ref_style"] == "member":
        return _local_refs(scope, lambda n: n.type in sp["member_types"] and _text(n) == key, stop)
    hits = _local_refs(scope, lambda n: n.type == "identifier" and _text(n) == key, stop)
    return _bound_to(hits, key, sp)


# --- immutable-constant recognition (Python only) ---------------------------
# A state key assigned once from an immutable construction, never mutated and never
# called, has a one-value domain: it is a constant, NEUTRAL wherever it flows,
# because no callee can mutate an immutable value. A one-level follow of the
# constructor tells the meter its return is immutable, so a declared machine (a
# MappingProxyType-wrapped table passed to a lookup) resolves on the evidence,
# reading no framework declaration.

_IMMUTABLE_WRAPPERS = frozenset({"MappingProxyType", "frozenset", "tuple", "bytes"})


def _rhs_is_immutable(rhs: Node | None, immutable_ctors: set[str]) -> bool:
    if rhs is None:
        return False
    if rhs.type in ("tuple", "true", "false", "none", "integer", "float", "string", "concatenated_string"):
        return True
    if rhs.type == "call":
        fn = _text(_field(rhs, "function"))
        return fn in _IMMUTABLE_WRAPPERS or fn in immutable_ctors
    return False


def _returns_immutable(func_node: Node) -> bool:
    returns = _refs(func_node, lambda n: n.type == "return_statement")
    if not returns:
        return False
    for r in returns:
        val = _first_named(r)
        if not _rhs_is_immutable(val, frozenset()):
            return False
    return True


def _collect_immutable_ctors(root: Node) -> set[str]:
    out: set[str] = set()
    for fn in _refs(root, lambda n: n.type == "function_definition"):
        name = _field(fn, "name")
        if name is not None and _returns_immutable(fn):
            out.add(_text(name))
    return out


def _reaches_decision(refs: list[Node], sp: LangSpec) -> bool:
    for r in refs:
        p = r.parent
        if p is None or p.type in sp["return_types"]:
            continue
        if _is_write_target(r, p, sp):
            continue
        return True
    return False


def _immutable_const_verdict(refs: list[Node], immutable_ctors: set[str], sp: LangSpec) -> tuple[str, bool] | None:
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
    if not _rhs_is_immutable(_field(assigns[0], "right"), immutable_ctors):
        return None
    return NEUTRAL, _reaches_decision(refs, sp)


def _binding_line(refs: list[Node], sp: LangSpec) -> int:
    """The line where the state is BOUND, not the first line its name appears on.

    The earliest reference is the wrong answer and it sends a reader to the wrong place.
    A module named `app` makes `from app.auth import X` on line 2 the first textual
    occurrence of the name, so a finding about the variable `app = FastAPI()` on line 4
    was reported against an import statement that binds nothing. On the repository that
    surfaced this, the reader was sent to line 19 for an object defined on line 113.

    So prefer the earliest reference that is an assignment target, using the same
    `_is_lvalue` the classifier already uses to decide what a write is. Falling back to
    the earliest reference keeps a line for state that is never assigned in this file,
    which is the case for an injected or inherited name.

    This changes no verdict and no count. It changes only where the reader is sent, which
    is the whole value of a finding they are meant to act on."""
    bindings = [r.start_point[0] + 1 for r in refs if _is_lvalue(r, sp)]
    if bindings:
        return min(bindings)
    return min((r.start_point[0] + 1 for r in refs), default=1)


def _finding(key: str, refs: list[Node], rel: str, sp: LangSpec, closed_sets: dict[str, int | None], immutable_ctors: set[str], instance: bool, hidden: frozenset[str]) -> Finding:
    const = _immutable_const_verdict(refs, immutable_ctors, sp) if sp is LANG_SPEC["python"] else None
    if const is not None:
        # An immutable constant has a one-value domain, so its partition is one class.
        verdict, drives, silence, construct, partition = (*const, "", "", state_partition.EMPTY)
    else:
        # Computed ONCE over every reference and handed to each, because the bound is a
        # fact about the state and not about the reference being judged. Per-reference
        # judgement is what let a read report unbounded while the writes it reads from
        # could only ever fill two cells.
        cells = _write_key_bound(refs, sp, closed_sets)
        verdict, drives, silence, construct, partition = _verdict(
            [_categorize(r, sp, closed_sets, cells) for r in refs])
        # An invoked slot earns NEUTRAL from the compositional rule; that rule has premises.
        if verdict == NEUTRAL and _injected_slot_premise_fails(refs, sp, instance):
            verdict, drives, silence, construct, partition = (
                UNRESOLVED, True, INJECTED_SLOT, "", state_partition.UNKNOWN)
    # Attribute-level false-positive filter: the per-reference verdict conflates unbounded
    # data with an unbounded decision. Clear a finding to NEUTRAL only when the attribute is
    # a provable write-once, memoization cache, carried-value or write-only-accumulator
    # shape. The filter is handed the spec and decides for itself which of its rules this
    # language can carry - the accumulator rule serves all nine, the other three are still
    # Python-only - so the language gate lives with the rules rather than at the call site,
    # where it used to withhold every rule from eight languages without saying so.
    if verdict != NEUTRAL and state_bounds_filters.is_false_positive(key, refs, verdict, sp):
        verdict, drives, silence, construct, partition = NEUTRAL, False, "", "", state_partition.EMPTY
    # THE READING WAS INCOMPLETE, and this is the last word on the finding for that reason.
    # `hidden` holds the names that appear inside a region the grammar handed back as tokens,
    # so a reference in one of them was never built and no walk above could have reached it.
    # Every line above ran on the references that WERE built, which is a proper subset, and a
    # verdict from a subset - most of all a NEUTRAL one a filter just cleared - would report
    # what was not looked at as what was read and found clean. It sits after the filter
    # rather than before it so that no rule can clear it back.
    if key.rsplit(".", 1)[-1] in hidden:
        verdict, drives, silence, construct, partition = (
            UNRESOLVED, True, state_partition.UNPARSED_REGION, "", state_partition.UNKNOWN)
    return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel,
            "line": _binding_line(refs, sp), "silence": silence, "construct": construct,
            "partition": partition}


class FileRead(TypedDict):
    """What the classifier made of one file, and what it walked to get there.

    `visited` and `judged` are the two halves the old coverage number could not separate.
    `visited` is every declaration the enumerators reached, admitted or declined; `judged` is
    the subset that yielded a state key which then reached a verdict. A declaration in neither
    is one nothing looked at, and only that is a gap in the reading.

    They are sets of census-vocabulary sites, not counts, because the comparison happens
    against the census's own per-file site set and a count cannot be intersected."""
    findings: list[Finding]
    visited: set[Site]
    judged: set[Site]


def _analyze_file(root: Node, rel: str, sp: LangSpec, cfg: LangCfg, immutable_ctors: set[str]) -> FileRead:
    closed_sets = _collect_closed_sets(root) if sp is LANG_SPEC["python"] else set()
    findings: list[Finding] = []
    visited: set[Site] = set()
    judged: set[Site] = set()
    # The names sitting inside regions this grammar left unparsed, for the whole file. Read
    # once and handed to every finding, because a macro in one function can name a field of
    # another and a module static alike, and because a language that parses everything gets
    # the empty set here without a walk.
    hidden = _hidden_names(root, sp)

    module = state_enum.module_cands(root, sp, cfg)
    visited |= set(module)
    for name in state_enum.keys_of(module):
        refs = _bound_to(_refs(root, lambda n, nm=name: n.type == "identifier" and _text(n) == nm), name, sp)
        if refs:
            findings.append(_finding(name, refs, rel, sp, closed_sets, immutable_ctors,
                                     instance=False, hidden=hidden))
            judged |= state_enum.sites_of(module, name)

    if sp.get("scope_by_receiver"):    # Go: state spans methods, grouped by receiver type
        for slot in state_enum.go_slots(root):
            findings.append(_finding(slot["state"], slot["refs"], rel, sp, closed_sets,
                                     immutable_ctors, instance=slot["writers_enumerable"],
                                     hidden=hidden))
            visited.add(slot["site"])
            judged.add(slot["site"])

    for cls in _refs(root, lambda n: n.type in sp["class_types"]):
        cands = state_enum.instance_cands(cls, sp)
        visited |= set(cands)
        for key in state_enum.keys_of(cands):
            refs = _state_refs(cls, key, sp)
            if refs:
                findings.append(_finding(key, refs, rel, sp, closed_sets, immutable_ctors,
                                         instance=True, hidden=hidden))
                judged |= state_enum.sites_of(cands, key)

    # State declared inside a record, which neither enumerator above can reach: both work
    # from a reference, and a slot declared once and thereafter only used is spelled one way
    # at its declaration and another at every use. record_state owns both halves, and it is
    # handed the keys already claimed for a record so it can stand down instead of reporting
    # the same slot twice (see its module docstring).
    read = record_state.slots(root, sp, lambda cls: state_enum.instance_keys(cls, sp))
    visited |= set(read["visited"])
    for slot in read["slots"]:
        findings.append(_finding(slot["state"], slot["refs"], rel, sp, closed_sets,
                                 immutable_ctors, instance=slot["writers_enumerable"],
                                 hidden=hidden))
        judged.add(slot["site"])

    return {"findings": findings, "visited": visited, "judged": judged}


# object, not Any: the verdict payload mixes strings, counts, nested dicts and a findings
# list, so no single value type fits. `object` still forces a caller to narrow before use,
# which is the property Any throws away. Same argument as thread_surface's scan result.
def _na(lang: str) -> dict[str, object]:
    return {
        "verdict": "n/a", "value": "n/a", "band": "n/a",
        "counts": {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0},
        "coverage": {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)},
        "resolvable_fraction": "n/a",
        "silence": state_partition.silence_summary([], 0),
        "partition": state_partition.partition_summary([]),
        # `declared: None`, not 0. A language with no spec was not counted, and a confident
        # zero here would report "there is no state" for a repository nobody read. The two
        # coverage fractions are None for the same reason: no denominator exists to divide by.
        "census": state_census.uncounted(0),
        "findings": [],
        "bucketed": {"counts": {}, "paths": []},
        "details": f"finite-testability classifier has no spec for {lang} yet",
    }


def classify(repo: Path, lang: str) -> dict[str, object]:
    """L1.18b: the finite-testability verdict distribution.

    Additive as a PANEL ENTRY: nothing reads this function's return value except the
    report. Its per-file machinery is another matter. Since 2026-08-15 L1.18 calls
    `_analyze_file` directly for its bound-awareness correction, so this module's
    verdicts now decide part of L1.18's number and the two can no longer be changed
    independently. A change to `_categorize`, `_verdict` or the partition roll-up moves
    both indicators, and the amendment record for either has to say so."""
    if lang not in LANG_SPEC:
        return _na(lang)
    sp = LANG_SPEC[lang]
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    # conformance/ holds law/spec scaffolding and test doubles (fault-injection
    # markers, failing connections), not production state; skip it like tests. docs,
    # tooling, and loose entry-point scripts are scoped out by _read_source_bytes and
    # disclosed below (never a silent skip).
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION_WITHOUT_CONFORMANCE)
    bucketed = bucketed_paths(repo, cfg["extensions"], PRODUCTION_WITHOUT_CONFORMANCE)

    # First pass: parse every file and collect the repo's immutable constructors
    # (functions whose returns are all immutable), so a constant built by one can be
    # resolved by a one-level follow. Second pass: analyze with that knowledge.
    roots: list[tuple[Node, str]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        roots.append((parser.parse(src).root_node, rel))
    immutable_ctors: set[str] = set()
    if sp is LANG_SPEC["python"]:
        for root, _rel in roots:
            immutable_ctors |= _collect_immutable_ctors(root)

    findings: list[Finding] = []
    # The visit record, per file, in the census's site vocabulary. It is collected here rather
    # than re-derived later because only the enumerators know where they went: a second walk
    # written to work out where the first one probably looked is a guess wearing a
    # measurement's name, which is the defect this number replaced.
    visited: dict[str, set[Site]] = {}
    judged: dict[str, set[Site]] = {}
    for root, rel in roots:
        read = _analyze_file(root, rel, sp, cfg, immutable_ctors)
        findings.extend(read["findings"])
        visited[rel] = read["visited"]
        judged[rel] = read["judged"]

    counts = {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0}
    coverage = {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)}
    for f in findings:
        counts[f["verdict"]] += 1
        coverage[f["verdict"]]["drives_decision" if f["drives_decision"] else "observe_only"] += 1

    total = sum(counts.values())
    if counts[PROMISCUOUS]:
        verdict = PROMISCUOUS
    elif counts[UNRESOLVED]:
        verdict = UNRESOLVED
    elif total:
        verdict = NEUTRAL
    else:
        verdict = "n/a"
    resolvable = round((counts[NEUTRAL] + counts[PROMISCUOUS]) / total, 3) if total else 1.0

    _order = {PROMISCUOUS: 0, UNRESOLVED: 1, NEUTRAL: 2}
    findings.sort(key=lambda f: (_order[f["verdict"]], not f["drives_decision"], f["file"], f["line"]))
    silence = state_partition.silence_summary(findings, total)
    partition = state_partition.partition_summary(findings)

    # The independent denominator. Every number above this line - the counts, the resolvable
    # fraction, the silence index, the partition summary - is computed over the state THIS
    # function recognized, and no measure over the enumerated set can see non-enumeration.
    # The census counts state-bearing declarations from the parse tree by a separate route,
    # so a struct field no enumerator here knows about still lands in the denominator and the
    # gap becomes visible. `value`, `band` and `details` are untouched: they are the fields
    # the Rust port is validated equal against, and the census is not ported yet.
    census = state_census.compare(repo, lang, len(findings), visited, judged)

    return {
        "verdict": verdict,
        "value": f"{counts[NEUTRAL]} neutral / {counts[PROMISCUOUS]} promiscuous / {counts[UNRESOLVED]} unresolved",
        "band": "n/a",
        "counts": counts,
        "coverage": coverage,
        "resolvable_fraction": resolvable,
        "silence": silence,
        "partition": partition,
        "census": census,
        "findings": findings,
        "bucketed": bucketed,
        "details": (
            f"finite-testability: {counts[NEUTRAL]} neutral, {counts[PROMISCUOUS]} promiscuous, "
            f"{counts[UNRESOLVED]} unresolved across {total} pieces of state; "
            f"resolvable fraction {resolvable}; silence {silence['fraction']}; "
            f"{partition['uncounted']} of {partition['deciding_states']} deciding partitions uncounted. "
            "Cardinality is per state and does not compose: two states that decide the same "
            "branch multiply, and this version reports each separately rather than guessing "
            "the product."
        ),
    }
