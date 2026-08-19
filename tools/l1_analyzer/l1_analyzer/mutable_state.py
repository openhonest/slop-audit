"""
L1.18 - mutable-state ratio (the "any language" indicator) and the module-mutable /
instance-field enumeration the finite-testability meter reuses.

Split out of indicators.py to keep that module under the god-file line the meter
enforces on itself. Depends only on the shared primitives in indicators (LANG_CFG,
the parser, the boundary readers, band); it never imports back the indicator
computations, so the two modules do not form a cycle.

Corrected in place on 2026-08-15, four defects at once. See
../../../research/amendments/amendment-2026-08-15-l1-18-corrected-ratio.md for the evidence, the rules and
the measured movement. In brief, and each is commented at its site below:

1. The I/O boundary exclusion is GONE. It only ever fired on a literal
   `honest: boundary` comment, so it excluded nothing anywhere; recognising a route
   handler, a database adapter or a CLI entry point by analysis was investigated and
   cannot be done without a per-framework enumeration. The claim is dropped rather
   than faked, and the canon row says so.
2. Every language names its own immutability keywords. The shared default carried
   `let `, which only javascript and go overrode, so a TypeScript module-level
   `let counter = 0` read as immutable while the same line in a .js file read as
   mutable state.
3. Java and C# fields are reached structurally and by bare name. The old scan looked
   at root children and one level below, while a field sits three levels down, and
   the reference walk only counted receiver-prefixed access. Between them, L1.18
   measured how often those authors wrote `this.`, which is a style preference.
4. The ratio is bound-aware. State whose reaching-set the finite-testability
   classifier could bound no longer counts, because a literal-keyed read against a
   closed set is exhaustively testable and an unbounded accumulator is not.

Corrected again on 2026-08-16, one defect, and it is the same shape as the third above.
C reached the member-access arm through two assumptions nobody made for it: the arm
hard-coded `.` as the operator, and `_receiver_names` fell through to an empty set for a
language with no `this` keyword and no Go method receiver. C spells the reach `s->cache`
and has neither, so the arm was dead code and a struct field mutated through a pointer
read as no external state at all. Both are now declared per language, `member_op` and
`receiver_scan`, and a language that names no receiver scan raises. json-c moves from 1.7
Healthy to 34.9 Not Healthy and libuv from 6.1 Healthy to 50.7 Slop, which is the size of
what the arm was not seeing.

STILL WRONG, and stated here rather than left for a reader to find: C's module scan is the
text heuristic, which needs an `=` on the line, so `static int cache[256];` at file scope -
the ordinary C global cache - never enters `module_mutables` and L1.18 reads 0.0 Healthy
over a file whose only state is one. It is the same architectural cause as the receiver gap:
C reached the text scan by omission rather than by decision. Filed as slop-audit-3ti.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tree_sitter import Node

from l1_analyzer import incomplete
from l1_analyzer.indicators import (
    _BODY_NODE_TYPES,
    LANG_CFG,
    L1Result,
    LangCfg,
    _get_parser,
    _read_source_bytes,
    _with_skipped,
    band,
)
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.scope import PRODUCTION

# ---------------------------------------------------------------------------
# L1.18 Mutable state ratio (the key "any language" indicator, using tree-sitter)
# Simplified reference implementation. Full production version lives in the
# Paper A replication package with all the bound-literal logic etc.
# ---------------------------------------------------------------------------

# Container literals/constructors whose empty form seeds an accumulator.
# Constructors of MUTABLE containers whose empty form is an accumulator seed.
# frozenset/tuple/bytes are immutable and cannot accumulate, so they are excluded:
# `X = frozenset()` is a constant, not mutable state.
_PY_CONTAINER_CTORS = frozenset({
    "dict", "list", "set", "defaultdict", "OrderedDict", "deque", "Counter", "bytearray",
})


def _py_is_type_expression(n: Node) -> bool:
    """A pure type expression: a bare name, a dotted name, a subscript
    (Iterable[X]), or a `|` union of those. No call, no container literal."""
    if n.type in ("identifier", "attribute", "subscript"):
        return True
    if n.type == "binary_operator":
        op = n.child_by_field_name("operator")
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        return (op is not None and op.text == b"|" and left is not None and right is not None
                and _py_is_type_expression(left) and _py_is_type_expression(right))
    return False


def _py_is_type_alias(node: Node, rhs: Node | None) -> bool:
    annot = node.child_by_field_name("type")
    if annot is not None and annot.text.decode("utf8", errors="ignore").split("[", 1)[0].strip() == "TypeAlias":
        return True
    return rhs is not None and _py_is_type_expression(rhs)


def _py_is_empty_container(rhs: Node | None) -> bool:
    """An accumulator seed: {}, [], or set()/dict()/list()/... with no elements."""
    if rhs is None:
        return False
    if rhs.type in ("dictionary", "list"):
        return not rhs.named_children
    if rhs.type == "call":
        fn = rhs.child_by_field_name("function")
        args = rhs.child_by_field_name("arguments")
        if fn is not None and fn.type == "identifier" and fn.text.decode("utf8", errors="ignore") in _PY_CONTAINER_CTORS:
            return args is None or not args.named_children
    return False


def _module_mutables_python(candidates: list[Node], this_idents: set[str]) -> set[str]:
    """Field-based module-global detection for Python. The binding name is read
    from the assignment's `left` field, so string literals and annotation tails
    are never scanned as source. Type aliases are skipped. An uppercase name is a
    constant by convention, unless it is seeded with an empty container, which is
    an accumulator (e.g. `CACHE = {}`), the pattern the indicator exists to catch."""
    mutables: set[str] = set()
    for node in candidates:
        left = node.child_by_field_name("left")
        if left is None or left.type != "identifier":  # skip subscripts, tuples, attributes
            continue
        name = left.text.decode("utf8", errors="ignore")
        # Dunders (__all__, __version__, ...) are module metadata, not state.
        if name in this_idents or (name.startswith("__") and name.endswith("__")):
            continue
        rhs = node.child_by_field_name("right")
        if _py_is_type_alias(node, rhs):
            continue
        if name.isupper():
            if _py_is_empty_container(rhs):
                mutables.add(name)
        else:
            mutables.add(name)
    return mutables


def _module_mutables_by_specifier(candidates: list[Node]) -> set[str]:
    """Rust-style: a top-level binding is mutable state iff its declaration carries
    a `mut` specifier (`static mut counter: i32 = 0`). The name is the declaration's
    `identifier` child, read structurally so the type token is never mistaken for
    the name. `const` and plain `static` are immutable and excluded."""
    mutables: set[str] = set()
    for node in candidates:
        if not any(c.type == "mutable_specifier" for c in node.children):
            continue
        name = next((c.text.decode("utf8", errors="ignore") for c in node.children if c.type == "identifier"), None)
        if name:
            mutables.add(name)
    return mutables


def _text(node: Node) -> str:
    return node.text.decode("utf8", errors="ignore") if node.text else ""


def _deep_nodes(root: Node, node_types: tuple[str, ...]) -> list[Node]:
    """Every node of these types at any depth. Used only for class fields, which is
    why it is not the general candidate collector: a deep walk over a language's whole
    assignment vocabulary would harvest function locals as module state."""
    out: list[Node] = []

    def walk(n: Node) -> None:
        if n.type in node_types:
            out.append(n)
        for c in n.children:
            walk(c)

    walk(root)
    return out


_MODIFIER_TYPES = ("modifiers", "modifier")


def _declared_modifiers(field: Node) -> set[str]:
    """The modifier words on a field declaration. Java wraps them in one `modifiers`
    node and C# repeats a `modifier` node per word; splitting the text of either on
    whitespace reads both without a per-grammar branch."""
    words: set[str] = set()
    for child in field.children:
        if child.type in _MODIFIER_TYPES:
            words |= set(_text(child).split())
    return words


def _module_mutables_class_fields(root: Node, cfg: LangCfg) -> set[str]:
    """Java/C#: mutable state is every field not declared final, readonly or const.

    Two things the old scan could not do. It reached only root children and one level
    below, and a field sits at root, class declaration, class body, field declaration,
    so no field ever entered the candidate set; and it required an `=` on the line, so
    `private int total;` was invisible even at the right depth. This walks to any depth
    for field-declaration nodes ONLY, which is what keeps method locals out: both
    languages list a local declaration type in `module_level_assign`, and a deep walk
    over that vocabulary would count every local as external state, an error worse than
    the one being fixed.

    Mutability is read from the declared modifiers rather than guessed from the name's
    casing, because both languages have a keyword for the property and it is already in
    the source. Bare field access is then counted by the identifier arm of
    _count_mutable_refs, which is the other half of this correction: the member-access
    arm sees only `this.x`, and `this.` is optional in both languages."""
    immutable = cfg["immutable_modifiers"]
    mutables: set[str] = set()
    for field in _deep_nodes(root, cfg["field_decl_types"]):
        if _declared_modifiers(field) & immutable:
            continue
        for vd in _deep_nodes(field, ("variable_declarator",)):
            named = vd.child_by_field_name("name") or next((c for c in vd.children if c.type == "identifier"), None)
            if named is not None and _text(named) not in cfg["this_ident"]:
                mutables.add(_text(named))
    return mutables


def _module_mutables_text(root: Node, cfg: LangCfg) -> set[str]:
    """The text heuristic, for the languages with no structural scan yet.

    `const_keywords` is read by direct subscript, with no default. The default it used
    to have was `("const ", "final ", "readonly ", "let ", "val ")`, a union of five
    languages' keywords that no single language uses, and only javascript and go
    overrode it. TypeScript therefore inherited `let ` and classified every
    module-level `let` as immutable. A shared default across languages is the shape
    that permits this: it is silent, it looks like a sensible fallback, and it is
    wrong in a way that only shows up one language at a time."""
    const_keywords = cfg["const_keywords"]
    this_idents = cfg["this_ident"]
    mutables: set[str] = set()
    for node in shallow_candidates(root, cfg["module_level_assign"]):
        for line in _text(node).splitlines():
            if "=" in line and not any(kw in line.lower() for kw in const_keywords):
                parts = line.split("=")[0].strip().split()
                if parts:
                    name = parts[-1].strip("()[]:,")
                    if name and name not in this_idents and not name.isupper():
                        mutables.add(name)
    return mutables


def _module_mutables_python_scan(root: Node, cfg: LangCfg) -> set[str]:
    return _module_mutables_python(shallow_candidates(root, cfg["module_level_assign"]), cfg["this_ident"])


def _module_mutables_specifier_scan(root: Node, cfg: LangCfg) -> set[str]:
    return _module_mutables_by_specifier(shallow_candidates(root, cfg["module_level_assign"]))


def _module_mutables_c_scan(root: Node, cfg: LangCfg) -> set[str]:
    """File-scope declarations in C, read from the parse tree rather than from line text.

    C used the text heuristic, which needs an `=` on the line, so `static int cache[256];`
    declared no state as far as L1.18 was concerned. On the fixture in
    tests/test_module_globals.py the text scan found `counter` and missed `cache`, `buf`,
    `NAME` and `MAX`, while the classifier enumerated all five. Two measures of one file
    disagreeing about what is even a candidate is the defect; the array was the instance.

    A prototype is not state and a function pointer is; `_c_declared_name` tells them apart,
    because the grammar puts `function_declarator` on top of both.

    Known limit, kept deliberately: a declaration carrying a `const` qualifier is excluded
    whole, which is right for `const int MAX = 10` and wrong for `const char *NAME`, where
    const qualifies the pointee and the pointer is still rebindable. That is the same call the
    text heuristic made when it screened the line for `const `, so this change fixes the
    missing-declaration bug without moving the const boundary at the same time.
    """
    const_keywords = tuple(kw.strip() for kw in cfg["const_keywords"])
    names: set[str] = set()
    for node in root.children:
        if node.type != "declaration":
            continue
        if any(c.type == "type_qualifier" and _text(c) in const_keywords for c in node.children):
            continue
        for child in node.children:
            if child.type in _C_DECLARATORS:
                name = _c_declared_name(child)
                if name is not None:
                    names.add(name)
                break
    return names


# The declarator forms a C file-scope declaration can carry. Written out rather than probed
# at runtime, so a form nobody listed is a missing row here and not a silent omission.
_C_DECLARATORS = ("identifier", "init_declarator", "array_declarator", "pointer_declarator",
                  "function_declarator")


def _c_declared_name(declarator: Node) -> str | None:
    """The identifier a C declarator binds, or None when it binds no state.

    A prototype binds none: `void proto(int)` is a `function_declarator` whose own declarator
    is a bare identifier. A function POINTER does bind state, and the grammar makes the two
    easy to confuse, because it puts `function_declarator` on top of both. `void
    (*handler)(int)` reaches its name through a `parenthesized_declarator` holding a
    `pointer_declarator`, and a rebindable pointer is state whatever it points at. I asserted
    the opposite when writing this, that a pointer sat on top, and the grammar said otherwise.

    Returns None rather than raising when no identifier is reachable, because a declaration
    the grammar could not resolve is a fact about the source and not about this table.
    """
    node: Node | None = declarator
    while node is not None and node.type != "identifier":
        if node.type == "function_declarator":
            inner = node.child_by_field_name("declarator")
            if inner is None or inner.type != "parenthesized_declarator":
                return None                      # a prototype, not a variable
            node = next((c for c in inner.children if c.type == "pointer_declarator"), None)
            continue
        nxt = node.child_by_field_name("declarator")
        node = nxt if nxt is not None else next(
            (c for c in node.children if c.type in _C_DECLARATORS), None)
    return _text(node) if node is not None else None


def shallow_candidates(root: Node, assign_types: tuple[str, ...]) -> list[Node]:
    """Top-level assignments, allowing one wrapper: Python nests `x = 0` inside an
    `expression_statement`, so the `assignment` node is a child of a root child.

    Public, and imported by `state_enum`, because it defines WHICH declarations the module
    scan considers. The scan reports only the names it judges mutable, and the coverage
    number needs the ones it judged and declined as well: a binding the reader walked and
    ruled out is read, not missed, and the two are separable only at the candidate list.
    A second walk written to guess the same candidates would drift from this one silently,
    which is the class of defect the coverage number exists to expose."""
    candidates: list[Node] = []
    for node in root.children:
        if node.type in assign_types:
            candidates.append(node)
        else:
            candidates.extend(c for c in node.children if c.type in assign_types)
    return candidates


# Dispatch on the language's declared scan strategy. This replaced a chain of
# `if cfg.get(flag)` tests whose fall-through was the text heuristic, which is how a
# language ended up on a scan nobody chose for it: TypeScript and C reached the text
# path by omission, not by decision, and inherited its shared keyword default with it.
# Every LANG_CFG entry now names its scan, and a missing name is a KeyError here
# rather than a silent default.
_MODULE_SCANS: dict[str, Callable[[Node, LangCfg], set[str]]] = {
    "python_fields": _module_mutables_python_scan,
    "mutable_specifier": _module_mutables_specifier_scan,
    "class_fields": _module_mutables_class_fields,
    "c_declarations": _module_mutables_c_scan,
    "text": _module_mutables_text,
}


def _find_module_mutable_names(root: Node, cfg: LangCfg) -> set[str]:
    """The names in one file that L1.18 treats as external mutable state.

    For Java and C# these are class fields rather than module-level bindings, because
    those two languages have no module scope worth measuring and their state is fields.
    The name is kept for the finite-testability classifier, which reads this function
    for Python only."""
    return _MODULE_SCANS[cfg["module_scan"]](root, cfg)

def _count_mutable_refs(
    body: Node, cfg: LangCfg, module_mutables: set[str], receiver_names: set[str], bounded: set[str]
) -> int:
    """Count references inside a function body to UNBOUNDED external mutable state.

    Handles, per-language via cfg: receiver/member access (self./this./<go
    receiver>.field), Ruby @instance / $global variables, module-level mutable
    globals and Java/C# fields referenced by bare identifier, and Rust/C raw patterns.

    `bounded` is the set of state keys the finite-testability classifier could bound in
    this file, and a reference to one of them does not count. That is the fourth
    correction: L1.18 used to count a reference to outside state whether or not the
    state could take unboundedly many values, so a read keyed by a literal against a
    closed set scored identically to an unbounded accumulator. The two are not the same
    fact about testability, and the classifier printed on the same panel already told
    them apart while the ratio did not.

    The operator joining receiver to member is read from the language's own config rather
    than assumed. It used to be a hard-coded `.`, which is right in eight of the nine
    languages and wrong in C, where a caller's record is reached as `s->cache`. Together
    with the receiver gap recorded on `_RECEIVER_SCANS` that made this arm dead code for C.

    The classifier keys instance state by the same text this walk sees - `self.x`,
    `this.x`, `@ivar`, and the bare field name in Java and C# - so the two vocabularies
    line up without translation. Go and C are the exceptions: Go keys by `<Type>.<field>`
    and C by `<struct tag>.<field>`, while this walk sees `<receiver>.<field>` and
    `<pointer>-><field>`, so no Go or C reference is ever matched as bounded and both keep
    their uncorrected reading on this axis. A key the classifier never enumerated is absent
    from `bounded` and therefore counts, so every gap reads high, never falsely clean.
    """
    count = 0
    member_type = cfg["member_access"]
    member_op = cfg["member_op"]
    instance_field_types = cfg["instance_field_types"]
    raw_mut_patterns = cfg["raw_mut_patterns"]

    def walk(n: Node):
        nonlocal count
        text = _text(n)
        if (n.type == member_type and receiver_names
                and any(text.startswith(r + member_op) for r in receiver_names) and text not in bounded):
            count += 1
        if n.type in instance_field_types and text not in bounded:
            count += 1
        if n.type == "identifier" and text in module_mutables and text not in bounded:
            count += 1
        # Raw-text mutable patterns are language-scoped (Rust only). Running them
        # for every language flagged any source that merely contained the strings.
        if raw_mut_patterns and any(p in text for p in raw_mut_patterns):
            count += 1
        for c in n.children:
            walk(c)
    walk(body)
    return count


def _bounded_state_keys(root: Node, rel: str, lang: str, cfg: LangCfg, immutable_ctors: set[str]) -> set[str]:
    """State keys in one file whose reaching-set the L1.18b classifier could bound.

    Three conditions, all read from the classifier's own finding, and all three needed.
    NEUTRAL is its verdict for state whose partition it bounded; PROMISCUOUS and
    UNRESOLVED both leave the partition unknown, so both keep counting.

    `drives_decision` and a counted partition are the other two, and dropping them is a
    trap this walked into once during implementation. NEUTRAL is also what the
    classifier returns for state that reaches no decision at all - an accumulator that
    is written and returned but never branched on - and its partition is then EMPTY,
    meaning "nothing to cover", not "finitely many classes". Excluding that state
    cancelled the Java and C# field correction exactly where it was needed, because a
    plain field accumulator is precisely that shape. Bounded here means the classifier
    looked at the state, found a decision depending on it, and could count the classes.

    Reusing the classifier rather than writing a second boundedness rule is deliberate:
    two rules for one concept drift, and the ratio would then contradict the classifier
    printed beside it on the same panel. Imported inside the function because
    state_bounds imports from indicators, which imports this module at its foot.
    """
    from l1_analyzer import state_bounds
    read = state_bounds._analyze_file(root, rel, LANG_SPEC[lang], cfg, immutable_ctors)
    return {
        f["state"] for f in read["findings"]
        if f["verdict"] == state_bounds.NEUTRAL and f["drives_decision"] and f["partition"]["counted"]
    }

def _c_function_declarator(func_node: Node) -> Node | None:
    """The `function_declarator` of a C function definition.

    C hangs the name and the parameter list off a declarator chain rather than off the
    definition, and a function returning a pointer wraps that chain in one or more
    `pointer_declarator`s (`struct Store *get(struct Store *s)`). Walking the chain is what
    lets the two readers below agree on which parameters and which name belong to one
    function."""
    declarator = func_node.child_by_field_name("declarator")
    while declarator is not None and declarator.type != "function_declarator":
        declarator = declarator.child_by_field_name("declarator")
    return declarator


def _function_name(node: Node) -> str:
    """The declared name of a function node, in any of the nine languages.

    Eight of them put it on a `name` field. C does not, and reading `name` alone returned
    nothing for every C function - harmless while no C function was ever counted, and a
    silent contract break the moment one was. `mutable_function_names` promises a name for
    every function `analyze_mutable_state` counts, and a C repository would have reported
    two counted functions and zero culprits."""
    named = node.child_by_field_name("name")
    if named is not None:
        return _text(named)
    declarator = _c_function_declarator(node)
    inner = declarator.child_by_field_name("declarator") if declarator is not None else None
    while inner is not None and inner.type != "identifier":
        inner = inner.child_by_field_name("declarator")
    return _text(inner) if inner is not None else ""


def _fixed_receivers(func_node: Node, cfg: LangCfg) -> set[str]:
    """The receiver keyword the language fixes for every function: `self` or `this`."""
    return set(cfg["this_ident"])


def _go_method_receivers(func_node: Node, cfg: LangCfg) -> set[str]:
    """Go names its receiver per method: `func (r *Foo) Bar(...)`. The first parameter_list
    is the receiver list, and a plain function has none, so nothing inside one is read as
    instance access."""
    names: set[str] = set()
    if func_node.type != "method_declaration":
        return names
    for child in func_node.children:
        if child.type == "parameter_list":
            for decl in child.children:
                if decl.type == "parameter_declaration":
                    names.update(_text(part) for part in decl.children if part.type == "identifier")
            break  # first parameter_list is the receiver
    return names


def _c_pointer_receivers(func_node: Node, cfg: LangCfg) -> set[str]:
    """C's receivers: the pointer parameters of this function.

    C has no receiver keyword and no receiver declaration, and that absence is why this
    arm was dead. A C function reaches state it does not own by being handed a pointer to
    the record that holds it, so the pointer parameters are the names through which a
    caller's state is read and written, and `s->cache` inside `void put(struct Store *s,
    ...)` is the same fact about testability as `self.cache` inside a Python method.

    Parameters only, never a local pointer. A pointer a function mallocs and fills is state
    that function owns for its own lifetime, and counting it would read local work as
    external state. A `const` pointer parameter is counted with the rest, because every
    other language counts a READ of outside state as a reference too.

    The limit worth naming: this counts the reach, not what is on the other end of it. A
    pointer to a caller's stack struct and a pointer to a process-wide singleton are one
    node type here, and separating them needs the points-to analysis this reader does not
    do. So C reads high on this axis rather than clean, which is the direction a measure
    that cannot see is allowed to be wrong in."""
    declarator = _c_function_declarator(func_node)
    if declarator is None:
        return set()
    params = next((c for c in declarator.children if c.type == "parameter_list"), None)
    if params is None:
        return set()
    names: set[str] = set()
    for decl in params.children:
        if decl.type != "parameter_declaration":
            continue
        inner = decl.child_by_field_name("declarator")
        if inner is None or inner.type != "pointer_declarator":
            continue
        while inner is not None and inner.type == "pointer_declarator":
            inner = inner.child_by_field_name("declarator")
        if inner is not None and inner.type == "identifier":
            names.add(_text(inner))
    return names


# Dispatch on the receiver scan the language DECLARES, for the same reason _MODULE_SCANS
# dispatches on the module scan it declares. What stood here was `if this_ident: return it`
# followed by a Go-shaped `if`, whose fall-through was the empty set. C took that
# fall-through: it has no `this` keyword and no `method_declaration`, so it reached "this
# function has no receiver" by omission rather than by anyone deciding it, and with no
# receiver the member-access arm of _count_mutable_refs cannot fire at all. A C struct field
# mutated through a pointer therefore counted as no external state on any repository ever
# audited, and L1.18 reported 0.0 Healthy over it. A language that names no scan is now a
# KeyError here rather than a silent nothing.
_RECEIVER_SCANS: dict[str, Callable[[Node, LangCfg], set[str]]] = {
    "fixed": _fixed_receivers,
    "go_method_receiver": _go_method_receivers,
    "c_pointer_params": _c_pointer_receivers,
}


def _receiver_names(func_node: Node, cfg: LangCfg) -> set[str]:
    """Names that denote the state-holding record this function reaches into."""
    return _RECEIVER_SCANS[cfg["receiver_scan"]](func_node, cfg)

# There is no I/O boundary exclusion, and its absence is the point.
#
# The canon promised to exclude route handlers, database adapters and CLI entry
# points. What was implemented was a comment marker, `honest: boundary`, that a
# function had to carry. It fired on no repository that had not adopted this
# project's private marker, which is every audited repository, so the exclusion was
# documented, implemented and inert.
#
# Doing it by analysis was investigated on 2026-08-15 across seven local trees
# (5,210 files, 77,576 functions) and the six pinned corpus repositories, and it
# cannot be done. A route-handler decorator list reaches 7.2% of production functions
# locally and 0% of the corpus, and its match keys are variable names the developer
# invents (`router.get`, `app.get`, `test_app.get` all appear, and `.patch` cannot
# separate `@router.patch` from `@mock.patch`). "Database adapter" has no syntactic
# signature at all: one measured module holds 53 adapters and 6 pure functions with
# nothing distinguishing them. "CLI entry point" had no marker whatsoever; every one
# was an undecorated `main()`. The framework-agnostic alternative, "the function calls
# an I/O primitive", measured 45% false positives at usable recall and 0% recall on
# that adapter module at usable precision, and it reads dict-lookup dispatch as I/O.
#
# So the claim is dropped rather than faked. The marker went with it, because an
# exclusion the subject opts into is an exclusion the subject controls, and this
# indicator's primary consumer is an AI that optimises what it is told to optimise.
# The consequence is disclosed rather than hidden: L1.18 is inflated by the whole I/O
# layer of every codebase it measures, and always was. The canon row now says so.


def _count_file_functions(
    root: Node, cfg: LangCfg, module_mutables: set[str], bounded: set[str]
) -> tuple[int, int]:
    """Pure per-file walk: return (total functions, functions touching unbounded
    external mutable state). Module-level (not a loop closure) so it binds no caller
    state. No function is excluded from the denominator; see the boundary note above."""
    totals = [0, 0]  # [total, mutable]

    def find_functions(n: Node):
        if n.type in cfg["function_types"]:
            totals[0] += 1
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers, bounded) > 0:
                    totals[1] += 1
        for c in n.children:
            find_functions(c)

    find_functions(root)
    return totals[0], totals[1]


def _parsed_roots(repo: Path, lang: str, cfg: LangCfg) -> tuple[list[tuple[Node, str]], int]:
    """Every production file of this language, parsed once, with its repo-relative
    path. One reader for the ratio and the two name-listing helpers, so the three
    cannot drift into scanning different file sets."""
    parser = _get_parser(lang)
    files, skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION)
    roots: list[tuple[Node, str]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        roots.append((parser.parse(src).root_node, rel))
    return roots, skipped


def _immutable_ctors_for(lang: str, roots: list[tuple[Node, str]]) -> set[str]:
    """The repo's immutable constructors, which the classifier needs before it can
    resolve a Python constant built by one. Two passes, matching the classifier's own
    contract: a constant built by a function defined in another file cannot be resolved
    until every file has been seen. Empty for every other language, which is what the
    classifier itself does."""
    if lang != "python":
        return set()
    from l1_analyzer import state_bounds
    ctors: set[str] = set()
    for root, _rel in roots:
        ctors |= state_bounds._collect_immutable_ctors(root)
    return ctors


def analyze_mutable_state(repo: Path, lang: str) -> L1Result:
    """L1.18: percentage of functions that reference unbounded external mutable state."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    cfg = LANG_CFG[lang]
    roots, skipped = _parsed_roots(repo, lang, cfg)
    immutable_ctors = _immutable_ctors_for(lang, roots)

    total_funcs = 0
    mutable_funcs = 0
    for root, rel in roots:
        module_mutables = _find_module_mutable_names(root, cfg)
        bounded = _bounded_state_keys(root, rel, lang, cfg, immutable_ctors)
        file_total, file_mutable = _count_file_functions(root, cfg, module_mutables, bounded)
        total_funcs += file_total
        mutable_funcs += file_mutable

    ratio = incomplete.ratio(mutable_funcs, total_funcs, "L1.18 unbounded mutable state",
                             f"no function was enumerated in {lang}, so the share of them touching "
                             "unbounded state is absent, not zero")
    return {
        "value": round(ratio, 1),
        "band": band(ratio, 15, 40, higher_is_better=False),
        "details": _with_skipped(
            f"{mutable_funcs}/{total_funcs} functions reference unbounded external mutable state ({lang})", skipped),
    }


def _file_mutable_names(
    root: Node, cfg: LangCfg, module_mutables: set[str], bounded: set[str]
) -> list[str]:
    """Names of the functions in one file that L1.18 counts as touching unbounded
    external mutable state. Same predicate as _count_file_functions (module-level so it
    binds no caller state), only it keeps the names instead of a tally."""
    names: list[str] = []

    def find(n: Node) -> None:
        if n.type in cfg["function_types"]:
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers, bounded) > 0:
                    nm = _function_name(n)
                    if nm:
                        names.append(nm)
        for c in n.children:
            find(c)

    find(root)
    return names


def mutable_function_names(repo: Path, lang: str) -> list[str]:
    """L1.18's culprits by name: functions that reference external mutable state.

    Additive, read-only. A name appears here iff analyze_mutable_state counts that
    function (identical _count_mutable_refs predicate), so this never moves L1.18's
    value or band. Exists so the behavioural suite can assert *which* function is
    flagged instead of fabricating the answer."""
    if lang not in LANG_CFG:
        return []
    cfg = LANG_CFG[lang]
    roots, _skipped = _parsed_roots(repo, lang, cfg)
    immutable_ctors = _immutable_ctors_for(lang, roots)
    names: list[str] = []
    for root, rel in roots:
        module_mutables = _find_module_mutable_names(root, cfg)
        bounded = _bounded_state_keys(root, rel, lang, cfg, immutable_ctors)
        names.extend(_file_mutable_names(root, cfg, module_mutables, bounded))
    return names


def module_mutable_names(repo: Path, lang: str) -> set[str]:
    """The module-level bindings L1.18 treats as mutable state. A binding is a
    *bound literal* (a constant, a frozen dispatch table) exactly when it is
    absent from this set. Additive, read-only; never affects L1.18's number."""
    if lang not in LANG_CFG:
        return set()
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION)
    out: set[str] = set()
    for _path, src in files:
        root = parser.parse(src).root_node
        out |= _find_module_mutable_names(root, cfg)
    return out
