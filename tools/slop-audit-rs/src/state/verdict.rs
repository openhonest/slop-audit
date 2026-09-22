//! From per-reference reaches to one verdict for the state. Ported from the roll-up half of
//! l1_analyzer.state_reach.
//!
//! A separate module from the reaches themselves, because it asks a different question. The
//! reach reader answers what ONE reference does to the domain; this answers what all of them
//! together say about the state, and which reference the reader should be sent to when they
//! could not be decided.

use crate::lang_spec::LangSpec;
use crate::nodes::{field, is_lvalue, same, text};
use crate::state::partition;
use crate::state::reach::is_call_target;
use tree_sitter::Node;

/// The host reaches INTO the value: `S.attr = v`, or a mutating method on S. Either way the
/// host depends on the collaborator's internal shape, which it cannot enumerate.
fn written_through(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(parent) = reference.parent() else { return false };
    if !sp.member_types.contains(&parent.kind())
        || !same(field(Some(parent), sp.mem_object), Some(reference)) {
        return false;
    }
    if is_lvalue(Some(parent), sp) {
        return true;                                       // S.attr = v
    }
    let called = parent.parent().is_some_and(|gp| sp.call_types.contains(&gp.kind())
        && same(field(Some(gp), sp.call_fn), Some(parent)));
    called && sp.mutating.contains(&text(field(Some(parent), sp.mem_attr), src).as_str())
}

/// Call-target position is compositional only while the value at the call site is provably
/// the value that was injected. Three constructs defeat that proof, and all three are
/// per-attribute, so none can be seen one reference at a time.
///
/// Not instance state: a module-level invoked slot, a C function pointer or a module global
/// holding a callable, has a writer set that is not enumerable at all, since any translation
/// unit can assign it. Only instance state has the property the scope rule relies on, that
/// its writers are the methods of its own class. Rebinding: more than one binding site means
/// which callee is live at the call depends on invisible history. Reaching in: writing
/// through the slot means the collaborator is no longer a black box behind its contract.
pub fn injected_slot_premise_fails(refs: &[Node], sp: &LangSpec, instance: bool,
                                   src: &[u8]) -> bool {
    if !refs.iter().any(|r| is_call_target(*r, sp)) {
        return false;
    }
    if !instance {
        return true;
    }
    if refs.iter().filter(|r| is_lvalue(Some(**r), sp)).count() > 1 {
        return true;
    }
    refs.iter().any(|r| written_through(*r, sp, src))
}

/// One state's verdict, from what each of its references does to the domain.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Verdict {
    pub verdict: &'static str,
    pub drives_decision: bool,
    pub silence: &'static str,
    pub construct: String,
    pub partition: partition::Partition,
    /// The line the silence sits on, which is the first undecided reference's own line.
    pub silence_line: usize,
}

/// Combine per-reference reaches into one verdict.
///
/// The silence reason reported is the FIRST undecided reference in source order, not the
/// worst of them by some ranking. Any ranking would be invented here, and the reader's next
/// move is to open the site, so the site that comes first is the one to send them to. Its
/// LINE travels with it, and so does the construct, for the same reason: naming a shape
/// read off one reference while publishing another reference's line sends a reader to one
/// place and describes another.
pub fn verdict(reaches: &[partition::Reach], refs: &[Node]) -> Verdict {
    if let Some((index, reach)) = reaches.iter().enumerate()
        .find(|(_, r)| r.kind == partition::UNDECIDED) {
        let line = refs.get(index).map(|r| r.start_position().row + 1).unwrap_or(0);
        return Verdict { verdict: partition::UNRESOLVED, drives_decision: true,
                         silence: reach.silence, construct: reach.construct.clone(),
                         partition: partition::UNKNOWN, silence_line: line };
    }
    if reaches.iter().any(|r| r.kind == partition::UNBOUNDED) {
        return Verdict { verdict: partition::PROMISCUOUS, drives_decision: true, silence: "",
                         construct: String::new(), partition: partition::UNKNOWN,
                         silence_line: 0 };
    }
    if reaches.iter().any(|r| r.kind == partition::FINITE) {
        return Verdict { verdict: partition::NEUTRAL, drives_decision: true, silence: "",
                         construct: String::new(), partition: partition::roll_up(reaches),
                         silence_line: 0 };
    }
    // Observe-only or output-only: an empty reaching set, so one class and nothing to cover.
    Verdict { verdict: partition::NEUTRAL, drives_decision: false, silence: "",
              construct: String::new(), partition: partition::EMPTY, silence_line: 0 }
}
