//! The node readers, ported from l1_analyzer.ts_nodes.
//!
//! Nothing here knows what state is or what a verdict is. It reads a parse tree and hands
//! back text or a child, and it exists so that two walks reading the same file cannot
//! disagree about what a node says.
//!
//! The Python originals return None where a node is absent and the empty string where its
//! text is. Both halves are kept: `field` and `first_named` answer `Option<Node>`, `text`
//! answers a `String` that is empty for an absent node, and every caller that can act on
//! the difference still gets to.

use tree_sitter::Node;

/// ts_nodes.text: a node's source, or the empty string when there is no node.
///
/// Invalid UTF-8 is dropped rather than raised, matching the reference's
/// `errors="ignore"`. A source file this analyzer cannot decode is still a file it must
/// report on, and a decode error would take the whole run down over one byte.
pub fn text(node: Option<Node>, src: &[u8]) -> String {
    match node {
        None => String::new(),
        Some(n) => String::from_utf8_lossy(&src[n.byte_range()])
            .replace('\u{FFFD}', ""),
    }
}

/// ts_nodes.field: the child a grammar files under `name`, if there is one.
pub fn field<'t>(node: Option<Node<'t>>, name: &str) -> Option<Node<'t>> {
    node?.child_by_field_name(name)
}

/// ts_nodes.first_named: a node's first named child, skipping punctuation and keywords.
pub fn first_named<'t>(node: Option<Node<'t>>) -> Option<Node<'t>> {
    let n = node?;
    let mut cursor = n.walk();
    // Bound before the block ends: the cursor owns the iterator and both die at the brace,
    // so returning the call directly is a borrow that outlives what it borrows.
    let first = n.named_children(&mut cursor).next();
    first
}

/// A node's children, ALL of them, named and anonymous alike.
///
/// The reference walks `node.children`, which in its binding includes the punctuation and
/// keyword nodes. Walking only the named ones would skip a node type a grammar files as
/// anonymous, and two walks that disagree about which children exist disagree about what
/// the file declares.
pub fn children<'t>(node: Node<'t>) -> Vec<Node<'t>> {
    let mut cursor = node.walk();
    let all: Vec<Node<'t>> = node.children(&mut cursor).collect();
    all
}

/// Every node under `scope`, `scope` included, in source order.
///
/// An explicit stack, not recursion. Parse-tree depth is set by the file being audited,
/// which is unbounded input, so a walk that recurses once per level has a ceiling nobody
/// chose. On 2026-09-05 five of two hundred repositories crashed the reference's recursive
/// walk, and they were the five largest: the instrument could not read the codebases its
/// claim is about.
///
/// Children go on reversed so they come off in order. A stack pops last in first out, and
/// the promise here is source order: a caller reading the first reference as the
/// declaration would otherwise get the last one.
pub fn descendants<'t>(scope: Node<'t>) -> Vec<Node<'t>> {
    let mut out = Vec::new();
    let mut stack = vec![scope];
    while let Some(node) = stack.pop() {
        out.push(node);
        stack.extend(children(node).into_iter().rev());
    }
    out
}

/// Like `descendants`, but never descends into a nested node of one of `stop`.
///
/// An inner record owns its own fields and is analysed as its own scope, so the enclosing
/// one must not harvest the inner one's state, which would count it twice. The root is
/// exempt from `stop` because the scope handed in IS a record, and a walk that refused to
/// enter it would return nothing.
pub fn local_descendants<'t>(scope: Node<'t>, stop: &[&str]) -> Vec<Node<'t>> {
    let mut out = Vec::new();
    let mut stack = vec![(scope, true)];
    while let Some((node, is_root)) = stack.pop() {
        if !is_root && stop.contains(&node.kind()) {
            continue;
        }
        out.push(node);
        stack.extend(children(node).into_iter().rev().map(|c| (c, false)));
    }
    out
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

    #[test]
    fn an_absent_node_reads_as_the_empty_string() {
        assert_eq!(text(None, b"anything"), "");
    }

    #[test]
    fn a_node_reads_as_its_own_source() {
        let (tree, src) = parse("struct Store { cache: i32 }", "rust");
        let item = tree.root_node().named_child(0).expect("the struct item");
        assert_eq!(text(field(Some(item), "name"), &src), "Store");
    }

    #[test]
    fn a_field_the_grammar_does_not_file_is_absent_rather_than_empty() {
        let (tree, _src) = parse("struct Store { cache: i32 }", "rust");
        let item = tree.root_node().named_child(0).expect("the struct item");
        assert!(field(Some(item), "no_such_field").is_none());
    }

    #[test]
    fn the_walk_reaches_a_node_nested_deeper_than_any_recursion_would_like() {
        // One deep chain, which is what a generated file looks like and what a recursive
        // walk dies on.
        let source = format!("fn f() {{ let x = {}0{}; }}", "(".repeat(400), ")".repeat(400));
        let (tree, src) = parse(&source, "rust");
        let reached = descendants(tree.root_node());
        assert!(reached.iter().any(|n| n.kind() == "integer_literal"),
                "the walk never reached the innermost literal");
        assert!(text(Some(tree.root_node()), &src).contains("let x"));
    }

    #[test]
    fn the_walk_is_in_source_order() {
        let (tree, src) = parse("struct A { }\nstruct B { }\n", "rust");
        let names: Vec<String> = descendants(tree.root_node())
            .into_iter()
            .filter(|n| n.kind() == "type_identifier")
            .map(|n| text(Some(n), &src))
            .collect();
        assert_eq!(names, vec!["A", "B"]);
    }
}
