//! Telling a data table from a pile of logic. Ported from l1_analyzer.data_tables.
//!
//! Two indicators ask the same question and must not answer it twice. The god-file count
//! discounts a large literal because a pile of logic is the smell and a table is not, and
//! the duplication check discounts one because normalising a per-language vocabulary makes
//! every row read identically and the whole table measures as copied code.
//!
//! The rule was written twice once, and the two copies disagreed for half a day.

use crate::lang_spec::LangSpec;
use crate::nodes::{children, field};
use tree_sitter::Node;

/// How a grammar spells one entry of a mapping.
///
/// A pair of literals is data for the same reason a literal is, and reading only the
/// container's own children stops one level short.
const PAIRS: &[&str] = &["pair", "keyword_argument", "key_value_pair", "pair_expression"];
/// How a grammar wraps one statement.
const STATEMENTS: &[&str] = &["expression_statement", "lexical_declaration",
                              "variable_declaration", "assignment"];
/// How a grammar spells binding a name.
const ASSIGNMENTS: &[&str] = &["assignment", "variable_declarator", "augmented_assignment"];
const CALLS: &[&str] = &["call", "call_expression", "method_invocation",
                         "invocation_expression"];

/// A container this big is a table whatever it holds.
pub const MIN_TABLE_LINES: usize = 12;

/// The node types this language spells a literal with.
///
/// Read from the table rather than defaulted: a supported language whose literals nobody
/// declared would read every table as logic, which is the direction that over-accuses on a
/// codebase made mostly of tables.
pub fn literal_types(sp: &LangSpec) -> &'static [&'static str] {
    sp.literal_types
}

/// The named children of a node, with comments left out.
fn elements<'t>(node: Node<'t>) -> Vec<Node<'t>> {
    children(node).into_iter()
        .filter(|c| c.is_named() && !c.kind().contains("comment"))
        .collect()
}

/// Whether this node is a container whose contents carry no logic.
pub fn is_table(node: Node, containers: &[&str], literals: &[&str]) -> bool {
    if !containers.contains(&node.kind()) {
        return false;
    }
    if node.end_position().row - node.start_position().row + 1 >= MIN_TABLE_LINES {
        return true;
    }
    all_data(node, containers, literals)
}

/// Whether this statement only binds a name to a table.
///
/// Discounting a table's contents leaves the declaration around it: a name, an equals sign,
/// an empty pair of brackets. Nine of those in a row is fifty tokens that match nine in a
/// row anywhere else, so a file of per-language vocabularies came back as its own largest
/// repeated block with every table inside it already discounted.
///
/// Only a declaration OF data. One that runs something to build its value is a statement
/// like any other, or a copied block could hide behind an equals sign.
pub fn declares_a_table(node: Node, containers: &[&str], literals: &[&str]) -> bool {
    if !STATEMENTS.contains(&node.kind()) {
        return false;
    }
    let Some(inner) = children(node).into_iter().find(|c| c.is_named()) else { return false };
    if !ASSIGNMENTS.contains(&inner.kind()) {
        return false;
    }
    let value = field(Some(inner), "right").or_else(|| field(Some(inner), "value"));
    match value {
        Some(value) => is_table(value, containers, literals)
            || builds_a_table(value, containers, literals),
        None => false,
    }
}

/// A call that wraps one table and nothing else: `frozenset({...})`, `tuple([...])`.
///
/// One argument, and that argument is data. Two arguments, or an argument that is not a
/// table, means a call doing work, so an ordinary call stays logic. Without this arm the
/// rule never reached a vocabulary written as a frozen set.
fn builds_a_table(node: Node, containers: &[&str], literals: &[&str]) -> bool {
    if !CALLS.contains(&node.kind()) {
        return false;
    }
    let Some(arguments) = field(Some(node), "arguments") else { return false };
    let given = elements(arguments);
    given.len() == 1 && is_table(given[0], containers, literals)
}

/// Whether every element under this container is data, all the way down.
///
/// Over an explicit stack, because the reference called itself once per level of nesting and
/// a generated file is nested as deep as its generator felt like. One vocabulary written as
/// two thousand nested lists exhausted the interpreter's stack, and what reached the person
/// running it was not a repository it could not read: it was a traceback, and the whole
/// panel died with it.
///
/// The flag on each work item is which nodes that item may hold. A container may hold a
/// pair; a pair may not hold another pair, only literals and containers. That is the one
/// difference between the two functions this replaces, and it is the one bit of state the
/// loop carries.
fn all_data(node: Node, containers: &[&str], literals: &[&str]) -> bool {
    let mut stack = vec![(node, true)];
    while let Some((current, pairs_allowed)) = stack.pop() {
        let kids = elements(current);
        if kids.is_empty() {
            return false;
        }
        for child in kids {
            if literals.contains(&child.kind()) {
                continue;
            }
            if containers.contains(&child.kind()) {
                stack.push((child, true));
            } else if pairs_allowed && PAIRS.contains(&child.kind()) {
                stack.push((child, false));
            } else {
                return false;
            }
        }
    }
    true
}
