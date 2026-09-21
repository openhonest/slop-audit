//! What a finite verdict carries beside the word "finite": how many classes, and whether
//! limit testing can defeat them. Ported from l1_analyzer.state_partition.
//!
//! "Finite" used to be one label, so a partition of two classes and a partition of four
//! billion came out the same and the grade could not tell them apart. This module holds
//! the value a reference now yields, the per-state roll-up of those values, and nothing
//! else.
//!
//! Two rules decide the shape here.
//!
//! CARDINALITY ALONE IS THE WRONG TEST. Limit testing defeats large ordered domains: a
//! 64-bit integer compared against three constants induces four intervals, and boundary
//! selection covers them with a handful of values. What limit testing cannot defeat is a
//! large UNORDERED partition, because there is no value just above a string key. So every
//! finite reach records `ordered` beside `classes`, and the route to finiteness supplies
//! it: a comparison arm is ordered, a membership test against a closed set and a
//! literal-keyed read are not.
//!
//! A COUNT WE CANNOT RECOVER IS SILENCE, NOT A FINDING. Some finite partitions have no
//! count the analyzer can reach: a frozen set built from a call we cannot read is provably
//! closed and of unknown size. `counted` carries that fact, and an uncounted partition is
//! excluded from the coarse test, because an unknown count is a limit of ours and the
//! finding is a claim about the audited code.
//!
//! The roll-up ADDS discriminators and does not multiply. Two states that decide the same
//! branch multiply, and this version does not compose across states at all; within one
//! state it sums the distinct discriminators, which is a lower bound on the true
//! partition. Both are under-counts, and under-counting is the safe direction for a
//! measure that only ever accuses: it can miss a coarse partition, never invent one. Every
//! report that quotes the number says so.

use crate::nodes::{children, field, first_named, text};
use std::collections::BTreeMap;
use tree_sitter::Node;

// Why a reaching-set could not be decided. Silence is a fact about the ANALYZER, so the
// reasons name whose problem each one is. A name handed to a sort and a name handed to a
// third-party workbook's save call are both undecided, and they are not the same fact: the
// first is a name we could model and have not, the second is a boundary only the adopter
// can make readable by putting an explicit contract at the edge. Reporting them as one
// number tells an adopter to go and fix our backlog.

/// A call into code the analyzer cannot read.
pub const EXTERNAL_BOUNDARY: &str = "external_boundary";
/// A plain name we could model and have not.
pub const UNMODELED_CALLEE: &str = "unmodeled_callee";
/// The call target is chosen while the program runs.
pub const DYNAMIC_DISPATCH: &str = "dynamic_dispatch";
/// An invoked slot whose compositional premise fails.
pub const INJECTED_SLOT: &str = "injected_slot";
/// A syntax shape no dispatch row covers.
pub const UNMODELED_CONSTRUCT: &str = "unmodeled_construct";
/// The grammar handed the region back as tokens, so there is no shape to dispatch on.
/// Rust's macro arguments are the case: `format!("{}", self.v.len())` parses to a flat
/// token tree that does not even keep the field name attached to `self`. Kept apart from
/// an unmodelled construct because the two send the reader to different places: a
/// construct is a dispatch row somebody can write, and this is not.
pub const UNPARSED_REGION: &str = "unparsed_region";
/// The value was handed out under a name the walk cannot follow, so writes can arrive
/// through an alias no rule about this state's own references will ever see. Rust's
/// `&mut self.v` is the case.
pub const MUTABLE_ALIAS: &str = "mutable_alias";

/// Every reason, in report order. A consumer reading a zero must know the analyzer looked
/// and found none, rather than guessing whether the key was omitted.
pub const SILENCE_REASONS: &[&str] = &[
    EXTERNAL_BOUNDARY, UNMODELED_CALLEE, DYNAMIC_DISPATCH, INJECTED_SLOT,
    UNMODELED_CONSTRUCT, UNPARSED_REGION, MUTABLE_ALIAS,
];

// The three verdicts a finding can carry.
pub const NEUTRAL: &str = "neutral";
pub const PROMISCUOUS: &str = "promiscuous";
pub const UNRESOLVED: &str = "unresolved";

/// Target of an assignment or a mutating method: not a decision.
pub const WRITE: &str = "write";
/// Returned or handed to the caller: compositional.
pub const OUTPUT: &str = "output";
/// Reaches a decision whose reaching partition is enumerable.
pub const FINITE: &str = "finite";
/// Reaches a decision whose reaching partition is provably unbounded.
pub const UNBOUNDED: &str = "unbounded";
/// Reaches a context whose reaching-set cannot be decided.
pub const UNDECIDED: &str = "undecided";

/// The reaching partition of one piece of state, rolled up from its references.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Partition {
    /// Zero when `counted` is false, because there is no number to report.
    pub classes: i64,
    pub ordered: bool,
    pub counted: bool,
}

/// How ONE reference to a state value is consumed, and what it does to the domain.
///
/// `key` identifies the discriminator rather than the site, so the same split written in
/// two places counts once: `if S:` in fifty methods is one two-class split, not fifty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reach {
    pub kind: &'static str,
    /// Equivalence classes this discriminator induces; zero unless finite.
    pub classes: i64,
    /// True when boundary values cover the split.
    pub ordered: bool,
    /// False when the class count could not be recovered.
    pub counted: bool,
    /// Identity of the discriminator, for de-duplication.
    pub key: String,
    /// Why undecided; empty on every decided reach.
    pub silence: &'static str,
    /// The syntax shape no row covered; empty on every reach a row decided.
    pub construct: String,
}

/// One of the three reaches that carry no detail beyond their kind.
///
/// They were three functions, identical once the kind and the one boolean were erased.
/// Every other field is the same in all three, and writing it out three times is how they
/// would drift.
fn plain(kind: &'static str, ordered: bool) -> Reach {
    Reach { kind, classes: 0, ordered, counted: true, key: String::new(),
            silence: "", construct: String::new() }
}

// honest-code-allow: L1.21.1 - write, output and unbounded are three names the classifier reads at 35 call sites. The duplicated record they each built is gone: all three fill it through `plain` now, and what is left is the naming. The reference carries this same declaration for the same three functions
/// A write reaches its own value, in order.
pub fn write() -> Reach {
    plain(WRITE, true)
}

/// An output reaches what it emitted, in order.
pub fn output() -> Reach {
    plain(OUTPUT, true)
}

/// Unbounded state has no order to reach, because there is no last one.
pub fn unbounded() -> Reach {
    plain(UNBOUNDED, false)
}

pub fn undecided(reason: &'static str) -> Reach {
    Reach { kind: UNDECIDED, classes: 0, ordered: true, counted: true, key: String::new(),
            silence: reason, construct: String::new() }
}

/// The total row of the categoriser's table: this construct has no rule, so nothing is
/// concluded about it.
///
/// It exists because a table with a fallthrough cannot tell "no rule applies" apart from
/// "the compositional rule applies". The classifier used to run off the bottom of its
/// dispatch into the output verdict, and output is a VERDICT: it says the value is handed
/// to the caller, reaches no decision and costs no tests. So a walrus in a condition, a
/// match subject and a comprehension source were not left unhandled, they were cleared,
/// and the finding read to an adopter as evidence that the code was fine. Measured across
/// eleven repositories before this row existed, that terminal decided 55 per cent of every
/// reference the classifier read.
///
/// Two properties make it a rule rather than a hole. It is reached only when every row
/// above it has declined, so an unhandled construct comes out unmeasured by construction
/// rather than by whoever remembered to check. And it is handed two node-type strings, so
/// no tree, no language row and no closed-set table are in scope: no verdict is reachable
/// from what it holds.
///
/// The silence is OURS. A construct nobody taught the reader is the same class of fact as
/// a callee nobody modelled, so it reports under its own reason and not under the
/// adopter's boundary, and `construct` carries the shape so the backlog can be read off
/// the report and worked down.
pub fn unmeasured(node_type: &str, parent_type: &str) -> Reach {
    Reach { kind: UNDECIDED, classes: 0, ordered: true, counted: true, key: String::new(),
            silence: UNMODELED_CONSTRUCT,
            construct: format!("{node_type} in {parent_type}") }
}

pub fn finite(classes: i64, ordered: bool, key: impl Into<String>) -> Reach {
    Reach { kind: FINITE, classes, ordered, counted: true, key: key.into(),
            silence: "", construct: String::new() }
}

/// Provably finite, count unrecoverable. Ordered is false because we cannot show it is
/// ordered, and claiming order we have not established would be the optimistic direction.
pub fn uncounted(key: impl Into<String>) -> Reach {
    Reach { kind: FINITE, classes: 0, ordered: false, counted: false, key: key.into(),
            silence: "", construct: String::new() }
}

/// A state with no finite reach at all is observe-only or output-only: its reaching set is
/// empty, which is ONE class (every value behaves alike), not zero.
pub const EMPTY: Partition = Partition { classes: 1, ordered: true, counted: true };
pub const UNKNOWN: Partition = Partition { classes: 0, ordered: false, counted: false };

/// The reaching partition of one state, from its per-reference reaches.
///
/// De-duplicated by discriminator, then summed: each distinct discriminator cuts one more
/// class out of the domain, so n of them leave n+1 classes. Ordered survives only if every
/// discriminator is ordered, since one unordered split is enough to defeat boundary
/// selection over the whole domain.
pub fn roll_up(reaches: &[Reach]) -> Partition {
    // Keyed, so the same split written in two places counts once. A map rather than a
    // dedup on the list: the reference keeps the LAST reach for a key, and a set would
    // keep whichever arrived first.
    let mut by_key: BTreeMap<&str, &Reach> = BTreeMap::new();
    for reach in reaches.iter().filter(|r| r.kind == FINITE) {
        by_key.insert(reach.key.as_str(), reach);
    }
    if by_key.is_empty() {
        return EMPTY;
    }
    if !by_key.values().all(|d| d.counted) {
        return UNKNOWN;
    }
    Partition {
        classes: 1 + by_key.values().map(|d| d.classes - 1).sum::<i64>(),
        ordered: by_key.values().all(|d| d.ordered),
        counted: true,
    }
}

/// The positive finding: finite, unordered, and over the bound.
///
/// `drives_decision` is required because a partition that reaches no decision costs no
/// tests at all, however many classes its domain would have had.
pub fn is_coarse(partition: Partition, drives_decision: bool, bound: i64) -> bool {
    drives_decision && partition.counted && !partition.ordered && partition.classes > bound
}

/// Literal node types whose values are ordered, across the nine grammars.
///
/// A map read by `S[0]`, `S[1]`, `S[2]` splits an ordered index domain, which boundary
/// values cover; a map read by `S["alpha"]`, `S["beta"]` does not, because no string sits
/// just above another. The two are the same node shape and only the literal tells them
/// apart.
pub const ORDERED_LITERALS: &[&str] = &[
    "integer", "float", "number", "decimal_integer_literal",
    "decimal_floating_point_literal", "integer_literal", "float_literal", "real_literal",
    "number_literal", "hex_integer_literal",
];

/// How many members a fixed collection has, or nothing when it cannot be counted.
///
/// A collection literal is counted by its elements. A wrapper call is counted through its
/// argument, so `frozenset(("a", "b"))` is two; `frozenset(config.load())` is closed and
/// of unknown size, which is a count we do not have rather than a size of zero. The
/// difference decides whether the state can ever be the positive finding, so it is never
/// guessed.
///
/// A loop rather than a call to itself, because the wrapper case is unbounded: nothing
/// stops a generated file writing `tuple(tuple(tuple(...)))` deeper than any stack, and a
/// reader that dies on its input is not a reader.
pub fn literal_size(node: Option<Node>, src: &[u8]) -> Option<i64> {
    let mut current = node;
    while let Some(n) = current {
        if matches!(n.kind(), "set" | "tuple" | "list") {
            return Some(children(n).iter().filter(|c| c.is_named()).count() as i64);
        }
        if n.kind() == "call" {
            let name = text(field(Some(n), "function"), src);
            if matches!(name.as_str(), "frozenset" | "set" | "tuple") {
                let Some(args) = field(Some(n), "arguments") else { return Some(0) };
                current = first_named(Some(args));
                continue;
            }
        }
        return None;
    }
    None
}

/// Member count of a node the closed-set rule already accepted, or nothing when unknown.
pub fn closed_set_size(node: Node, closed_sets: &BTreeMap<String, Option<i64>>,
                       src: &[u8]) -> Option<i64> {
    match node.kind() {
        "identifier" => closed_sets.get(&text(Some(node), src)).copied().flatten(),
        "attribute" => closed_sets
            .get(&text(field(Some(node), "attribute"), src))
            .copied()
            .flatten(),
        _ => literal_size(Some(node), src),
    }
}

/// `S in FIXED`: which member S equals, or none of them, which is k+1 classes with nothing
/// ordering them. When the container's size is unrecoverable the partition is still
/// finite, so the verdict stands; only the count is silent.
pub fn membership_reach(container: Node, closed_sets: &BTreeMap<String, Option<i64>>,
                        src: &[u8]) -> Reach {
    let key = format!("set:{}", text(Some(container), src));
    match closed_set_size(container, closed_sets, src) {
        None => uncounted(key),
        Some(size) => finite(size + 1, false, key),
    }
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
    fn a_state_that_reaches_no_decision_is_one_class_and_not_zero() {
        // Its reaching set is empty, which means every value behaves alike. Zero would say
        // the domain has no classes at all, and a zero-class partition divides nothing.
        assert_eq!(roll_up(&[]), EMPTY);
        assert_eq!(roll_up(&[write(), output()]), EMPTY);
    }

    #[test]
    fn the_same_split_written_twice_is_counted_once() {
        // `if S:` in fifty methods is one two-class split, not fifty. The key identifies
        // the discriminator and not the site, which is what makes that true.
        let twice = [finite(2, true, "truth:S"), finite(2, true, "truth:S")];
        assert_eq!(roll_up(&twice).classes, 2);
    }

    #[test]
    fn distinct_discriminators_add_rather_than_multiply() {
        // n discriminators leave n+1 classes. Multiplying would be the true partition for
        // two states deciding one branch, and this version does not compose across states
        // at all: under-counting is the safe direction for a measure that only accuses.
        let reaches = [finite(2, true, "a"), finite(3, true, "b")];
        assert_eq!(roll_up(&reaches).classes, 1 + 1 + 2);
    }

    #[test]
    fn one_unordered_split_defeats_boundary_selection_over_the_whole_domain() {
        let reaches = [finite(2, true, "a"), finite(4, false, "b")];
        assert!(!roll_up(&reaches).ordered);
    }

    #[test]
    fn one_uncounted_discriminator_makes_the_whole_partition_uncounted() {
        // An unknown count is a limit of OURS, so it must not reach a finding that accuses
        // the audited code.
        let reaches = [finite(2, true, "a"), uncounted("b")];
        assert_eq!(roll_up(&reaches), UNKNOWN);
    }

    #[test]
    fn a_partition_that_decides_nothing_is_never_coarse_however_wide_it_is() {
        let wide = Partition { classes: 4_000_000, ordered: false, counted: true };
        assert!(!is_coarse(wide, false, 12));
        assert!(is_coarse(wide, true, 12));
    }

    #[test]
    fn an_uncounted_partition_is_never_coarse() {
        assert!(!is_coarse(UNKNOWN, true, 12));
    }

    #[test]
    fn an_ordered_partition_is_never_coarse_because_limit_testing_defeats_it() {
        // A 64-bit integer against three constants induces four intervals, and boundary
        // selection covers them with a handful of values.
        let ordered = Partition { classes: 4_000_000_000, ordered: true, counted: true };
        assert!(!is_coarse(ordered, true, 12));
    }

    #[test]
    fn a_collection_literal_is_counted_by_its_elements() {
        let (tree, src) = parse("X = ('a', 'b', 'c')\n", "python");
        assert_eq!(literal_size(Some(first_of(&tree, "tuple")), &src), Some(3));
    }

    #[test]
    fn a_wrapper_call_is_counted_through_its_argument() {
        let (tree, src) = parse("X = frozenset(('a', 'b'))\n", "python");
        assert_eq!(literal_size(Some(first_of(&tree, "call")), &src), Some(2));
    }

    #[test]
    fn a_wrapper_round_a_call_we_cannot_read_is_closed_and_of_unknown_size() {
        // Not a size of zero. The difference decides whether the state can ever carry the
        // positive finding, so it is never guessed.
        let (tree, src) = parse("X = frozenset(config.load())\n", "python");
        assert_eq!(literal_size(Some(first_of(&tree, "call")), &src), None);
    }

    #[test]
    fn a_membership_test_against_an_unreadable_container_is_still_finite() {
        // The verdict stands and only the count is silent: `S in FIXED` splits the domain
        // into which member S equals, whether or not we can say how many there are.
        let (tree, src) = parse("if s in FIXED:\n    pass\n", "python");
        let container = crate::nodes::descendants(tree.root_node())
            .into_iter()
            .find(|n| n.kind() == "identifier" && text(Some(*n), &src) == "FIXED")
            .expect("the container");
        let closed: BTreeMap<String, Option<i64>> = BTreeMap::new();
        let reach = membership_reach(container, &closed, &src);
        assert_eq!(reach.kind, FINITE);
        assert!(!reach.counted);
    }

    #[test]
    fn a_membership_test_against_a_known_container_is_its_size_plus_one() {
        // Plus one for "none of them", which is a class of the domain like any member.
        let (tree, src) = parse("if s in FIXED:\n    pass\n", "python");
        let container = crate::nodes::descendants(tree.root_node())
            .into_iter()
            .find(|n| n.kind() == "identifier" && text(Some(*n), &src) == "FIXED")
            .expect("the container");
        let closed = BTreeMap::from([("FIXED".to_string(), Some(4))]);
        assert_eq!(membership_reach(container, &closed, &src).classes, 5);
    }

    #[test]
    fn an_unmeasured_construct_names_the_shape_so_the_backlog_can_be_worked() {
        // Told a rule is missing and not which one is a complaint, not a backlog.
        let reach = unmeasured("named_expression", "if_statement");
        assert_eq!(reach.kind, UNDECIDED);
        assert_eq!(reach.silence, UNMODELED_CONSTRUCT);
        assert_eq!(reach.construct, "named_expression in if_statement");
    }

    #[test]
    fn an_unmeasured_construct_is_not_an_output_verdict() {
        // The defect this row exists for. Running off the bottom of the dispatch into
        // `output` CLEARED the reference: it says the value is handed to the caller,
        // reaches no decision and costs no tests. Across eleven repositories that terminal
        // decided 55 per cent of every reference the classifier read.
        assert_ne!(unmeasured("named_expression", "if_statement").kind, output().kind);
    }
}
