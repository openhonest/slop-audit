//! How one declaration site is NAMED, ported from l1_analyzer.state_sites.
//!
//! Two independent walks read the same files: the census counts the places state is
//! spelled, and the classifier enumerates state from its references. Neither could say
//! anything about the other's units until they agreed on a name for a site. `declared`
//! counted declarations and `admitted` counted conclusions, so their ratio compared two
//! unlike things: one record of five fields beside one module binding reported six
//! declared, one admitted, and published a coverage of 0.167 with nothing missed.
//!
//! A shared NAME is what the comparison needs, and it is the only thing shared here. The
//! counting stays independent, which is the whole reason the census exists; a shared
//! enumerator would make the two agree by construction and prove nothing. This module
//! holds no walk and no rule about what state is. Given a node one walk is looking at, it
//! says what to call the declaration site that node sits on.
//!
//! A SITE IS (kind, owner, name). The kind is the construct. The name is the declared
//! identifier. The owner is the record that declares it, named by its own name and not by
//! its byte offset, which is the change that made the two walks comparable: the census
//! walks down from the record and always holds it, while the classifier mostly arrives
//! from a USE (`self.cache` inside an impl, `s.cache` inside a Go method) and has no path
//! back to the declaring record without resolving a type. What both can see is a name.
//! `struct Store` and `impl Store` agree on "Store" without either resolving anything.
//!
//! WHERE THE CORRESPONDENCE FAILS, in full, because a silent failure here reads as a
//! coverage gap that is really a naming gap:
//!
//! - An ANONYMOUS record has no name to agree on. Its owner is `@<byte offset>`, which
//!   both walks can compute only when both hold the record node. The census always does;
//!   the classifier does for a C struct and never for a Go anonymous struct type, so a
//!   field of one can never be matched and reads as unvisited.
//! - TWO RECORDS OF THE SAME NAME in one file collapse to one owner, so their same-named
//!   fields become one site. Both walks count them once, in the same direction.
//! - RUST names the owner from the `impl` block, so a struct with no impl in the same file
//!   has no path from any use back to its fields. Those read as unvisited, which is true:
//!   nothing in this file's reading looked at them.
//! - GO names the owner from the `type_spec` the struct type sits under, and the
//!   classifier names it from the method receiver's type. A struct type not bound to a
//!   named type has no type_spec and is unmatched.

use crate::nodes::{field, first_named, text};
use tree_sitter::Node;

/// The declaration kinds, one per construct a language spells state with.
///
/// They are finer than the three the census started with (field / attribute / module), and
/// every extra cut is where capability was MEASURED to differ inside one of the old
/// buckets: a C# auto-property and a C# field were both "field", and the enumerator reads
/// one and not the other. A kind that hides a capability difference hides a blind spot.
pub const MODULE_BINDING: &str = "module_binding";
pub const CLASS_BODY_BINDING: &str = "class_body_binding";
pub const RECEIVER_ATTRIBUTE: &str = "receiver_attribute";
pub const INSTANCE_VARIABLE: &str = "instance_variable";
pub const FIELD_DECLARATION: &str = "field_declaration";
pub const PROPERTY_DECLARATION: &str = "property_declaration";

/// One declaration site: the construct, the record that declares it, and the declared
/// name. `owner` is the empty string at module scope, which is the one owner both walks
/// can name without looking at anything.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Site {
    pub kind: &'static str,
    pub owner: String,
    pub name: String,
}

impl Site {
    pub fn new(kind: &'static str, owner: impl Into<String>, name: impl Into<String>) -> Self {
        Site { kind, owner: owner.into(), name: name.into() }
    }
}

/// The kind each field-declaration node type belongs to, read from the node the parser
/// produced rather than from the language.
///
/// Looked up and refused, never defaulted: a node type nobody assigned a kind must be a
/// refusal on the next run, because a default kind files a new construct under an existing
/// capability answer and hides it there.
pub fn decl_kind(node_type: &str) -> Option<&'static str> {
    match node_type {
        "field_declaration" => Some(FIELD_DECLARATION),
        "constant_declaration" => Some(FIELD_DECLARATION),    // Java, inside an interface
        "public_field_definition" => Some(FIELD_DECLARATION), // TypeScript
        "field_definition" => Some(FIELD_DECLARATION),        // JavaScript
        "property_declaration" => Some(PROPERTY_DECLARATION), // C#
        _ => None,
    }
}

/// Rust type expressions that wrap the name of a type, and the field holding the inner
/// one. `impl Store` names the owner directly; `impl<T> Store<T>` and `impl a::Store` reach
/// the same struct through a wrapper, and the census sees only `struct Store`, so the
/// wrappers are peeled to the bare name.
fn rust_type_wrapper(node_type: &str) -> Option<&'static str> {
    match node_type {
        "generic_type" => Some("type"),
        "scoped_type_identifier" => Some("name"),
        "reference_type" => Some("type"),
        _ => None,
    }
}

/// What to call the record a declaration sits in.
///
/// None is module scope, spelled as the empty string. A record with a `name` field is
/// called by its name, which is the only handle a walk arriving from a USE can produce. A
/// record with no name gets its byte offset, which only a walk holding the record node can
/// produce, and that is the honest answer: an anonymous record cannot be named from a
/// distance.
pub fn owner_name(record: Option<Node>, src: &[u8]) -> String {
    let Some(node) = record else { return String::new() };
    match field(Some(node), "name") {
        Some(named) => text(Some(named), src),
        None => format!("@{}", node.start_byte()),
    }
}

/// The owner of the nearest ancestor record of one of `record_types`, or module scope.
///
/// Nearest, not outermost: a class nested in a class owns its own body, and charging the
/// outer one with the inner one's fields would make two records into one site.
pub fn enclosing_owner(node: Node, record_types: &[&str], src: &[u8]) -> String {
    let mut parent = node.parent();
    while let Some(candidate) = parent {
        if record_types.contains(&candidate.kind()) {
            return owner_name(Some(candidate), src);
        }
        parent = candidate.parent();
    }
    String::new()
}

/// The struct an `impl` block belongs to, by the name the struct declares itself with.
///
/// Rust is the one language whose classifier scope is not the record: state is enumerated
/// from `self.<field>` inside an impl, and the fields are declared on a struct somewhere
/// else. The impl names its type and the struct names itself, and those two names are the
/// whole of the correspondence. A struct whose impl is in another file is never visited
/// from here.
pub fn rust_impl_owner(impl_item: Node, src: &[u8]) -> String {
    let mut typ = field(Some(impl_item), "type");
    while let Some(node) = typ {
        let Some(inner_field) = rust_type_wrapper(node.kind()) else { break };
        typ = field(Some(node), inner_field).or_else(|| first_named(Some(node)));
    }
    text(typ, src)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser_for;

    fn parse(source: &str, lang: &str) -> (tree_sitter::Tree, Vec<u8>) {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        (parser.parse(&bytes, None).expect("a parse"), bytes)
    }

    fn first_of<'t>(tree: &'t tree_sitter::Tree, kind: &str) -> Node<'t> {
        crate::nodes::descendants(tree.root_node())
            .into_iter()
            .find(|n| n.kind() == kind)
            .unwrap_or_else(|| panic!("no {kind} in the fixture"))
    }

    #[test]
    fn module_scope_is_the_empty_string_because_both_walks_can_name_it() {
        assert_eq!(owner_name(None, b""), "");
    }

    #[test]
    fn a_record_is_called_by_the_name_it_declares() {
        let (tree, src) = parse("struct Store { cache: i32 }", "rust");
        assert_eq!(owner_name(Some(first_of(&tree, "struct_item")), &src), "Store");
    }

    #[test]
    fn an_anonymous_record_is_named_by_its_offset_and_says_so() {
        // The honest answer, not a workaround: a record with no name cannot be named from
        // a distance, and `@` marks that this owner only one of the two walks can produce.
        let (tree, src) = parse("package p\n\nvar x struct { n int }\n", "go");
        let owner = owner_name(Some(first_of(&tree, "struct_type")), &src);
        assert!(owner.starts_with('@'), "{owner}");
    }

    #[test]
    fn the_nearest_record_owns_a_declaration_and_not_the_outermost() {
        let (tree, src) = parse(
            "class Outer:\n    class Inner:\n        x = 1\n", "python");
        let assignment = first_of(&tree, "assignment");
        assert_eq!(enclosing_owner(assignment, &["class_definition"], &src), "Inner");
    }

    #[test]
    fn a_declaration_outside_every_record_is_at_module_scope() {
        let (tree, src) = parse("x = 1\n", "python");
        let assignment = first_of(&tree, "assignment");
        assert_eq!(enclosing_owner(assignment, &["class_definition"], &src), "");
    }

    #[test]
    fn a_plain_impl_names_its_struct() {
        let (tree, src) = parse("impl Store { fn f(&self) {} }", "rust");
        assert_eq!(rust_impl_owner(first_of(&tree, "impl_item"), &src), "Store");
    }

    #[test]
    fn a_wrapped_impl_is_peeled_to_the_name_the_struct_declares() {
        // The census sees `struct Store` and nothing else. An owner of "Store<T>" or
        // "a::Store" agrees with nothing, so every field of a generic or scoped type would
        // read as unvisited.
        for source in ["impl<T> Store<T> { fn f(&self) {} }",
                       "impl a::Store { fn f(&self) {} }"] {
            let (tree, src) = parse(source, "rust");
            assert_eq!(rust_impl_owner(first_of(&tree, "impl_item"), &src), "Store",
                       "{source}");
        }
    }

    #[test]
    fn a_node_type_with_no_kind_is_refused_rather_than_defaulted() {
        // A construct nobody has classified must not be filed under an existing capability
        // answer, because that is where a blind spot goes to hide.
        assert_eq!(decl_kind("field_declaration"), Some(FIELD_DECLARATION));
        assert_eq!(decl_kind("property_declaration"), Some(PROPERTY_DECLARATION));
        assert_eq!(decl_kind("something_no_grammar_here_produces"), None);
    }

    #[test]
    fn two_records_of_one_name_collapse_to_one_site_and_this_is_recorded() {
        // Named as a known limit in the module docstring. The test exists so the limit is
        // a measured fact rather than a paragraph, and so a future fix has something to
        // fail against.
        let (tree, src) = parse("class A:\n    x = 1\n\nclass A:\n    x = 2\n", "python");
        let owners: Vec<String> = crate::nodes::descendants(tree.root_node())
            .into_iter()
            .filter(|n| n.kind() == "assignment")
            .map(|n| enclosing_owner(n, &["class_definition"], &src))
            .collect();
        assert_eq!(owners, vec!["A", "A"], "two records, one owner name");
    }
}
