//! Which Python module bindings hold mutable state. Ported from the module scan in
//! l1_analyzer.mutable_state.
//!
//! This is the one rule the enumerator could not reach without, and the reason the whole
//! Python arm refused. It is shared: L1.18 reads it to count references to external
//! mutable state, and the finite-testability enumerator reads it to decide which of the
//! bindings it walked are state. One rule, two readers, so the two cannot disagree about
//! what a module keeps.
//!
//! The split matters for the coverage number. The scan reports only the names it judges
//! mutable; the enumerator needs the ones it judged and DECLINED as well, because a
//! binding the reader walked and ruled out is read, not missed. That is why the candidate
//! list is a function of its own rather than something each reader guesses: a second walk
//! written to produce the same candidates would drift from this one silently, which is the
//! class of defect the coverage number exists to expose.

use crate::nodes::{children, field, text};
use tree_sitter::Node;

/// The container constructors whose empty call seeds an accumulator.
const PY_CONTAINER_CTORS: &[&str] = &[
    "dict", "list", "set", "defaultdict", "OrderedDict", "deque", "Counter", "bytearray",
];

/// The names that build a type rather than hold a value.
const PY_TYPE_CTORS: &[&str] = &["TypedDict", "NewType", "NamedTuple", "TypeVar"];

/// The receiver identifiers this language spells, which are never module state.
const PY_THIS_IDENTS: &[&str] = &["self"];

/// The assignment node types a Python module binding can be spelled with.
const PY_MODULE_ASSIGN: &[&str] = &["assignment", "augmented_assignment"];

/// Top-level assignments, allowing ONE wrapper: Python nests `x = 0` inside an expression
/// statement, so the assignment node is a child of a root child.
///
/// Its own function, because it defines WHICH declarations the module scan considers, and
/// the enumerator needs that list whole. The scan reports only the names it judged
/// mutable; a binding it walked and ruled out is read, not missed, and the two are
/// separable only here.
pub fn shallow_candidates<'t>(root: Node<'t>) -> Vec<Node<'t>> {
    let mut candidates = Vec::new();
    for node in children(root) {
        if PY_MODULE_ASSIGN.contains(&node.kind()) {
            candidates.push(node);
        } else {
            candidates.extend(
                children(node).into_iter().filter(|c| PY_MODULE_ASSIGN.contains(&c.kind())),
            );
        }
    }
    candidates
}

/// A pure type expression: a bare name, a dotted name, a subscript, or a `|` union of
/// those. No call, no container literal.
fn is_type_expression(n: Node, src: &[u8]) -> bool {
    match n.kind() {
        "identifier" | "attribute" | "subscript" => true,
        "binary_operator" => {
            let (op, left, right) = (field(Some(n), "operator"), field(Some(n), "left"),
                                     field(Some(n), "right"));
            match (op, left, right) {
                (Some(op), Some(left), Some(right)) => {
                    text(Some(op), src) == "|"
                        && is_type_expression(left, src)
                        && is_type_expression(right, src)
                }
                _ => false,
            }
        }
        _ => false,
    }
}

/// Whether this binding declares a TYPE rather than holding a value.
///
/// The call form is here because a type expression declines anything with a call in it,
/// and `TypedDict("Panel", {...})` is a call that returns a type. The class form of the
/// same declaration was never counted, so one declaration read two ways depending on which
/// syntax spelled it, and only one of the two can spell a key with a dot in it.
fn is_type_alias(node: Node, rhs: Option<Node>, src: &[u8]) -> bool {
    if let Some(annot) = field(Some(node), "type") {
        let spelled = text(Some(annot), src);
        if spelled.split('[').next().unwrap_or("").trim() == "TypeAlias" {
            return true;
        }
    }
    let Some(rhs) = rhs else { return false };
    if rhs.kind() == "call" {
        if let Some(fn_node) = field(Some(rhs), "function") {
            if PY_TYPE_CTORS.contains(&text(Some(fn_node), src).as_str()) {
                return true;
            }
        }
    }
    is_type_expression(rhs, src)
}

/// An accumulator seed: `{}`, `[]`, or `set()` / `dict()` / `list()` with no elements.
fn is_empty_container(rhs: Option<Node>, src: &[u8]) -> bool {
    let Some(rhs) = rhs else { return false };
    match rhs.kind() {
        "dictionary" | "list" => !children(rhs).iter().any(|c| c.is_named()),
        "call" => {
            let Some(fn_node) = field(Some(rhs), "function") else { return false };
            if fn_node.kind() != "identifier"
                || !PY_CONTAINER_CTORS.contains(&text(Some(fn_node), src).as_str())
            {
                return false;
            }
            match field(Some(rhs), "arguments") {
                None => true,
                Some(args) => !children(args).iter().any(|c| c.is_named()),
            }
        }
        _ => false,
    }
}

/// The names in one Python file that count as module-level mutable state.
///
/// The binding name is read from the assignment's own `left` field, so string literals and
/// annotation tails are never scanned as source. Type aliases are skipped. An uppercase
/// name is a constant by convention, UNLESS it is seeded with an empty container, which is
/// an accumulator: `CACHE = {}` is the pattern this rule exists to catch.
pub fn module_mutable_names(root: Node, src: &[u8]) -> Vec<String> {
    let mut mutables: Vec<String> = Vec::new();
    for node in shallow_candidates(root) {
        // Subscripts, tuples and attributes are not a plain binding.
        let Some(left) = field(Some(node), "left") else { continue };
        if left.kind() != "identifier" {
            continue;
        }
        let name = text(Some(left), src);
        // Dunders are module metadata, not state.
        if PY_THIS_IDENTS.contains(&name.as_str())
            || (name.starts_with("__") && name.ends_with("__"))
        {
            continue;
        }
        let rhs = field(Some(node), "right");
        if is_type_alias(node, rhs, src) {
            continue;
        }
        let is_state = if name.chars().any(|c| c.is_alphabetic())
            && name.chars().filter(|c| c.is_alphabetic()).all(|c| c.is_uppercase())
        {
            is_empty_container(rhs, src)
        } else {
            true
        };
        if is_state && !mutables.contains(&name) {
            mutables.push(name);
        }
    }
    mutables
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser_for;

    fn mutables(source: &str) -> Vec<String> {
        let mut parser = parser_for("python");
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        module_mutable_names(tree.root_node(), &bytes)
    }

    #[test]
    fn a_lowercase_binding_is_state_whatever_it_holds() {
        assert_eq!(mutables("cache = {}\n"), vec!["cache"]);
        assert_eq!(mutables("counter = 0\n"), vec!["counter"]);
    }

    #[test]
    fn an_uppercase_name_is_a_constant_by_convention() {
        assert!(mutables("LIMIT = 5\n").is_empty());
        assert!(mutables("NAMES = ('a', 'b')\n").is_empty());
    }

    #[test]
    fn an_uppercase_name_seeded_with_an_empty_container_is_the_accumulator_this_catches() {
        // The convention says constant and the seed says otherwise, and the seed wins:
        // `CACHE = {}` is the pattern the whole indicator exists for.
        assert_eq!(mutables("CACHE = {}\n"), vec!["CACHE"]);
        assert_eq!(mutables("SEEN = set()\n"), vec!["SEEN"]);
        assert_eq!(mutables("ROWS = []\n"), vec!["ROWS"]);
    }

    #[test]
    fn an_uppercase_name_seeded_with_a_full_container_is_still_a_constant() {
        assert!(mutables("TABLE = {'a': 1}\n").is_empty());
        assert!(mutables("SEEN = set(('a',))\n").is_empty());
    }

    #[test]
    fn a_dunder_is_module_metadata_and_not_state() {
        assert!(mutables("__all__ = ['a']\n__version__ = '1.0'\n").is_empty());
    }

    #[test]
    fn a_type_alias_declares_a_type_rather_than_holding_a_value() {
        assert!(mutables("Reading = dict[str, object]\n").is_empty());
        assert!(mutables("Row = tuple\n").is_empty());
        assert!(mutables("Either = int | str\n").is_empty());
    }

    #[test]
    fn a_type_built_by_a_call_is_a_type_too() {
        // A type expression declines anything with a call in it, and this IS a call that
        // returns a type. The class form of the same declaration was never counted, so
        // one declaration read two ways depending on which syntax spelled it.
        assert!(mutables("Panel = TypedDict('Panel', {'a': int})\n").is_empty());
        assert!(mutables("UserId = NewType('UserId', int)\n").is_empty());
    }

    #[test]
    fn a_binding_annotated_as_a_type_alias_is_a_type() {
        assert!(mutables("Reading: TypeAlias = dict\n").is_empty());
    }

    #[test]
    fn a_subscript_target_is_not_a_binding() {
        // `d['k'] = 1` writes through a name; it does not declare one.
        assert!(mutables("d['k'] = 1\n").is_empty());
    }

    #[test]
    fn a_name_bound_inside_a_function_is_never_a_candidate() {
        assert!(mutables("def f():\n    cache = {}\n    return cache\n").is_empty());
    }

    #[test]
    fn the_candidate_list_carries_what_the_scan_declined() {
        // The whole reason this is a function of its own. Four bindings are walked and one
        // is judged state; the other three are READ, not missed, and only the candidate
        // list can say so.
        let source = "cache = {}\nLIMIT = 5\nReading = dict[str, int]\n__all__ = ['x']\n";
        let mut parser = parser_for("python");
        let bytes = source.as_bytes().to_vec();
        let tree = parser.parse(&bytes, None).expect("a parse");
        assert_eq!(shallow_candidates(tree.root_node()).len(), 4);
        assert_eq!(module_mutable_names(tree.root_node(), &bytes), vec!["cache"]);
    }
}
