//! Reading a slot declared inside a record. Ported from l1_analyzer.record_state.
//!
//! The classifier reaches most state from a USE, and a slot declared once and thereafter
//! only used is spelled one way at its declaration and another at every use. This module
//! owns the declaration half.

use crate::nodes::{field, local_descendants, text};
use tree_sitter::Node;

/// The field carrying the declared name, for declarations that name it directly.
///
/// A C# auto-property is the reason this table exists. The classifier's field vocabulary
/// named `field_declaration` alone, so the same dictionary was read when it was written
/// `Dictionary<string,int> cache;` and invisible when it was written
/// `Dictionary<string,int> Cache { get; set; }`, which is the spelling the language's own
/// style guide asks for on anything public. 678 of Newtonsoft.Json's 1,360 state
/// declarations and 267 of RestSharp's 378 are spelled that way.
fn direct_name_field(node_type: &str) -> Option<&'static str> {
    match node_type {
        "public_field_definition" => Some("name"),    // TypeScript
        "field_definition" => Some("property"),       // JavaScript
        "property_declaration" => Some("name"),       // C#
        _ => None,
    }
}

/// The names declared by one field-declaration node.
///
/// TypeScript, JavaScript and a C# property name the slot directly; a Java or C# field
/// nests one or more declarators, because `int a, b;` is one declaration of two slots.
pub fn field_decl_names(fd: Node, src: &[u8]) -> Vec<String> {
    if let Some(direct) = direct_name_field(fd.kind()) {
        return match field(Some(fd), direct) {
            Some(name) => vec![text(Some(name), src)],
            None => Vec::new(),
        };
    }
    local_descendants(fd, &[])
        .into_iter()
        .filter(|n| n.kind() == "variable_declarator")
        .filter_map(|vd| field(Some(vd), "name").map(|name| text(Some(name), src)))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nodes::descendants;
    use crate::parser_for;

    fn names(source: &str, lang: &str, node_type: &str) -> Vec<String> {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        let fd = descendants(tree.root_node())
            .into_iter()
            .find(|n| n.kind() == node_type)
            .unwrap_or_else(|| panic!("no {node_type} in the fixture"));
        field_decl_names(fd, &bytes)
    }

    #[test]
    fn one_declaration_of_two_slots_yields_two_names() {
        assert_eq!(names("class S { int a, b; }\n", "java", "field_declaration"),
                   vec!["a", "b"]);
    }

    #[test]
    fn a_csharp_auto_property_names_its_slot_directly() {
        // 678 of Newtonsoft.Json's 1,360 state declarations are spelled this way, and the
        // classifier read none of them until this node type was added.
        let source = "class S { public int Cache { get; set; } }\n";
        assert_eq!(names(source, "csharp", "property_declaration"), vec!["Cache"]);
    }

    #[test]
    fn a_typescript_field_names_its_slot_directly() {
        assert_eq!(names("class S { cache: number = 0; }\n", "typescript",
                         "public_field_definition"), vec!["cache"]);
    }

    #[test]
    fn a_javascript_field_names_its_slot_under_a_different_field() {
        // The grammar files it as `property` where TypeScript files it as `name`, which is
        // why the table is keyed by node type rather than shared across the two.
        assert_eq!(names("class S { cache = {}; }\n", "javascript", "field_definition"),
                   vec!["cache"]);
    }
}
