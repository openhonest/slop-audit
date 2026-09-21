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

// --- readers that need one grammar's vocabulary -------------------------------
//
// Still no knowledge of state or verdicts: these read a parse tree through the generated
// language table, which is a table of node types and field names.

use crate::lang_spec::{lookup, LangSpec};

/// Node identity. A field lookup hands back a fresh wrapper each call, so two values that
/// name the same node are not the same value; the stable id is what compares them.
pub fn same(a: Option<Node>, b: Option<Node>) -> bool {
    match (a, b) {
        (Some(a), Some(b)) => a.id() == b.id(),
        _ => false,
    }
}

/// A subscript's named children.
fn sub_named<'t>(subscript: Node<'t>) -> Vec<Node<'t>> {
    children(subscript).into_iter().filter(|c| c.is_named()).collect()
}

/// The collection being indexed. Rust's index expression has no fields, so the collection
/// is the first named child; other grammars name it.
pub fn sub_collection<'t>(subscript: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    if sp.sub_positional {
        return sub_named(subscript).into_iter().next();
    }
    field(Some(subscript), sp.sub_value?)
}

/// The key or index node of a subscript. Rust indexes positionally; C# wraps the key in a
/// bracketed argument list; the others name it.
pub fn sub_key<'t>(subscript: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    if sp.sub_positional {
        return sub_named(subscript).into_iter().nth(1);
    }
    let idx = field(Some(subscript), sp.sub_index?)?;
    if idx.kind() == "bracketed_argument_list" {
        return arg_value(first_named(Some(idx)));
    }
    Some(idx)
}

/// Unwrap a C# argument wrapper to the expression it carries.
pub fn arg_value<'t>(node: Option<Node<'t>>) -> Option<Node<'t>> {
    match node {
        Some(n) if n.kind() == "argument" => first_named(Some(n)),
        other => other,
    }
}

/// True when this node is the assigned lvalue of an assignment, unwrapping an optional
/// wrapper (Go puts assignment targets inside an expression list).
pub fn is_lvalue(node: Option<Node>, sp: &LangSpec) -> bool {
    let Some(mut node) = node else { return false };
    let mut parent = node.parent();
    if !sp.lvalue_wrapper.is_empty() {
        if let Some(p) = parent {
            if p.kind() == sp.lvalue_wrapper {
                node = p;
                parent = p.parent();
            }
        }
    }
    match parent {
        Some(p) => sp.assign_types.contains(&p.kind())
            && same(field(Some(p), sp.assign_left), Some(node)),
        None => false,
    }
}

/// The reference is the DECLARED NAME in a declaration.
///
/// A declaration binds the state, it does not consume it, which is what an assignment
/// target does too. It is a separate predicate only because the node is not an assignment
/// in any of the nine grammars and would never match the assignment types.
///
/// The FIELD is checked, not just the node type: `int y = stack.length;` puts `stack`
/// under a declarator too, in the VALUE, where it is read and not bound.
pub fn is_binding_site(reference: Node, parent: Node, sp: &LangSpec) -> bool {
    match lookup(sp.binding_sites, parent.kind()) {
        Some(binding_field) => same(field(Some(parent), binding_field), Some(reference)),
        None => false,
    }
}

/// Whether this reference is being written to rather than read.
///
/// The parent is optional because a node at the root of a parse has none, and callers pass
/// `node.parent()` straight in. A reference with nothing above it is not being written to
/// by anything.
pub fn is_write_target(reference: Node, parent: Option<Node>, sp: &LangSpec) -> bool {
    let Some(parent) = parent else { return false };
    if is_lvalue(Some(reference), sp) || is_binding_site(reference, parent, sp) {
        return true;
    }
    // `S[k] = v`: the reference is the collection of a subscript that is the assign target.
    sp.subscript_types.contains(&parent.kind())
        && same(sub_collection(parent, sp), Some(reference))
        && is_lvalue(Some(parent), sp)
}

/// Peel the wrappers that leave a value's identity alone, so none of them can hide a
/// literal underneath.
///
/// A unary operator over a literal is itself one compile-time value: `-1` is the last
/// element, `+1` the second. So is a borrow, a parenthesis and a cast: `&1`, `(1)` and
/// `(int)1` each name the same single constant that `1` names. Unwrapping rather than
/// listing the wrapper is what keeps `-x` and `&k` unbounded, because both peel to an
/// identifier, which is no literal.
///
/// The vocabulary is the VALUE wrapper list and deliberately not the flow walker's
/// passthrough list, though the two overlap. Passthrough answers whether the value flows
/// onward through this node, which is true of a boolean operator, a negation, a try and an
/// await. None of those preserves a literal's identity: `s[1 or x]` is not a constant
/// index, and folding it would be a false green rather than the false red this fixes.
///
/// The borrow is why it was worth a second pass. Rust's reference expression was already
/// in its passthrough set, so the flow walker read the borrow as transparent while this
/// predicate did not, and two walks disagreeing about one wrapper is what let the defect
/// survive. In Rust it is not an edge case: `map.contains_key(&1)` is what real code
/// writes, and it graded worst where the unidiomatic spelling graded neutral.
pub fn unwrap_unary<'t>(node: Option<Node<'t>>, sp: &LangSpec) -> Option<Node<'t>> {
    let mut current = node;
    while let Some(n) = current {
        if !sp.value_wrapper_types.contains(&n.kind()) {
            return Some(n);
        }
        current = first_named(Some(n));
    }
    None
}
