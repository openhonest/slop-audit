"""
Per-language node-type vocabulary for the finite-testability meter (L1.18b).

Each LANG_SPEC entry maps the shared predicate's vocabulary (assignment, subscript,
member access, membership, dynamic dispatch) onto one grammar's node types and field
names, so the single algorithm in state_bounds.py serves every language. This table
is split out from that algorithm to keep each module focused, and to keep the
algorithm file under the god-file line the meter enforces on itself.

_PY_MUTATING is imported by state_bounds for its Python-only immutable-constant check;
every other constant here is referenced only through the LANG_SPEC table.
"""

from __future__ import annotations

from typing import TypedDict


class LangSpec(TypedDict, total=False):
    """The node-type vocabulary of one grammar. total=False: each language populates
    the subset it needs (Python has no call_recv; Rust has no field_decl_types), and
    the algorithm reads optional keys through .get(). Typing this replaces the
    dict[str, Any] the specs used to be, so a spec typo is a type error, not a
    KeyError at run time."""
    class_types: tuple[str, ...]
    func_types: tuple[str, ...]
    assign_types: tuple[str, ...]
    assign_left: str
    assign_right: str
    subscript_types: tuple[str, ...]
    sub_value: str | None
    sub_index: str | None
    # True where the grammar gives its subscript node no fields, so the collection and the
    # key are the first two named children. Rust and Ruby index that way; the other seven
    # declare False rather than leaving the key out, because a missing key here would read
    # as "not positional" and reach the field branch by default rather than by decision.
    sub_positional: bool
    decorator_types: tuple[str, ...]
    destructuring_types: tuple[str, ...]
    member_types: tuple[str, ...]
    member_name_field: str | None
    out_argument_types: tuple[str, ...]
    key_removal_types: tuple[str, ...]
    cond_at_index: dict[str, int]
    writing_builtins: frozenset[str]
    iterate_types: tuple[str, ...]
    local_binding: dict[str, tuple[str, str | None]]
    switch_types: dict[str, tuple[str, str]]
    immutable_modifiers: frozenset[str]
    immutable_ctor_rule: bool
    mem_object: str
    mem_attr: str
    call_types: tuple[str, ...]
    flat_call: bool
    call_fn: str
    call_args: str
    call_name: str | None
    call_recv: str
    arglist_types: tuple[str, ...]
    return_types: tuple[str, ...]
    branch_types: tuple[str, ...]
    branch_cond: str
    elif_types: tuple[str, ...]
    passthrough_types: tuple[str, ...]
    comparison_types: tuple[str, ...]
    membership: str
    this_idents: frozenset[str]
    # The constructor, which two languages name and two spell as a node type. A clause that
    # hard-codes `__init__` measures something different in every other language, quietly.
    # Both empty means this language has no constructor shape a clause can read, and a clause
    # that needs one says it could not decide rather than returning a quiet nothing.
    constructor_names: frozenset[str]
    constructor_types: tuple[str, ...]
    # A parameter that can carry a default, and the field holding its name. Empty means the
    # language has no default parameter at all, which is a fact about the language rather
    # than a gap in this reader, and a clause needing one says so.
    #
    # There is no field for the default itself. Five grammars spell it five ways, and in two
    # of them the node type covers every parameter whether it has a default or not. What
    # they all do carry is the `=` token, so the default is the named child after it, which
    # is the grammar's own answer rather than a per-language guess.
    default_param_types: tuple[str, ...]
    default_param_name: str
    # The two ways a language supplies a value for a key that is not in a table. One is a
    # method taking the key and the answer to give when it is absent; the other is an
    # operator to the right of an ordinary lookup. A language may have both, either, or
    # neither, and a clause reading them names no language.
    fallback_methods: frozenset[str]
    fallback_operators: frozenset[str]
    # Exceptions: the guarded statement, the handler hung off it, the node holding the
    # handler's own statements, and the statement that sends a failure onward. Empty means
    # the language has no exception at all. Go returns an error beside the value and Rust
    # returns a Result, so a clause about handlers says the question cannot arise there
    # rather than reporting those files clean.
    try_types: tuple[str, ...]
    handler_types: tuple[str, ...]
    handler_body_types: tuple[str, ...]
    raise_types: tuple[str, ...]
    # Ruby spells its raise as an ordinary call, so no node type tells it apart. Naming the
    # calls that send a failure onward is how that language is read without pretending it
    # has a statement it does not have.
    raise_names: frozenset[str]
    # The values that are indistinguishable from a successful empty result. A handler
    # returning one cannot be told from a call that found nothing, which is the swallow.
    absent_types: tuple[str, ...]
    # Signals that carry control flow rather than a failure. Catching one and returning is
    # how a program stops cleanly, and the rule about swallowing errors is not about these.
    # Empty where the language has no such signal.
    control_flow_exceptions: frozenset[str]
    # Where the runtime is guaranteed to hand another caller a turn. Between a read and a
    # write of something shared, one of these turns an occasional race into a certain one.
    # Empty where the language has no such point, which is not the same as having no races.
    suspension_types: tuple[str, ...]
    # The statement that records a failure. A try body ending in one is ASSERTING that its
    # call raised, so the handler beneath is the success condition and reaching the recorder
    # is the defect. Keying on the handler alone made both readings look alike.
    assertion_types: tuple[str, ...]
    # Literals that hold other values. `literal_types` carries the scalars; an empty list or
    # an empty map is just as much a value nobody chose, and is the default that bites.
    container_literal_types: frozenset[str]
    instance_ref_style: str
    # Which enumerator reads this language's instance state, and which reads its module
    # state. Both are now named by EVERY entry, including the two that read nothing
    # ("none"), so the dispatch tables in state_enum can subscript them. A spec that omits
    # one used to fall through to a default, which is how a language ends up on a rule
    # nobody chose for it: silence in the table read as a decision.
    instance_enum: str
    # Where this grammar spells the DECLARATION of a piece of state: node type -> the field
    # holding the declared name. A reference sitting in that field binds the state; it does
    # not consume it, so it is a write like any other assignment target.
    #
    # It is a map rather than a tuple because one language spells the same job two ways:
    # JavaScript names a class field through `property` and a module variable through
    # `name`, and a single field name for the language would have to be wrong about one of
    # them. Every entry declares its own, including the two that declare nothing
    # (Python and Ruby have no declarator node - binding there IS an assignment), because
    # a spec that omits the key should raise rather than decline silently.
    binding_sites: dict[str, str]
    # Where a value comes to REST, so it reaches no decision in this scope. Two shapes, one
    # conclusion. The language discards it: a bare expression statement's result is read by
    # nobody. Or the language hands it back without a keyword: the tail expression of a Ruby
    # body and of a Rust block is that language's return, and `return_types` above only
    # knows the spelled form. Either way no arm selector reads the value, which is the same
    # thing `return_types` concludes and is why this sits beside it.
    sink_types: tuple[str, ...]
    field_decl_types: tuple[str, ...]
    record_enum: str
    key_prefix: str
    mutating: frozenset[str]
    keyed_read: frozenset[str]
    dispatch_methods: frozenset[str]
    literal_types: frozenset[str]
    unary_types: tuple[str, ...]
    value_wrapper_types: tuple[str, ...]
    unread_operand_types: tuple[str, ...]
    module_enum: str
    # The node a grammar wraps assignment TARGETS in. Go puts them in an expression_list;
    # the other eight put the target under the assignment directly and declare the empty
    # string, which is a named "no wrapper" case rather than an omission. Every entry
    # declares it, so the readers subscript instead of reaching for a default.
    lvalue_wrapper: str
    scope_by_receiver: bool
    extra_bounded: frozenset[str]
    # --- vocabulary the write-only-accumulator rule reads (state_bounds_filters) -------
    #
    # The rule argues that a per-key tally nothing ever reads back cannot change an
    # observable outcome. Making that argument in nine grammars needs five things named
    # per language: how the language ASKS whether a key is present, which methods WRITE a
    # container without handing a value back, where a value is DISCARDED, which node holds
    # the statements a gate guards, and which field of a branch the gate's test sits in.
    #
    # A language that spells one of these no way at all declares the empty case, and the
    # rule then declines that half explicitly. That is the point of declaring it: an
    # omission would read as a default somebody chose.

    # Methods that answer "does this container hold this key" WITHOUT yielding the stored
    # value. Kept apart from keyed_read, which yields the value: a presence test in a
    # condition is the accumulator's own gate, and folding the two together would make the
    # gate look like a value inspected in a branch and refuse every shape the rule exists
    # for. Python, JavaScript and TypeScript also have an `in` operator (see `membership`).
    presence_methods: frozenset[str]
    # In-place methods that write the container and hand back nothing the caller can branch
    # on. A subset of `mutating`: pop, popitem, remove and their spellings mutate AND yield
    # the value they touched, so a reference in that position is not confined.
    write_methods: frozenset[str]
    # Methods that hand back the value or handle they were given. Rust reaches a map slot
    # through `get_mut(&k).unwrap()`, so the unwrap has to be transparent for the walk to
    # see the write on the other side of it. Nothing else in the table needs one.
    value_preserving_methods: frozenset[str]
    # Where a value is thrown away, and where a statement wraps its expression - one node
    # type doing both jobs, because they are the same fact. Ruby declares none: every Ruby
    # expression is a value and only position decides whether anything reads it.
    discard_types: tuple[str, ...]
    # Go's comma-ok presence test: `_, ok := d[k]` binds the value and the presence flag at
    # once. `blank_idents` names the discard target that proves the value was not taken.
    # The other eight declare the empty case - they ask presence with an operator or a
    # method, not with a binding.
    presence_bind_types: tuple[str, ...]
    blank_idents: frozenset[str]
    # The fields of a branch node a presence test may occupy. Go's comma-ok sits in the
    # `initializer` of an `if`, not in its condition, which is why this is a tuple.
    gate_fields: tuple[str, ...]
    # Node types that hold the statements a gate guards. Java's constructor body is
    # `constructor_body` and not `block`; Ruby's arms are `then` and `else`; Go nests a
    # `statement_list` inside its `block`.
    gate_body_types: tuple[str, ...]
    # Key removal spelled as a STATEMENT. Only Python has one. Everywhere else removing a
    # key is a call that hands the removed value back (`map.remove(k)`, `h.delete(k)`) or,
    # in JavaScript, a `unary_expression` that collides with the transparent wrapper
    # already declared in passthrough_types. The rule declines a key removal in those eight
    # rather than read one shape as another.
    delete_stmt_types: tuple[str, ...]
    # Test positions beyond `branch_types` + `branch_cond`, as node type -> where the test
    # sits: "field" reads `branch_cond`, "first" and "second" take that named child, "all"
    # means the whole node is a test. Python's ternary has no condition field, which is why
    # this is a slot rule and not another tuple of node types.
    extra_test_positions: dict[str, str]
    # --- vocabulary added by the 2026-08-17 per-language sweep ------------------------
    #
    # Nodes that WRITE their operand in place, as node type -> the operator tokens that make
    # one. `n++`, `++n`, `@xs << x`: the reference is mutated where it stands, and no
    # assignment node is involved anywhere, so `assign_types` can never reach it. Four
    # grammars spell it four ways and one shared question sits underneath, which is why this
    # is one table and not four special cases.
    #
    # The operator has to be checked and not just the node type, because C# reuses
    # `postfix_unary_expression` for the null-forgiving `x!` and `prefix_unary_expression`
    # for `!b` and `-n`, none of which writes anything. Ruby reuses `binary` for every
    # operator it has. A language that writes nothing in place declares the empty table, and
    # the reader then never asks for an operator.
    read_write_assign_ops: tuple[str, ...]
    write_in_place_ops: dict[str, tuple[str, ...]]
    # Unary operators the language does NOT let a value pass through untouched. Go's `<-ch`
    # is a `unary_expression` like `-x` and `!b`, and unary_expression is declared a
    # transparent wrapper, so a channel receive read as the channel itself flowing on. It is
    # not: the receive CONSUMES an element. Naming the operator is what separates the
    # transparent unary from the consuming one; the eight that have no such operator declare
    # the empty set.
    opaque_unary_ops: frozenset[str]
    # Branch nodes that hold their condition POSITIONALLY, as node type -> the child types
    # that are never the condition. Go's `for` takes its condition as a bare first named
    # child and gives it no field, so `branch_cond` reads nothing there however the type is
    # declared: `for p.running {}` was a loop on a bool field that no row could see. The
    # excluded types are what tell `for {}` (body only) and `for k := range m {}` (a range
    # clause) apart from a real condition. Every other grammar names the field and declares
    # the empty table.
    bare_cond_types: dict[str, tuple[str, ...]]
    # Nodes that take a MUTABLE ALIAS of a value, as node type -> the field holding the
    # aliased value. `let r = &mut self.v; r.push(1);` writes the field through a local whose
    # name has no relation to it, so every rule that argues from where the FIELD's own
    # references sit is unsound the moment one of these exists. Only Rust spells it; the
    # other eight declare the empty table and never consult the marker below.
    alias_types: dict[str, str]
    # The child node type that marks an alias as mutable (`mutable_specifier` in Rust). The
    # empty string where the language declares no alias type, so a reader that got there
    # anyway would match no child rather than every child.
    alias_marker: str
    # Regions the grammar hands back as unparsed tokens. Rust's `macro_invocation` swallows
    # its arguments into a `token_tree`, so `format!("{}", self.v.len())` holds no
    # field_expression and no call_expression and every reference inside it is invisible to a
    # walk. An invisible reference reads as absence, which is the failure this analyzer
    # exists to name, so a state whose name appears inside one of these regions is refused
    # rather than judged on the half that could be read. The eight whose grammars parse
    # everything declare the empty tuple.
    opaque_region_types: tuple[str, ...]

from l1_analyzer.lang_vocab import (  # noqa: F401 - re-exported: the table below and its readers use these
    _C_LITERALS,
    _CS_KEYED_READ,
    _CS_LITERALS,
    _CS_MUTATING,
    _GO_LITERALS,
    _JAVA_KEYED_READ,
    _JAVA_LITERALS,
    _JAVA_MUTATING,
    _JS_LITERALS,
    _JS_MUTATING,
    _PY_IN_PLACE,
    _PY_LITERALS,
    _PY_MUTATING,
    _PY_WRITE_ONLY,
    _RUBY_DISPATCH,
    _RUBY_KEYED_READ,
    _RUBY_LITERALS,
    _RUBY_MUTATING,
    _RUST_KEYED_READ,
    _RUST_LITERALS,
    _RUST_MUTATING,
    COMPARISON_OPS,
    DECISION_NODE_TYPES,
)

LANG_SPEC: dict[str, LangSpec] = {
    "python": {
        "class_types": ("class_definition",),
        "func_types": ("function_definition",),
        "assign_types": ("assignment", "augmented_assignment"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript",), "sub_value": "value", "sub_index": "subscript", "sub_positional": False,
        "destructuring_types": ("pattern_list", "tuple_pattern", "list_pattern"),
        "decorator_types": ("decorator",),
        "member_types": ("attribute",), "mem_object": "object", "mem_attr": "attribute",
        "member_name_field": None,
        "out_argument_types": (),
        # The STATEMENT form of removing a key, which is a write and not a select, so
        # its key selects nothing. Python spells it `del d[k]` and JavaScript and
        # TypeScript spell it as a unary `delete d[k]`. The other six spell it as a
        # METHOD, `d.Remove(k)` and its kin, which `mutating` already covers, so they
        # declare an empty row rather than being omitted.
        "key_removal_types": ("delete_statement",),
        # A condition held POSITIONALLY at an index. Python's ternary names no field at
        # all and puts the CONSEQUENCE first: `X if C else Y` reads as [X, C, Y], so
        # neither the `condition` key the other six use nor the first-named-child rule
        # Go needs can find it. The other eight declare an empty map.
        "cond_at_index": {"conditional_expression": 1},
        "writing_builtins": frozenset(),
        # EMPTY, and not because Python lacks the shape. `for x in self.items` and
        # `[x for x in self.items]` read every cell exactly as Go's range does, and the
        # row would land. It is left out because that comprehension is the fixture
        # test_unmeasured_constructs uses to hold its property, that a construct with no
        # dispatch row is unmeasured rather than clean, and giving it a row makes the
        # example stale rather than the property wrong. Replacing that fixture needs a
        # construct still unread today, which is its own small piece of work.
        "iterate_types": (),
        "local_binding": {"assignment": ("left", "right")},
        "switch_types": {},
        "immutable_modifiers": frozenset(),
        # The immutable-CONSTRUCTION rule, which follows a constructor one level to see
        # whether its return can be mutated. Python only, and now declared here rather
        # than by an identity check on the spec object in _finding.
        "immutable_ctor_rule": True,
        "call_types": ("call",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement", "conditional_expression"), "branch_cond": "condition",
        "elif_types": ("elif_clause",),
        # `await X` is a transparent wrapper around X's value: an awaited call result reaches
        # the same decision the bare call result would, so it must not stop the flow walk.
        "passthrough_types": ("parenthesized_expression", "not_operator", "boolean_operator",
                              "unary_operator", "await", "keyword_argument"),
        # `keyword_argument` last, and it is a wrapper rather than an operator: Python puts
        # that node between the value and the argument list, so `f(url=self.url)` never
        # reached the argument row that `f(self.url)` reaches. C# already solves the same
        # problem the same way, with its `argument` wrapper listed here. Eleven of
        # psf/requests' forty-five silent states were this one shape.
        "comparison_types": ("comparison_operator",),
        "membership": "comparison_in",
        "this_idents": frozenset({"self"}),
        "constructor_names": frozenset({"__init__"}),
        "constructor_types": (),
        "default_param_types": ("default_parameter", "typed_default_parameter"),
        "default_param_name": "name",
        "fallback_methods": frozenset({"get"}),
        "fallback_operators": frozenset(),
        "try_types": ("try_statement",),
        "handler_types": ("except_clause",),
        "handler_body_types": ("block",),
        "raise_types": ("raise_statement",),
        "raise_names": frozenset(),
        "absent_types": ("none", "false"),
        "control_flow_exceptions": frozenset({"SystemExit", "KeyboardInterrupt", "GeneratorExit"}),
        "suspension_types": ("await",),
        "assertion_types": ("assert_statement", "raise_statement"),
        "container_literal_types": frozenset({"list", "dictionary", "set", "tuple"}),
        "instance_ref_style": "member",
        "instance_enum": "member",
        "binding_sites": {},
        "sink_types": ("expression_statement", "global_statement", "nonlocal_statement"),
        "field_decl_types": (),
        "record_enum": "python_class_body",
        "key_prefix": "",
        # `dict.get(k)` is the same keyed read as `Map.get(k)`, which javascript and
        # typescript have declared since the spec was written. Python declared an empty set,
        # so `self._h.get(k, 0)` fell through to "the method result flows on" and the flow
        # walk then met an assignment it had no row for. `setdefault` and `pop` are keyed
        # too but they mutate, and _PY_MUTATING already claims them; a name in both sets
        # would be read by whichever branch ran first, so `get` is the only addition.
        "mutating": _PY_MUTATING, "keyed_read": frozenset({"get"}),
        "literal_types": _PY_LITERALS,
        "unary_types": ("unary_operator",),
        "value_wrapper_types": ('unary_operator', 'parenthesized_expression'),
        "unread_operand_types": (),
        "module_enum": "python",
        "lvalue_wrapper": "",
        "presence_methods": frozenset(),          # spelled `k in d` / `k not in d`
        "write_methods": _PY_WRITE_ONLY,
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("block", "elif_clause", "else_clause"),
        "delete_stmt_types": ("delete_statement",),
        "read_write_assign_ops": (),  # the language has no conditional-assignment operator
        "write_in_place_ops": {},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {
            "conditional_expression": "second",   # a if <cond> else b: no condition field
            "assert_statement": "first",
            "if_clause": "all",                   # comprehension guard: the node IS a test
        },
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "javascript": {
        "class_types": ("class_declaration",),
        "func_types": ("function_declaration", "method_definition", "arrow_function", "function_expression", "generator_function_declaration"),
        "assign_types": ("assignment_expression", "augmented_assignment_expression"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript_expression",), "sub_value": "object", "sub_index": "index", "sub_positional": False,
        "destructuring_types": ("array_pattern", "object_pattern"),
        "decorator_types": ("decorator",),
        "member_types": ("member_expression",), "mem_object": "object", "mem_attr": "property",
        "member_name_field": None,
        "out_argument_types": (),
        "key_removal_types": ("unary_expression",),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"variable_declarator": ("name", "value")},
        "switch_types": {},
        "immutable_modifiers": frozenset({"const"}),
        "immutable_ctor_rule": False,
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("arguments",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement", "ternary_expression"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "binary_in",
        "this_idents": frozenset({"this"}),
        "constructor_names": frozenset({"constructor"}),
        "constructor_types": (),
        "default_param_types": ("assignment_pattern",),
        "default_param_name": "left",
        "fallback_methods": frozenset(),
        "fallback_operators": frozenset({"??", "||"}),
        "try_types": ("try_statement",),
        "handler_types": ("catch_clause",),
        "handler_body_types": ("statement_block",),
        "raise_types": ("throw_statement",),
        "raise_names": frozenset(),
        "absent_types": ("null", "undefined", "false"),
        "control_flow_exceptions": frozenset(),
        "suspension_types": ("await_expression",),
        "assertion_types": ("throw_statement",),
        "container_literal_types": frozenset({"array", "object"}),
        "instance_ref_style": "member",
        "instance_enum": "member",
        "binding_sites": {"field_definition": "property", "variable_declarator": "name"},
        "sink_types": ("expression_statement",),
        "field_decl_types": ("field_definition",),
        "record_enum": "none",
        "key_prefix": "this.",
        "mutating": _JS_MUTATING, "keyed_read": frozenset({"get", "has"}),
        "literal_types": _JS_LITERALS,
        "unary_types": ("unary_expression",),
        "value_wrapper_types": ('unary_expression', 'parenthesized_expression'),
        "unread_operand_types": (),
        "module_enum": "js",
        "lvalue_wrapper": "",
        "presence_methods": frozenset({"has"}),
        "write_methods": frozenset({"set", "add", "clear", "fill", "copyWithin", "sort", "push", "unshift"}),
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("statement_block", "else_clause"),
        "delete_stmt_types": (),
        "read_write_assign_ops": ("||=", "&&=", "??="),
        "write_in_place_ops": {"update_expression": ("++", "--")},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {"ternary_expression": "field"},
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "java": {
        "class_types": ("class_declaration",),
        "func_types": ("method_declaration", "constructor_declaration"),
        "assign_types": ("assignment_expression",),   # `+=` is an assignment_expression with a += operator
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("array_access",), "sub_value": "array", "sub_index": "index", "sub_positional": False,
        "destructuring_types": (),  # destructuring is a declaration here, not an assignment
        "decorator_types": ("annotation",),
        "member_types": ("field_access",), "mem_object": "object", "mem_attr": "field",
        "member_name_field": "field",
        "out_argument_types": (),
        "key_removal_types": (),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"variable_declarator": ("name", "value")},
        "switch_types": {"switch_expression": ("condition", "switch_block_statement_group")},
        "immutable_modifiers": frozenset({"final"}),
        "immutable_ctor_rule": False,
        "call_types": ("method_invocation",), "flat_call": True,
        "call_fn": "name", "call_args": "arguments", "call_name": "name", "call_recv": "object",
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement", "ternary_expression"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset({"this"}),
        "constructor_names": frozenset(),
        "constructor_types": ("constructor_declaration",),
        "default_param_types": (),
        "default_param_name": "",
        "fallback_methods": frozenset({"getOrDefault"}),
        "fallback_operators": frozenset(),
        "try_types": ("try_statement", "try_with_resources_statement"),
        "handler_types": ("catch_clause",),
        "handler_body_types": ("block",),
        "raise_types": ("throw_statement",),
        "raise_names": frozenset(),
        "absent_types": ("null_literal", "false"),
        "control_flow_exceptions": frozenset(),
        "suspension_types": (),
        "assertion_types": ("assert_statement", "throw_statement"),
        "container_literal_types": frozenset({"array_initializer"}),
        "instance_ref_style": "identifier",
        "instance_enum": "identifier",
        "binding_sites": {"variable_declarator": "name"},
        "sink_types": ("expression_statement",),
        "field_decl_types": ("field_declaration",),
        "record_enum": "none",
        "key_prefix": "",
        "module_enum": "none",
        "mutating": _JAVA_MUTATING, "keyed_read": _JAVA_KEYED_READ,
        "literal_types": _JAVA_LITERALS,
        "unary_types": ("unary_expression",),
        "value_wrapper_types": ('unary_expression', 'parenthesized_expression', 'cast_expression'),
        "unread_operand_types": (),
        "lvalue_wrapper": "",
        # Java has no membership operator: presence is a method.
        "presence_methods": frozenset({"containsKey", "contains", "containsValue"}),
        # `put` returns the PREVIOUS value at the key, so it counts as write-only only when
        # the result is discarded, which _is_pure_write_call checks. remove, poll, pop,
        # replace, merge and the compute family exist to hand a value back and are out.
        "write_methods": frozenset({"put", "putAll", "add", "addAll", "clear", "offer", "push"}),
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("block", "constructor_body"),
        "delete_stmt_types": (),                  # `map.remove(k)` yields the removed value
        "read_write_assign_ops": (),  # the language has no conditional-assignment operator
        "write_in_place_ops": {"update_expression": ("++", "--")},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {"ternary_expression": "field", "assert_statement": "first"},
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "csharp": {
        "class_types": ("class_declaration",),
        "func_types": ("method_declaration", "constructor_declaration"),
        "assign_types": ("assignment_expression",),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("element_access_expression",), "sub_value": "expression", "sub_index": "subscript", "sub_positional": False,
        "destructuring_types": (),  # destructuring is a declaration here, not an assignment
        "decorator_types": ("attribute",),  # C# member access is member_access_expression, so no clash
        "member_types": ("member_access_expression",), "mem_object": "expression", "mem_attr": "name",
        "member_name_field": "name",
        "out_argument_types": ("declaration_expression",),
        "key_removal_types": (),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"variable_declarator": ("name", None)},
        "switch_types": {"switch_statement": ("value", "switch_section")},
        "immutable_modifiers": frozenset({"const", "readonly"}),
        "immutable_ctor_rule": False,
        "call_types": ("invocation_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement", "arrow_expression_clause"),
        # `=> expr` is the body of an expression-bodied member, so its value leaves the
        # member exactly as a spelled return does. Without this row `public int V => _v;`
        # read unresolved while `{ get { return _v; } }` read neutral: one program, two
        # spellings, and only one of them read. 237 sites across the pinned corpus, 228 of
        # them in Newtonsoft.Json.
        "branch_types": ("if_statement", "while_statement", "conditional_expression"),
        # The ternary joins the branch list because its condition IS a condition: the
        # truthiness row already says a state tested for truth is the same two-class split
        # wherever it is written, and a ternary is one of the places it is written.
        # Python is deliberately absent: its conditional_expression carries no named
        # fields, so the condition cannot be read by the `condition` key and adding it
        # would make the reader take the consequence for the condition.
        "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "prefix_unary_expression", "cast_expression", "argument"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset({"this"}),
        "constructor_names": frozenset(),
        "constructor_types": ("constructor_declaration",),
        "default_param_types": ("parameter",),
        "default_param_name": "name",
        "fallback_methods": frozenset({"GetValueOrDefault"}),
        "fallback_operators": frozenset({"??"}),
        "try_types": ("try_statement",),
        "handler_types": ("catch_clause",),
        "handler_body_types": ("block",),
        "raise_types": ("throw_statement",),
        "raise_names": frozenset(),
        "absent_types": ("null_literal", "false"),
        "control_flow_exceptions": frozenset(),
        "suspension_types": ("await_expression",),
        "assertion_types": ("throw_statement",),
        "container_literal_types": frozenset({"array_creation_expression", "initializer_expression"}),
        "instance_ref_style": "identifier",
        "instance_enum": "identifier",
        "binding_sites": {"variable_declarator": "name", "property_declaration": "name"},
        "sink_types": ("expression_statement",),
        "field_decl_types": ("field_declaration", "property_declaration"),
        "record_enum": "none",
        "key_prefix": "",
        "module_enum": "none",
        "mutating": _CS_MUTATING, "keyed_read": _CS_KEYED_READ,
        "literal_types": _CS_LITERALS,
        "unary_types": ("prefix_unary_expression",),
        "value_wrapper_types": ('prefix_unary_expression', 'parenthesized_expression', 'cast_expression'),
        "unread_operand_types": ("sizeof_expression", "typeof_expression"),
        "lvalue_wrapper": "",
        "presence_methods": frozenset({"ContainsKey", "Contains", "ContainsValue"}),
        # Remove and RemoveAt return a bool the caller can branch on, TryAdd likewise, and
        # Pop and Dequeue exist to yield. None of them is write-only.
        "write_methods": frozenset({"Add", "AddRange", "Clear", "Insert", "Push", "Enqueue", "Set"}),
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("block",),
        "delete_stmt_types": (),                  # `dict.Remove(k)` answers with a bool
        "read_write_assign_ops": ("??=",),
        "write_in_place_ops": {"postfix_unary_expression": ("++", "--"), "prefix_unary_expression": ("++", "--")},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {"conditional_expression": "field"},
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "rust": {
        # No classes: state is struct fields used as self.<field> inside a separate
        # impl block, so the impl is the scope and state is enumerated from usage.
        "class_types": ("impl_item",),
        "func_types": ("function_item",),
        "assign_types": ("assignment_expression", "compound_assignment_expr"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("index_expression",), "sub_value": None, "sub_index": None,
        "sub_positional": True,   # index_expression has no fields: [collection, key] by position
        "destructuring_types": (),  # destructuring is a declaration here, not an assignment
        "decorator_types": ("attribute",),  # Rust member access is field_expression, so no clash
        "member_types": ("field_expression",), "mem_object": "value", "mem_attr": "field",
        "member_name_field": None,
        "out_argument_types": (),
        "key_removal_types": (),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"let_declaration": ("pattern", "value")},
        "switch_types": {},
        "immutable_modifiers": frozenset({"const", "static"}),
        "immutable_ctor_rule": False,
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("arguments",),
        "return_types": ("return_expression",),
        "branch_types": ("if_expression", "while_expression"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "reference_expression", "unary_expression", "try_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset({"self"}),
        "constructor_names": frozenset(),
        "constructor_types": (),
        "default_param_types": (),
        "default_param_name": "",
        "fallback_methods": frozenset({"unwrap_or", "unwrap_or_else", "unwrap_or_default"}),
        "fallback_operators": frozenset(),
        "try_types": (),
        "handler_types": (),
        "handler_body_types": (),
        "raise_types": (),
        "raise_names": frozenset(),
        "absent_types": ("unit_expression",),
        "control_flow_exceptions": frozenset(),
        "suspension_types": ("await_expression",),
        "assertion_types": (),
        "container_literal_types": frozenset({"array_expression", "tuple_expression"}),
        "instance_ref_style": "member",
        "instance_enum": "self_usage",
        "binding_sites": {"static_item": "name", "field_declaration": "name", "let_declaration": "pattern"},
        "sink_types": ("expression_statement", "block"),
        "field_decl_types": (),
        "record_enum": "none",
        "key_prefix": "",
        "mutating": _RUST_MUTATING, "keyed_read": _RUST_KEYED_READ,
        "literal_types": _RUST_LITERALS,
        "unary_types": ("unary_expression",),
        "value_wrapper_types": ('unary_expression', 'parenthesized_expression', 'reference_expression', 'type_cast_expression'),
        "unread_operand_types": (),
        "module_enum": "rust",
        "lvalue_wrapper": "",
        "presence_methods": frozenset({"contains_key", "contains"}),
        # HashMap::insert returns the previous value, so the discard check carries it.
        # remove, pop, drain, replace and swap exist to yield and are out.
        "write_methods": frozenset({
            "insert", "push", "push_back", "push_front", "clear", "extend", "append",
            "retain", "truncate",
        }),
        # `self.h.get_mut(&k).unwrap()` reaches a map slot to write through. The unwrap
        # hands back the handle it was given, so the walk has to see past it to find the
        # compound assignment on the other side.
        "value_preserving_methods": frozenset({"unwrap", "expect"}),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("block", "else_clause"),
        "delete_stmt_types": (),                  # `map.remove(&k)` yields an Option
        "read_write_assign_ops": (),  # the language has no conditional-assignment operator
        "write_in_place_ops": {},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {"reference_expression": "value"}, "alias_marker": "mutable_specifier",
        "opaque_region_types": ("macro_invocation",),
        "extra_test_positions": {},               # `if` is an expression, already in branch_types
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "ruby": {
        "class_types": ("class", "module"),
        "func_types": ("method", "singleton_method"),
        "assign_types": ("assignment", "operator_assignment"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("element_reference",), "sub_value": "object", "sub_index": None,
        "sub_positional": True,   # element_reference: [object, key] by position
        "destructuring_types": ("left_assignment_list",),
        "decorator_types": (),    # the language has no decorator syntax
        "member_types": ("call",),   # unused for ivar state, but keep valid node types
        "member_name_field": None,
        "out_argument_types": (),
        "key_removal_types": (),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"assignment": ("left", "right")},
        "switch_types": {},
        "immutable_modifiers": frozenset(),
        "immutable_ctor_rule": False,
        "mem_object": "receiver", "mem_attr": "method",
        "call_types": ("call",), "flat_call": True,
        "call_fn": "method", "call_args": "arguments", "call_name": "method", "call_recv": "receiver",
        "arglist_types": ("argument_list",),
        "return_types": ("return",),
        "branch_types": ("if", "unless", "while", "until", "if_modifier", "unless_modifier", "while_modifier", "until_modifier", "elsif", "conditional"),
        "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_statements", "unary", "begin"),
        "comparison_types": ("binary",),
        "membership": "none",
        "this_idents": frozenset(),
        "constructor_names": frozenset({"initialize"}),
        "constructor_types": (),
        "default_param_types": ("optional_parameter",),
        "default_param_name": "name",
        "fallback_methods": frozenset({"fetch", "dig"}),
        "fallback_operators": frozenset({"||"}),
        "try_types": ("begin",),
        "handler_types": ("rescue",),
        "handler_body_types": ("then",),
        "raise_types": (),
        "raise_names": frozenset({"raise", "fail"}),
        "absent_types": ("nil", "false"),
        "control_flow_exceptions": frozenset({"SystemExit", "Interrupt"}),
        "suspension_types": (),
        "assertion_types": (),
        "container_literal_types": frozenset({"array", "hash"}),
        "instance_ref_style": "member",
        "instance_enum": "ruby_ivar",
        "binding_sites": {},
        "sink_types": ("body_statement",),
        "field_decl_types": (),
        "record_enum": "none",
        "key_prefix": "",
        "module_enum": "none",
        "mutating": _RUBY_MUTATING, "keyed_read": _RUBY_KEYED_READ, "dispatch_methods": _RUBY_DISPATCH,
        "literal_types": _RUBY_LITERALS,
        "unary_types": ("unary",),
        "value_wrapper_types": ('unary', 'parenthesized_statements'),
        "unread_operand_types": (),
        "lvalue_wrapper": "",
        "presence_methods": frozenset({"key?", "has_key?", "include?", "member?"}),
        # `<<` is deliberately absent from the METHOD set: Ruby parses an append as a
        # `binary` node, so the entry carrying it in _RUBY_MUTATING can never match a method
        # name. The operator form is declared in write_in_place_ops below, which is where a
        # node that writes its operand belongs; the `<<` in _RUBY_MUTATING covers only the
        # rare `@xs.<<(x)` spelling and is kept for it.
        "write_methods": frozenset({
            "store", "clear", "concat", "merge!", "update", "reject!", "map!", "fill",
            "push", "append", "unshift", "insert", "delete_if",
        }),
        "value_preserving_methods": frozenset(),
        # Ruby discards nothing syntactically: every expression is a value and only its
        # position decides whether anything reads it. So a write method whose result must
        # be proven unread cannot be proven here, and the rule declines it.
        "discard_types": (),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("then", "else", "body_statement"),
        "delete_stmt_types": (),                  # `h.delete(k)` yields the removed value
        "read_write_assign_ops": ("||=", "&&="),
        "write_in_place_ops": {"binary": ("<<",)},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {"conditional": "field"},
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "c": {
        # No classes or methods: state is file-scope variables only (module_enum: c).
        "class_types": (),
        "func_types": ("function_definition",),
        "assign_types": ("assignment_expression",),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript_expression",), "sub_value": "argument", "sub_index": "index", "sub_positional": False,
        "destructuring_types": (),  # destructuring is a declaration here, not an assignment
        "decorator_types": (),       # the language has no decorator syntax
        "member_types": ("field_expression",), "mem_object": "argument", "mem_attr": "field",
        "member_name_field": "field",
        "out_argument_types": (),
        "key_removal_types": (),
        "cond_at_index": {},
        "writing_builtins": frozenset(),
        "iterate_types": (),
        "local_binding": {"init_declarator": ("declarator", "value")},
        "switch_types": {},
        "immutable_modifiers": frozenset({"const"}),
        "immutable_ctor_rule": False,
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement", "conditional_expression"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression",
                              "pointer_expression", "cast_expression"),
        # `cast_expression` last, and it was the omission: C# has listed it since the
        # table was written, so `(object)x` flowed on there while `(int) g.flag` stopped
        # here and was reported as a construct with no rule. Same two-readers-disagree
        # shape as the Rust borrow wrapper.
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset(),
        "constructor_names": frozenset(),
        "constructor_types": (),
        "default_param_types": (),
        "default_param_name": "",
        "fallback_methods": frozenset(),
        "fallback_operators": frozenset(),
        "try_types": (),
        "handler_types": (),
        "handler_body_types": (),
        "raise_types": (),
        "raise_names": frozenset(),
        "absent_types": ("null",),
        "control_flow_exceptions": frozenset(),
        "suspension_types": (),
        "assertion_types": (),
        "container_literal_types": frozenset({"initializer_list"}),
        "instance_ref_style": "identifier",
        "instance_enum": "none",
        "binding_sites": {"declaration": "declarator", "init_declarator": "declarator", "array_declarator": "declarator", "pointer_declarator": "declarator", "field_declaration": "declarator"},
        "sink_types": ("expression_statement",),
        "field_decl_types": (),
        "record_enum": "c_struct_field",
        "key_prefix": "",
        "mutating": frozenset(), "keyed_read": frozenset(),
        "literal_types": _C_LITERALS,
        "unary_types": ("unary_expression",),
        "value_wrapper_types": ('unary_expression', 'parenthesized_expression', 'cast_expression'),
        "unread_operand_types": ("sizeof_expression",),
        "module_enum": "c",
        "lvalue_wrapper": "",
        # C asks no presence question and grows no container: a fixed array answers for
        # every index whether or not anything was stored there. Both halves of the
        # accumulator rule's gate are unspellable here, so the rule declines rather than
        # stretching an analogy, and C carries no gated-accumulator shape at all.
        "presence_methods": frozenset(),
        "write_methods": frozenset(),
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        "presence_bind_types": (), "blank_idents": frozenset(),
        "gate_fields": ("condition",),
        "gate_body_types": ("compound_statement",),
        "delete_stmt_types": (),
        "read_write_assign_ops": (),  # the language has no conditional-assignment operator
        "write_in_place_ops": {"update_expression": ("++", "--")},
        "opaque_unary_ops": frozenset(),
        "bare_cond_types": {},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {"conditional_expression": "field"},
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
        # No language builtins beyond the shared bounded set.
        "extra_bounded": frozenset(),
        # State does not span methods by receiver type here.
        "scope_by_receiver": False,
    },
    "go": {
        # No classes: state is struct fields, methods bound by a named receiver. State
        # is grouped by receiver type (scope_by_receiver) and keyed <Type>.<field>.
        "class_types": (),
        "func_types": ("function_declaration", "method_declaration", "func_literal"),
        # `:=` is the commonest store in Go and it is a `short_var_declaration`, not an
        # `assignment_statement`. It carries the same `left` and `right` fields and the same
        # expression_list wrapper, so it is the same row, and leaving it out made every
        # idiomatic Go store a construct with no rule. It stays in presence_bind_types too:
        # `_, ok := d[k]` is one of these AND the language's presence test, and the two
        # readings do not collide because the comma-ok read sits on the RIGHT of it.
        "assign_types": ("assignment_statement", "short_var_declaration"),
        "assign_left": "left", "assign_right": "right",
        "lvalue_wrapper": "expression_list",   # Go wraps assignment targets in expression_list
        "subscript_types": ("index_expression",), "sub_value": "operand", "sub_index": "index", "sub_positional": False,
        "destructuring_types": (),  # destructuring is a declaration here, not an assignment
        "decorator_types": (),      # the language has no decorator syntax
        "member_types": ("selector_expression",), "mem_object": "operand", "mem_attr": "field",
        "member_name_field": None,
        "out_argument_types": (),
        "key_removal_types": (),
        "cond_at_index": {},
        # Builtins that WRITE the argument they are handed, rather than returning a
        # value derived from it. `delete(m, k)` removes a key and returns nothing, and
        # it is the plainest key removal Go has; it read as an unmodelled callee
        # because it is not in extra_bounded, which is the list of builtins whose
        # RESULT flows on. Different question, so a different row.
        "writing_builtins": frozenset({"delete", "clear"}),
        "iterate_types": ("range_clause",),
        "local_binding": {"short_var_declaration": ("left", "right")},
        "switch_types": {"expression_switch_statement": ("value", "expression_case")},
        "immutable_modifiers": frozenset({"const"}),
        "immutable_ctor_rule": False,
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        # `for_clause` is the three-clause loop header (`for i := 0; g.live; i++`), and it is
        # the node that carries the `condition` field: the for_statement above it has only a
        # `body`. Both are named, because the two spellings of a Go loop put the condition in
        # two different places and declaring one of them reads the other as no loop at all.
        # The bare form (`for g.live {}`) has no field anywhere and is declared in
        # bare_cond_types instead.
        "branch_types": ("if_statement", "for_statement", "for_clause", "expression_switch_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression", "expression_list"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset(),
        "constructor_names": frozenset(),
        "constructor_types": (),
        "default_param_types": (),
        "default_param_name": "",
        "fallback_methods": frozenset(),
        "fallback_operators": frozenset(),
        "try_types": (),
        "handler_types": (),
        "handler_body_types": (),
        "raise_types": (),
        "raise_names": frozenset(),
        "absent_types": ("nil",),
        "control_flow_exceptions": frozenset(),
        "suspension_types": (),
        "assertion_types": (),
        "container_literal_types": frozenset({"composite_literal"}),
        "instance_ref_style": "member",
        "instance_enum": "none",
        "scope_by_receiver": True,
        "binding_sites": {"var_spec": "name", "field_declaration": "name"},
        "sink_types": ("expression_statement",),
        "field_decl_types": (),
        "record_enum": "none",
        "key_prefix": "",
        "mutating": frozenset(), "keyed_read": frozenset(),
        "extra_bounded": frozenset({"append", "len", "cap", "copy", "make", "new"}),
        "literal_types": _GO_LITERALS,
        "unary_types": ("unary_expression",),
        "value_wrapper_types": ('unary_expression', 'parenthesized_expression'),
        "unread_operand_types": (),
        "module_enum": "go",
        # Go maps carry no methods: a write is an index assignment and a removal is the
        # `delete` builtin, so both method sets are empty on purpose.
        "presence_methods": frozenset(),
        "write_methods": frozenset(),
        "value_preserving_methods": frozenset(),
        "discard_types": ("expression_statement",),
        # `_, ok := d[k]` is Go's presence test. It binds rather than compares, and it sits
        # in the `initializer` of the `if` rather than in its condition, which is why both
        # presence_bind_types and gate_fields carry an entry no other language needs.
        "presence_bind_types": ("short_var_declaration",),
        "blank_idents": frozenset({"_"}),
        "gate_fields": ("condition", "initializer"),
        "gate_body_types": ("block", "statement_list"),
        "delete_stmt_types": (),                  # `delete(d, k)` is a builtin call
        "read_write_assign_ops": (),  # the language has no conditional-assignment operator
        "write_in_place_ops": {"inc_statement": ("++",), "dec_statement": ("--",)},
        "opaque_unary_ops": frozenset({"<-"}),
        "bare_cond_types": {"for_statement": ("block", "for_clause", "range_clause")},
        "alias_types": {}, "alias_marker": "",
        "opaque_region_types": (),
        "extra_test_positions": {},               # no ternary, no assert expression
        # Calls here are not flat, so there is no receiver field on the call node; the
                # receiver is reached through member_types instead. Guarded by flat_call, and
                # written out rather than left absent so no reader has to default it.
        "call_recv": "",
        # No dynamic-dispatch spelling in this grammar.
        "dispatch_methods": frozenset(),
    },
}


# --------------------------------------------------------------------------
# TypeScript follows JavaScript, and diverges only where it is declared to.
#
# The two tables used to be written out separately and agreed on 64 of their 70 fields. A
# rule added to JavaScript reached TypeScript only if whoever added it remembered the
# second copy, and nothing said whether they had. Every defect fixed in this package this
# week was that shape: a construct read under one spelling and missed under another.
#
# Deriving it also settled one that had already happened. TypeScript's func_types listed
# three node types where JavaScript listed five, so a TypeScript `const f = function(){}`
# or `function* g(){}` was not a function to any rule keyed on that field. The
# tree-sitter-typescript grammar produces both node types; the omission was a copy that
# never caught up, not a grammar difference, so func_types is NOT overridden below.
#
# Each override names a real difference in the TypeScript grammar, with the reason.
# --------------------------------------------------------------------------

_TYPESCRIPT: LangSpec = {**LANG_SPEC["javascript"]}

# A class field parses as `public_field_definition` in TypeScript and `field_definition`
# in JavaScript, and the name sits in a different field.
_TYPESCRIPT["binding_sites"] = {"public_field_definition": "name", "variable_declarator": "name"}
_TYPESCRIPT["field_decl_types"] = ("public_field_definition",)
# `readonly x = 1` is TypeScript's own immutability marker; JavaScript has only `const`.
_TYPESCRIPT["immutable_modifiers"] = frozenset({"const", "readonly"})
# `x!` and `x as T` are TypeScript-only wrappers, and both are transparent: the value under
# them is the value. A walk that stopped at either would lose the operand.
_TYPESCRIPT["passthrough_types"] = ("parenthesized_expression", "unary_expression",
                                    "non_null_expression", "as_expression")
_TYPESCRIPT["value_wrapper_types"] = ("unary_expression", "parenthesized_expression",
                                      "non_null_expression", "as_expression")
# An annotated parameter parses as `required_parameter` whether it carries a default or not,
# so the node type alone says nothing and the `=` token is what decides.
_TYPESCRIPT["default_param_types"] = ("assignment_pattern", "required_parameter",
                                      "optional_parameter")
_TYPESCRIPT["default_param_name"] = "pattern"

# The overridden keys, named once so a test can assert that nothing ELSE diverged. Written
# out per key above rather than merged from a dict of object, so each value is checked
# against the field it lands in instead of being waved past the checker with an ignore.
TYPESCRIPT_OVERRIDES = frozenset({
    "binding_sites", "default_param_name", "default_param_types", "field_decl_types",
    "immutable_modifiers", "passthrough_types", "value_wrapper_types",
})

LANG_SPEC["typescript"] = _TYPESCRIPT
