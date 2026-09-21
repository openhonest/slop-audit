//! Which references actually denote a piece of state. Ported from l1_analyzer.state_refs.
//!
//! One question, asked before any verdict is reached: this identifier's text matches the
//! state's name, but does it MEAN the state? Three ways it does not, and each was found by
//! a repository reading wrong rather than by inspection. The name is part of an import or
//! package path and binds nothing here. The name is a TYPE that a field happens to share.
//! A nearer parameter binds it, so the reference belongs to the parameter.

use crate::lang_spec::LangSpec;
use crate::nodes::{children, descendants, text};
use tree_sitter::Node;

/// The node types whose subtree is an import or package path.
const IMPORT_PATH_TYPES: &[&str] =
    &["import", "using_directive", "package_declaration", "package_clause"];

/// True when the identifier is part of an import or package path, so it binds nothing here
/// and is not a reference to same-named state.
pub fn under_import_path(node: Node) -> bool {
    let mut parent = node.parent();
    while let Some(p) = parent {
        if IMPORT_PATH_TYPES.iter().any(|marker| p.kind().contains(marker)) {
            return true;
        }
        parent = p.parent();
    }
    false
}

/// True when the identifier is naming a TYPE rather than referring to state.
///
/// `private static readonly Encoding Encoding = null;` names a type and then a field, both
/// `Encoding`. References are collected by matching identifier text, so the type
/// occurrence was collected as a reference to the field, and no dispatch row covers an
/// identifier in a declaration's type slot: it surfaced as an unmodelled construct, which
/// reads as a missing rule when the reference should never have been collected at all.
///
/// The test is the grammar's own `type` field, which is the convention across every
/// grammar in the table rather than a per-language spelling, so this needs no vocabulary
/// entry. The walk is bounded to the enclosing type expression: a nullable, generic or
/// array type wraps the name in one or two more nodes before the field appears, and
/// stopping at the first non-type ancestor keeps `Foo.Bar` on the value side out of it.
pub fn in_type_position(node: Node) -> bool {
    let mut current = node;
    let mut parent = node.parent();
    while let Some(p) = parent {
        if let Some(slot) = p.child_by_field_name("type") {
            if slot.id() == current.id() {
                return true;
            }
        }
        if !p.kind().contains("type") {
            return false;
        }
        current = p;
        parent = p.parent();
    }
    false
}

/// The nearest enclosing function that BINDS `key` itself, or nothing.
///
/// A parameter named `app` and a module variable named `app` are different objects, and
/// the classifier treated them as one because their text matched. A reference inside a
/// function whose own parameter list declares that name belongs to the parameter, so it is
/// not evidence about the module variable. The ablation that isolated this: renaming the
/// parameter, and changing nothing else, flipped the file's verdict.
///
/// Only the parameter list is consulted. A local assignment shadows too, in Python and in
/// most of the nine, but the rules diverge per language (Python's `global`, Ruby's block
/// scoping), and a parameter is unambiguous everywhere. Narrow on purpose.
pub fn shadowing_scope<'t>(node: Node<'t>, key: &str, sp: &LangSpec, src: &[u8])
    -> Option<Node<'t>> {
    let mut parent = node.parent();
    while let Some(p) = parent {
        if sp.func_types.contains(&p.kind()) {
            for params in children(p) {
                if !sp.arglist_types.contains(&params.kind())
                    && !params.kind().contains("param") {
                    continue;
                }
                let binds = descendants(params)
                    .into_iter()
                    .any(|n| n.kind() == "identifier" && text(Some(n), src) == key);
                if binds {
                    return Some(p);
                }
            }
        }
        parent = p.parent();
    }
    None
}

/// The references that actually denote `key`, dropping the three ways a matching name does
/// not: it names a package, it names a type, or a nearer parameter binds it.
///
/// BOTH collection sites go through this. Module state and class state used to collect
/// references separately, so a filter applied to one silently missed the other.
pub fn bound_to<'t>(refs: &[Node<'t>], key: &str, sp: &LangSpec, src: &[u8]) -> Vec<Node<'t>> {
    refs.iter()
        .copied()
        .filter(|n| {
            !under_import_path(*n)
                && !in_type_position(*n)
                && shadowing_scope(*n, key, sp, src).is_none()
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang_spec::spec_for;
    use crate::parser_for;

    fn parse(source: &str, lang: &str) -> (tree_sitter::Tree, Vec<u8>) {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        (parser.parse(&bytes, None).expect("a parse"), bytes)
    }

    fn named<'t>(tree: &'t tree_sitter::Tree, name: &str, src: &[u8]) -> Vec<Node<'t>> {
        descendants(tree.root_node())
            .into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), src) == name)
            .collect()
    }

    #[test]
    fn a_name_in_an_import_path_binds_nothing_here() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("import cache\n\ncache = {}\n", "python");
        let refs = named(&tree, "cache", &src);
        assert_eq!(refs.len(), 2, "the text matches twice");
        assert_eq!(bound_to(&refs, "cache", sp, &src).len(), 1,
                   "only the binding is a reference to the state");
    }

    #[test]
    fn a_type_sharing_a_field_name_is_not_a_reference_to_the_field() {
        // `private static readonly Encoding Encoding = null;` names a type and then a
        // field, both Encoding. The type occurrence was collected as a reference to the
        // field and surfaced as an unmodelled construct, which reads as a missing rule
        // when the reference should never have been collected at all.
        let sp = spec_for("csharp").expect("csharp");
        let source = "class P { private static readonly Encoding Encoding = null;\n\
                      int F() { return Encoding == null ? 1 : 0; } }\n";
        let (tree, src) = parse(source, "csharp");
        let refs = named(&tree, "Encoding", &src);
        assert!(refs.len() >= 2);
        let kept = bound_to(&refs, "Encoding", sp, &src);
        assert!(kept.len() < refs.len(), "the type occurrence must be dropped");
    }

    #[test]
    fn a_reference_inside_a_function_that_declares_the_name_belongs_to_the_parameter() {
        // A parameter named `app` and a module variable named `app` are different objects.
        // Renaming the parameter, and changing nothing else, once flipped a file's verdict.
        let sp = spec_for("python").expect("python");
        let source = "app = {}\n\ndef run(app):\n    return app['k']\n";
        let (tree, src) = parse(source, "python");
        let refs = named(&tree, "app", &src);
        let kept = bound_to(&refs, "app", sp, &src);
        assert_eq!(kept.len(), 1, "only the module binding survives");
    }

    #[test]
    fn a_reference_in_a_function_that_does_not_declare_the_name_is_kept() {
        let sp = spec_for("python").expect("python");
        let source = "app = {}\n\ndef run(other):\n    return app['k']\n";
        let (tree, src) = parse(source, "python");
        let refs = named(&tree, "app", &src);
        assert_eq!(bound_to(&refs, "app", sp, &src).len(), refs.len());
    }

    #[test]
    fn a_dotted_value_expression_is_not_a_type_position() {
        // The walk stops at the first non-type ancestor, which is what keeps `Foo.Bar` on
        // the value side out of the type rule.
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("cache = {}\n\ndef f():\n    return cache.get('k')\n", "python");
        let refs = named(&tree, "cache", &src);
        assert_eq!(bound_to(&refs, "cache", sp, &src).len(), refs.len());
    }
}
