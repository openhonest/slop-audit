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
    sub_positional: bool
    member_types: tuple[str, ...]
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
    instance_ref_style: str
    instance_enum: str
    field_decl_types: tuple[str, ...]
    key_prefix: str
    mutating: frozenset[str]
    keyed_read: frozenset[str]
    dispatch_methods: frozenset[str]
    literal_types: frozenset[str]
    module_enum: str
    lvalue_wrapper: str
    scope_by_receiver: bool
    extra_bounded: frozenset[str]


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

LANG_SPEC: dict[str, LangSpec] = {
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
