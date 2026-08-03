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
from typing import Any

from l1_analyzer.indicators import (
    LANG_CFG,
    _find_module_mutable_names,
    _get_parser,
    _read_source_bytes,
    bucketed_paths,
)

_IGNORE = ("tests", "test", "conformance")

NEUTRAL = "neutral"
PROMISCUOUS = "promiscuous"
UNRESOLVED = "unresolved"

# Per-reference categories (internal): how one use of a state value is consumed.
_WRITE = "write"          # target of an assignment / mutating method: not a decision
_OUTPUT = "output"        # returned or otherwise handed to the caller: compositional
_FINITE = "finite"        # reaches a decision whose reaching partition is enumerable
_UNBOUNDED = "unbounded"  # reaches a decision whose reaching partition is provably unbounded
_UNDECIDABLE = "undecidable"  # reaches a context whose reaching-set cannot be decided

# Builtins that read a bounded feature of their argument (the value flows onward).
_BOUNDED_BUILTINS = frozenset({"len", "isinstance", "bool", "id", "type", "hash", "ord", "abs"})
# Builtins that consume a value as an effect/assertion, not a partitioning decision.
_EFFECT_CALLS = frozenset({"print", "repr", "str", "format", "log", "logging"})
# Comparison operators: a state value meeting one is split into finitely many classes.
_COMPARISON_OPS = frozenset({"<", ">", "<=", ">=", "==", "!=", "===", "!==", "<>"})

_PY_MUTATING = frozenset({
    "append", "add", "update", "extend", "insert", "pop", "remove", "discard",
    "clear", "setdefault", "popitem", "sort", "appendleft",
})
_JS_MUTATING = frozenset({
    "push", "pop", "shift", "unshift", "splice", "fill", "sort", "copyWithin",
    "set", "add", "delete", "clear",
})
_JAVA_MUTATING = frozenset({
    "put", "putAll", "putIfAbsent", "merge", "replace", "compute", "computeIfAbsent",
    "computeIfPresent", "add", "addAll", "remove", "removeAll", "retainAll", "clear",
    "set", "offer", "push", "poll", "pop",
})
_CS_MUTATING = frozenset({
    "Add", "AddRange", "AddOrUpdate", "TryAdd", "Remove", "RemoveAt", "Clear",
    "Insert", "Push", "Pop", "Enqueue", "Dequeue", "Set",
})
# Map lookups keyed by an argument: like a subscript read, the key's domain decides
# the partition (unbounded key -> unbounded partition).
_RUST_MUTATING = frozenset({
    "insert", "push", "push_back", "push_front", "remove", "pop", "pop_back", "pop_front",
    "clear", "extend", "append", "retain", "set", "replace", "swap", "truncate", "drain",
})
_JAVA_KEYED_READ = frozenset({"get", "containsKey", "getOrDefault", "contains", "containsValue"})
_CS_KEYED_READ = frozenset({"ContainsKey", "TryGetValue", "Contains", "ContainsValue", "GetValueOrDefault"})
_RUST_KEYED_READ = frozenset({"get", "get_mut", "contains_key", "contains", "get_or_insert"})
_RUBY_MUTATING = frozenset({
    "push", "store", "delete", "delete_if", "clear", "concat", "unshift", "append",
    "pop", "shift", "insert", "merge!", "update", "reject!", "map!", "fill", "<<",
})
_RUBY_KEYED_READ = frozenset({"key?", "has_key?", "include?", "member?", "fetch", "dig", "value?", "has_value?"})
# Invoking a value as code: the callee is chosen at runtime, an unbounded target.
_RUBY_DISPATCH = frozenset({"call", "send", "public_send", "__send__", "instance_eval", "instance_exec", "method"})

_PY_LITERALS = frozenset({"string", "integer", "float", "true", "false", "none", "concatenated_string"})
_JS_LITERALS = frozenset({"number", "string", "true", "false", "null", "undefined", "template_string"})
_JAVA_LITERALS = frozenset({
    "decimal_integer_literal", "hex_integer_literal", "octal_integer_literal",
    "string_literal", "true", "false", "null_literal", "character_literal",
    "decimal_floating_point_literal",
})
_CS_LITERALS = frozenset({
    "integer_literal", "real_literal", "string_literal", "character_literal",
    "null_literal", "boolean_literal",
})
_RUST_LITERALS = frozenset({
    "integer_literal", "float_literal", "string_literal", "raw_string_literal",
    "char_literal", "boolean_literal", "true", "false",
})
_RUBY_LITERALS = frozenset({
    "integer", "float", "string", "simple_symbol", "true", "false", "nil", "character",
})
_C_LITERALS = frozenset({"number_literal", "char_literal", "string_literal", "true", "false", "null"})
_GO_LITERALS = frozenset({
    "int_literal", "float_literal", "imaginary_literal", "rune_literal",
    "interpreted_string_literal", "raw_string_literal", "true", "false", "nil",
})


# --------------------------------------------------------------------------
# Per-language node-type vocabulary. Every value below is the grammar's own node
# type / field name for a shared concept; the algorithm reads only through this
# spec, never a hard-coded string, so one implementation serves every language.
# --------------------------------------------------------------------------

LANG_SPEC: dict[str, dict[str, Any]] = {
    "python": {
        "class_types": ("class_definition",),
        "func_types": ("function_definition",),
        "assign_types": ("assignment", "augmented_assignment"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript",), "sub_value": "value", "sub_index": "subscript",
        "member_types": ("attribute",), "mem_object": "object", "mem_attr": "attribute",
        "call_types": ("call",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": ("elif_clause",),
        "passthrough_types": ("parenthesized_expression", "not_operator", "boolean_operator", "unary_operator"),
        "comparison_types": ("comparison_operator",),
        "membership": "comparison_in",
        "this_idents": frozenset({"self"}),
        "instance_ref_style": "member",
        "field_decl_types": (),
        "key_prefix": "",
        "mutating": _PY_MUTATING, "keyed_read": frozenset(),
        "literal_types": _PY_LITERALS,
        "module_enum": "python",
    },
    "typescript": {
        "class_types": ("class_declaration",),
        "func_types": ("function_declaration", "method_definition", "arrow_function"),
        "assign_types": ("assignment_expression", "augmented_assignment_expression"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript_expression",), "sub_value": "object", "sub_index": "index",
        "member_types": ("member_expression",), "mem_object": "object", "mem_attr": "property",
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("arguments",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression", "non_null_expression", "as_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "binary_in",
        "this_idents": frozenset({"this"}),
        "instance_ref_style": "member",
        "field_decl_types": ("public_field_definition",),
        "key_prefix": "this.",
        "mutating": _JS_MUTATING, "keyed_read": frozenset({"get", "has"}),
        "literal_types": _JS_LITERALS,
        "module_enum": "js",
    },
    "javascript": {
        "class_types": ("class_declaration",),
        "func_types": ("function_declaration", "method_definition", "arrow_function", "function_expression", "generator_function_declaration"),
        "assign_types": ("assignment_expression", "augmented_assignment_expression"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript_expression",), "sub_value": "object", "sub_index": "index",
        "member_types": ("member_expression",), "mem_object": "object", "mem_attr": "property",
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("arguments",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "binary_in",
        "this_idents": frozenset({"this"}),
        "instance_ref_style": "member",
        "field_decl_types": ("field_definition",),
        "key_prefix": "this.",
        "mutating": _JS_MUTATING, "keyed_read": frozenset({"get", "has"}),
        "literal_types": _JS_LITERALS,
        "module_enum": "js",
    },
    "java": {
        "class_types": ("class_declaration",),
        "func_types": ("method_declaration", "constructor_declaration"),
        "assign_types": ("assignment_expression",),   # `+=` is an assignment_expression with a += operator
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("array_access",), "sub_value": "array", "sub_index": "index",
        "member_types": ("field_access",), "mem_object": "object", "mem_attr": "field",
        "call_types": ("method_invocation",), "flat_call": True,
        "call_fn": "name", "call_args": "arguments", "call_name": "name", "call_recv": "object",
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset({"this"}),
        "instance_ref_style": "identifier",
        "field_decl_types": ("field_declaration",),
        "key_prefix": "",
        "mutating": _JAVA_MUTATING, "keyed_read": _JAVA_KEYED_READ,
        "literal_types": _JAVA_LITERALS,
    },
    "csharp": {
        "class_types": ("class_declaration",),
        "func_types": ("method_declaration", "constructor_declaration"),
        "assign_types": ("assignment_expression",),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("element_access_expression",), "sub_value": "expression", "sub_index": "subscript",
        "member_types": ("member_access_expression",), "mem_object": "expression", "mem_attr": "name",
        "call_types": ("invocation_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "prefix_unary_expression", "cast_expression", "argument"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset({"this"}),
        "instance_ref_style": "identifier",
        "field_decl_types": ("field_declaration",),
        "key_prefix": "",
        "mutating": _CS_MUTATING, "keyed_read": _CS_KEYED_READ,
        "literal_types": _CS_LITERALS,
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
        "member_types": ("field_expression",), "mem_object": "value", "mem_attr": "field",
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
        "instance_ref_style": "member",
        "instance_enum": "self_usage",
        "field_decl_types": (),
        "key_prefix": "",
        "mutating": _RUST_MUTATING, "keyed_read": _RUST_KEYED_READ,
        "literal_types": _RUST_LITERALS,
        "module_enum": "rust",
    },
    "ruby": {
        "class_types": ("class", "module"),
        "func_types": ("method", "singleton_method"),
        "assign_types": ("assignment", "operator_assignment"),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("element_reference",), "sub_value": "object", "sub_index": None,
        "sub_positional": True,   # element_reference: [object, key] by position
        "member_types": ("call",),   # unused for ivar state, but keep valid node types
        "mem_object": "receiver", "mem_attr": "method",
        "call_types": ("call",), "flat_call": True,
        "call_fn": "method", "call_args": "arguments", "call_name": "method", "call_recv": "receiver",
        "arglist_types": ("argument_list",),
        "return_types": ("return",),
        "branch_types": ("if", "unless", "while", "until", "if_modifier", "unless_modifier", "while_modifier", "until_modifier", "elsif"),
        "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_statements", "unary", "begin"),
        "comparison_types": ("binary",),
        "membership": "none",
        "this_idents": frozenset(),
        "instance_ref_style": "member",
        "instance_enum": "ruby_ivar",
        "field_decl_types": (),
        "key_prefix": "",
        "mutating": _RUBY_MUTATING, "keyed_read": _RUBY_KEYED_READ, "dispatch_methods": _RUBY_DISPATCH,
        "literal_types": _RUBY_LITERALS,
    },
    "c": {
        # No classes or methods: state is file-scope variables only (module_enum: c).
        "class_types": (),
        "func_types": ("function_definition",),
        "assign_types": ("assignment_expression",),
        "assign_left": "left", "assign_right": "right",
        "subscript_types": ("subscript_expression",), "sub_value": "argument", "sub_index": "index",
        "member_types": ("field_expression",), "mem_object": "argument", "mem_attr": "field",
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "while_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression", "pointer_expression"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset(),
        "instance_ref_style": "identifier",
        "field_decl_types": (),
        "key_prefix": "",
        "mutating": frozenset(), "keyed_read": frozenset(),
        "literal_types": _C_LITERALS,
        "module_enum": "c",
    },
    "go": {
        # No classes: state is struct fields, methods bound by a named receiver. State
        # is grouped by receiver type (scope_by_receiver) and keyed <Type>.<field>.
        "class_types": (),
        "func_types": ("function_declaration", "method_declaration", "func_literal"),
        "assign_types": ("assignment_statement",),
        "assign_left": "left", "assign_right": "right",
        "lvalue_wrapper": "expression_list",   # Go wraps assignment targets in expression_list
        "subscript_types": ("index_expression",), "sub_value": "operand", "sub_index": "index",
        "member_types": ("selector_expression",), "mem_object": "operand", "mem_attr": "field",
        "call_types": ("call_expression",), "flat_call": False,
        "call_fn": "function", "call_args": "arguments", "call_name": None,
        "arglist_types": ("argument_list",),
        "return_types": ("return_statement",),
        "branch_types": ("if_statement", "for_statement", "expression_switch_statement"), "branch_cond": "condition",
        "elif_types": (),
        "passthrough_types": ("parenthesized_expression", "unary_expression", "expression_list"),
        "comparison_types": ("binary_expression",),
        "membership": "none",
        "this_idents": frozenset(),
        "instance_ref_style": "member",
        "scope_by_receiver": True,
        "field_decl_types": (),
        "key_prefix": "",
        "mutating": frozenset(), "keyed_read": frozenset(),
        "extra_bounded": frozenset({"append", "len", "cap", "copy", "make", "new"}),
        "literal_types": _GO_LITERALS,
        "module_enum": "go",
    },
}


def _text(node: Any) -> str:
    return node.text.decode("utf8", errors="ignore") if node is not None and node.text else ""


def _field(node: Any, name: str) -> Any:
    return node.child_by_field_name(name) if node is not None and name else None


def _same(a: Any, b: Any) -> bool:
    """Node identity by id. child_by_field_name returns a fresh wrapper each call,
    so `is` is unreliable; compare the stable node id instead."""
    return a is not None and b is not None and a.id == b.id


def _first_named(node: Any) -> Any:
    return next((c for c in node.children if c.is_named), None) if node is not None else None


def _arg_value(node: Any) -> Any:
    """Unwrap a C# `argument` wrapper to the expression it carries."""
    if node is not None and node.type == "argument":
        return _first_named(node)
    return node


def _sub_named(subscript: Any) -> list[Any]:
    return [c for c in subscript.children if c.is_named]


def _sub_collection(subscript: Any, sp: dict[str, Any]) -> Any:
    """The collection being indexed. Rust's index_expression has no fields, so the
    collection is the first named child; other grammars name it."""
    if sp.get("sub_positional"):
        named = _sub_named(subscript)
        return named[0] if named else None
    return _field(subscript, sp["sub_value"])


def _sub_key(subscript: Any, sp: dict[str, Any]) -> Any:
    """The key/index node of a subscript. Rust indexes positionally (second named
    child); C# wraps the key in a bracketed_argument_list; others name it."""
    if sp.get("sub_positional"):
        named = _sub_named(subscript)
        return named[1] if len(named) > 1 else None
    idx = _field(subscript, sp["sub_index"])
    if idx is not None and idx.type == "bracketed_argument_list":
        return _arg_value(_first_named(idx))
    return idx


def _first_arg(call: Any, sp: dict[str, Any]) -> Any:
    return _arg_value(_first_named(_field(call, sp["call_args"])))


def _callee_name(call: Any, sp: dict[str, Any]) -> str:
    if call is None or call.type not in sp["call_types"]:
        return ""
    return _text(_field(call, sp["call_name"] if sp["flat_call"] else sp["call_fn"]))


# --------------------------------------------------------------------------
# Closed-set detection (Python only). Membership `x in S` is a finite partition
# when S is a statically fixed collection. Element *values* are irrelevant to the
# count: a tuple of symbolic constants bounds the partition exactly as literals do.
# --------------------------------------------------------------------------

def _is_immutable_collection(rhs: Any) -> bool:
    if rhs is None:
        return False
    if rhs.type == "tuple":
        return True
    if rhs.type == "call":
        return _text(_field(rhs, "function")) == "frozenset"
    return False


def _collect_closed_sets(root: Any) -> set[str]:
    names: set[str] = set()

    def walk(n: Any) -> None:
        if n.type == "assignment":
            left, rhs = _field(n, "left"), _field(n, "right")
            if left is not None and _is_immutable_collection(rhs):
                if left.type == "identifier":
                    names.add(_text(left))
                elif left.type == "attribute":
                    attr = _field(left, "attribute")
                    if attr is not None:
                        names.add(_text(attr))
        for c in n.children:
            walk(c)

    walk(root)
    return names


def _is_closed_set(node: Any, closed_sets: set[str]) -> bool:
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


def _is_unbounded_value(node: Any, sp: dict[str, Any]) -> bool:
    """A value used as a lookup key / index. Literals are bounded; anything else
    (a parameter, a variable) ranges over an unbounded domain."""
    return node is not None and node.type not in sp["literal_types"]


# --------------------------------------------------------------------------
# Membership and comparison helpers.
# --------------------------------------------------------------------------

def _membership_operands(node: Any, sp: dict[str, Any]) -> tuple[Any, Any] | None:
    """(left, right) for an `in` / `not in` membership test, else None."""
    style = sp["membership"]
    if style == "comparison_in" and node.type == "comparison_operator":
        if not any(c.type == "in" for c in node.children):
            return None
        named = [c for c in node.children if c.is_named]
        return (named[0], named[-1]) if len(named) >= 2 else None
    if style == "binary_in" and node.type == "binary_expression":
        if _text(_field(node, "operator")) == "in":
            return _field(node, "left"), _field(node, "right")
    return None


def _is_comparison(node: Any, sp: dict[str, Any]) -> bool:
    if node.type == "comparison_operator":       # Python: always a comparison
        return True
    return _text(_field(node, "operator")) in _COMPARISON_OPS


# --------------------------------------------------------------------------
# Per-reference categorisation.
# --------------------------------------------------------------------------

def _is_lvalue(node: Any, sp: dict[str, Any]) -> bool:
    """True if `node` is the assigned lvalue of an assignment, unwrapping an optional
    lvalue wrapper (Go puts assignment targets inside an expression_list)."""
    wrapper = sp.get("lvalue_wrapper")
    p = node.parent
    if wrapper and p is not None and p.type == wrapper:
        node, p = p, p.parent
    return p is not None and p.type in sp["assign_types"] and _same(_field(p, sp["assign_left"]), node)


def _is_write_target(ref: Any, parent: Any, sp: dict[str, Any]) -> bool:
    if _is_lvalue(ref, sp):
        return True
    # S[k] = v  -> ref (S) is the collection of a subscript that is the assign target
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), ref):
        if _is_lvalue(parent, sp):
            return True
    return False


def _keyed_read(key_node: Any, sp: dict[str, Any]) -> str:
    return _UNBOUNDED if _is_unbounded_value(key_node, sp) else _FINITE


def _categorize(ref: Any, sp: dict[str, Any], closed_sets: set[str]) -> str:
    """How this single reference to a state value is consumed."""
    parent = ref.parent
    if parent is None:
        return _OUTPUT

    if _is_write_target(ref, parent, sp):
        return _WRITE

    # S(...) : the state is the call target -> dynamic dispatch, unbounded callee.
    if not sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), ref):
        return _UNDECIDABLE

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
            return _UNDECIDABLE                   # invoking a stored callable: unbounded target
        if called and attr in sp["mutating"]:
            return _WRITE
        if called and attr in sp["keyed_read"]:
            return _keyed_read(_first_arg(gp, sp), sp)
        if called:
            return _flow(gp, sp, closed_sets)     # method result flows on (.clone(), .len(), an accessor)
        return _flow(parent, sp, closed_sets)     # plain field access: self.x.y

    # S.method(args) flattened (Java method_invocation / Ruby call with a receiver).
    if sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_recv"]), ref):
        name = _text(_field(parent, sp["call_name"]))
        if name in sp.get("dispatch_methods", frozenset()):
            return _UNDECIDABLE
        if name in sp["mutating"]:
            return _WRITE
        if name in sp["keyed_read"]:
            return _keyed_read(_first_arg(parent, sp), sp)
        return _flow(parent, sp, closed_sets)

    # f(..., S, ...) : argument to a call.
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets)
        if fname in _EFFECT_CALLS:
            return _OUTPUT
        return _UNDECIDABLE

    return _flow(ref, sp, closed_sets)


def _flow(node: Any, sp: dict[str, Any], closed_sets: set[str]) -> str:
    """Categorise how a value derived from the state (node) reaches a decision."""
    parent = node.parent
    if parent is None:
        return _OUTPUT
    if parent.type in sp["return_types"]:
        return _OUTPUT
    # The state is invoked as a callable, possibly through a wrapper: `(self.f)(x)`
    # in Rust reaches the call via a parenthesized_expression. Dynamic dispatch,
    # unbounded callee. (Direct `S(x)` is caught earlier in _categorize.)
    if not sp["flat_call"] and parent.type in sp["call_types"] and _same(_field(parent, sp["call_fn"]), node):
        return _UNDECIDABLE
    if parent.type in sp["passthrough_types"]:
        return _flow(parent, sp, closed_sets)
    if parent.type in sp["comparison_types"]:
        mem = _membership_operands(parent, sp)
        if mem is not None:
            left, right = mem
            if _same(node, right):          # x in S : node is the container
                if _is_closed_set(node, closed_sets):
                    return _FINITE
                return _UNBOUNDED if _is_unbounded_value(left, sp) else _FINITE
            return _FINITE if _is_closed_set(right, closed_sets) else _UNBOUNDED   # S in Y
        if _is_comparison(parent, sp):
            return _FINITE                  # S <cmp> other : two classes
        return _flow(parent, sp, closed_sets)   # arithmetic / logical: derived value flows on
    if parent.type in sp["branch_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return _FINITE                      # truthiness: two classes
    if parent.type in sp["elif_types"] and _same(_field(parent, sp["branch_cond"]), node):
        return _FINITE
    if parent.type in sp["arglist_types"]:
        fname = _callee_name(parent.parent, sp)
        if fname in _BOUNDED_BUILTINS or fname in sp.get("extra_bounded", frozenset()):
            return _flow(parent.parent, sp, closed_sets)
        if fname in _EFFECT_CALLS:
            return _OUTPUT
        return _UNDECIDABLE
    if parent.type in sp["subscript_types"] and _same(_sub_collection(parent, sp), node):
        return _keyed_read(_sub_key(parent, sp), sp)
    return _OUTPUT


def _verdict(categories: list[str]) -> tuple[str, bool]:
    """Combine per-reference categories into (verdict, drives_decision)."""
    if _UNDECIDABLE in categories:
        return UNRESOLVED, True
    if _UNBOUNDED in categories:
        return PROMISCUOUS, True
    if _FINITE in categories:
        return NEUTRAL, True
    return NEUTRAL, False   # observe-only or output-only: empty reaching-set


# --------------------------------------------------------------------------
# State enumeration and file analysis.
# --------------------------------------------------------------------------

def _refs(scope: Any, predicate: Any) -> list[Any]:
    out: list[Any] = []

    def walk(n: Any) -> None:
        if predicate(n):
            out.append(n)
        for c in n.children:
            walk(c)

    walk(scope)
    return out


def _local_refs(scope: Any, predicate: Any, sp: dict[str, Any]) -> list[Any]:
    """Like _refs, but does not descend into a nested class: an inner class owns its
    own fields and is analysed as its own scope, so the enclosing class must not
    harvest the inner class's state (which double-counts it)."""
    out: list[Any] = []

    def walk(n: Any, is_root: bool) -> None:
        if not is_root and n.type in sp["class_types"]:
            return
        if predicate(n):
            out.append(n)
        for c in n.children:
            walk(c, False)

    walk(scope, True)
    return out


def _field_decl_names(fd: Any, sp: dict[str, Any]) -> list[str]:
    """Declared field names inside a field-declaration node. TypeScript names the
    field directly; Java and C# nest one or more variable_declarators."""
    if fd.type == "public_field_definition":   # TypeScript
        name = _field(fd, "name")
        return [_text(name)] if name is not None else []
    if fd.type == "field_definition":          # JavaScript
        name = _field(fd, "property")
        return [_text(name)] if name is not None else []
    names: list[str] = []
    for vd in _refs(fd, lambda n: n.type == "variable_declarator"):
        name = _field(vd, "name")
        if name is not None:
            names.append(_text(name))
    return names


def _enum_instance_state(cls: Any, sp: dict[str, Any]) -> set[str]:
    """State keys for a class. Member-style languages name state through a receiver
    (self.x / this.x) and may also declare fields; identifier-style languages (Java,
    C#) reference fields by bare name, so the key is the field name itself."""
    keys: set[str] = set()
    if sp.get("instance_enum") == "ruby_ivar":
        # Ruby: state is @instance_variables, a node type of their own (no receiver).
        for iv in _local_refs(cls, lambda n: n.type == "instance_variable", sp):
            keys.add(_text(iv))
        return keys
    if sp.get("instance_enum") == "self_usage":
        # Rust: the field list is on the struct, but state is used as self.<field> in
        # the impl (reads and writes). Enumerate from that usage, not from assignments.
        for m in _local_refs(cls, lambda n: n.type in sp["member_types"], sp):
            obj = _field(m, sp["mem_object"])
            if obj is not None and _text(obj) in sp["this_idents"]:
                keys.add(_text(m))              # "self.<field>"
        return keys
    if sp["instance_ref_style"] == "member":
        for n in _local_refs(cls, lambda n: n.type in sp["assign_types"], sp):
            left = _field(n, sp["assign_left"])
            if left is not None and left.type in sp["member_types"]:
                obj = _field(left, sp["mem_object"])
                if obj is not None and _text(obj) in sp["this_idents"]:
                    keys.add(_text(left))       # "self.x" / "this.x"
    for fd in _local_refs(cls, lambda n: n.type in sp["field_decl_types"], sp):
        for name in _field_decl_names(fd, sp):
            keys.add(sp["key_prefix"] + name)
    return keys


def _go_type_name(typ: Any) -> str | None:
    """The struct type a Go receiver binds to, unwrapping `*T` to `T`."""
    if typ is None:
        return None
    if typ.type == "pointer_type":
        return _go_type_name(_first_named(typ))
    if typ.type == "type_identifier":
        return _text(typ)
    return None


def _go_receiver(method: Any) -> tuple[str | None, str | None]:
    """(receiver type, receiver variable name) for a Go method_declaration."""
    recv = _field(method, "receiver")               # parameter_list `(c *Cache)`
    pd = _first_named(recv) if recv is not None else None
    if pd is None:
        return None, None
    name = _field(pd, "name")
    return _go_type_name(_field(pd, "type")), (_text(name) if name is not None else None)


def _go_receiver_findings(root: Any, rel: str, sp: dict[str, Any], closed_sets: set[str], immutable_ctors: set[str]) -> list[dict[str, Any]]:
    """Go state, grouped by receiver TYPE across all its methods (spec section 4:
    analyse state across the whole type, not one method). A field is `<recv>.<field>`
    inside a method; the key is `<Type>.<field>` so it is stable across methods whose
    receivers are named differently."""
    by_type: dict[str, list[tuple[Any, str]]] = {}
    for m in _refs(root, lambda n: n.type == "method_declaration"):
        tname, rname = _go_receiver(m)
        if tname and rname:
            by_type.setdefault(tname, []).append((m, rname))

    findings: list[dict[str, Any]] = []
    for tname, methods in by_type.items():
        field_refs: dict[str, list[Any]] = {}
        for method, rname in methods:
            for sel in _refs(method, lambda n: n.type == "selector_expression"):
                operand = _field(sel, "operand")
                if operand is not None and operand.type == "identifier" and _text(operand) == rname:
                    field = _text(_field(sel, "field"))
                    field_refs.setdefault(field, []).append(sel)
        for field, refs in field_refs.items():
            findings.append(_finding(f"{tname}.{field}", refs, rel, sp, closed_sets, immutable_ctors))
    return findings


def _state_refs(scope: Any, key: str, sp: dict[str, Any]) -> list[Any]:
    if sp.get("instance_enum") == "ruby_ivar":
        return _local_refs(scope, lambda n: n.type == "instance_variable" and _text(n) == key, sp)
    if sp["instance_ref_style"] == "member":
        return _local_refs(scope, lambda n: n.type in sp["member_types"] and _text(n) == key, sp)
    return _local_refs(scope, lambda n: n.type == "identifier" and _text(n) == key, sp)


def _enum_module_state(root: Any, sp: dict[str, Any], cfg: dict[str, Any]) -> set[str]:
    """Top-level mutable bindings, per language (spec key module_enum). Java/C#/Ruby
    keep module/static state out of this prototype and rely on class scope; C is the
    reverse (no classes, so file-scope variables are the only state)."""
    mode = sp.get("module_enum")
    names: set[str] = set()
    if mode == "python":
        return _find_module_mutable_names(root, cfg)
    if mode == "js":
        # top-level `let`/`var` declarators (const is not module-mutable state)
        for decl in root.children:
            if decl.type == "lexical_declaration":
                if decl.children and _text(decl.children[0]) == "const":
                    continue
            elif decl.type != "variable_declaration":
                continue
            for vd in _refs(decl, lambda n: n.type == "variable_declarator"):
                name = _field(vd, "name")
                if name is not None and name.type == "identifier":
                    names.add(_text(name))
        return names
    if mode == "rust":
        # `static mut NAME` only; a plain static or const is immutable, not counted.
        for st in root.children:
            if st.type == "static_item" and any(c.type == "mutable_specifier" for c in st.children):
                name = _field(st, "name")
                if name is not None:
                    names.add(_text(name))
        return names
    if mode == "go":
        # package-level `var` declarations (const is immutable, not counted)
        for decl in root.children:
            if decl.type == "var_declaration":
                for vs in _refs(decl, lambda n: n.type == "var_spec"):
                    nm = _field(vs, "name")
                    if nm is not None and nm.type == "identifier":
                        names.add(_text(nm))
        return names
    if mode == "c":
        # C has no classes: file-scope variable declarations are the only state. Skip
        # function declarations and typedefs; take the innermost declared identifier.
        for decl in root.children:
            if decl.type != "declaration" or any(c.type == "type_definition" for c in decl.children):
                continue
            for dcl in decl.children:
                nm = _c_declarator_name(dcl)
                if nm is not None:
                    names.add(nm)
        return names
    return set()


def _c_declarator_name(node: Any) -> str | None:
    """The identifier a C declarator binds, unwrapping init/array/pointer declarators.
    Returns None for a function declarator (not a variable) or a non-declarator node."""
    if node is None:
        return None
    if node.type == "identifier":
        return _text(node)
    if node.type == "function_declarator":
        return None
    if node.type in ("init_declarator", "array_declarator", "pointer_declarator"):
        return _c_declarator_name(_field(node, "declarator"))
    return None


# --- immutable-constant recognition (Python only) ---------------------------
# A state key assigned once from an immutable construction, never mutated and never
# called, has a one-value domain: it is a constant, NEUTRAL wherever it flows,
# because no callee can mutate an immutable value. A one-level follow of the
# constructor tells the meter its return is immutable, so a declared machine (a
# MappingProxyType-wrapped table passed to a lookup) resolves on the evidence,
# reading no framework declaration.

_IMMUTABLE_WRAPPERS = frozenset({"MappingProxyType", "frozenset", "tuple", "bytes"})


def _rhs_is_immutable(rhs: Any, immutable_ctors: set[str]) -> bool:
    if rhs is None:
        return False
    if rhs.type in ("tuple", "true", "false", "none", "integer", "float", "string", "concatenated_string"):
        return True
    if rhs.type == "call":
        fn = _text(_field(rhs, "function"))
        return fn in _IMMUTABLE_WRAPPERS or fn in immutable_ctors
    return False


def _returns_immutable(func_node: Any) -> bool:
    returns = _refs(func_node, lambda n: n.type == "return_statement")
    if not returns:
        return False
    for r in returns:
        val = _first_named(r)
        if not _rhs_is_immutable(val, frozenset()):
            return False
    return True


def _collect_immutable_ctors(root: Any) -> set[str]:
    out: set[str] = set()
    for fn in _refs(root, lambda n: n.type == "function_definition"):
        name = _field(fn, "name")
        if name is not None and _returns_immutable(fn):
            out.add(_text(name))
    return out


def _reaches_decision(refs: list[Any], sp: dict[str, Any]) -> bool:
    for r in refs:
        p = r.parent
        if p is None or p.type in sp["return_types"]:
            continue
        if _is_write_target(r, p, sp):
            continue
        return True
    return False


def _immutable_const_verdict(refs: list[Any], immutable_ctors: set[str], sp: dict[str, Any]) -> tuple[str, bool] | None:
    """(NEUTRAL, drives) if the state is an immutable constant: assigned exactly once
    from an immutable construction, never mutated, never called. Else None."""
    assigns: list[Any] = []
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


def _finding(key: str, refs: list[Any], rel: str, sp: dict[str, Any], closed_sets: set[str], immutable_ctors: set[str]) -> dict[str, Any]:
    const = _immutable_const_verdict(refs, immutable_ctors, sp) if sp is LANG_SPEC["python"] else None
    if const is not None:
        verdict, drives = const
    else:
        verdict, drives = _verdict([_categorize(r, sp, closed_sets) for r in refs])
    line = min((r.start_point[0] + 1 for r in refs), default=1)
    return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel, "line": line}


def _analyze_file(root: Any, rel: str, sp: dict[str, Any], cfg: dict[str, Any], immutable_ctors: set[str]) -> list[dict[str, Any]]:
    closed_sets = _collect_closed_sets(root) if sp is LANG_SPEC["python"] else set()
    findings: list[dict[str, Any]] = []

    for name in _enum_module_state(root, sp, cfg):
        refs = _refs(root, lambda n, nm=name: n.type == "identifier" and _text(n) == nm)
        if refs:
            findings.append(_finding(name, refs, rel, sp, closed_sets, immutable_ctors))

    if sp.get("scope_by_receiver"):    # Go: state spans methods, grouped by receiver type
        findings.extend(_go_receiver_findings(root, rel, sp, closed_sets, immutable_ctors))

    for cls in _refs(root, lambda n: n.type in sp["class_types"]):
        for key in _enum_instance_state(cls, sp):
            refs = _state_refs(cls, key, sp)
            if refs:
                findings.append(_finding(key, refs, rel, sp, closed_sets, immutable_ctors))

    return findings


def _na(lang: str) -> dict[str, Any]:
    return {
        "verdict": "n/a", "value": "n/a", "band": "n/a",
        "counts": {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0},
        "coverage": {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)},
        "resolvable_fraction": "n/a",
        "findings": [],
        "bucketed": {"counts": {}, "paths": []},
        "details": f"finite-testability classifier has no spec for {lang} yet",
    }


def classify(repo: Path, lang: str) -> dict[str, Any]:
    """L1.18b: the finite-testability verdict distribution. Additive; never
    consulted by L1.18 itself."""
    if lang not in LANG_SPEC:
        return _na(lang)
    sp = LANG_SPEC[lang]
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    # conformance/ holds law/spec scaffolding and test doubles (fault-injection
    # markers, failing connections), not production state; skip it like tests. docs,
    # tooling, and loose entry-point scripts are scoped out by _read_source_bytes and
    # disclosed below (never a silent skip).
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=_IGNORE)
    bucketed = bucketed_paths(repo, cfg["extensions"], _IGNORE)

    # First pass: parse every file and collect the repo's immutable constructors
    # (functions whose returns are all immutable), so a constant built by one can be
    # resolved by a one-level follow. Second pass: analyze with that knowledge.
    roots: list[tuple[Any, str]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        roots.append((parser.parse(src).root_node, rel))
    immutable_ctors: set[str] = set()
    if sp is LANG_SPEC["python"]:
        for root, _rel in roots:
            immutable_ctors |= _collect_immutable_ctors(root)

    findings: list[dict[str, Any]] = []
    for root, rel in roots:
        findings.extend(_analyze_file(root, rel, sp, cfg, immutable_ctors))

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

    return {
        "verdict": verdict,
        "value": f"{counts[NEUTRAL]} neutral / {counts[PROMISCUOUS]} promiscuous / {counts[UNRESOLVED]} unresolved",
        "band": "n/a",
        "counts": counts,
        "coverage": coverage,
        "resolvable_fraction": resolvable,
        "findings": findings,
        "bucketed": bucketed,
        "details": (
            f"finite-testability: {counts[NEUTRAL]} neutral, {counts[PROMISCUOUS]} promiscuous, "
            f"{counts[UNRESOLVED]} unresolved across {total} pieces of state; "
            f"resolvable fraction {resolvable}"
        ),
    }
