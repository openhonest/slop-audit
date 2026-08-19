"""The per-language method and literal vocabularies the grammar table is built from.

Data, not code. It moved out of lang_spec.py when that file crossed the god-file threshold
this package gates on, which the completed vocabulary keys pushed it over. Three things
lived in one file: the LangSpec type, these vocabularies, and the nine-language table that
composes them. The table is what a reader opens lang_spec for; these are its ingredients.

Every name is re-exported from lang_spec, so nothing that reads them had to change.
"""

from __future__ import annotations

# Comparison operators, as every grammar in the table spells them. A state value meeting one
# is split into finitely many classes; a binary node carrying any OTHER operator is
# arithmetic, and the value it produces flows on. Both readings are needed by state_bounds
# and by state_bounds_filters, and the two cannot import each other, so the set lives here.
COMPARISON_OPS = frozenset({"<", ">", "<=", ">=", "==", "!=", "===", "!==", "<>"})

_PY_MUTATING = frozenset({
    "append", "add", "update", "extend", "insert", "pop", "remove", "discard",
    "clear", "setdefault", "popitem", "sort", "appendleft",
})
# Every method that mutates a Python container in place, which is _PY_MUTATING plus the
# names the classifier has no use for. state_bounds_filters imports this as _IN_PLACE, and
# derives python's write-only set from it below, so the two cannot drift: a name added to
# _PY_MUTATING is in both sets on the next line.
_PY_IN_PLACE = _PY_MUTATING | frozenset({
    "reverse", "intersection_update", "difference_update", "symmetric_difference_update",
})
# pop, popitem and setdefault mutate AND hand the stored value back, so a reference sitting
# in one of them is not confined however the result is used. Excluded by name rather than by
# checking whether the caller reads the result: the call's purpose IS the read.
_PY_WRITE_ONLY = _PY_IN_PLACE - frozenset({"pop", "popitem", "setdefault"})

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

# A unary operator applied to a literal is itself one compile-time value, so it
# partitions a domain exactly as a bare literal does: `s[-1]` is the last element,
# not an unbounded lookup. Every grammar spells the node differently, and none of
# them treat the operator token as named, so unwrapping to the first named child
# reaches the operand. `-x` unwraps to an identifier and stays unbounded, which is
# the whole point of unwrapping rather than whitelisting the node type.
#
# C is listed even though `s[-1]` lexes as a single signed `number_literal`: the
# fold is whitespace-sensitive, and `s[- 1]` is a unary_expression like everywhere
# else. Binary operators are deliberately absent - `s[1 - 1]` stays unbounded,
# which is conservative (never a false green).


# --------------------------------------------------------------------------
# Per-language node-type vocabulary. Every value below is the grammar's own node
# type / field name for a shared concept; the algorithm reads only through this
# spec, never a hard-coded string, so one implementation serves every language.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Decision points, per grammar (L1.19, static half).
#
# THE RULE, stated so a reader can check the published number:
#
#   A decision point is a construct at which control can take more than one path.
#
#   - An `if`, an `elif`/`elsif`, an `unless`, a ternary or conditional expression:
#     one each. An `else` is NOT a decision; it is the other path of the `if` that
#     already counted.
#   - Each ARM of a switch or match, including the default or wildcard arm: one
#     each. The switch or match CONTAINER is not counted separately, because its
#     arms are where the choosing happens.
#
# Declared per language rather than shared, because the same string means different
# things in different grammars. Ruby's `if`, `unless`, `case` and `when` are NAMED
# node types; Python's `if` is an unnamed keyword token sitting inside the
# if_statement that already matched. One shared frozenset cannot tell those apart,
# which is how the double-count survived: every `if` in all nine languages counted
# twice, while seven real constructs went unseen. Read by subscript, so a language
# that declares nothing raises rather than reaching a default.
#
# Every type below was probed against the grammar on 2026-08-17 and is NAMED; the
# enumerator walks named children only, so an unnamed keyword token can never match.
#
# Two grammar-specific readings that a reader would otherwise have to derive:
#
#   java  -- `switch_label` is the arm. Both the classic form (`case 1:`) and the
#            arrow form (`case 1 ->`) emit one label per arm, so the single type
#            covers both. `switch_block_statement_group` would count only the
#            classic form, and counting both would double every classic arm.
#   ruby  -- Ruby spells a `case`'s default arm with the same `else` node it uses
#            for an `if`'s else, so no node type can tell the two apart. A Ruby
#            `case ... else` therefore counts its `when` arms only. This is a known
#            asymmetry with the seven grammars whose default arm has a type of its
#            own and does count; it is named here rather than left to be found.
DECISION_NODE_TYPES: dict[str, frozenset[str]] = {
    "python": frozenset({
        "if_statement", "elif_clause", "conditional_expression", "case_clause",
    }),
    "ruby": frozenset({
        "if", "unless", "elsif", "if_modifier", "unless_modifier",
        "conditional", "when", "in_clause",
    }),
    "c": frozenset({
        "if_statement", "conditional_expression", "case_statement",
    }),
    "java": frozenset({
        "if_statement", "ternary_expression", "switch_label",
    }),
    "csharp": frozenset({
        "if_statement", "conditional_expression", "switch_section", "switch_expression_arm",
    }),
    "rust": frozenset({
        "if_expression", "match_arm",
    }),
    "go": frozenset({
        "if_statement", "expression_case", "type_case", "default_case", "communication_case",
    }),
    "javascript": frozenset({
        "if_statement", "ternary_expression", "switch_case", "switch_default",
    }),
    "typescript": frozenset({
        "if_statement", "ternary_expression", "switch_case", "switch_default",
    }),
}
