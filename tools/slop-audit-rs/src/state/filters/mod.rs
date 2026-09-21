//! Attribute-level false-positive filters for the L1.18b finite-testability classifier.
//! Ported from l1_analyzer.state_bounds_filters.
//!
//! The classifier grades each REFERENCE to a piece of state and combines the categories into
//! a verdict. That is right for most state, but it conflates unbounded DATA with an
//! unbounded DECISION: a value indexed by an unbounded key, or carried through a builder, is
//! flagged even when no value derived from it ever reaches a branch. Decision space, not
//! data cardinality, is what bounds testability.
//!
//! These filters run once per attribute, over all its references, and clear a finding to
//! neutral only when a shape is PROVABLY testable. They are conservative: any doubt keeps
//! the finding. Four shapes, each carrying at least one case the others cannot:
//!
//!   write-once   assigned once through ANY receiver, never mutated, never handed out whole
//!   memoization  a presence-gated, result-invariant cache whose stored value never reaches
//!                a branch condition
//!   carried      a value that appears in no test expression at all
//!   accumulator  a presence-gated counter or tally that is only ever written: no reference
//!                reads the stored value out, so nothing observable turns on it
//!
//! The last two overlap on an UNGATED accumulator, which carried already clears. What only
//! the accumulator rule reaches is the gated form, `if k not in self._h: self._h[k] = 0`,
//! where the membership test does put a reference in a condition.
//!
//! Two guards sit in front of the rules and refuse a shape outright, because a rule that
//! argues from where a reference sits cannot see either of them:
//!
//!   value in a condition  the stored value is inspected in a branch, so presence or
//!                         magnitude is the answer and the cache is a decision
//!   open-key selection    the container is read at a key the class does not bound, so it
//!                         answers one way per key and the caller chooses which
//!
//! Only memoization is allowed past the second guard, and only because a presence-gated,
//! result-invariant cache can be deleted without changing an answer.
//!
//! This port only ever CLEARS a finding the classifier already reached, so a port that
//! shipped without it would over-accuse relative to the reference on every repository. That
//! is the wrong direction for an instrument whose whole claim is that it never says more
//! than it measured.

pub mod accumulator;
pub mod memoization;
pub mod open_key;
pub mod write_once;

use crate::lang_spec::LangSpec;
use crate::state::partition::PROMISCUOUS;
use crate::state::ref_reads as reads;
use tree_sitter::Node;

/// The bare attribute name from a state key: `self._rows` becomes `_rows`.
///
/// Ruby's sigil survives, and `@hits` stays `@hits`, which is right: the sigil is part of
/// the name the grammar puts in the node, and the naming predicate matches against that
/// node.
pub fn attr_of(key: &str) -> &str {
    key.rsplit('.').next().unwrap_or(key)
}

/// The nearest ancestor of `reference` whose type is one of `types`.
///
/// Called with the class types and with the function types, and it is ONE function for both
/// rather than a named wrapper each. The two wrappers were the same three lines with one
/// table field swapped, so a reader comparing them had to spot the field to learn that the
/// rule is the same rule. A language with no class types at all, which is Go and C, gets
/// nothing back from the class call, and the rules that need a class body check for
/// themselves.
pub fn enclosing<'t>(reference: Node<'t>, types: &[&str]) -> Option<Node<'t>> {
    let mut cur = reference.parent();
    while let Some(node) = cur {
        if types.contains(&node.kind()) {
            return Some(node);
        }
        cur = node.parent();
    }
    None
}

/// Carried value: no reference appears in a test expression, so the attribute decides
/// nothing. Unbounded data that never reaches a branch does not bound testability.
pub fn drives_no_decision(refs: &[Node], sp: &LangSpec) -> bool {
    !refs.iter().any(|r| reads::in_test(*r, sp))
}

pub fn has_presence_gate(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    refs.iter().any(|r| reads::is_presence_test(*r, sp, src))
}

/// A stored value is inspected in a branch: a keyed READ of the attribute appears inside a
/// test expression. This is the guard that keeps a magnitude test (`now - t >= 3600`)
/// flagged.
pub fn value_reaches_condition(refs: &[Node], sp: &LangSpec, src: &[u8]) -> bool {
    refs.iter().any(|r| match reads::keyed_value_read(*r, sp, src) {
        Some(read) => reads::in_test(read, sp),
        None => false,
    })
}

/// True when the finding for this attribute is a provable false positive under one of the
/// four rules, and should be reclassified neutral. Conservative: any doubt is false.
///
/// The verdict gates which rules may fire. An unresolved verdict means the classifier could
/// not decide the reaching set, through dynamic dispatch or an unknown callee, and that is a
/// genuine fail-closed finding, so the carried-value rule, which only argues about decision
/// space, must never clear it. Only write-once can clear an unresolved, and only when the
/// value provably never escapes.
pub fn is_false_positive(key: &str, refs: &[Node], verdict: &str, sp: &LangSpec,
                         src: &[u8]) -> bool {
    let Some(&first) = refs.first() else { return false };
    let attr = attr_of(key);
    // The single guard that keeps every genuine finding: if the attribute drives a decision
    // whose answer depends on an unbounded value or key, it stays flagged, whatever else is
    // true of it. Only once no such decision exists is a shape eligible to clear.
    //
    // Compared against `Some(false)` and not merely negated: the predicate answers nothing
    // when no method gates on presence, and that means the question does not apply rather
    // than "presence decides".
    if value_reaches_condition(refs, sp, src)
        || memoization::result_invariant(attr, refs, sp, src) == Some(false) {
        return false;
    }
    // The enclosing class, or nothing where the language has none. Go declares no class
    // types at all and Rust's scope is an impl block.
    let cls = enclosing(first, sp.class_types);
    // MEMOIZATION is settled BEFORE the open-key guard, and it is the one shape allowed past
    // it. A presence-gated, result-invariant cache answers the same for a key whether or not
    // that key is stored, so the partition its keyed read cuts belongs to the function being
    // memoised and not to the cache: delete the cache and every observable answer is
    // unchanged. No other rule can make that argument, which is why no other rule is exempt.
    if let Some(cls) = cls {
        if verdict == PROMISCUOUS && memoization::is_memoization(cls, attr, refs, sp, src) {
            return true;
        }
    }
    // THE WRITE-ONLY ACCUMULATOR, also settled before the guard, because it is exempt from
    // it: it clears a shape where every reference is a WRITE, and a write at an open key
    // does not make the answer depend on that key. Behind the guard it stopped clearing a
    // per-key tally in five languages, which the vectors declare neutral for exactly this
    // reason.
    if verdict == PROMISCUOUS && accumulator::is_write_only_accumulator(attr, refs, sp, src) {
        return true;
    }
    if open_key::selects_on_an_open_key(refs, sp, src) {
        return false;
    }
    // WRITE-ONCE sits above the verdict gate because it clears an unresolved as well as a
    // promiscuous: a value that provably never escapes was never unresolved.
    if let Some(cls) = cls {
        if write_once::is_write_once(cls, attr, refs, sp, src) {
            return true;
        }
    }
    if verdict != PROMISCUOUS {
        return false;
    }
    drives_no_decision(refs, sp)
}

// --- the parity dump -------------------------------------------------------------

/// Every reference to one piece of INSTANCE state inside its own class.
///
/// Never descends into a nested class: an inner one owns its own fields and is analysed as
/// its own scope, so the enclosing class must not harvest the inner one's state.
pub fn state_refs<'t>(scope: Node<'t>, key: &str, sp: &LangSpec, src: &[u8]) -> Vec<Node<'t>> {
    let found: Vec<Node<'t>> = crate::nodes::local_descendants(scope, sp.class_types)
        .into_iter()
        .filter(|n| {
            if sp.instance_enum == "ruby_ivar" {
                n.kind() == "instance_variable"
            } else if sp.instance_ref_style == "member" {
                sp.member_types.contains(&n.kind())
            } else {
                n.kind() == "identifier"
            }
        })
        .filter(|n| crate::nodes::text(Some(*n), src) == key)
        .collect();
    if sp.instance_enum == "ruby_ivar" || sp.instance_ref_style == "member" {
        return found;
    }
    crate::state::references::bound_to(&found, key, sp, src)
}

/// What every rule and guard above said about one piece of state.
///
/// The verdict the classifier reached is not available here, because the classifier itself
/// is not ported yet. Both verdicts a rule can act on are reported instead, so the entry
/// point is compared whole rather than on whichever verdict a repository happened to
/// produce.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Verdicts {
    pub scope: usize,
    pub key: String,
    pub refs: usize,
    /// One letter per answer, in a fixed order, so two implementations emit one spelling.
    pub answers: String,
}

fn yes_no(answer: bool) -> char {
    if answer { 'y' } else { 'n' }
}

/// Every rule's answer about one piece of state, in the order the entry point asks them.
pub fn verdicts_for(cls: Option<Node>, key: &str, refs: &[Node], sp: &LangSpec,
                    src: &[u8]) -> String {
    let attr = attr_of(key);
    let invariant = match memoization::result_invariant(attr, refs, sp, src) {
        None => '-',
        Some(true) => 'y',
        Some(false) => 'n',
    };
    let memo = cls.is_some_and(|c| memoization::is_memoization(c, attr, refs, sp, src));
    let once = cls.is_some_and(|c| write_once::is_write_once(c, attr, refs, sp, src));
    format!(
        "{}{invariant}{}{}{}{}{}{}{}",
        yes_no(value_reaches_condition(refs, sp, src)),
        yes_no(memo),
        yes_no(accumulator::is_write_only_accumulator(attr, refs, sp, src)),
        yes_no(open_key::selects_on_an_open_key(refs, sp, src)),
        yes_no(once),
        yes_no(drives_no_decision(refs, sp)),
        yes_no(is_false_positive(key, refs, crate::state::partition::PROMISCUOUS, sp, src)),
        yes_no(is_false_positive(key, refs, crate::state::partition::UNRESOLVED, sp, src)),
    )
}

/// Everything the filters say about one parsed file.
///
/// Two of the three routes the classifier walks: module-level state, and instance state
/// inside a class. Go's receiver-grouped slots are the third and are not here, because the
/// enumerator hands those back as byte offsets rather than nodes; Go's package-level state
/// still goes through the module route, so the grammar is exercised.
pub fn file_verdicts(root: Node, sp: &LangSpec, src: &[u8]) -> Vec<Verdicts> {
    let mut out = Vec::new();
    if let Some(module) = crate::state::enumerate::module_cands(root, sp, src) {
        for key in crate::state::enumerate::keys_of(&module) {
            let named: Vec<Node> = crate::nodes::descendants(root)
                .into_iter()
                .filter(|n| n.kind() == "identifier"
                        && crate::nodes::text(Some(*n), src) == key)
                .collect();
            let refs = crate::state::references::bound_to(&named, &key, sp, src);
            if refs.is_empty() {
                continue;
            }
            out.push(Verdicts { scope: 0, key: key.clone(), refs: refs.len(),
                                answers: verdicts_for(None, &key, &refs, sp, src) });
        }
    }
    for cls in crate::nodes::descendants(root).into_iter()
        .filter(|n| sp.class_types.contains(&n.kind())) {
        let Some(cands) = crate::state::enumerate::instance_cands(cls, sp, src) else { continue };
        for key in crate::state::enumerate::keys_of(&cands) {
            let refs = state_refs(cls, &key, sp, src);
            if refs.is_empty() {
                continue;
            }
            out.push(Verdicts { scope: cls.start_byte(), key: key.clone(), refs: refs.len(),
                                answers: verdicts_for(Some(cls), &key, &refs, sp, src) });
        }
    }
    out
}

/// Every file in scope, read by the filters. Same scope and same files as the census walk.
pub fn walk(repo: &std::path::Path, lang: &str)
    -> std::collections::BTreeMap<String, Vec<Verdicts>> {
    let Some(sp) = crate::lang_spec::spec_for(lang) else {
        return std::collections::BTreeMap::new();
    };
    crate::state::census::parsed_files(repo, lang)
        .into_iter()
        .map(|(rel, tree, src)| (rel, file_verdicts(tree.root_node(), sp, &src)))
        .collect()
}
