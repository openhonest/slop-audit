//! How wide a keyed access is: the cell-domain rules for subscripted state. Ported from
//! l1_analyzer.state_cells.
//!
//! One question, asked from several places in the classifier: given `S[k]`, how many
//! distinct behaviours of the program can S's value distinguish? The answer turns on the
//! key, on what the file declares closed, and on the WRITES.

use crate::lang_spec::LangSpec;
use crate::nodes::{
    children, descendants, field, is_write_target, same, sub_collection, sub_key, text,
    unwrap_unary,
};
use crate::state::partition::{self, Reach};
use std::collections::BTreeMap;
use tree_sitter::Node;

/// The sets a file declares closed, and how many members each holds. Absent where the
/// collection is provably fixed and not countable.
pub type ClosedSets = BTreeMap<String, Option<i64>>;

/// A value used as a lookup key or index. Literals are bounded; anything else, a
/// parameter or a variable, ranges over an unbounded domain.
pub fn is_unbounded_value(node: Option<Node>, sp: &LangSpec) -> bool {
    match unwrap_unary(node, sp) {
        Some(n) => !sp.literal_types.contains(&n.kind()),
        None => false,
    }
}

/// The discriminator identity of one cell of a keyed state.
///
/// Both spellings of a question about a literal key share it, so `"a" in S` and `S["a"]`
/// cut the partition once between them rather than twice. It is a function rather than a
/// format string at each site because the two sites are in different modules and drifted
/// apart: one wrote `holds:"a"` and the other `key:"a"` for the same cell.
pub fn cell_key(key_node: Option<Node>, src: &[u8]) -> String {
    format!("cell:{}", text(key_node, src))
}

/// `S[k]` read.
///
/// An unbounded key ranges over an unbounded domain; a literal key cuts one more class out
/// of it, and whether that class has a NEIGHBOUR is the whole ordered/unordered
/// distinction: `S[3]` sits between `S[2]` and `S[4]`, `S["beta"]` sits between nothing.
/// Distinct literals are distinct discriminators, so d of them leave d+1 classes.
pub fn keyed_read(key_node: Option<Node>, sp: &LangSpec, cells: Option<i64>,
                  src: &[u8]) -> Reach {
    if is_unbounded_value(key_node, sp) {
        // An open key over a BOUNDED cell set reaches the cells and nothing else: the ones
        // the writes can create, plus absent. Every such read splits on the SAME cell set,
        // so they share one discriminator key rather than counting once per read site.
        return match cells {
            Some(cells) => partition::finite(cells + 1, false, "cells"),
            None => partition::unbounded(),
        };
    }
    let key = unwrap_unary(key_node, sp);
    let ordered = key.map(|k| partition::ORDERED_LITERALS.contains(&k.kind())).unwrap_or(false);
    partition::finite(2, ordered, cell_key(key, src))
}

/// Whether `node` sits inside `scope`, by byte span.
pub fn contains(scope: Node, node: Node) -> bool {
    scope.start_byte() <= node.start_byte() && node.end_byte() <= scope.end_byte()
}

const MEMBERSHIP_TOKENS: &[&str] = &["in", "not in"];

/// (left, right) for an `in` / `not in` membership test, else nothing.
///
/// An absent node is an absent answer. The reference declared that it takes one and
/// reached into it on the next line, so handing it the absence it advertised raised, and
/// on the run that did it an adopter would get a stack trace instead of an audit.
pub fn membership_operands<'t>(node: Option<Node<'t>>, sp: &LangSpec)
    -> Option<(Node<'t>, Node<'t>)> {
    let node = node?;
    match sp.membership {
        "comparison_in" if node.kind() == "comparison_operator" => {
            if !children(node).iter().any(|c| MEMBERSHIP_TOKENS.contains(&c.kind())) {
                return None;
            }
            let named: Vec<Node> = children(node).into_iter().filter(|c| c.is_named()).collect();
            if named.len() >= 2 {
                Some((named[0], named[named.len() - 1]))
            } else {
                None
            }
        }
        "binary_in" if node.kind() == "binary_expression"
            && text(field(Some(node), "operator"), &[]) == "in" => {
            // Both halves or neither. A membership test missing one side is not a
            // membership test, and handing back a pair with a hole in it made every
            // caller's unpacking a promise this function never made.
            match (field(Some(node), "left"), field(Some(node), "right")) {
                (Some(left), Some(right)) => Some((left, right)),
                _ => None,
            }
        }
        _ => None,
    }
}

pub fn is_closed_set(node: Option<Node>, closed_sets: &ClosedSets, src: &[u8]) -> bool {
    let Some(node) = node else { return false };
    match node.kind() {
        "set" | "tuple" | "list" => true,
        "call" => {
            let name = text(field(Some(node), "function"), src);
            name == "frozenset" || name == "set"
        }
        "identifier" => closed_sets.contains_key(&text(Some(node), src)),
        "attribute" => match field(Some(node), "attribute") {
            Some(attr) => closed_sets.contains_key(&text(Some(attr), src)),
            None => false,
        },
        _ => false,
    }
}

fn is_immutable_collection(rhs: Option<Node>, src: &[u8]) -> bool {
    let Some(rhs) = rhs else { return false };
    match rhs.kind() {
        "tuple" => true,
        "call" => text(field(Some(rhs), "function"), src) == "frozenset",
        _ => false,
    }
}

/// Every name this file binds to a provably fixed collection, with its member count.
pub fn collect_closed_sets(root: Node, src: &[u8]) -> ClosedSets {
    let mut names = ClosedSets::new();
    for n in descendants(root) {
        if n.kind() != "assignment" {
            continue;
        }
        let (Some(left), rhs) = (field(Some(n), "left"), field(Some(n), "right")) else { continue };
        if !is_immutable_collection(rhs, src) {
            continue;
        }
        let size = partition::literal_size(rhs, src);
        match left.kind() {
            "identifier" => {
                names.insert(text(Some(left), src), size);
            }
            "attribute" => {
                if let Some(attr) = field(Some(left), "attribute") {
                    names.insert(text(Some(attr), src), size);
                }
            }
            _ => {}
        }
    }
    names
}

/// How many values an enclosing membership test confines this key to, or nothing.
///
/// `if k in KINDS: CACHE[k] = v` writes only under a key KINDS holds, so the store can
/// reach at most two cells however wide `k`'s type is. The bound is the DECLARED set's
/// cardinality, which is why only a set the file declares immutable counts: a mutable list
/// bounds nothing, because a later append moves the number.
///
/// Only the CONSEQUENCE is read. A store on the else branch is reached by keys the test
/// rejected, which the set does not bound, so walking up from it must find nothing.
pub fn guarded_by_closed_set(key_node: Option<Node>, sp: &LangSpec,
                             closed_sets: &ClosedSets, src: &[u8]) -> Option<i64> {
    let key_node = key_node?;
    let name = text(Some(key_node), src);
    let mut node = key_node;
    while let Some(parent) = node.parent() {
        if sp.func_types.contains(&parent.kind()) {
            break;
        }
        if sp.branch_types.contains(&parent.kind()) {
            let cond = field(Some(parent), sp.branch_cond);
            let consequence = field(Some(parent), "consequence");
            if let (Some((left, right)), Some(consequence)) =
                (membership_operands(cond, sp), consequence) {
                if text(Some(left), src) == name
                    && is_closed_set(Some(right), closed_sets, src)
                    && contains(consequence, key_node) {
                    if let Some(Some(size)) = closed_sets.get(&text(Some(right), src)) {
                        return Some(*size);
                    }
                }
            }
        }
        node = parent;
    }
    None
}

/// How many distinct cells the subscript STORES to this state can create, or nothing when
/// nothing bounds them.
///
/// This is the rule the classifier had no way to express, and its absence was a false
/// proof rather than a missed refinement. Every reference used to be judged alone, so a
/// read with an open key reported the state provably unbounded even when every write into
/// it went through a two-member frozen set. A read cannot observe a cell no write created,
/// so the write side is what bounds the state and the read side never was.
///
/// Absent means the rule DECLINES, not that the state is fine: a state with no subscript
/// store at all is outside its scope, and one store with an open key reopens the whole
/// cell set however narrow every other store is. Both come back absent and leave the
/// per-reference verdict exactly as it was.
pub fn write_key_bound(refs: &[Node], sp: &LangSpec, closed_sets: &ClosedSets,
                       src: &[u8]) -> Option<i64> {
    let mut cells: i64 = 0;
    let mut saw_store = false;
    for reference in refs {
        let Some(parent) = reference.parent() else { continue };
        if !sp.subscript_types.contains(&parent.kind())
            || !same(sub_collection(parent, sp), Some(*reference)) {
            continue;
        }
        if !is_write_target(parent, parent.parent(), sp) {
            continue;
        }
        saw_store = true;
        let key = sub_key(parent, sp);
        if !is_unbounded_value(key, sp) {
            cells += 1;
            continue;
        }
        match guarded_by_closed_set(key, sp, closed_sets, src) {
            None => return None,
            Some(guarded) => cells += guarded,
        }
    }
    if saw_store { Some(cells) } else { None }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lang_spec::spec_for;
    use crate::nodes::descendants;
    use crate::parser_for;

    fn parse(source: &str, lang: &str) -> (tree_sitter::Tree, Vec<u8>) {
        let mut parser = parser_for(lang);
        let bytes = source.as_bytes().to_vec();
        (parser.parse(&bytes, None).expect("a parse"), bytes)
    }

    fn first_of<'t>(tree: &'t tree_sitter::Tree, kind: &str) -> Node<'t> {
        descendants(tree.root_node()).into_iter().find(|n| n.kind() == kind)
            .unwrap_or_else(|| panic!("no {kind} in the fixture"))
    }

    #[test]
    fn a_literal_key_cuts_one_class_and_a_number_has_a_neighbour() {
        // `S[3]` sits between `S[2]` and `S[4]`; `S["beta"]` sits between nothing, and
        // that is the whole ordered/unordered distinction.
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("S[3]\n", "python");
        let reach = keyed_read(sub_key(first_of(&tree, "subscript"), sp), sp, None, &src);
        assert_eq!(reach.kind, partition::FINITE);
        assert_eq!(reach.classes, 2);
        assert!(reach.ordered);

        let (tree, src) = parse("S['beta']\n", "python");
        let reach = keyed_read(sub_key(first_of(&tree, "subscript"), sp), sp, None, &src);
        assert_eq!(reach.classes, 2);
        assert!(!reach.ordered, "no string sits just above another");
    }

    #[test]
    fn an_open_key_over_an_unbounded_cell_set_is_unbounded() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("S[k]\n", "python");
        let reach = keyed_read(sub_key(first_of(&tree, "subscript"), sp), sp, None, &src);
        assert_eq!(reach.kind, partition::UNBOUNDED);
    }

    #[test]
    fn an_open_key_over_a_bounded_cell_set_reaches_the_cells_and_absent() {
        // A read cannot observe a cell no write created, so the write side bounds it.
        // Every such read splits on the SAME cell set and they share one discriminator.
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("S[k]\n", "python");
        let reach = keyed_read(sub_key(first_of(&tree, "subscript"), sp), sp, Some(2), &src);
        assert_eq!(reach.kind, partition::FINITE);
        assert_eq!(reach.classes, 3);
        assert_eq!(reach.key, "cells");
    }

    #[test]
    fn both_spellings_of_a_question_about_one_cell_share_a_discriminator() {
        // `"a" in S` and `S["a"]` cut the partition once between them, not twice. The two
        // sites are in different modules and drifted apart once already.
        let (tree, src) = parse("S['a']\n", "python");
        let sp = spec_for("python").expect("python");
        let key = sub_key(first_of(&tree, "subscript"), sp);
        assert_eq!(cell_key(key, &src), "cell:'a'");
    }

    #[test]
    fn a_borrowed_literal_is_still_one_compile_time_value() {
        // Rust writes `map.contains_key(&1)`, and the borrow used to make it unbounded:
        // it graded worst where the unidiomatic spelling graded neutral.
        let sp = spec_for("rust").expect("rust");
        let (tree, src) = parse("fn f() { let x = &1; }", "rust");
        let borrowed = first_of(&tree, "reference_expression");
        assert!(!is_unbounded_value(Some(borrowed), sp), "{}", text(Some(borrowed), &src));
    }

    #[test]
    fn a_negated_variable_is_not_a_literal_however_it_is_wrapped() {
        let sp = spec_for("python").expect("python");
        let (tree, _src) = parse("S[-x]\n", "python");
        assert!(is_unbounded_value(sub_key(first_of(&tree, "subscript"), sp), sp));
    }

    #[test]
    fn a_file_declaring_a_frozen_set_has_its_size_recorded() {
        let (tree, src) = parse("KINDS = frozenset(('a', 'b'))\n", "python");
        let closed = collect_closed_sets(tree.root_node(), &src);
        assert_eq!(closed.get("KINDS"), Some(&Some(2)));
    }

    #[test]
    fn a_mutable_collection_is_not_a_closed_set_because_an_append_moves_the_number() {
        let (tree, src) = parse("KINDS = ['a', 'b']\n", "python");
        assert!(collect_closed_sets(tree.root_node(), &src).is_empty());
    }

    #[test]
    fn a_store_under_a_guarded_key_is_bounded_by_the_declared_set() {
        // `if k in KINDS: CACHE[k] = v` reaches at most two cells however wide k is.
        let sp = spec_for("python").expect("python");
        let source = "KINDS = frozenset(('a', 'b'))\n\
                      def put(k, v):\n    if k in KINDS:\n        CACHE[k] = v\n";
        let (tree, src) = parse(source, "python");
        let closed = collect_closed_sets(tree.root_node(), &src);
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "CACHE")
            .collect();
        assert_eq!(write_key_bound(&refs, sp, &closed, &src), Some(2));
    }

    #[test]
    fn a_store_on_the_else_branch_is_not_bounded_by_the_test_that_rejected_its_key() {
        // The else branch is reached by keys the set does NOT hold, so walking up from it
        // must find nothing. Reading the whole statement rather than the consequence
        // would bound a store the set says nothing about.
        let sp = spec_for("python").expect("python");
        let source = "KINDS = frozenset(('a', 'b'))\n\
                      def put(k, v):\n    if k in KINDS:\n        pass\n    else:\n        CACHE[k] = v\n";
        let (tree, src) = parse(source, "python");
        let closed = collect_closed_sets(tree.root_node(), &src);
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "CACHE")
            .collect();
        assert_eq!(write_key_bound(&refs, sp, &closed, &src), None);
    }

    #[test]
    fn a_state_with_no_subscript_store_is_outside_this_rule() {
        // Absent means the rule DECLINES, not that the state is fine.
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("def f():\n    return CACHE\n", "python");
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "CACHE")
            .collect();
        assert_eq!(write_key_bound(&refs, sp, &ClosedSets::new(), &src), None);
    }

    #[test]
    fn one_unguarded_store_reopens_the_whole_cell_set() {
        // However narrow every other store is.
        let sp = spec_for("python").expect("python");
        let source = "KINDS = frozenset(('a', 'b'))\n\
                      def put(k, v):\n\
                      \x20   if k in KINDS:\n        CACHE[k] = v\n\
                      \x20   CACHE[other] = v\n";
        let (tree, src) = parse(source, "python");
        let closed = collect_closed_sets(tree.root_node(), &src);
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "CACHE")
            .collect();
        assert_eq!(write_key_bound(&refs, sp, &closed, &src), None);
    }

    #[test]
    fn a_literal_key_store_counts_one_cell_each() {
        let sp = spec_for("python").expect("python");
        let source = "def put(v):\n    CACHE['a'] = v\n    CACHE['b'] = v\n";
        let (tree, src) = parse(source, "python");
        let refs: Vec<Node> = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "CACHE")
            .collect();
        assert_eq!(write_key_bound(&refs, sp, &ClosedSets::new(), &src), Some(2));
    }
}
