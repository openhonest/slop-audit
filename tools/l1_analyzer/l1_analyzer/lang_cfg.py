"""The per-language tree-sitter vocabulary the indicators read.

Data, not code. It moved out of indicators.py when that file crossed the god-file
threshold this package gates on, which it had been sitting one line under: a
thousand-line file at 999 is a god-file waiting for the next commit. Separating the data
from the code is the standard answer, and it is the one this project gives other people.

Everything still imports LANG_CFG and LangCfg from indicators, which re-exports them, so
no reader had to learn a new name to keep working.
"""

from __future__ import annotations

from typing import TypedDict

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript
from tree_sitter import Language

# ---------------------------------------------------------------------------
# Tree-sitter setup for language-agnostic source analysis
# ---------------------------------------------------------------------------

class LangCfg(TypedDict, total=False):
    """Per-language tree-sitter config for L1.12-L1.20. total=False: each language
    fills the subset it needs. Typing this replaces the dict[str, Any] the cfg params
    used to be, so a config-key typo is a type error, not a silent KeyError."""
    language: Language
    extensions: tuple[str, ...]
    function_types: tuple[str, ...]
    member_access: str
    this_ident: frozenset[str]
    module_level_assign: tuple[str, ...]
    type_escape_patterns: tuple[str, ...]
    type_escape_nonpositions: tuple[str, ...]
    type_cast_calls: tuple[str, ...]
    annotation_escape_nodes: tuple[str, ...]
    annotation_escape_names: tuple[str, ...]
    member_op: str
    module_scan: str
    receiver_scan: str
    const_keywords: tuple[str, ...]
    field_decl_types: tuple[str, ...]
    immutable_modifiers: frozenset[str]
    instance_field_types: tuple[str, ...]
    raw_mut_patterns: tuple[str, ...]


LANG_CFG: dict[str, LangCfg] = {
    "python": {
        "language": Language(tree_sitter_python.language()),
        "extensions": (".py",),
        "function_types": ("function_definition",),
        "member_access": "attribute",
        "this_ident": {"self"},
        "module_level_assign": ("assignment", "augmented_assignment"),
        "type_escape_patterns": ("Any",),  # typing.Any; plus comments # type: ignore
        "type_escape_nonpositions": ("import_statement", "import_from_statement"),
        "type_cast_calls": ("cast",),
        # Read the binding name from the assignment's `left` field, not by text-
        # splitting the node. See ../../../research/amendments/amendment-2026-08-01-l1-18-module-global.md.
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "python_fields",
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # No keyword makes a module binding immutable here.
        "const_keywords": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "rust": {
        "language": Language(tree_sitter_rust.language()),
        "extensions": (".rs",),
        "function_types": ("function_item",),
        "member_access": "field_expression",
        # A Rust method is a `function_item` carrying a `self_parameter`; `self.field`
        # is a `field_expression` reading "self.<field>". Treating `self` as the
        # receiver counts that access exactly as Python's does. Free functions have
        # no `self.` access, so this never over-counts them.
        "this_ident": {"self"},
        "module_level_assign": ("let_declaration", "static_item", "const_item"),
        # A Rust global is mutable state iff its declaration carries `mut`
        # (`static mut NAME: TYPE`). The name is the declaration's identifier child;
        # the legacy text split grabbed the type (`i32`) instead, so no global was
        # ever recognized. See ../../../research/amendments/amendment-2026-08-02-rust-receiver-and-static.md.
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "mutable_specifier",
        "type_escape_patterns": (),
        "type_escape_nonpositions": (),
        "type_cast_calls": (),
        # Retained per ../../../research/amendments/amendment-2026-07-31-rust-raw-pattern-scope.md; structural
        # detection above now carries the load, and these never fire inside a body.
        "raw_mut_patterns": ("static mut", "&mut self", "mut self"),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # No keyword makes a module binding immutable here.
        "const_keywords": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
    },
    "c": {
        "language": Language(tree_sitter_c.language()),
        "extensions": (".c", ".h"),
        "function_types": ("function_definition",),
        "member_access": "field_expression",
        "this_ident": set(),
        "module_level_assign": ("declaration", "init_declarator"),
        "type_escape_patterns": (),
        "type_escape_nonpositions": (),
        "type_cast_calls": (),
        "member_op": "->",
        "receiver_scan": "c_pointer_params",
        "module_scan": "c_declarations",
        # C's only immutability keyword. It used to inherit a shared default carrying
        # `let `, `val ` and `readonly `, none of which are C.
        "const_keywords": ("const ",),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "java": {
        "language": Language(tree_sitter_java.language()),
        "extensions": (".java",),
        "function_types": ("method_declaration", "constructor_declaration"),
        "member_access": "field_access",
        "this_ident": {"this"},
        "module_level_assign": ("field_declaration", "local_variable_declaration"),
        "type_escape_patterns": ("Object",),  # raw types, etc.
        "type_escape_nonpositions": ("import_declaration",),
        "type_cast_calls": (),
        # Java's suppression marker is an annotation node, not a comment. See
        # ../../../research/amendments/amendment-2026-08-14-java-suppression-marker.md.
        "annotation_escape_nodes": ("annotation", "marker_annotation"),
        "annotation_escape_names": ("SuppressWarnings",),
        # A Java field is state wherever it sits in the class body, and it is reached
        # by bare name, not through `this.`. See
        # ../../../research/amendments/amendment-2026-08-15-l1-18-corrected-ratio.md.
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "class_fields",
        "field_decl_types": ("field_declaration",),
        "immutable_modifiers": frozenset({"final"}),
        # No keyword makes a module binding immutable here.
        "const_keywords": (),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "csharp": {
        "language": Language(tree_sitter_c_sharp.language()),
        "extensions": (".cs",),
        "function_types": ("method_declaration", "constructor_declaration"),
        "member_access": "member_access_expression",
        "this_ident": {"this"},
        "module_level_assign": ("field_declaration", "local_declaration_statement"),
        "type_escape_patterns": ("object", "dynamic"),
        "type_escape_nonpositions": ("using_directive",),
        "type_cast_calls": (),
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "class_fields",
        "field_decl_types": ("field_declaration",),
        "immutable_modifiers": frozenset({"readonly", "const"}),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # No keyword makes a module binding immutable here.
        "const_keywords": (),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "javascript": {
        "language": Language(tree_sitter_javascript.language()),
        "extensions": (".js", ".jsx", ".mjs", ".cjs"),
        "function_types": ("function_declaration", "function_expression", "generator_function_declaration", "method_definition", "arrow_function"),
        "member_access": "member_expression",
        "this_ident": {"this"},
        "module_level_assign": ("variable_declaration", "lexical_declaration"),
        "type_escape_patterns": (),  # untyped
        "type_escape_nonpositions": (),
        "type_cast_calls": (),
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "text",
        # `const` bindings are immutable; `let`/`var` are mutable module state
        "const_keywords": ("const ",),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "ruby": {
        "language": Language(tree_sitter_ruby.language()),
        "extensions": (".rb",),
        "function_types": ("method", "singleton_method"),
        "member_access": "call",
        "this_ident": {"self"},
        # Ruby signals external mutable state through @instance and $global variables,
        # not a `self.`-prefixed member access.
        "instance_field_types": ("instance_variable", "global_variable"),
        "module_level_assign": ("assignment", "operator_assignment"),
        "type_escape_patterns": (),  # untyped
        "type_escape_nonpositions": (),
        "type_cast_calls": (),
        "member_op": ".",
        "receiver_scan": "fixed",
        "module_scan": "text",
        # Ruby has no immutability keyword: a constant is spelled in capitals, which
        # the scan already honours. The empty tuple says so; it used to inherit a
        # default whose words (`let `, `val `, `final `) are not Ruby at all.
        "const_keywords": (),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
    "go": {
        "language": Language(tree_sitter_go.language()),
        "extensions": (".go",),
        "function_types": ("function_declaration", "method_declaration"),
        "member_access": "selector_expression",
        # Go has no fixed receiver keyword; the receiver name is parsed per method.
        "this_ident": set(),
        "module_level_assign": ("var_declaration",),
        "type_escape_patterns": ("any",),  # Go's `any` alias for interface{}
        "type_escape_nonpositions": ("import_declaration", "import_spec"),
        "type_cast_calls": (),
        "member_op": ".",
        "receiver_scan": "go_method_receiver",
        "module_scan": "text",
        "const_keywords": ("const ",),
        # No annotation can suppress a type check in this language.
        "annotation_escape_names": (),
        "annotation_escape_nodes": (),
        # Class fields are not how module state is spelled here.
        "field_decl_types": (),
        "immutable_modifiers": frozenset(),
        # No instance- or global-variable sigil in this grammar.
        "instance_field_types": (),
        # No text-level mutability marker to look for.
        "raw_mut_patterns": (),
    },
}

# --------------------------------------------------------------------------
# TypeScript follows JavaScript here too, and diverges only where it is declared to.
#
# The two entries were written out separately and the TypeScript function_types listed
# three node types where JavaScript listed five. A TypeScript `const f = function(){}` or
# `function* g(){}` was therefore not a function to L1.18, which is the denominator of the
# unbounded-state share, and to everything else that enumerates functions. The
# tree-sitter-typescript grammar produces both node types, so this was a copy that never
# caught up rather than a grammar difference. It is not overridden below.
#
# The same omission had also been made in lang_spec's LangSpec table, independently. Two
# tables, two copies each, one construct: this is what a copied vocabulary costs.
# --------------------------------------------------------------------------

_TYPESCRIPT_CFG: LangCfg = {**LANG_CFG["javascript"]}

_TYPESCRIPT_CFG["language"] = Language(tree_sitter_typescript.language_typescript())
_TYPESCRIPT_CFG["extensions"] = (".ts", ".tsx")
# TypeScript has types to escape from; JavaScript has none, so its patterns are empty.
_TYPESCRIPT_CFG["type_escape_patterns"] = ("any", "unknown")  # plus // @ts-ignore
_TYPESCRIPT_CFG["type_escape_nonpositions"] = ("import_statement", "pair")

# The overridden keys, named once so a test can assert that nothing ELSE diverged. Written
# out per key rather than merged from a dict of object, so each value is checked against
# the field it lands in instead of being waved past the checker with an ignore.
TYPESCRIPT_CFG_OVERRIDES = frozenset({
    "language", "extensions", "type_escape_patterns", "type_escape_nonpositions",
})

LANG_CFG["typescript"] = _TYPESCRIPT_CFG
