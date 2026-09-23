//! L1.18b, the finite-testability classifier. Ported from l1_analyzer.state_bounds.
//!
//! A piece of state is testability-neutral when the production decisions reaching it
//! partition its domain into a statically enumerable finite set of equivalence classes.
//! PARTITION-COUNT, not value-count: an integer that only meets comparisons against
//! constants is cheap; a value used as an unbounded lookup key is not.
//!
//! Every piece of state resolves to exactly one of three verdicts, and to whether it drives
//! a decision:
//!
//!   neutral      the reaching partition is a statically enumerable finite set, or empty
//!   promiscuous  the reaching partition is provably unbounded, which is a proven finding
//!   unresolved   the reaching set is undecidable within scope; fail-closed, and disclosed
//!
//! The analysis scope is the class or the module, never the function: instance state is
//! analysed across every method of its class. Returns are output, not promiscuity. It fails
//! closed only on a value passed to an unbounded call target or reached reflectively.
//!
//! The predicate is language-neutral and the node types that express it are not, which is
//! what the generated language table is for.
//!
//! WHAT THIS PORT DOES NOT CARRY. The reference's reading also holds the path buckets the
//! report card groups findings by. They are computed by the indicator layer rather than
//! here, nothing in the panel reads them, and inventing an empty list for them would say
//! this reading produced no buckets where the truth is that it never computed any.

use crate::lang_spec::LangSpec;
use crate::nodes::{
    descendants, hidden_names, is_lvalue, local_descendants, text,
};
use crate::state::cells::{collect_closed_sets, write_key_bound, ClosedSets};
use crate::state::census;
use crate::state::constants::{collect_immutable_ctors, declared_constant, immutable_const_verdict};
use crate::state::enumerate;
use crate::state::filters;
use crate::state::partition::{
    self, Partition, INJECTED_SLOT, NEUTRAL, PROMISCUOUS, UNPARSED_REGION, UNRESOLVED,
};
use crate::state::reach;
use crate::state::reading::{
    partition_summary, silence_summary, Finding, FileRead, PartitionSummary, StateReading,
};
use crate::state::records;
use crate::state::verdict;
use crate::state::references::bound_to;
use crate::state::sites::Site;
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;
use tree_sitter::Node;

/// Every reference to one piece of instance state, inside its own class.
///
/// Never descends into a nested class: an inner one owns its own fields and is analysed as
/// its own scope, so the enclosing class must not harvest the inner one's state.
pub fn state_refs<'t>(scope: Node<'t>, key: &str, sp: &LangSpec, src: &[u8]) -> Vec<Node<'t>> {
    let found: Vec<Node<'t>> = local_descendants(scope, sp.class_types)
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
        .filter(|n| text(Some(*n), src) == key)
        .collect();
    if sp.instance_enum == "ruby_ivar" || sp.instance_ref_style == "member" {
        return found;
    }
    bound_to(&found, key, sp, src)
}

/// The line where the state is BOUND, not the first line its name appears on.
///
/// The earliest reference is the wrong answer and it sends a reader to the wrong place. A
/// module named `app` makes `from app.auth import X` on line 2 the first textual occurrence
/// of the name, so a finding about the variable `app = FastAPI()` on line 4 was reported
/// against an import statement that binds nothing. On the repository that surfaced this, the
/// reader was sent to line 19 for an object defined on line 113.
///
/// So prefer the earliest reference that is an assignment target, through the same lvalue
/// reader the classifier already uses to decide what a write is. Falling back to the
/// earliest reference keeps a line for state that is never assigned in this file, which is
/// the case for an injected or inherited name.
fn binding_line(refs: &[Node], sp: &LangSpec) -> usize {
    let line_of = |n: &Node| n.start_position().row + 1;
    refs.iter().filter(|r| is_lvalue(Some(**r), sp)).map(line_of).min()
        .or_else(|| refs.iter().map(line_of).min())
        .unwrap_or(1)
}

/// One finding, built where it is decided.
#[allow(clippy::too_many_arguments)]
fn finding(key: &str, refs: &[Node], rel: &str, sp: &LangSpec, closed_sets: &ClosedSets,
           immutable_ctors: &[String], instance: bool, hidden: &BTreeSet<String>,
           src: &[u8]) -> Finding {
    let line = binding_line(refs, sp);
    let settled = |verdict: &'static str, drives: bool, part: Partition| Finding {
        state: key.to_string(), verdict, drives_decision: drives, file: rel.to_string(),
        line, silence: "", construct: String::new(), silence_line: 0, partition: part,
    };

    // A state the language DECLARES immutable is settled before any reach is read: one
    // value, one class. The partition is EMPTY, the same one the immutable-constant branch
    // below writes. An earlier version built a per-reference REACH here, which is what ONE
    // reference does to the domain where this field holds the rolled-up partition of all of
    // them, so it told the summary that every declared constant was unordered. That is the
    // distribution the coarseness bound is set from, and a one-value domain has nothing to
    // order either way.
    if declared_constant(refs, sp, src) {
        return settled(NEUTRAL, false, partition::EMPTY);
    }

    let mut result = if sp.immutable_ctor_rule {
        immutable_const_verdict(refs, immutable_ctors, sp, src)
            .map(|(verdict, drives)| settled(verdict, drives, partition::EMPTY))
    } else {
        None
    };

    if result.is_none() {
        // Computed ONCE over every reference and handed to each, because the bound is a
        // fact about the state and not about the reference being judged. Per-reference
        // judgement is what let a read report unbounded while the writes it reads from
        // could only ever fill two cells.
        let cells = write_key_bound(refs, sp, closed_sets, src);
        let reaches: Vec<partition::Reach> = refs.iter()
            // The recursion budget, stated where the recursion starts rather than as a
            // default on the reader itself, so the one caller that sets it and the many
            // recursive calls that spend it do not look identical at the call site.
            .map(|r| reach::categorize(*r, sp, closed_sets, cells, reach::REACH_DEPTH, src))
            .collect();
        let rolled = verdict::verdict(&reaches, refs);
        let mut f = Finding {
            state: key.to_string(), verdict: rolled.verdict,
            drives_decision: rolled.drives_decision, file: rel.to_string(), line,
            silence: rolled.silence, construct: rolled.construct,
            silence_line: rolled.silence_line, partition: rolled.partition,
        };
        // An invoked slot earns neutral from the compositional rule; that rule has premises.
        if f.verdict == NEUTRAL && verdict::injected_slot_premise_fails(refs, sp, instance, src) {
            f = Finding { state: key.to_string(), verdict: UNRESOLVED, drives_decision: true,
                          file: rel.to_string(), line, silence: INJECTED_SLOT,
                          construct: String::new(), silence_line: 0,
                          partition: partition::UNKNOWN };
        }
        result = Some(f);
    }
    let mut f = result.expect("a finding was built on both paths");

    // The attribute-level false-positive filter: the per-reference verdict conflates
    // unbounded data with an unbounded decision. It clears a finding to neutral only where
    // the attribute is a provable write-once, memoization cache, carried value or write-only
    // accumulator, and it decides for itself which of its rules this language can carry.
    if f.verdict != NEUTRAL && filters::is_false_positive(key, refs, f.verdict, sp, src) {
        f = settled(NEUTRAL, false, partition::EMPTY);
    }

    // THE READING WAS INCOMPLETE, and this is the last word on the finding for that reason.
    // `hidden` holds the names that appear inside a region the grammar handed back as
    // tokens, so a reference in one of them was never built and no walk above could have
    // reached it. Every line above ran on the references that WERE built, which is a proper
    // subset, and a verdict from a subset, most of all a neutral one a filter just cleared,
    // would report what was not looked at as what was read and found clean. It sits after
    // the filter rather than before it so that no rule can clear it back.
    if hidden.contains(filters::attr_of(key)) {
        return Finding { state: key.to_string(), verdict: UNRESOLVED, drives_decision: true,
                         file: rel.to_string(), line, silence: UNPARSED_REGION,
                         construct: String::new(), silence_line: 0,
                         partition: partition::UNKNOWN };
    }
    f
}

/// One file's findings, and every declaration the enumerators walked to reach them.
///
/// Refused where a language's own enumerator is one nobody wrote: an empty finding list for
/// such a file reads exactly like a file holding no state.
pub fn analyze_file(root: Node, rel: &str, sp: &LangSpec, immutable_ctors: &[String],
                    src: &[u8]) -> Option<FileRead> {
    // An empty TABLE, not an empty set. The parameter is a mapping of name to bound and
    // three readers ask it for one; a set has none.
    let closed_sets = if sp.closed_set_rule {
        collect_closed_sets(root, src)
    } else {
        ClosedSets::new()
    };
    let mut findings: Vec<Finding> = Vec::new();
    let mut visited: BTreeSet<Site> = BTreeSet::new();
    let mut judged: BTreeSet<Site> = BTreeSet::new();
    // The names sitting inside regions this grammar left unparsed, for the whole file. Read
    // once and handed to every finding, because a macro in one function can name a field of
    // another and a module static alike, and because a language that parses everything gets
    // the empty set here without a walk.
    let hidden = hidden_names(root, sp, src);

    let module = enumerate::module_cands(root, sp, src)?;
    visited.extend(enumerate::visited(&module));
    for name in enumerate::keys_of(&module) {
        let named: Vec<Node> = descendants(root).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), src) == name)
            .collect();
        let refs = bound_to(&named, &name, sp, src);
        if refs.is_empty() {
            continue;
        }
        findings.push(finding(&name, &refs, rel, sp, &closed_sets, immutable_ctors, false,
                              &hidden, src));
        judged.extend(enumerate::sites_of(&module, &name));
    }

    // Go: state spans methods, grouped by receiver type.
    if sp.scope_by_receiver {
        for slot in enumerate::go_slots(root, src) {
            findings.push(finding(&slot.state, &slot.refs, rel, sp, &closed_sets,
                                  immutable_ctors, slot.writers_enumerable, &hidden, src));
            visited.insert(slot.site.clone());
            judged.insert(slot.site);
        }
    }

    for cls in descendants(root).into_iter().filter(|n| sp.class_types.contains(&n.kind())) {
        let cands = enumerate::instance_cands(cls, sp, src)?;
        visited.extend(enumerate::visited(&cands));
        for key in enumerate::keys_of(&cands) {
            let refs = state_refs(cls, &key, sp, src);
            if refs.is_empty() {
                continue;
            }
            findings.push(finding(&key, &refs, rel, sp, &closed_sets, immutable_ctors, true,
                                  &hidden, src));
            judged.extend(enumerate::sites_of(&cands, &key));
        }
    }

    // State declared inside a record, which neither enumerator above can reach: both work
    // from a reference, and a slot declared once and thereafter only used is spelled one way
    // at its declaration and another at every use. The record rules own both halves, and are
    // handed the keys already claimed for a record so they can stand down instead of
    // reporting the same slot twice.
    let already = |cls: Node| -> Vec<String> {
        enumerate::instance_cands(cls, sp, src)
            .map(|cands| enumerate::keys_of(&cands))
            .unwrap_or_default()
    };
    let read = records::slots(root, sp, src, &already)?;
    visited.extend(read.visited);
    for slot in read.slots {
        findings.push(finding(&slot.state, &slot.refs, rel, sp, &closed_sets, immutable_ctors,
                              slot.writers_enumerable, &hidden, src));
        judged.insert(slot.site);
    }

    Some(FileRead { findings, visited, judged })
}

/// The reading for a language this classifier has no table for.
///
/// The resolvable fraction is ABSENT rather than the string "n/a": a reading that did not
/// happen has no fraction, and a string in a number's field made the one question a reader
/// asks first into a type check.
pub fn na(lang: &str) -> StateReading {
    StateReading {
        verdict: "n/a".into(),
        band: "n/a".into(),
        counts: [(NEUTRAL, 0), (PROMISCUOUS, 0), (UNRESOLVED, 0)].into_iter().collect(),
        resolvable_fraction: None,
        silence: silence_summary(&[], 0),
        // The census is absent rather than zeroed for the same reason: a language with no
        // table was not counted, and a confident zero would report "there is no state" for a
        // repository nobody read.
        census: census::uncounted(0),
        findings: Vec::new(),
        details: format!("finite-testability classifier has no spec for {lang} yet"),
    }
}

/// How the findings are ordered for a reader: worst first, deciding before observing, then
/// by where they are.
fn severity(verdict: &str) -> u8 {
    match verdict {
        PROMISCUOUS => 0,
        UNRESOLVED => 1,
        _ => 2,
    }
}

/// L1.18b: the finite-testability verdict distribution over a repository.
pub fn classify(repo: &Path, lang: &str) -> StateReading {
    let Some(sp) = crate::lang_spec::spec_for(lang) else { return na(lang) };
    let parsed = census::parsed_files(repo, lang);

    // First pass: collect the repository's immutable constructors, the functions whose
    // returns are all immutable, so a constant built by one can be resolved by a one-level
    // follow. Second pass: analyse with that knowledge.
    let mut immutable_ctors: Vec<String> = Vec::new();
    if sp.immutable_ctor_rule {
        for (_rel, tree, src) in &parsed {
            immutable_ctors.extend(collect_immutable_ctors(tree.root_node(), src));
        }
    }

    let mut findings: Vec<Finding> = Vec::new();
    // The visit record, per file, in the census's site vocabulary. Collected here rather
    // than re-derived later, because only the enumerators know where they went: a second
    // walk written to work out where the first one probably looked is a guess wearing a
    // measurement's name, which is the defect this number replaced.
    let mut visited: BTreeMap<String, BTreeSet<Site>> = BTreeMap::new();
    let mut judged: BTreeMap<String, BTreeSet<Site>> = BTreeMap::new();
    for (rel, tree, src) in &parsed {
        let Some(read) = analyze_file(tree.root_node(), rel, sp, &immutable_ctors, src) else {
            // A language whose enumerator nobody wrote. Refused whole rather than reported
            // as a repository holding no state.
            return na(lang);
        };
        findings.extend(read.findings);
        visited.insert(rel.clone(), read.visited);
        judged.insert(rel.clone(), read.judged);
    }

    let mut counts: BTreeMap<&'static str, usize> =
        [(NEUTRAL, 0), (PROMISCUOUS, 0), (UNRESOLVED, 0)].into_iter().collect();
    for f in &findings {
        *counts.entry(f.verdict).or_insert(0) += 1;
    }
    let total: usize = counts.values().sum();
    let verdict = if counts[PROMISCUOUS] > 0 {
        PROMISCUOUS
    } else if counts[UNRESOLVED] > 0 {
        UNRESOLVED
    } else if total > 0 {
        NEUTRAL
    } else {
        "n/a"
    };
    // One over zero state is deliberate: a codebase with no mutable state by design IS fully
    // resolved, and the report reads a number here as the signal that the meter ran at all.
    // The vacuity checker flags it as a fabricated affirmative and it is a FALSE POSITIVE for
    // the same reason as the silence fraction: the "read nothing" failure is the census's job.
    let resolvable = if total > 0 {
        ((counts[NEUTRAL] + counts[PROMISCUOUS]) as f64 / total as f64 * 1000.0).round() / 1000.0
    } else {
        1.0
    };

    findings.sort_by(|a, b| {
        severity(a.verdict).cmp(&severity(b.verdict))
            .then(a.drives_decision.cmp(&b.drives_decision).reverse())
            .then(a.file.cmp(&b.file))
            .then(a.line.cmp(&b.line))
    });
    let silence = silence_summary(&findings, total);
    let partition_counts: PartitionSummary = partition_summary(&findings);

    // The independent denominator. Every number above this line is computed over the state
    // THIS function recognised, and no measure over the enumerated set can see
    // non-enumeration. The census counts state-bearing declarations from the parse tree by a
    // separate route, so a struct field no enumerator here knows about still lands in the
    // denominator and the gap becomes visible.
    let census = census::compare(repo, lang, findings.len(), &visited, &judged);

    let details = format!(
        "finite-testability: {} neutral, {} promiscuous, {} unresolved across {total} \
         pieces of state; resolvable fraction {}; silence {}; {} of {} deciding \
         partitions uncounted. Cardinality is per state and does not compose: two states \
         that decide the same branch multiply, and this version reports each separately \
         rather than guessing the product.",
        counts[NEUTRAL], counts[PROMISCUOUS], counts[UNRESOLVED],
        crate::py_float(resolvable), crate::py_float(silence.fraction),
        partition_counts.uncounted, partition_counts.deciding_states);

    StateReading {
        verdict: verdict.to_string(),
        band: "n/a".into(),
        counts,
        resolvable_fraction: Some(resolvable),
        silence,
        census,
        findings,
        details,
    }
}

/// The panel's value string for this reading.
///
/// Kept beside the reading rather than inside it, because it is one rendering of three
/// counts the reading already carries, and a second stored copy of a number is how the two
/// come apart.
pub fn value_of(reading: &StateReading) -> String {
    format!("{} neutral / {} promiscuous / {} unresolved",
            reading.counts[NEUTRAL], reading.counts[PROMISCUOUS], reading.counts[UNRESOLVED])
}
