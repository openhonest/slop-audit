//! Whether a state is settled at one value before any reach is read. Ported from
//! l1_analyzer.state_const.
//!
//! Two rules, one question. A declaration the language marks immutable AND binds to a
//! literal has a one-value domain. A Python name assigned once from an immutable
//! construction has one too, which takes following the constructor a level to see.
//!
//! Both rules are declared per language, by the immutable-modifier list and the
//! immutable-constructor flag. The declared rule replaced an identity check against the
//! Python language row, which is the language conditional welded into shared code that
//! this project objects to elsewhere.

use crate::lang_spec::LangSpec;
use crate::nodes::{
    descendants, field, first_named, is_write_target, same, text, unwrap_unary,
};
use crate::state::partition::NEUTRAL;
use tree_sitter::Node;

/// The wrappers whose call produces a value nothing can change.
const IMMUTABLE_WRAPPERS: &[&str] = &["MappingProxyType", "frozenset", "tuple", "bytes"];

/// The Python methods that mutate the receiver in place. A state one of these is called on
/// is not a constant, whatever it was bound to.
const PY_MUTATING: &[&str] = &[
    "add", "append", "appendleft", "clear", "discard", "extend", "insert", "pop",
    "popitem", "remove", "setdefault", "sort", "update",
];

/// The literal node types an immutable right-hand side can be.
const IMMUTABLE_RHS: &[&str] = &[
    "tuple", "true", "false", "none", "integer", "float", "string", "concatenated_string",
];

pub fn rhs_is_immutable(rhs: Option<Node>, immutable_ctors: &[String], src: &[u8]) -> bool {
    let Some(rhs) = rhs else { return false };
    if IMMUTABLE_RHS.contains(&rhs.kind()) {
        return true;
    }
    if rhs.kind() == "call" {
        let name = text(field(Some(rhs), "function"), src);
        return IMMUTABLE_WRAPPERS.contains(&name.as_str())
            || immutable_ctors.iter().any(|ctor| *ctor == name);
    }
    false
}

/// Whether every return this function makes hands back something immutable.
///
/// EVERY return, and a function with none answers false. One mutable return is enough to
/// make the constructor's result something the program can change, and a function that
/// returns nothing has produced no value to settle.
pub fn returns_immutable(func_node: Node, src: &[u8]) -> bool {
    let returns: Vec<Node> = descendants(func_node)
        .into_iter()
        .filter(|n| n.kind() == "return_statement")
        .collect();
    if returns.is_empty() {
        return false;
    }
    returns.iter().all(|r| rhs_is_immutable(first_named(Some(*r)), &[], src))
}

/// Every function in this file whose result is immutable, by name.
pub fn collect_immutable_ctors(root: Node, src: &[u8]) -> Vec<String> {
    let mut out = Vec::new();
    for fn_node in descendants(root).into_iter().filter(|n| n.kind() == "function_definition") {
        if let Some(name) = field(Some(fn_node), "name") {
            if returns_immutable(fn_node, src) {
                let spelled = text(Some(name), src);
                if !out.contains(&spelled) {
                    out.push(spelled);
                }
            }
        }
    }
    out
}

/// Whether any reference to this state reaches a decision rather than being written or
/// returned. A state that decides nothing costs no tests, however wide its domain.
pub fn reaches_decision(refs: &[Node], sp: &LangSpec) -> bool {
    for r in refs {
        let Some(p) = r.parent() else { continue };
        if sp.return_types.contains(&p.kind()) {
            continue;
        }
        if is_write_target(*r, Some(p), sp) {
            continue;
        }
        return true;
    }
    false
}

/// `(NEUTRAL, drives)` when the state is an immutable constant: assigned exactly once from
/// an immutable construction, never mutated, never called. Nothing otherwise.
pub fn immutable_const_verdict(refs: &[Node], immutable_ctors: &[String], sp: &LangSpec,
                               src: &[u8]) -> Option<(&'static str, bool)> {
    let mut assigns: Vec<Node> = Vec::new();
    for r in refs {
        let Some(p) = r.parent() else { continue };
        match p.kind() {
            "assignment" if same(field(Some(p), "left"), Some(*r)) => {
                assigns.push(p);
            }
            // `S += ...` is a reassignment, so the name is not settled at one value.
            "augmented_assignment" if same(field(Some(p), "left"), Some(*r)) => return None,
            // `S[k] = v` mutates what the name holds.
            "subscript" if same(field(Some(p), "value"), Some(*r)) => {
                if let Some(gp) = p.parent() {
                    if matches!(gp.kind(), "assignment" | "augmented_assignment")
                        && same(field(Some(gp), "left"), Some(p)) {
                        return None;
                    }
                }
            }
            // Called, so the target is chosen while the program runs.
            "call" if same(field(Some(p), "function"), Some(*r)) => return None,
            // A mutating method on the receiver.
            "attribute" if same(field(Some(p), "object"), Some(*r)) => {
                let method = text(field(Some(p), "attribute"), src);
                if PY_MUTATING.contains(&method.as_str()) {
                    if let Some(gp) = p.parent() {
                        if gp.kind() == "call" && same(field(Some(gp), "function"), Some(p)) {
                            return None;
                        }
                    }
                }
            }
            _ => {}
        }
    }
    if assigns.len() != 1 {
        return None;
    }
    if !rhs_is_immutable(field(Some(assigns[0]), "right"), immutable_ctors, src) {
        return None;
    }
    Some((NEUTRAL, reaches_decision(refs, sp)))
}

/// Whether every value bound in this declaration is a literal.
///
/// A declaration binding several names is settled only if all of them are, and one binding
/// none, such as an enum member with no initialiser, is not settled here at all: this rule
/// reads what was written, and nothing was.
///
/// It takes no source buffer, because it reads no text: whether a value is a literal is a
/// question about node TYPES, and a parameter nothing reads is a claim about the inputs
/// that is not true.
pub fn literal_initialiser(declaration: Node, sp: &LangSpec) -> bool {
    let Some((node_type, _name_field, value_field)) = sp.local_binding.first() else {
        return false;
    };
    let mut values: Vec<Node> = Vec::new();
    for node in descendants(declaration).into_iter().filter(|n| n.kind() == *node_type) {
        let value = match value_field {
            Some(field_name) => field(Some(node), field_name),
            None => {
                let named: Vec<Node> =
                    crate::nodes::children(node).into_iter().filter(|c| c.is_named()).collect();
                if named.len() > 1 { named.last().copied() } else { None }
            }
        };
        if let Some(value) = value {
            values.push(value);
        }
    }
    if values.is_empty() {
        return false;
    }
    // Peeled, THEN checked. A unary wrapper with nothing under it peels to nothing, and
    // asking that for its type raised in the reference: `s[-]` is not valid Python, but a
    // parse of broken source produces exactly that shape, and this reader runs on whatever
    // it is given. An unwrapped nothing is not a literal.
    values.iter().all(|v| match unwrap_unary(Some(*v), sp) {
        Some(peeled) => sp.literal_types.contains(&peeled.kind()),
        None => false,
    })
}

/// Whether the language's own declaration settles this state at ONE literal value.
///
/// `private static final int PEEKED = 11;` and `private const int Peeked = 11;` have a
/// one-value domain. They were enumerated as state, came back unresolved, and the blame
/// fell on the place they are READ, a case label, rather than on the declaration that
/// settles them. Nineteen sites in gson alone.
///
/// BOTH halves are required, and the second is the one that took a failing test to learn.
/// A modifier alone buys binding immutability, not value immutability: JavaScript's
/// `const arr = []` forbids reassigning `arr` and permits `arr.push(1)`, and Java's
/// `final List<X> L = new ArrayList<>()` is the same trap in a stricter language. Only a
/// LITERAL initialiser closes the domain, which is the premise Python's
/// immutable-construction rule checks before it clears anything.
///
/// A language declaring no modifiers answers false for every state.
pub fn declared_constant(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    if sp.immutable_modifiers.is_empty() {
        return false;
    }
    for reference in refs {
        let mut climbing = Some(*reference);
        for _ in 0..4 {
            climbing = climbing.and_then(|n| n.parent());
            let Some(node) = climbing else { break };
            // One level deeper as well: Java gathers `private static final` into a
            // modifiers node, so the keyword is a grandchild, while C# hangs `const` and
            // `readonly` directly off the declaration.
            let declared = crate::nodes::children(node).into_iter().any(|c| {
                let names = |n: Node| sp.immutable_modifiers.contains(&n.kind())
                    || sp.immutable_modifiers.contains(&text(Some(n), src).as_str());
                names(c) || crate::nodes::children(c).into_iter().any(names)
            });
            if declared && literal_initialiser(node, sp) {
                return true;
            }
        }
    }
    false
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

    fn named_refs<'t>(tree: &'t tree_sitter::Tree, name: &str, src: &[u8]) -> Vec<Node<'t>> {
        descendants(tree.root_node())
            .into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), src) == name)
            .collect()
    }

    #[test]
    fn a_name_assigned_once_from_a_literal_is_settled_at_one_value() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("LIMIT = 5\n\ndef f(n):\n    return n > LIMIT\n", "python");
        let refs = named_refs(&tree, "LIMIT", &src);
        let verdict = immutable_const_verdict(&refs, &[], sp, &src).expect("a verdict");
        assert_eq!(verdict.0, NEUTRAL);
        assert!(verdict.1, "it is compared, so it decides something");
    }

    #[test]
    fn a_name_that_is_written_through_is_not_a_constant() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("S = ()\n\ndef f(k, v):\n    S[k] = v\n", "python");
        assert!(immutable_const_verdict(&named_refs(&tree, "S", &src), &[], sp, &src).is_none());
    }

    #[test]
    fn a_name_a_mutating_method_is_called_on_is_not_a_constant() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("S = ()\n\ndef f(v):\n    S.append(v)\n", "python");
        assert!(immutable_const_verdict(&named_refs(&tree, "S", &src), &[], sp, &src).is_none());
    }

    #[test]
    fn a_name_that_is_reassigned_is_not_settled() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("N = 0\n\ndef f():\n    N += 1\n", "python");
        assert!(immutable_const_verdict(&named_refs(&tree, "N", &src), &[], sp, &src).is_none());
    }

    #[test]
    fn a_name_that_is_called_is_dynamic_dispatch_and_not_a_constant() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("F = ()\n\ndef g():\n    return F()\n", "python");
        assert!(immutable_const_verdict(&named_refs(&tree, "F", &src), &[], sp, &src).is_none());
    }

    #[test]
    fn a_frozen_construction_settles_the_domain() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("KINDS = frozenset(('a',))\n\ndef f(k):\n    return k in KINDS\n",
                                "python");
        assert!(immutable_const_verdict(&named_refs(&tree, "KINDS", &src), &[], sp, &src)
                .is_some());
    }

    #[test]
    fn a_constructor_whose_every_return_is_immutable_settles_what_it_builds() {
        let (tree, src) = parse("def kinds():\n    return ('a', 'b')\n", "python");
        assert_eq!(collect_immutable_ctors(tree.root_node(), &src), vec!["kinds"]);
    }

    #[test]
    fn one_mutable_return_disqualifies_a_constructor() {
        // Every return, not any. One mutable result is enough to make what the caller
        // holds something the program can change.
        let source = "def kinds(flag):\n    if flag:\n        return ('a',)\n    return []\n";
        let (tree, src) = parse(source, "python");
        assert!(collect_immutable_ctors(tree.root_node(), &src).is_empty());
    }

    #[test]
    fn a_function_that_returns_nothing_has_produced_no_value_to_settle() {
        let (tree, src) = parse("def kinds():\n    pass\n", "python");
        assert!(collect_immutable_ctors(tree.root_node(), &src).is_empty());
    }

    #[test]
    fn a_java_final_field_bound_to_a_literal_is_settled() {
        // Nineteen of these in gson came back unresolved, and the blame fell on the case
        // label that reads them rather than on the declaration that settles them.
        let sp = spec_for("java").expect("java");
        let source = "class P { private static final int PEEKED = 11;\n\
                      int f(int t) { return t == PEEKED ? 1 : 0; } }\n";
        let (tree, src) = parse(source, "java");
        assert!(declared_constant(&named_refs(&tree, "PEEKED", &src), sp, &src));
    }

    #[test]
    fn a_final_field_bound_to_a_mutable_object_is_not_settled() {
        // The half that took a failing test to learn. A modifier buys BINDING
        // immutability: `final List<X> L = new ArrayList<>()` forbids reassigning L and
        // permits L.add(x), and JavaScript's `const arr = []` is the same trap.
        let sp = spec_for("java").expect("java");
        let source = "class P { private static final java.util.List<String> L = new java.util.ArrayList<>();\n\
                      int f() { return L.size(); } }\n";
        let (tree, src) = parse(source, "java");
        assert!(!declared_constant(&named_refs(&tree, "L", &src), sp, &src));
    }

    #[test]
    fn a_csharp_const_hangs_its_modifier_directly_off_the_declaration() {
        // Java gathers `private static final` into a modifiers node, so the keyword is a
        // grandchild; C# does not. Both spellings have to reach the same answer.
        let sp = spec_for("csharp").expect("csharp");
        let source = "class P { private const int Peeked = 11;\n\
                      int F(int t) { return t == Peeked ? 1 : 0; } }\n";
        let (tree, src) = parse(source, "csharp");
        assert!(declared_constant(&named_refs(&tree, "Peeked", &src), sp, &src));
    }

    #[test]
    fn a_language_declaring_no_immutable_modifier_answers_no_for_every_state() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("LIMIT = 5\n", "python");
        assert!(!declared_constant(&named_refs(&tree, "LIMIT", &src), sp, &src));
    }
}
