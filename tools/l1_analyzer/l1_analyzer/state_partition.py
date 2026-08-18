"""What a finite verdict carries beside the word "finite": how many classes, and whether
limit testing can defeat them.

`_FINITE` used to be one label, so a partition of two classes and a partition of four
billion came out the same and the grade could not tell them apart. This module holds the
value a reference now yields (`Reach`), the per-state roll-up of those values
(`Partition`), and nothing else. It lives beside state_bounds rather than inside it
because state_bounds is within a hundred lines of the god-file gate this repository runs
against its own source, and a file that trips its own audit is not an argument for the
audit.

Two rules decide the shape here.

CARDINALITY ALONE IS THE WRONG TEST. Limit testing defeats large ordered domains: a 64-bit
integer compared against three constants induces four intervals, and boundary selection
covers them with a handful of values. What limit testing cannot defeat is a large
UNORDERED partition, because there is no value just above a string key. So every finite
reach records `ordered` beside `classes`, and the route to finiteness supplies it: a
comparison arm is ordered, a membership test against a closed set and a literal-keyed read
are not.

A COUNT WE CANNOT RECOVER IS SILENCE, NOT A FINDING. Some finite partitions have no count
the analyzer can reach - a frozenset built from a call we cannot read is provably closed
and of unknown size. `counted` carries that fact, and an uncounted partition is excluded
from the coarse test, because an unknown count is a limit of ours and D is a claim about
the audited code.

The roll-up ADDS discriminators and does not multiply. Two states that decide the same
branch multiply, and this version does not compose across states at all; within one state
it sums the distinct discriminators, which is a lower bound on the true partition. Both are
under-counts, and under-counting is the safe direction for a measure that only ever
accuses: it can miss a coarse partition, never invent one. Every report that quotes the
number says so.
"""

from __future__ import annotations

from typing import TypedDict

from tree_sitter import Node

from l1_analyzer.lang_spec import LangSpec
from l1_analyzer.ts_nodes import field as _field
from l1_analyzer.ts_nodes import first_named as _first_named
from l1_analyzer.ts_nodes import text as _text

# Why a reaching-set could not be decided. Silence is a fact about the ANALYZER, so the
# reasons name whose problem each one is. `S` handed to `sorted(...)` and `S` handed to a
# third-party workbook's save call are both undecided, and they are not the same fact: the
# first is a name we could model and have not, the second is a boundary only the adopter can
# make readable by putting an explicit contract at the edge. Reporting them as one number
# tells an adopter to go and fix our backlog.
EXTERNAL_BOUNDARY = "external_boundary"   # a call into code the analyzer cannot read
UNMODELED_CALLEE = "unmodeled_callee"     # a plain name we could model and have not
DYNAMIC_DISPATCH = "dynamic_dispatch"     # the call target is chosen while the program runs
INJECTED_SLOT = "injected_slot"           # an invoked slot whose compositional premise fails
UNMODELED_CONSTRUCT = "unmodeled_construct"   # a syntax shape no dispatch row covers
# The grammar handed the region back as tokens, so there is no shape to dispatch on. Rust's
# macro arguments are the case: `format!("{}", self.v.len())` parses to a flat token_tree
# that does not even keep the field name attached to `self`. It is kept apart from
# UNMODELED_CONSTRUCT because the two send the reader to different places - a construct is a
# dispatch row somebody can write, and this is not.
UNPARSED_REGION = "unparsed_region"
# The value was handed out under a name the walk cannot follow, so writes can arrive through
# an alias no rule about this state's own references will ever see. Rust's `&mut self.v` is
# the case in the table.
MUTABLE_ALIAS = "mutable_alias"

# The three verdicts a finding can carry. They live here rather than in state_bounds
# because state_const reaches one of them too, and a second definition of a verdict name
# is the drift this table exists to stop.
NEUTRAL = "neutral"
PROMISCUOUS = "promiscuous"
UNRESOLVED = "unresolved"
SILENCE_REASONS = (EXTERNAL_BOUNDARY, UNMODELED_CALLEE, DYNAMIC_DISPATCH, INJECTED_SLOT,
                   UNMODELED_CONSTRUCT, UNPARSED_REGION, MUTABLE_ALIAS)

WRITE = "write"            # target of an assignment / mutating method: not a decision
OUTPUT = "output"          # returned or handed to the caller: compositional
FINITE = "finite"          # reaches a decision whose reaching partition is enumerable
UNBOUNDED = "unbounded"    # reaches a decision whose reaching partition is provably unbounded
UNDECIDED = "undecided"    # reaches a context whose reaching-set cannot be decided


class Reach(TypedDict):
    """How ONE reference to a state value is consumed, and what it does to the domain.

    `key` identifies the discriminator rather than the site, so the same split written in
    two places counts once: `if S:` in fifty methods is one two-class split, not fifty."""
    kind: str
    classes: int      # equivalence classes this discriminator induces (0 unless FINITE)
    ordered: bool     # True when boundary values cover the split
    counted: bool     # False when the class count could not be recovered
    key: str          # identity of the discriminator, for de-duplication
    silence: str      # why undecided; empty on every decided reach
    construct: str    # the syntax shape no row covered; empty on every reach a row decided


class Partition(TypedDict):
    """The reaching partition of one piece of state, rolled up from its references."""
    classes: int      # 0 when counted is False, because there is no number to report
    ordered: bool
    counted: bool


def write() -> Reach:
    return {"kind": WRITE, "classes": 0, "ordered": True, "counted": True, "key": "",
            "silence": "", "construct": ""}


def output() -> Reach:
    return {"kind": OUTPUT, "classes": 0, "ordered": True, "counted": True, "key": "",
            "silence": "", "construct": ""}


def unbounded() -> Reach:
    return {"kind": UNBOUNDED, "classes": 0, "ordered": False, "counted": True, "key": "",
            "silence": "", "construct": ""}


def undecided(reason: str) -> Reach:
    return {"kind": UNDECIDED, "classes": 0, "ordered": True, "counted": True, "key": "",
            "silence": reason, "construct": ""}


def unmeasured(node_type: str, parent_type: str) -> Reach:
    """The total row of the categoriser's table: this construct has no rule, so nothing is
    concluded about it.

    It exists because a table with a fallthrough cannot tell "no rule applies" apart from
    "the compositional rule applies". The classifier used to run off the bottom of
    `_categorize` into `_flow`, and off the bottom of `_flow` into `output()` - and
    `output()` is a VERDICT. It says the value is handed to the caller, reaches no decision
    and costs no tests. So a walrus in a condition, a `match` subject and a comprehension
    source were not left unhandled, they were cleared, and the finding read to an adopter as
    evidence that the code was fine. Measured across eleven repositories before this row
    existed, that terminal decided 55 percent of every reference the classifier read.

    Two properties make it a rule rather than a hole. It is reached only when every row
    above it has declined, so an unhandled construct comes out unmeasured by construction
    rather than by whoever remembered to check. And it is handed two node-type strings, so
    no tree, no language spec and no closed-set table are in scope: no verdict is reachable
    from what it holds, which is the apophatic rule applied at the dispatch instead of at
    the renderer.

    The silence is OURS. A construct nobody taught the reader is the same class of fact as a
    callee nobody modeled, so it reports under its own reason beside UNMODELED_CALLEE and
    not under the adopter's boundary, and `construct` carries the shape so the backlog can
    be read off the report and worked down."""
    return {"kind": UNDECIDED, "classes": 0, "ordered": True, "counted": True, "key": "",
            "silence": UNMODELED_CONSTRUCT, "construct": f"{node_type} in {parent_type}"}


def finite(classes: int, ordered: bool, key: str) -> Reach:
    return {"kind": FINITE, "classes": classes, "ordered": ordered, "counted": True,
            "key": key, "silence": "", "construct": ""}


def uncounted(key: str) -> Reach:
    """Provably finite, count unrecoverable. Ordered is False because we cannot show it is
    ordered, and claiming order we have not established would be the optimistic direction."""
    return {"kind": FINITE, "classes": 0, "ordered": False, "counted": False, "key": key,
            "silence": "", "construct": ""}


# A state with no finite reach at all is observe-only or output-only: its reaching set is
# empty, which is one class (every value behaves alike), not zero.
EMPTY: Partition = {"classes": 1, "ordered": True, "counted": True}
UNKNOWN: Partition = {"classes": 0, "ordered": False, "counted": False}


def roll_up(reaches: list[Reach]) -> Partition:
    """The reaching partition of one state, from its per-reference reaches.

    De-duplicated by discriminator, then summed: each distinct discriminator cuts one more
    class out of the domain, so n of them leave n+1 classes. Ordered survives only if every
    discriminator is ordered, since one unordered split is enough to defeat boundary
    selection over the whole domain."""
    by_key = {r["key"]: r for r in reaches if r["kind"] == FINITE}
    if not by_key:
        return EMPTY
    discriminators = list(by_key.values())
    if not all(d["counted"] for d in discriminators):
        return UNKNOWN
    return {"classes": 1 + sum(d["classes"] - 1 for d in discriminators),
            "ordered": all(d["ordered"] for d in discriminators),
            "counted": True}


def is_coarse(partition: Partition, drives_decision: bool, bound: int) -> bool:
    """The positive finding D now carries: finite, unordered, and over the bound.

    `drives_decision` is required because a partition that reaches no decision costs no
    tests at all, however many classes its domain would have had."""
    return (drives_decision and partition["counted"]
            and not partition["ordered"] and partition["classes"] > bound)


# --------------------------------------------------------------------------
# Roll-ups over a whole repository's findings. Pure mappings over the finding dicts, so
# they carry no tree-sitter knowledge and sit here rather than in the classifier.
# --------------------------------------------------------------------------

def silence_summary(findings: list[dict], total: int) -> dict[str, object]:
    """The silence index: the share of state the analyzer could not decide, and every site.

    This is reported BESIDE the grade and never inside it. A state we did not decide is not
    evidence about the audited code, so counting it as a defect reports our own blind spot
    as their fault, which is the failure this measure exists to stop. Sites are listed in
    full rather than capped, because the reader's next move is to open each one and decide
    whether to make that boundary readable, and a sampled list cannot support that.

    `by_reason` always carries every reason key, so a consumer reading a zero knows the
    analyzer looked and found none, rather than guessing whether the key was omitted."""
    silent = [f for f in findings if f["silence"]]
    by_reason = {reason: 0 for reason in SILENCE_REASONS}
    for f in silent:
        by_reason[f["silence"]] += 1
    return {
        "count": len(silent),
        # 0.0 over zero state is vacuously true and deliberately kept: no state means
        # nothing went unread. vacuity.check flags this line as a fabricated affirmative
        # and it is a FALSE POSITIVE, because the failure it guards against, a repository
        # the classifier never read, is caught by the census rather than here. Replacing
        # the constant with None on 2026-08-18 broke three census tests that say exactly
        # that, and the revert is the answer to the finding rather than a workaround.
        "fraction": round(len(silent) / total, 3) if total else 0.0,
        "by_reason": by_reason,
        # `construct` is empty on every reason but UNMODELED_CONSTRUCT, and on that one it
        # names the syntax shape no dispatch row covered. Without it the reader is told a
        # rule is missing and not which one, which is a complaint rather than a backlog.
        # `line` is the SILENT REFERENCE's line, not the state's binding line. The two are
        # usually different, and publishing the binding line here named a shape at a line
        # that does not hold it, which makes the backlog this list exists to be unworkable.
        # The finding keeps the binding line, because that is the right answer about the
        # state; only the site, which is about one reference, follows the reference.
        "sites": [{"file": f["file"], "line": f.get("silence_line") or f["line"], "state": f["state"],
                   "reason": f["silence"], "construct": f["construct"]}
                  for f in silent],
    }


def partition_summary(findings: list[dict]) -> dict[str, object]:
    """The cardinality distribution over state that decides something, plus the count of
    partitions whose size could not be recovered.

    `unordered_classes` is published as the raw list rather than a summary statistic,
    because the bound that turns a cardinality into a grade has to be set from a
    distribution, and a mean cannot answer where real code sits."""
    deciding = [f for f in findings if f["verdict"] == "neutral" and f["drives_decision"]]
    counted = [f for f in deciding if f["partition"]["counted"]]
    return {
        "deciding_states": len(deciding),
        "uncounted": len(deciding) - len(counted),
        "ordered_classes": sorted(f["partition"]["classes"] for f in counted if f["partition"]["ordered"]),
        "unordered_classes": sorted(f["partition"]["classes"] for f in counted if not f["partition"]["ordered"]),
    }


# ------------------------------------------------------------------------
# Reference-level reads. These need a parse tree, which is why they take LangSpec and
# Node; they sit here rather than in the classifier because every one of them answers
# 'how wide is this split, and is it ordered', which is what this module is about.
# ------------------------------------------------------------------------

# Literal node types whose values are ordered, across the nine grammars. A map read by
# `S[0]`, `S[1]`, `S[2]` splits an ordered index domain, which boundary values cover; a map
# read by `S["alpha"]`, `S["beta"]` does not, because no string sits just above another.
# The two are the same node shape and only the literal tells them apart.
ORDERED_LITERALS = frozenset({
    "integer", "float", "number", "decimal_integer_literal", "decimal_floating_point_literal",
    "integer_literal", "float_literal", "real_literal", "number_literal", "hex_integer_literal",
})


def literal_size(node: Node | None) -> int | None:
    """How many members a fixed collection has, or None when it cannot be counted.

    A collection literal is counted by its elements. A wrapper call is counted through its
    argument, so `frozenset(("a", "b"))` is two; `frozenset(config.load())` is closed and
    of unknown size, which is a count we do not have rather than a size of zero. The
    difference decides whether the state can ever be D, so it is never guessed."""
    if node is None:
        return None
    if node.type in ("set", "tuple", "list"):
        return len([c for c in node.children if c.is_named])
    if node.type == "call" and _text(_field(node, "function")) in ("frozenset", "set", "tuple"):
        args = _field(node, "arguments")
        return literal_size(_first_named(args)) if args is not None else 0
    return None


def closed_set_size(node: Node, closed_sets: dict[str, int | None]) -> int | None:
    """Member count of a node `_is_closed_set` already accepted, or None when unknown."""
    if node.type == "identifier":
        return closed_sets.get(_text(node))
    if node.type == "attribute":
        return closed_sets.get(_text(_field(node, "attribute")))
    return literal_size(node)


def membership_reach(container: Node, closed_sets: dict[str, int | None]) -> Reach:
    """`S in FIXED`: which member S equals, or none of them - k+1 classes with nothing
    ordering them. When the container's size is unrecoverable the partition is still finite,
    so the verdict stands; only the count is silent."""
    size = closed_set_size(container, closed_sets)
    key = f"set:{_text(container)}"
    return uncounted(key) if size is None else finite(size + 1, False, key)


def silence_kind(call: Node | None, sp: LangSpec) -> Reach:
    """The category for a call whose reaching-set the analyzer cannot decide, carrying
    which KIND of silence it is (see the reason constants above).

    The test is where the callee comes from. A bare name is inside our reach: it is a
    builtin missing from the lists, or a function defined in the repository, and either
    way the fix is ours. A name reached through another object is a boundary we cannot
    read, except when that object is the receiver of the class under analysis, whose
    methods are in scope by the spec's own scoping rule. A callee that is not a name at
    all is computed, so nobody can enumerate it by reading."""
    if call is None:
        return undecided(DYNAMIC_DISPATCH)
    if sp["flat_call"]:
        receiver = _field(call, sp["call_recv"])
        return undecided(EXTERNAL_BOUNDARY if receiver is not None else UNMODELED_CALLEE)
    fn = _field(call, sp["call_fn"])
    if fn is None:
        return undecided(DYNAMIC_DISPATCH)
    if fn.type in sp["member_types"]:
        obj = _field(fn, sp["mem_object"])
        ours = obj is not None and _text(obj) in sp["this_idents"]
        return undecided(UNMODELED_CALLEE if ours else EXTERNAL_BOUNDARY)
    if fn.type == "identifier":
        return undecided(UNMODELED_CALLEE)
    return undecided(DYNAMIC_DISPATCH)
