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
from l1_analyzer.lang_spec import _PY_MUTATING, LANG_SPEC, LangSpec
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.state_partition import (
    DYNAMIC_DISPATCH,
    INJECTED_SLOT,
    Partition,
    Reach,
)
from l1_analyzer.state_sites import Site
from l1_analyzer.ts_nodes import arg_value as _arg_value
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_named as _first_named
from l1_analyzer.ts_nodes import local_refs as _local_refs
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import same as _same
from l1_analyzer.ts_nodes import text as _text

NEUTRAL = "neutral"
PROMISCUOUS = "promiscuous"
UNRESOLVED = "unresolved"

# Builtins that read a bounded feature of their argument (the value flows onward).
_BOUNDED_BUILTINS = frozenset({"len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"})
# Builtins that consume a value as an effect/assertion, not a partitioning decision.
_EFFECT_CALLS = frozenset({"print", "repr", "str", "format", "log", "logging"})
# Comparison operators: a state value meeting one is split into finitely many classes.
_COMPARISON_OPS = frozenset({"<", ">", "<=", ">=", "==", "!=", "===", "!==", "<>"})


class Finding(TypedDict):
    """One piece of state and its verdict. Fixed keys, so a TypedDict, not a bag.

    `silence` carries why the reaching-set could not be decided, and is the empty string
    on every decided finding. It is on the finding rather than in a parallel list because
    a silent site and its verdict are one fact, and two lists drift."""
    state: str
    verdict: str
    drives_decision: bool
    file: str
    line: int
    silence: str
    partition: Partition


def _sub_named(subscript: Node) -> list[Node]:
    return [c for c in subscript.children if c.is_named]


def _sub_collection(subscript: Node, sp: LangSpec) -> Node | None:
    """The collection being indexed. Rust's index_expression has no fields, so the
    collection is the first named child; other grammars name it."""
    if sp.get("sub_positional"):
        named = _sub_named(subscript)
        return named[0] if named else None
    return _field(subscript, sp["sub_value"])


def _sub_key(subscript: Node, sp: LangSpec) -> Node | None:
    """The key/index node of a subscript. Rust indexes positionally (second named
    child); C# wraps the key in a bracketed_argument_list; others name it."""
    if sp.get("sub_positional"):
        named = _sub_named(subscript)
        return named[1] if len(named) > 1 else None
    idx = _field(subscript, sp["sub_index"])
    if idx is not None and idx.type == "bracketed_argument_list":
        return _arg_value(_first_named(idx))
    return idx


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

def _is_immutable_collection(rhs: Node | None) -> bool:
    if rhs is None:
        return False
    if rhs.type == "tuple":
        return True
    if rhs.type == "call":
        return _text(_field(rhs, "function")) == "frozenset"
    return False


# name -> member count, with None for a collection that is provably fixed and not countable.
def _collect_closed_sets(root: Node) -> dict[str, int | None]:
    names: dict[str, int | None] = {}

    def walk(n: Node) -> None:
        if n.type == "assignment":
            left, rhs = _field(n, "left"), _field(n, "right")
            if left is not None and _is_immutable_collection(rhs):
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


def _is_closed_set(node: Node | None, closed_sets: dict[str, int | None]) -> bool:
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


def _unwrap_unary(node: Node | None, sp: LangSpec) -> Node | None:
    """Peel unary operators off a value. A unary operator over a literal is itself one
    compile-time value (`-1` is the last element, `+1` the second), so the wrapper must
    not hide the literal underneath. Unwrapping rather than whitelisting the wrapper is
    what keeps `-x` unbounded: it peels to an identifier, which is no literal. The loop
    handles a stack of them (`- -1`). The operator token is unnamed in every grammar in
    the table, so the first named child is the operand."""
    while node is not None and node.type in sp.get("unary_types", ()):
        node = _first_named(node)
    return node


def _is_unbounded_value(node: Node | None, sp: LangSpec) -> bool:
    """A value used as a lookup key / index. Literals are bounded; anything else
    (a parameter, a variable) ranges over an unbounded domain."""
    node = _unwrap_unary(node, sp)
    return node is not None and node.type not in sp["literal_types"]


# --------------------------------------------------------------------------
# Membership and comparison helpers.
# --------------------------------------------------------------------------

# Every spelling of a membership operator, as tree-sitter TOKENISES it. `not in` is one
# token of type "not in", not a `not` wrapping an `in`, so matching only "in" missed the
# negated form entirely. It then fell through to the comparison arm and was graded finite
# and ORDERED, which inverted the verdict: `key in store` graded the repository F and
# `key not in store` graded it A. One word, semantics unchanged, and no disclosure.
_MEMBERSHIP_TOKENS = frozenset({"in", "not in"})


def _membership_operands(node: Node | None, sp: LangSpec) -> tuple[Node, Node] | None:
    """(left, right) for an `in` / `not in` membership test, else None."""
    style = sp["membership"]
    if style == "comparison_in" and node.type == "comparison_operator":
        if not any(c.type in _MEMBERSHIP_TOKENS for c in node.children):
            return None
        named = [c for c in node.children if c.is_named]
        return (named[0], named[-1]) if len(named) >= 2 else None
    if style == "binary_in" and node.type == "binary_expression" and _text(_field(node, "operator")) == "in":
        return _field(node, "left"), _field(node, "right")
    return None


def _is_comparison(node: Node | None, sp: LangSpec) -> bool:
    if node.type == "comparison_operator":       # Python: always a comparison
        return True
    return _text(_field(node, "operator")) in _COMPARISON_OPS


# --------------------------------------------------------------------------
# Per-reference categorisation.
# --------------------------------------------------------------------------

def _is_lvalue(node: Node | None, sp: LangSpec) -> bool:
    """True if `node` is the assigned lvalue of an assignment, unwrapping an optional
    lvalue wrapper (Go puts assignment targets inside an expression_list)."""
    wrapper = sp.get("lvalue_wrapper")
    p = node.parent
    if wrapper and p is not None and p.type == wrapper:
        node, p = p, p.parent
    return p is not None and p.type in sp["assign_types"] and _same(_field(p, sp["assign_left"]), node)


def _is_write_target(ref: Node, parent: Node, sp: LangSpec) -> bool:
    if _is_lvalue(ref, sp):
        return True
    # S[k] = v  -> ref (S) is the collection of a subscript that is the assign target
    return parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref) and _is_lvalue(parent, sp)


def _keyed_read(key_node: Node | None, sp: LangSpec) -> Reach:
    """`S[k]` read. An unbounded key ranges over an unbounded domain; a literal key cuts
    one more class out of it, and whether that class has a neighbour is the whole
    ordered/unordered distinction: `S[3]` sits between `S[2]` and `S[4]`, `S["beta"]` sits
    between nothing. Distinct literals are distinct discriminators, so d of them leave
    d+1 classes."""
    if _is_unbounded_value(key_node, sp):
        return state_partition.unbounded()
    key = _unwrap_unary(key_node, sp)
    return state_partition.finite(2, key is not None and key.type in state_partition.ORDERED_LITERALS, f"key:{_text(key)}")


def _categorize(ref: Node, sp: LangSpec, closed_sets: dict[str, int | None]) -> Reach:
    """How this single reference to a state value is consumed."""
    parent = ref.parent
    if parent is None:
        return state_partition.output()

    if _is_write_target(ref, parent, sp):
        return state_partition.write()

    # S(...) : the state supplies WHAT RUNS. No arm selector reads its value, so call-target
    # position is compositional exactly as return position is, and the meter neither
    # fail-closes nor assumes: it follows the call RESULT like any other call result (spec
    # section 4). `return S(x)` is output; `if S(x):` is the host's own two arms. The premise
    # checks that make this a proof rather than an assumption are per-attribute, and live in
    # _injected_slot_premise_fails.
    if not sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), ref):
        return _flow(parent, sp, closed_sets)

    # S[x] read : indexed by x. Unbounded key -> unbounded partition.
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        return _keyed_read(_sub_key(parent, sp), sp)

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
            return _keyed_read(_first_arg(gp, sp), sp)
        if called:
            return _flow(gp, sp, closed_sets)     # method result flows on (.clone(), .len(), an accessor)
        return _flow(parent, sp, closed_sets)     # plain field access: self.x.y

    # S.method(args) flattened (Java method_invocation / Ruby call with a receiver).
    if sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_recv"]), ref):
        name = _text(_field(parent, sp["call_name"]))
        if name in sp.get("dispatch_methods", frozenset()):
            return state_partition.undecided(DYNAMIC_DISPATCH)
        if name in sp["mutating"]:
            return state_partition.write()
        if name in sp["keyed_read"]:
            return _keyed_read(_first_arg(parent, sp), sp)
        return _flow(parent, sp, closed_sets)

    # f(..., S, ...) : argument to a call.
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets)
        if fname in _EFFECT_CALLS:
            return state_partition.output()
        return state_partition.silence_kind(parent.parent, sp)

    return _flow(ref, sp, closed_sets)


def _flow(node: Node | None, sp: LangSpec, closed_sets: dict[str, int | None]) -> Reach:
    """Categorise how a value derived from the state (node) reaches a decision."""
    parent = node.parent
    if parent is None:
        return state_partition.output()
    if parent.type in sp["return_types"]:
        return state_partition.output()
    # The state value itself is invoked as a callable, possibly through a wrapper:
    # `(self.f)(x)` in Rust reaches the call via a parenthesized_expression. Same rule as
    # direct `S(x)` in _categorize: follow the call result, do not fail-close.
    # A call RESULT being invoked is method-chaining, not state dispatch: `app.get(p)
    # (handler)` (the decorator idiom in call form) calls what app.get returns,
    # not app - so exclude nodes that are themselves a call.
    if (not sp["flat_call"] and node.type not in sp["call_types"]
            and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), node)):
        return _flow(parent, sp, closed_sets)
    if parent.type in sp["passthrough_types"]:
        return _flow(parent, sp, closed_sets)
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
        return _flow(parent, sp, closed_sets)   # arithmetic / logical: derived value flows on
    # Truthiness is the SAME two-class split wherever it is written, so every site shares
    # one key: `if S:` in fifty methods is two classes, not fifty-one.
    if parent.type in sp["branch_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return state_partition.finite(2, True, "truthy")
    if parent.type in sp["elif_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return state_partition.finite(2, True, "truthy")
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets)
        if fname in _EFFECT_CALLS:
            return state_partition.output()
        return state_partition.silence_kind(parent.parent, sp)
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), node):
        return _keyed_read(_sub_key(parent, sp), sp)
    return state_partition.output()


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


def _verdict(reaches: list[Reach]) -> tuple[str, bool, str, Partition]:
    """Combine per-reference reaches into (verdict, drives_decision, silence, partition).

    The silence reason reported is the FIRST undecided reference in source order, not the
    worst of them by some ranking. Any ranking would be invented here, and the reader's next
    move is to open the site, so the site that comes first is the one to send them to."""
    kinds = [r["kind"] for r in reaches]
    silent = [r["silence"] for r in reaches if r["kind"] == state_partition.UNDECIDED]
    if silent:
        return UNRESOLVED, True, silent[0], state_partition.UNKNOWN
    if state_partition.UNBOUNDED in kinds:
        return PROMISCUOUS, True, "", state_partition.UNKNOWN
    if state_partition.FINITE in kinds:
        return NEUTRAL, True, "", state_partition.roll_up(reaches)
    # observe-only or output-only: empty reaching-set, so one class and nothing to cover
    return NEUTRAL, False, "", state_partition.EMPTY


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


def _finding(key: str, refs: list[Node], rel: str, sp: LangSpec, closed_sets: dict[str, int | None], immutable_ctors: set[str], instance: bool) -> Finding:
    const = _immutable_const_verdict(refs, immutable_ctors, sp) if sp is LANG_SPEC["python"] else None
    if const is not None:
        # An immutable constant has a one-value domain, so its partition is one class.
        verdict, drives, silence, partition = (*const, "", state_partition.EMPTY)
    else:
        verdict, drives, silence, partition = _verdict([_categorize(r, sp, closed_sets) for r in refs])
        # An invoked slot earns NEUTRAL from the compositional rule; that rule has premises.
        if verdict == NEUTRAL and _injected_slot_premise_fails(refs, sp, instance):
            verdict, drives, silence, partition = UNRESOLVED, True, INJECTED_SLOT, state_partition.UNKNOWN
    # Attribute-level false-positive filter (Python): the per-reference verdict conflates
    # unbounded data with an unbounded decision. Clear a finding to NEUTRAL only when the
    # attribute is a provable write-once, memoization cache, or carried-value shape.
    if verdict != NEUTRAL and sp is LANG_SPEC["python"] and state_bounds_filters.is_false_positive(key, refs, verdict):
        verdict, drives, silence, partition = NEUTRAL, False, "", state_partition.EMPTY
    return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel,
            "line": _binding_line(refs, sp), "silence": silence, "partition": partition}


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

    module = state_enum.module_cands(root, sp, cfg)
    visited |= set(module)
    for name in state_enum.keys_of(module):
        refs = _bound_to(_refs(root, lambda n, nm=name: n.type == "identifier" and _text(n) == nm), name, sp)
        if refs:
            findings.append(_finding(name, refs, rel, sp, closed_sets, immutable_ctors, instance=False))
            judged |= state_enum.sites_of(module, name)

    if sp.get("scope_by_receiver"):    # Go: state spans methods, grouped by receiver type
        for slot in state_enum.go_slots(root):
            findings.append(_finding(slot["state"], slot["refs"], rel, sp, closed_sets,
                                     immutable_ctors, instance=slot["writers_enumerable"]))
            visited.add(slot["site"])
            judged.add(slot["site"])

    for cls in _refs(root, lambda n: n.type in sp["class_types"]):
        cands = state_enum.instance_cands(cls, sp)
        visited |= set(cands)
        for key in state_enum.keys_of(cands):
            refs = _state_refs(cls, key, sp)
            if refs:
                findings.append(_finding(key, refs, rel, sp, closed_sets, immutable_ctors, instance=True))
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
                                 immutable_ctors, instance=slot["writers_enumerable"]))
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
