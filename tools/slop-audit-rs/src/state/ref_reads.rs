//! How ONE reference to a piece of state reads, in nine grammars. Ported from
//! l1_analyzer.state_ref_reads.
//!
//! The false-positive filters argue about an attribute from the positions its references
//! occupy: a write, a presence test, a keyed read, a test expression. Those positions are
//! the same question in every language and a different set of node types in each, and the
//! reading was Python's node types written into the rules, which is why eight languages got
//! no filtering at all. This module is the reading, parameterised by the language table;
//! the rules are next door.
//!
//! Nothing here reaches a verdict or knows what a false positive is. Each function answers
//! one question about one node: is this reference a presence test, is the value it produces
//! thrown away, does this node name the attribute. The rules compose those answers.
//!
//! Three divergences cost more than the rest, and each has a function of its own here so no
//! rule has to know about them:
//!
//!   flat calls        Java and Ruby put receiver, method and arguments on ONE node, so a
//!                     predicate written as "parent is a member access, grandparent is a
//!                     call" reads them off by a level. `receiver_call` reconciles the two
//!                     shapes.
//!   presence tests    an operator in Python, JavaScript and TypeScript; a method in Java,
//!                     C#, Ruby and Rust; a BINDING in Go, whose `_, ok := d[k]` is neither.
//!   attribute naming  a member access, a bare identifier, or a sigil, depending on how the
//!                     language reaches its own state.
//!
//! C is present in every table and answers no to every presence question, which is the
//! truth about the language rather than a gap: C asks no membership question and grows no
//! container.

use crate::lang_spec::{lookup, spec_for, LangSpec};
use crate::nodes::{
    bare_condition, children, descendants, field, is_lvalue, same, sub_collection, text,
};
use crate::state::cells::MEMBERSHIP_TOKENS;
use std::collections::BTreeMap;
use std::path::Path;
use tree_sitter::Node;

/// The absent case for a test position. It is the empty string, which no written row holds,
/// so a miss is readable as a miss rather than as somebody's answer to a different input.
pub const NO_TEST_SLOT: &str = "";

/// A node's named children, which is what every positional rule below counts.
fn named_children<'t>(node: Node<'t>) -> Vec<Node<'t>> {
    children(node).into_iter().filter(|c| c.is_named()).collect()
}

// --- naming the attribute --------------------------------------------------------

/// Python, Rust, JavaScript, TypeScript and Go reach state through a receiver.
fn named_as_member(node: Node, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    sp.member_types.contains(&node.kind()) && text(field(Some(node), sp.mem_attr), src) == attr
}

/// The node IS the name, with nothing to strip off it.
///
/// Java, C# and C name a field bare inside its own scope, and Ruby's sigil is part of the
/// node's own text. Those are one rule reading two node types, so the type is an argument.
/// The reference spells them as two functions whose bodies differ in a single string; a
/// reader comparing them has to notice that string to learn that the languages agree.
fn named_bare(node: Node, attr: &str, node_type: &str, src: &[u8]) -> bool {
    node.kind() == node_type && text(Some(node), src) == attr
}

/// `node` denotes the attribute itself: `self.hits`, `this.hits`, `@hits`, `hits`, `s.hits`.
///
/// The style is read off the same two table keys the enumerator reads to FIND the
/// references, so the two cannot disagree about what a reference looks like.
///
/// A style no arm covers stops the run. Elsewhere in this port an unwritten language rule
/// answers `None` and the caller reports a refusal, because there the caller can say which
/// repository it could not read. Here the answer feeds a predicate several rules deep, and
/// `false` there would say "no reference names this attribute" in exactly the words a real
/// reading uses. The table is generated and checked against the reference, so no arm being
/// hit means the two have come apart, and that is worth stopping for.
pub fn names_the_attribute(node: Option<Node>, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(node) = node else { return false };
    let style = if sp.instance_enum == "ruby_ivar" { "ruby_ivar" } else { sp.instance_ref_style };
    match style {
        "member" => named_as_member(node, attr, sp, src),
        "identifier" => named_bare(node, attr, "identifier", src),
        "ruby_ivar" => named_bare(node, attr, "instance_variable", src),
        other => panic!("{} declares the reference style {other:?}, which nobody wrote", sp.key),
    }
}

// --- calls on the attribute, in flat and nested grammars -------------------------

/// The call whose RECEIVER this reference is: the `d.get(k)` node, given `d`. Nothing when
/// the reference is not a receiver.
///
/// Java and Ruby put receiver, method and arguments on ONE node, so the reference's own
/// parent is the call. The other seven nest a member access in between, and a predicate
/// written for one shape reads the other off by a level, which is the whole reason this is
/// a function and not four lines repeated in every predicate that needs it.
pub fn receiver_call<'t>(reference: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    let parent = reference.parent()?;
    if sp.flat_call {
        if sp.call_types.contains(&parent.kind())
            && same(field(Some(parent), sp.call_recv), Some(reference)) {
            return Some(parent);
        }
        return None;
    }
    if !sp.member_types.contains(&parent.kind())
        || !same(field(Some(parent), sp.mem_object), Some(reference)) {
        return None;
    }
    let gp = parent.parent()?;
    if sp.call_types.contains(&gp.kind()) && same(field(Some(gp), sp.call_fn), Some(parent)) {
        return Some(gp);
    }
    None
}

/// The receiver of a call: the inverse of `receiver_call`, for a walk that arrived at the
/// call first. Nothing when the call has no receiver at all, which is what a plain function
/// call is.
pub fn call_receiver<'t>(call: Option<Node<'t>>, sp: &LangSpec) -> Option<Node<'t>> {
    let call = call?;
    if !sp.call_types.contains(&call.kind()) {
        return None;
    }
    if sp.flat_call {
        return field(Some(call), sp.call_recv);
    }
    field(field(Some(call), sp.call_fn), sp.mem_object)
}

/// The bare method name of a call on a receiver, without the receiver text a flat grammar
/// would otherwise fold into it.
pub fn method_name(call: Node, sp: &LangSpec, src: &[u8]) -> String {
    if sp.flat_call {
        return match sp.call_name {
            Some(name_field) => text(field(Some(call), name_field), src),
            None => String::new(),
        };
    }
    text(field(field(Some(call), sp.call_fn), sp.mem_attr), src)
}

// honest-code-allow: L1.21.1 - result_discarded and is_deleted ask different questions of a
// parent node through different vocabulary keys, and each carries the reason its language
// can or cannot answer. Collapsing them would put both reasons on one function that answers
// neither
/// The call's result is thrown away. Java's `Map.put` and Rust's `HashMap::insert` return
/// the value previously stored at the key, so they write and nothing more only where nobody
/// reads the answer. Ruby declares no discard form, since every Ruby expression is a value
/// and only position decides whether anything reads it, so Ruby can never prove this, which
/// is an honest decline rather than a stretched one.
///
/// Takes the absence: the caller hands it a field lookup, and a call with nothing above it
/// cannot be shown to have its result thrown away.
pub fn result_discarded(call: Option<Node>, sp: &LangSpec) -> bool {
    let Some(call) = call else { return false };
    match call.parent() {
        Some(parent) => sp.discard_types.contains(&parent.kind()),
        None => false,
    }
}

// --- test positions --------------------------------------------------------------

/// The test sits in the branch node's declared condition field.
fn test_slot_field(parent: Node, child: Node, sp: &LangSpec) -> bool {
    same(field(Some(parent), sp.branch_cond), Some(child))
}

/// The test is the first named child: `assert <test>`.
fn test_slot_first(parent: Node, child: Node) -> bool {
    match named_children(parent).first() {
        Some(first) => same(Some(*first), Some(child)),
        None => false,
    }
}

/// The test is the second named child: Python's `a if <test> else b`, which carries no
/// condition field at all.
fn test_slot_second(parent: Node, child: Node) -> bool {
    match named_children(parent).get(1) {
        Some(second) => same(Some(*second), Some(child)),
        None => false,
    }
}

/// The test is held positionally, with no field naming it. Go's `for` is the only one in the
/// table: `for_statement` names `body` and nothing else, so asking for a condition field
/// there returns nothing however the node type is declared.
fn test_slot_bare(parent: Node, child: Node, sp: &LangSpec) -> bool {
    same(bare_condition(Some(parent), sp), Some(child))
}

/// How this construct holds its test, or `NO_TEST_SLOT`.
///
/// Branch and elif nodes read their declared condition field; every other construct has to
/// be declared in the extra test positions, so a construct nobody wrote a rule for is a miss
/// and not a row.
pub fn test_slot_of(parent: Node, sp: &LangSpec) -> &'static str {
    if let Some(slot) = lookup(sp.extra_test_positions, parent.kind()) {
        if slot != NO_TEST_SLOT {
            return slot;
        }
    }
    // Before the field reading, because a node in both tables holds its test positionally
    // and names no field: Go's for_statement is a branch type AND has only a `body`, so
    // falling through to "field" there asks for a condition that does not exist.
    if lookup(sp.bare_cond_types, parent.kind()).is_some() {
        return "bare";
    }
    if sp.branch_types.contains(&parent.kind()) || sp.elif_types.contains(&parent.kind()) {
        return "field";
    }
    NO_TEST_SLOT
}

/// True when `child` is the test part of `parent`: an if, while or elif condition, a ternary
/// condition, an assert test, or a comprehension guard.
///
/// A declared slot no arm covers stops the run, for the reason `names_the_attribute` gives.
pub fn is_condition_position(parent: Node, child: Node, sp: &LangSpec) -> bool {
    match test_slot_of(parent, sp) {
        NO_TEST_SLOT => false,
        "field" => test_slot_field(parent, child, sp),
        "first" => test_slot_first(parent, child),
        "second" => test_slot_second(parent, child),
        // The whole node is a test: a comprehension guard is nothing else.
        "all" => true,
        "bare" => test_slot_bare(parent, child, sp),
        other => panic!("{} declares the test slot {other:?}, which nobody wrote", sp.key),
    }
}

/// The reference sits inside a real test expression, nested to any depth
/// (`if self._cfg.enabled`, `if len(self._items) > 3`), stopping at the function boundary.
///
/// JavaScript and TypeScript wrap every condition in a parenthesized expression and C# in a
/// prefix unary expression, so a direct child comparison against the condition field would
/// never match. The walk carries the child up with it, which is what makes those wrappers
/// cost nothing.
pub fn in_test(reference: Node, sp: &LangSpec) -> bool {
    let mut current = reference;
    while let Some(parent) = current.parent() {
        if sp.func_types.contains(&parent.kind()) {
            return false;
        }
        if is_condition_position(parent, current, sp) {
            return true;
        }
        current = parent;
    }
    false
}

// --- presence tests: three spellings across the nine -----------------------------
//
// Python, JavaScript and TypeScript ask with an operator. Java, C#, Ruby and Rust have no
// membership operator and ask with a method. Go asks with a BINDING, `_, ok := d[k]`, which
// is neither, and whose value half goes to the blank identifier. All three read no stored
// value out, which is the property the accumulator rule turns on, so all three are one
// question spelled three ways rather than three questions.

/// Python: `k in d` is a comparison carrying an `in` or `not in` token, and the container is
/// its last named operand.
fn container_of_comparison_in(reference: Node, parent: Node) -> bool {
    if !children(parent).iter().any(|c| MEMBERSHIP_TOKENS.contains(&c.kind())) {
        return false;
    }
    match named_children(parent).last() {
        Some(last) => same(Some(*last), Some(reference)),
        None => false,
    }
}

/// JavaScript and TypeScript: `k in o` is a binary expression whose operator is `in`.
///
/// The operator is read by node type, because a keyword token's type is the keyword and
/// reading its text would mean carrying the source into every predicate here.
fn container_of_binary_in(reference: Node, parent: Node) -> bool {
    field(Some(parent), "operator").map(|op| op.kind()) == Some("in")
        && same(field(Some(parent), "right"), Some(reference))
}

/// `reference` is the container of a membership test written with an operator.
///
/// Java, C#, Ruby, Rust, Go and C have no membership operator, and their decline is
/// explicit: those six ask presence with a method or a binding, handled by the two
/// predicates below, and reading their comparison nodes as membership would be an invention.
pub fn is_membership_container(reference: Node, sp: &LangSpec) -> bool {
    let Some(parent) = reference.parent() else { return false };
    if !sp.comparison_types.contains(&parent.kind()) {
        return false;
    }
    match sp.membership {
        "comparison_in" => container_of_comparison_in(reference, parent),
        "binary_in" => container_of_binary_in(reference, parent),
        "none" => false,
        other => panic!("{} declares the membership form {other:?}, which nobody wrote", sp.key),
    }
}

/// `map.containsKey(k)`, `dict.ContainsKey(k)`, `@h.key?(k)`, `h.contains_key(&k)`: the
/// method answers whether the key is there and hands no stored value back.
pub fn is_presence_method_call(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    match receiver_call(reference, sp) {
        Some(call) => sp.presence_methods.contains(&method_name(call, sp, src).as_str()),
        None => false,
    }
}

/// The binding a keyed read feeds, when the language spells presence that way.
///
/// Go's `_, ok := d[k]` is a short variable declaration, which is NOT one of Go's assignment
/// types, so no other reader in the tree recognises it as anything. Nothing for the other
/// eight, which declare no presence binding types.
pub fn presence_binding<'t>(subscript: Node<'t>, sp: &LangSpec) -> Option<Node<'t>> {
    let mut holder = subscript.parent()?;
    let wrapper = sp.lvalue_wrapper;
    if !wrapper.is_empty() && holder.kind() == wrapper {
        let above = holder.parent()?;
        if !same(field(Some(above), sp.assign_right), Some(holder)) {
            return None;
        }
        holder = above;
    }
    if !sp.presence_bind_types.contains(&holder.kind()) {
        return None;
    }
    Some(holder)
}

/// The names a binding writes, unwrapping the language's lvalue wrapper.
pub fn binding_targets<'t>(bind: Node<'t>, sp: &LangSpec) -> Vec<Node<'t>> {
    let Some(left) = field(Some(bind), sp.assign_left) else { return Vec::new() };
    let wrapper = sp.lvalue_wrapper;
    if !wrapper.is_empty() && left.kind() == wrapper {
        named_children(left)
    } else {
        vec![left]
    }
}

/// Go's `_, ok := d[k]`. The keyed read's VALUE goes to the blank identifier and only the
/// presence flag is kept, so no stored value is read out. The other eight declare neither a
/// presence binding nor a blank identifier, and decline here.
pub fn is_comma_ok_presence(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(parent) = reference.parent() else { return false };
    if !sp.subscript_types.contains(&parent.kind()) {
        return false;
    }
    if !same(sub_collection(parent, sp), Some(reference)) {
        return false;
    }
    let Some(bind) = presence_binding(parent, sp) else { return false };
    let targets = binding_targets(bind, sp);
    targets.len() == 2 && sp.blank_idents.contains(&text(Some(targets[0]), src).as_str())
}

/// The reference is asked whether it holds a key, in whichever of the three forms this
/// language spells. Every form reads no stored value out, which is the whole of why they
/// answer as one.
pub fn is_presence_test(reference: Node, sp: &LangSpec, src: &[u8]) -> bool {
    is_membership_container(reference, sp)
        || is_presence_method_call(reference, sp, src)
        || is_comma_ok_presence(reference, sp, src)
}

// --- keyed reads and removals ----------------------------------------------------

/// `node` is the target of a key removal spelled as a STATEMENT. Only Python has one.
/// Everywhere else a removal is a call that hands the removed value back, or, in
/// JavaScript, a unary expression that collides with a wrapper already declared transparent,
/// so the eight declare no delete statement and decline here.
pub fn is_deleted(node: Node, sp: &LangSpec) -> bool {
    match node.parent() {
        Some(parent) => sp.delete_stmt_types.contains(&parent.kind()),
        None => false,
    }
}

/// `expr` is `self.attr[...]`: the stored value addressed by key.
pub fn is_keyed_read_of(expr: Option<Node>, attr: &str, sp: &LangSpec, src: &[u8]) -> bool {
    let Some(expr) = expr else { return false };
    if !sp.subscript_types.contains(&expr.kind()) {
        return false;
    }
    names_the_attribute(sub_collection(expr, sp), attr, sp, src)
}

/// The node that yields a value stored under a key, or nothing when the reference is not
/// such a read.
///
/// A store target is not a read: `d[k] = v`, `d[k] += 1` and `del d[k]` put a value in
/// rather than take one out. Neither is a presence test, which answers about the key and
/// never about what is stored under it.
pub fn keyed_value_read<'t>(reference: Node<'t>, sp: &LangSpec, src: &[u8]) -> Option<Node<'t>> {
    let parent = reference.parent()?;
    if sp.subscript_types.contains(&parent.kind())
        && same(sub_collection(parent, sp), Some(reference)) {
        if is_lvalue(Some(parent), sp) || is_deleted(parent, sp) {
            return None;
        }
        return Some(parent);
    }
    let call = receiver_call(reference, sp)?;
    let name = method_name(call, sp, src);
    if sp.keyed_read.contains(&name.as_str()) && !sp.presence_methods.contains(&name.as_str()) {
        return Some(call);
    }
    None
}

// --- the parity dump -------------------------------------------------------------

/// What every position predicate above answered about one node.
///
/// A row is emitted only where at least one of them fired. The alternative, a row per node,
/// buries the nine-language divergence this module exists to hold in a column of falses,
/// and the divergence is the only thing worth diffing.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Read {
    pub start: usize,
    pub end: usize,
    pub kind: String,
    /// The predicates that fired, sorted, so two implementations emit one order.
    pub flags: Vec<String>,
}

/// Everything the position predicates say about one parsed file.
pub fn file_reads(root: Node, sp: &LangSpec, src: &[u8]) -> Vec<Read> {
    let mut out = Vec::new();
    for node in descendants(root) {
        let mut flags: Vec<String> = Vec::new();
        if in_test(node, sp) {
            flags.push("in_test".into());
        }
        if is_membership_container(node, sp) {
            flags.push("membership".into());
        }
        if is_presence_method_call(node, sp, src) {
            flags.push("presence_method".into());
        }
        if is_comma_ok_presence(node, sp, src) {
            flags.push("comma_ok".into());
        }
        if is_deleted(node, sp) {
            flags.push("deleted".into());
        }
        if let Some(read) = keyed_value_read(node, sp, src) {
            flags.push(format!("keyed_read@{}", read.start_byte()));
        }
        if let Some(call) = receiver_call(node, sp) {
            flags.push(format!("call:{}", method_name(call, sp, src)));
            if result_discarded(Some(call), sp) {
                flags.push("discarded".into());
            }
        }
        if let Some(recv) = call_receiver(Some(node), sp) {
            flags.push(format!("recv@{}", recv.start_byte()));
        }
        if flags.is_empty() {
            continue;
        }
        flags.sort();
        out.push(Read {
            start: node.start_byte(),
            end: node.end_byte(),
            kind: node.kind().to_string(),
            flags,
        });
    }
    out
}

/// Every file in scope, read by the position predicates. Same scope and same files as the
/// census walk, so a scoping difference cannot masquerade as a reading difference.
pub fn walk(repo: &Path, lang: &str) -> BTreeMap<String, Vec<Read>> {
    let Some(sp) = spec_for(lang) else { return BTreeMap::new() };
    crate::state::census::parsed_files(repo, lang)
        .into_iter()
        .map(|(rel, tree, src)| (rel, file_reads(tree.root_node(), sp, &src)))
        .collect()
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

    fn first_of<'t>(tree: &'t tree_sitter::Tree, kind: &str) -> Node<'t> {
        descendants(tree.root_node()).into_iter().find(|n| n.kind() == kind)
            .unwrap_or_else(|| panic!("no {kind} in the fixture"))
    }

    // The three naming rules. The corpus harness compares the seven POSITION predicates
    // over nine languages, and it cannot reach these three: they take an attribute name,
    // and a dump over every node in a repository has none to give them. So they are proved
    // here instead, one fixture per style, which is the whole of their variation.

    #[test]
    fn a_receiver_language_names_its_attribute_through_the_receiver() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("self.hits += 1\n", "python");
        let member = first_of(&tree, "attribute");
        assert!(names_the_attribute(Some(member), "hits", sp, &src));
        assert!(!names_the_attribute(Some(member), "misses", sp, &src));
    }

    #[test]
    fn a_bare_field_language_names_its_attribute_with_no_receiver_at_all() {
        // Java reads `hits` inside its own class as the field. A member rule would want a
        // receiver here and find none, so the style is not cosmetic.
        let sp = spec_for("java").expect("java");
        let (tree, src) = parse("class C { int hits; void f() { hits++; } }", "java");
        let bare = descendants(tree.root_node()).into_iter()
            .filter(|n| n.kind() == "identifier" && text(Some(*n), &src) == "hits")
            .next_back().expect("the use, not the declaration");
        assert!(names_the_attribute(Some(bare), "hits", sp, &src));
    }

    #[test]
    fn ruby_reads_its_sigil_as_part_of_the_name_and_overrides_its_own_reference_style() {
        // Ruby declares the reference style "member" and the enumerator "ruby_ivar", and
        // the enumerator wins. Reading the style alone would look for a receiver that
        // `@hits` does not have, and no Ruby attribute would ever be named.
        let sp = spec_for("ruby").expect("ruby");
        assert_eq!(sp.instance_ref_style, "member");
        let (tree, src) = parse("def f\n  @hits += 1\nend\n", "ruby");
        let ivar = first_of(&tree, "instance_variable");
        assert!(names_the_attribute(Some(ivar), "@hits", sp, &src));
        assert!(!names_the_attribute(Some(ivar), "hits", sp, &src));
    }

    #[test]
    fn an_absent_node_names_no_attribute() {
        let sp = spec_for("python").expect("python");
        assert!(!names_the_attribute(None, "hits", sp, b""));
    }

    #[test]
    fn a_keyed_read_of_the_attribute_is_told_apart_from_a_keyed_read_of_something_else() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("x = self.cache[k]\n", "python");
        let sub = first_of(&tree, "subscript");
        assert!(is_keyed_read_of(Some(sub), "cache", sp, &src));
        assert!(!is_keyed_read_of(Some(sub), "store", sp, &src));
        // Not a subscript at all, and an absent node, both decline rather than reaching in.
        assert!(!is_keyed_read_of(Some(first_of(&tree, "attribute")), "cache", sp, &src));
        assert!(!is_keyed_read_of(None, "cache", sp, &src));
    }

    #[test]
    fn a_store_under_a_key_is_not_a_read_of_what_is_stored_there() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("self.cache[k] = v\n", "python");
        let collection = first_of(&tree, "attribute");
        assert_eq!(keyed_value_read(collection, sp, &src), None);
    }

    #[test]
    fn a_deletion_takes_no_value_out_either() {
        let sp = spec_for("python").expect("python");
        let (tree, src) = parse("del self.cache[k]\n", "python");
        let collection = first_of(&tree, "attribute");
        assert_eq!(keyed_value_read(collection, sp, &src), None);
    }
}
