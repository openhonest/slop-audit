//! Category 1 of L1.12: a statement that follows a terminator in the same block. Ported
//! from the unreachable half of l1_analyzer.dead_code.
//!
//! Decidable from syntax alone, in every supported grammar, at full confidence. No
//! reference, type or framework knowledge is involved, which is what separates it from the
//! unreferenced-definition half that needs all three.
//!
//! NOT YET WIRED INTO THE PANEL, because L1.12's published number is both halves and half a
//! port would be a different number under the same name. This half is ported, tested and
//! compared against the reference by validate_unreachable.py.
//!
//! What that comparison found is worth knowing before anyone ports the other half: on all
//! thirteen pinned repositories, in nine languages, BOTH sides find zero unreachable
//! statements. Well-maintained code does not carry a statement after a return, because every
//! compiler warns about it. So on this corpus L1.12's number is entirely the unreferenced
//! half, and that is where the whole parity risk sits.

use crate::lang_spec::lookup;
use crate::nodes::{children, descendants};
use tree_sitter::Node;

/// The node each grammar spells a block of statements with.
const BLOCK_TYPES: &[(&str, &[&str])] = &[
    ("python", &["block"]),
    ("rust", &["block"]),
    ("c", &["compound_statement"]),
    ("java", &["block"]),
    ("typescript", &["statement_block"]),
    ("javascript", &["statement_block"]),
    ("csharp", &["block"]),
    ("ruby", &["body_statement", "then", "else"]),
    ("go", &["statement_list"]),
];

/// What ends a block's straight-line flow.
///
/// `goto` is deliberately NOT a terminator in any of the three languages that have one.
/// Where a goto lands is a label that may sit anywhere below, including nested inside a
/// loop, and a sibling scan cannot see it. One C function does exactly that, jumping into
/// the middle of a `for`, and treating the goto as a terminator charged the whole loop as
/// dead code.
const TERMINATORS: &[(&str, &[&str])] = &[
    ("python", &["return_statement", "raise_statement", "break_statement",
                 "continue_statement"]),
    ("rust", &["return_expression", "break_expression", "continue_expression"]),
    ("c", &["return_statement", "break_statement", "continue_statement"]),
    ("java", &["return_statement", "throw_statement", "break_statement", "continue_statement",
               "yield_statement"]),
    ("typescript", &["return_statement", "throw_statement", "break_statement",
                     "continue_statement"]),
    ("javascript", &["return_statement", "throw_statement", "break_statement",
                     "continue_statement"]),
    ("csharp", &["return_statement", "throw_statement", "break_statement",
                 "continue_statement"]),
    ("ruby", &["return", "break", "next", "redo", "retry"]),
    ("go", &["return_statement", "break_statement", "continue_statement"]),
];

/// Node types that remain reachable after a terminator, so the scan of that block stops at
/// the first one rather than charging everything below it.
///
/// EVERY TYPE HERE WAS OBSERVED IN THAT POSITION. A type that cannot occupy the position
/// cannot spare anything, and a row of such types reads as protection while doing nothing:
/// fifteen of sixteen jump-target names did exactly that in the reference until they were
/// measured and removed.
///
/// A `case` below a `return` is entered from the switch rather than from the statement
/// above, so it must be spared, but only C spells a switch body with the same node it uses
/// for every other block. Every other grammar gives the arms a body node of their own, which
/// the scan never reaches, so only C's needs sparing.
///
/// WHAT A LABEL IS WORTH depends on whether the language has a `goto` that can jump forward
/// into it. C, Go and C# do, so a label below a terminator there is a real entry point. Java,
/// JavaScript and TypeScript label only for a labelled break or continue, both reached from
/// INSIDE the labelled statement, so a label below a terminator in those three is genuinely
/// dead and is charged.
///
/// The rest are reachable for reasons of their own: a hoisted declaration is still callable,
/// a Rust item is in scope for the whole block whatever precedes it, a type-only declaration
/// is erased before anything runs, and Ruby's `ensure` runs precisely BECAUSE the return
/// happened.
const REACHABLE_AFTER: &[(&str, &[&str])] = &[
    // Empty, and deliberately. Python has no goto, no hoisting and no arm the scan can
    // reach: a definition below a return never executes, so its name is never bound, and it
    // is dead by the same rule as any other statement.
    ("python", &[]),
    // Every item form, because a Rust item is scoped to the whole block and usable from
    // above its own position.
    ("rust", &["function_item", "macro_definition", "struct_item", "enum_item", "union_item",
               "const_item", "static_item", "type_item", "use_declaration", "mod_item",
               "trait_item", "impl_item", "foreign_mod_item"]),
    ("c", &["labeled_statement", "declaration", "case_statement"]),
    ("java", &["local_variable_declaration"]),
    ("typescript", &["function_declaration", "class_declaration",
                     "generator_function_declaration", "interface_declaration",
                     "type_alias_declaration"]),
    ("javascript", &["function_declaration", "class_declaration",
                     "generator_function_declaration"]),
    ("csharp", &["labeled_statement", "local_function_statement"]),
    ("ruby", &["method", "class", "module", "else", "rescue", "ensure"]),
    ("go", &["labeled_statement"]),
];

/// A preprocessor directive is not executable, so it is never unreachable CODE.
///
/// Worse, a conditional one cuts across the syntax: a directive sitting between a condition
/// and its body detaches them in the parse, so the `return` reads as a plain statement of
/// the enclosing block and everything below it reads as dead. That is not a fixable
/// off-by-one; a linear sibling scan is unsound inside a conditionally compiled block, so
/// such a block is NOT SCANNED. It costs real findings and never invents one.
///
/// Matched by prefix because every C-family grammar spells a dozen directives.
const DIRECTIVE_PREFIX: &str = "preproc";

fn conditionally_compiled(node: Node) -> bool {
    children(node).into_iter()
        .any(|c| c.is_named() && c.kind().starts_with(DIRECTIVE_PREFIX))
}

/// A comment carries no execution.
///
/// One test framework writes `return 0L; // 0 = never failed` and the trailing comment was
/// charged as an unreachable statement, so this matches every grammar's spelling rather
/// than one.
fn skip_in_scan(node_type: &str) -> bool {
    node_type.contains("comment")
}

/// True for a terminator statement, in either grammar shape: the statement node itself, or
/// a wrapper holding one, as Rust wraps its return in an expression statement.
fn is_terminator(node: Node, terminators: &[&str]) -> bool {
    if terminators.contains(&node.kind()) {
        return true;
    }
    node.kind() == "expression_statement"
        && children(node).into_iter().filter(|c| c.is_named()).next()
            .is_some_and(|first| terminators.contains(&first.kind()))
}

/// One statement the scan found unreachable, by the lines it spans.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Unreachable {
    pub line: usize,
    pub end_line: usize,
}

/// Every statement that follows a terminator in the same block.
///
/// Refused for a language with no row, rather than scanned with empty tables: empty
/// terminators find nothing, which reads exactly like code with nothing unreachable in it.
pub fn unreachable_statements(root: Node, lang: &str) -> Option<Vec<Unreachable>> {
    let blocks = lookup(BLOCK_TYPES, lang)?;
    let terminators = lookup(TERMINATORS, lang)?;
    let reachable_after = lookup(REACHABLE_AFTER, lang)?;
    let mut found = Vec::new();

    for node in descendants(root) {
        if !blocks.contains(&node.kind()) || conditionally_compiled(node) {
            continue;
        }
        let mut seen_terminator = false;
        for child in children(node).into_iter().filter(|c| c.is_named()) {
            if skip_in_scan(child.kind()) {
                continue;
            }
            if seen_terminator {
                if reachable_after.contains(&child.kind()) {
                    break;
                }
                found.push(Unreachable {
                    line: child.start_position().row + 1,
                    end_line: child.end_position().row + 1,
                });
            } else if is_terminator(child, terminators) {
                seen_terminator = true;
            }
        }
    }
    Some(found)
}

/// Every unreachable statement in the production files of one repository, for the parity
/// dump.
///
/// The reference skips a file whose tree carries an error, because a tree the grammar could
/// not parse cannot support a claim about what it contains: one large file parses with error
/// nodes and the statements around them read as unreachable, sixteen of them.
pub fn walk(repo: &std::path::Path, lang: &str)
    -> std::collections::BTreeMap<String, Vec<Unreachable>> {
    let (parsed, _skipped) = crate::indicators::dead_code_grammars::parsed_files(repo, lang);
    let mut out = std::collections::BTreeMap::new();
    for (rel, tree, _src) in parsed {
        if tree.root_node().has_error() {
            continue;
        }
        if let Some(found) = unreachable_statements(tree.root_node(), lang) {
            out.insert(rel, found);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser_for;

    fn found(source: &str, lang: &str) -> Vec<usize> {
        let mut parser = parser_for(lang);
        let src = source.as_bytes().to_vec();
        let tree = parser.parse(&src, None).expect("a parse");
        unreachable_statements(tree.root_node(), lang).expect("a language row")
            .into_iter().map(|u| u.line).collect()
    }

    #[test]
    fn a_statement_after_a_return_is_unreachable() {
        assert_eq!(found("def f():\n    return 1\n    print('no')\n", "python"), vec![3]);
    }

    #[test]
    fn a_comment_after_a_return_carries_no_execution() {
        // One test framework writes a trailing comment on its return, and it was charged.
        assert!(found("def f():\n    return 1  # why\n", "python").is_empty());
    }

    #[test]
    fn a_hoisted_declaration_below_a_return_is_still_callable() {
        let js = "function outer() {\n  return 1;\n  function inner() {}\n  x();\n}\n";
        // The scan stops at the hoisted declaration rather than charging it or anything
        // after it.
        assert!(found(js, "javascript").is_empty());
    }

    #[test]
    fn a_label_is_an_entry_point_where_the_language_can_jump_to_it() {
        // C has a goto that jumps forward, so a label below a return is reachable.
        let c = "void f(void) {\n  return;\n  again: ;\n}\n";
        assert!(found(c, "c").is_empty());
        // Java labels only for a labelled break, which is reached from inside, so a label
        // below a return there is genuinely dead.
        let java = "class A { void f() {\n  return;\n  again: while (true) { break again; }\n} }\n";
        assert_eq!(found(java, "java").len(), 1);
    }

    #[test]
    fn a_conditionally_compiled_block_is_not_scanned_at_all() {
        // A directive between a condition and its body detaches them in the parse, so a
        // sibling scan there is unsound whatever it finds.
        let c = "int f(void) {\n#if A\n  return 1;\n#endif\n  return 2;\n}\n";
        assert!(found(c, "c").is_empty());
    }

    #[test]
    fn a_language_with_no_row_is_refused_rather_than_scanned_with_empty_tables() {
        let mut parser = parser_for("python");
        let src = b"def f():\n    return 1\n".to_vec();
        let tree = parser.parse(&src, None).expect("a parse");
        assert!(unreachable_statements(tree.root_node(), "cobol").is_none());
    }

    #[test]
    fn rust_wraps_its_return_in_an_expression_statement_and_it_still_counts() {
        let rust = "fn f() -> i32 {\n    return 1;\n    let x = 2;\n    x\n}\n";
        assert_eq!(found(rust, "rust"), vec![3, 4]);
    }
}
