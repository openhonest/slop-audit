"""
L1.18b - finite-testability classifier (gated, additive refinement of L1.18).

Implements the shared predicate in
~/dev/honest/open-honest/honest-framework/specs/finite-testability.md:

  A piece of state is testability-neutral iff the production decisions reaching it
  partition its domain into a statically-enumerable finite set of equivalence
  classes. PARTITION-COUNT, not value-count: an int that only meets comparisons
  against constants is cheap; a value used as an unbounded lookup key is not.

Every piece of state resolves to exactly one of three verdicts, and to whether it
drives a decision, so the coverage matrix (spec section 7) can be published:

  NEUTRAL     - reaching partition is a statically-enumerable finite set (or empty)
  PROMISCUOUS - reaching partition is provably unbounded (a proven finding)
  UNRESOLVED  - reaching-set undecidable within scope; fail-closed, disclosed

Design guarantees:
  - Additive. Never touches L1.18's value/band. Runs only when the caller opts in
    (classify_state_bounds=True), off for the pre-registered experiments.
  - Analysis scope is the class or module, not the function (spec section 4):
    instance state is analysed across all methods of its class.
  - Returns are output, not promiscuity. Fail-close (UNRESOLVED) only on a value
    passed to an unbounded call target or reflective/dynamic access.

The predicate is language-neutral; the AST node types that express it are not. A
per-language LANG_SPEC maps the shared vocabulary (assignment, subscript, member
access, membership, dynamic dispatch) onto each grammar's node types, so the same
partition-count reasoning runs over Python, TypeScript, Java and C#. Immutable-
constant and closed-set recognition (frozenset / MappingProxyType machines) remain
Python-only refinements; the other languages simply resolve fewer states to NEUTRAL
by that route, which is conservative (never a false green). Languages with no spec
return n/a rather than guess.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from tree_sitter import Node

from l1_analyzer import (
    record_state,
    state_bounds_filters,
    state_census,
    state_enum,
    state_partition,
)
from l1_analyzer.indicators import (
    LANG_CFG,
    LangCfg,
    _read_source_bytes,
    bucketed_paths,
    parser_for,
)
from l1_analyzer.lang_spec import LANG_SPEC, LangSpec
from l1_analyzer.scope import PRODUCTION_WITHOUT_CONFORMANCE
from l1_analyzer.state_cells import collect_closed_sets as _collect_closed_sets
from l1_analyzer.state_cells import write_key_bound as _write_key_bound
from l1_analyzer.state_const import collect_immutable_ctors as _collect_immutable_ctors
from l1_analyzer.state_const import declared_constant as _declared_constant
from l1_analyzer.state_const import immutable_const_verdict as _immutable_const_verdict
from l1_analyzer.state_partition import (
    INJECTED_SLOT,
    NEUTRAL,
    PROMISCUOUS,
    UNRESOLVED,
    Partition,
)
from l1_analyzer.state_reach import (
    _REACH_DEPTH,
    _categorize,
    _injected_slot_premise_fails,
    _verdict,
)
from l1_analyzer.state_reading import (
    FileRead,
    StateReading,
)
from l1_analyzer.state_refs import bound_to as _bound_to
from l1_analyzer.state_sites import Site
from l1_analyzer.ts_nodes import hidden_names as _hidden_names
from l1_analyzer.ts_nodes import is_lvalue as _is_lvalue
from l1_analyzer.ts_nodes import local_refs as _local_refs
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import text as _text

# Comparison operators: a state value meeting one is split into finitely many classes. The
# set moved to lang_spec so state_bounds_filters can read the same one; the name stays here
# so every call site below reads as it did.


class Finding(TypedDict):
    """One piece of state and its verdict. Fixed keys, so a TypedDict, not a bag.

    `silence` carries why the reaching-set could not be decided, and is the empty string
    on every decided finding. It is on the finding rather than in a parallel list because
    a silent site and its verdict are one fact, and two lists drift. `construct` names the
    syntax shape when the reason is that no dispatch row covered it, and is empty for every
    other reason: a missing rule the reader cannot name is a complaint, not a backlog."""
    state: str
    verdict: str
    drives_decision: bool
    file: str
    line: int
    silence: str
    # The line the silence sits on, written at both sites and never declared. A type checker
    # had never run over this package, so nothing said the record and the code disagreed.
    silence_line: int
    construct: str
    partition: Partition




# --------------------------------------------------------------------------
# Closed-set detection (Python only). Membership `x in S` is a finite partition
# when S is a statically fixed collection. Element *values* are irrelevant to the
# count: a tuple of symbolic constants bounds the partition exactly as literals do.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Membership and comparison helpers.
# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
# Per-reference categorisation.
# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
# State enumeration and file analysis.
# --------------------------------------------------------------------------

# Node types whose subtree is a module path rather than a value: `from app.auth import X`
# names a package, not the variable `app` defined below it. Matching on identifier text
# alone made the two the same state.
def _state_refs(scope: Node, key: str, sp: LangSpec) -> list[Node]:
    stop = sp["class_types"]
    if sp["instance_enum"] == "ruby_ivar":
        return _local_refs(scope, lambda n: n.type == "instance_variable" and _text(n) == key, stop)
    if sp["instance_ref_style"] == "member":
        return _local_refs(scope, lambda n: n.type in sp["member_types"] and _text(n) == key, stop)
    hits = _local_refs(scope, lambda n: n.type == "identifier" and _text(n) == key, stop)
    return _bound_to(hits, key, sp)


# --- immutable-constant recognition (Python only) ---------------------------
# A state key assigned once from an immutable construction, never mutated and never
# called, has a one-value domain: it is a constant, NEUTRAL wherever it flows,
# because no callee can mutate an immutable value. A one-level follow of the
# constructor tells the meter its return is immutable, so a declared machine (a
# MappingProxyType-wrapped table passed to a lookup) resolves on the evidence,
# reading no framework declaration.

def _binding_line(refs: list[Node], sp: LangSpec) -> int:
    """The line where the state is BOUND, not the first line its name appears on.

    The earliest reference is the wrong answer and it sends a reader to the wrong place.
    A module named `app` makes `from app.auth import X` on line 2 the first textual
    occurrence of the name, so a finding about the variable `app = FastAPI()` on line 4
    was reported against an import statement that binds nothing. On the repository that
    surfaced this, the reader was sent to line 19 for an object defined on line 113.

    So prefer the earliest reference that is an assignment target, using the same
    `_is_lvalue` the classifier already uses to decide what a write is. Falling back to
    the earliest reference keeps a line for state that is never assigned in this file,
    which is the case for an injected or inherited name.

    This changes no verdict and no count. It changes only where the reader is sent, which
    is the whole value of a finding they are meant to act on."""
    bindings = [r.start_point[0] + 1 for r in refs if _is_lvalue(r, sp)]
    if bindings:
        return min(bindings)
    return min((r.start_point[0] + 1 for r in refs), default=1)


def _finding(key: str, refs: list[Node], rel: str, sp: LangSpec, closed_sets: dict[str, int | None], immutable_ctors: set[str], instance: bool, hidden: frozenset[str]) -> Finding:
    # A state the language DECLARES immutable is settled before any reach is read: one
    # value, one class. This row replaced a `sp is LANG_SPEC["python"]` identity check,
    # which is the language conditional welded into shared code that this project objects
    # to elsewhere; the modifiers are a table row now and eight more languages get the rule.
    if _declared_constant(refs, sp):
        # EMPTY, the same partition the immutable-constant branch below writes. It built a
        # per-reference REACH here, which is what ONE reference does to the domain, where
        # this field holds the rolled-up partition of all of them. A reach carries the
        # partition's three fields and four more, so it fitted at run time and told the
        # summary that every declared constant was UNORDERED. That is the distribution the
        # coarseness bound is meant to be set from, and a one-value domain has nothing to
        # order either way.
        verdict, drives, silence, construct, partition, silence_line = (
            NEUTRAL, False, "", "", state_partition.EMPTY, 0)
        return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel,
                "line": _binding_line(refs, sp), "silence": silence, "construct": construct,
                "silence_line": silence_line, "partition": partition}
    const = _immutable_const_verdict(refs, immutable_ctors, sp) if sp["immutable_ctor_rule"] else None
    if const is not None:
        # An immutable constant has a one-value domain, so its partition is one class.
        verdict, drives, silence, construct, partition, silence_line = (*const, "", "", state_partition.EMPTY, 0)
    else:
        # Computed ONCE over every reference and handed to each, because the bound is a
        # fact about the state and not about the reference being judged. Per-reference
        # judgement is what let a read report unbounded while the writes it reads from
        # could only ever fill two cells.
        cells = _write_key_bound(refs, sp, closed_sets)
        verdict, drives, silence, construct, partition, silence_line = _verdict(
            # The recursion budget, stated where the recursion starts. It used to be a
            # default on `_categorize` itself, so the one caller that sets it and the many
            # recursive calls that spend it looked identical at the call site.
            [_categorize(r, sp, closed_sets, cells, _REACH_DEPTH) for r in refs], refs)
        # An invoked slot earns NEUTRAL from the compositional rule; that rule has premises.
        if verdict == NEUTRAL and _injected_slot_premise_fails(refs, sp, instance):
            verdict, drives, silence, construct, partition, silence_line = (
                UNRESOLVED, True, INJECTED_SLOT, "", state_partition.UNKNOWN, 0)
    # Attribute-level false-positive filter: the per-reference verdict conflates unbounded
    # data with an unbounded decision. Clear a finding to NEUTRAL only when the attribute is
    # a provable write-once, memoization cache, carried-value or write-only-accumulator
    # shape. The filter is handed the spec and decides for itself which of its rules this
    # language can carry - the accumulator rule serves all nine, the other three are still
    # Python-only - so the language gate lives with the rules rather than at the call site,
    # where it used to withhold every rule from eight languages without saying so.
    if verdict != NEUTRAL and state_bounds_filters.is_false_positive(key, refs, verdict, sp):
        verdict, drives, silence, construct, partition, silence_line = NEUTRAL, False, "", "", state_partition.EMPTY, 0
    # THE READING WAS INCOMPLETE, and this is the last word on the finding for that reason.
    # `hidden` holds the names that appear inside a region the grammar handed back as tokens,
    # so a reference in one of them was never built and no walk above could have reached it.
    # Every line above ran on the references that WERE built, which is a proper subset, and a
    # verdict from a subset - most of all a NEUTRAL one a filter just cleared - would report
    # what was not looked at as what was read and found clean. It sits after the filter
    # rather than before it so that no rule can clear it back.
    if key.rsplit(".", 1)[-1] in hidden:
        verdict, drives, silence, construct, partition, silence_line = (
            UNRESOLVED, True, state_partition.UNPARSED_REGION, "", state_partition.UNKNOWN, 0)
    return {"state": key, "verdict": verdict, "drives_decision": drives, "file": rel,
            "line": _binding_line(refs, sp), "silence": silence, "construct": construct,
            # The reference the construct was read off, so the silence site can send the
            # reader to the shape it names rather than to where the state was bound.
            "silence_line": silence_line,
            "partition": partition}


def _named(name: str) -> Callable[[Node], bool]:
    """A test for identifiers spelling one name.

    A named function rather than a lambda with a default parameter standing in for a
    binding. The loop rebinds the name every turn and a captured one would test every state
    against the last, which is a real reason spelled as a trick: nothing could say what the
    default was."""
    def spells_it(node: Node) -> bool:
        return node.type == "identifier" and _text(node) == name
    return spells_it


def _analyze_file(root: Node, rel: str, sp: LangSpec, cfg: LangCfg, immutable_ctors: set[str]) -> FileRead:
    # An empty TABLE, not an empty set. The parameter is declared eight times over as a
    # mapping of name to bound and three readers call `.get` on it; a set has none. It never
    # raised, because the predicate gating each of those reads asks `name in closed_sets`
    # first and an empty set answers no to everything, so the wrong shape was reachable only
    # through a gate the wrong shape happened to close.
    closed_sets = _collect_closed_sets(root) if sp["closed_set_rule"] else {}
    findings: list[Finding] = []
    visited: set[Site] = set()
    judged: set[Site] = set()
    # The names sitting inside regions this grammar left unparsed, for the whole file. Read
    # once and handed to every finding, because a macro in one function can name a field of
    # another and a module static alike, and because a language that parses everything gets
    # the empty set here without a walk.
    hidden = _hidden_names(root, sp)

    module = state_enum.module_cands(root, sp, cfg)
    visited |= set(module)
    for name in state_enum.keys_of(module):
        refs = _bound_to(_refs(root, _named(name)), name, sp)
        if refs:
            findings.append(_finding(name, refs, rel, sp, closed_sets, immutable_ctors,
                                     instance=False, hidden=hidden))
            judged |= state_enum.sites_of(module, name)

    if sp["scope_by_receiver"]:    # Go: state spans methods, grouped by receiver type
        for slot in state_enum.go_slots(root):
            findings.append(_finding(slot["state"], slot["refs"], rel, sp, closed_sets,
                                     immutable_ctors, instance=slot["writers_enumerable"],
                                     hidden=hidden))
            visited.add(slot["site"])
            judged.add(slot["site"])

    for cls in _refs(root, lambda n: n.type in sp["class_types"]):
        cands = state_enum.instance_cands(cls, sp)
        visited |= set(cands)
        for key in state_enum.keys_of(cands):
            refs = _state_refs(cls, key, sp)
            if refs:
                findings.append(_finding(key, refs, rel, sp, closed_sets, immutable_ctors,
                                         instance=True, hidden=hidden))
                judged |= state_enum.sites_of(cands, key)

    # State declared inside a record, which neither enumerator above can reach: both work
    # from a reference, and a slot declared once and thereafter only used is spelled one way
    # at its declaration and another at every use. record_state owns both halves, and it is
    # handed the keys already claimed for a record so it can stand down instead of reporting
    # the same slot twice (see its module docstring).
    read = record_state.slots(root, sp, lambda cls: state_enum.instance_keys(cls, sp))
    visited |= set(read["visited"])
    for slot in read["slots"]:
        findings.append(_finding(slot["state"], slot["refs"], rel, sp, closed_sets,
                                 immutable_ctors, instance=slot["writers_enumerable"],
                                 hidden=hidden))
        judged.add(slot["site"])

    return {"findings": findings, "visited": visited, "judged": judged}


# object, not Any: the verdict payload mixes strings, counts, nested dicts and a findings
# list, so no single value type fits. `object` still forces a caller to narrow before use,
# which is the property Any throws away. Same argument as thread_surface's scan result.
def _na(lang: str) -> StateReading:
    """The reading for a language this classifier has no spec for.

    `resolvable_fraction` is absent rather than "n/a": a reading that did not happen has no
    fraction, and a string in a number's field made the one question a reader asks first
    into a type check."""
    return {
        "verdict": "n/a", "value": "n/a", "band": "n/a",
        "counts": {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0},
        "coverage": {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)},
        "silence": state_partition.silence_summary([], 0),
        "partition": state_partition.partition_summary([]),
        # `declared: None`, not 0. A language with no spec was not counted, and a confident
        # zero here would report "there is no state" for a repository nobody read. The two
        # coverage fractions are None for the same reason: no denominator exists to divide by.
        "census": state_census.uncounted(0),
        "findings": [],
        "bucketed": {"counts": {}, "paths": []},
        "details": f"finite-testability classifier has no spec for {lang} yet",
    }


def classify(repo: Path, lang: str) -> StateReading:
    """L1.18b: the finite-testability verdict distribution.

    Additive as a PANEL ENTRY: nothing reads this function's return value except the
    report. Its per-file machinery is another matter. Since 2026-08-15 L1.18 calls
    `_analyze_file` directly for its bound-awareness correction, so this module's
    verdicts now decide part of L1.18's number and the two can no longer be changed
    independently. A change to `_categorize`, `_verdict` or the partition roll-up moves
    both indicators, and the amendment record for either has to say so."""
    if lang not in LANG_SPEC:
        return _na(lang)
    sp = LANG_SPEC[lang]
    cfg = LANG_CFG[lang]
    # conformance/ holds law/spec scaffolding and test doubles (fault-injection
    # markers, failing connections), not production state; skip it like tests. docs,
    # tooling, and loose entry-point scripts are scoped out by _read_source_bytes and
    # disclosed below (never a silent skip).
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION_WITHOUT_CONFORMANCE)
    bucketed = bucketed_paths(repo, cfg["extensions"], PRODUCTION_WITHOUT_CONFORMANCE)

    # First pass: parse every file and collect the repo's immutable constructors
    # (functions whose returns are all immutable), so a constant built by one can be
    # resolved by a one-level follow. Second pass: analyze with that knowledge.
    roots: list[tuple[Node, str]] = []
    for path, src in files:
        rel = str(path.relative_to(repo)) if (repo in path.parents or path == repo) else str(path)
        roots.append((parser_for(path.suffix, lang).parse(src).root_node, rel))
    immutable_ctors: set[str] = set()
    if sp is LANG_SPEC["python"]:
        for root, _rel in roots:
            immutable_ctors |= _collect_immutable_ctors(root)

    findings: list[Finding] = []
    # The visit record, per file, in the census's site vocabulary. It is collected here rather
    # than re-derived later because only the enumerators know where they went: a second walk
    # written to work out where the first one probably looked is a guess wearing a
    # measurement's name, which is the defect this number replaced.
    visited: dict[str, set[Site]] = {}
    judged: dict[str, set[Site]] = {}
    for root, rel in roots:
        read = _analyze_file(root, rel, sp, cfg, immutable_ctors)
        findings.extend(read["findings"])
        visited[rel] = read["visited"]
        judged[rel] = read["judged"]

    counts = {NEUTRAL: 0, PROMISCUOUS: 0, UNRESOLVED: 0}
    coverage = {v: {"observe_only": 0, "drives_decision": 0} for v in (NEUTRAL, PROMISCUOUS, UNRESOLVED)}
    for f in findings:
        counts[f["verdict"]] += 1
        coverage[f["verdict"]]["drives_decision" if f["drives_decision"] else "observe_only"] += 1

    total = sum(counts.values())
    if counts[PROMISCUOUS]:
        verdict = PROMISCUOUS
    elif counts[UNRESOLVED]:
        verdict = UNRESOLVED
    elif total:
        verdict = NEUTRAL
    else:
        verdict = "n/a"
    # 1.0 over zero state is deliberate and load-bearing: a codebase with no mutable
    # state by design IS fully resolved, and report._meter_ran reads a numeric value here
    # as the signal that the meter ran at all. vacuity.check flags it as a fabricated
    # affirmative and it is a FALSE POSITIVE for the same reason as the silence fraction:
    # the "read nothing" failure is the census's job, not this line's.
    resolvable = round((counts[NEUTRAL] + counts[PROMISCUOUS]) / total, 3) if total else 1.0

    _order = {PROMISCUOUS: 0, UNRESOLVED: 1, NEUTRAL: 2}
    findings.sort(key=lambda f: (_order[f["verdict"]], not f["drives_decision"], f["file"], f["line"]))
    silence = state_partition.silence_summary(findings, total)
    partition = state_partition.partition_summary(findings)

    # The independent denominator. Every number above this line - the counts, the resolvable
    # fraction, the silence index, the partition summary - is computed over the state THIS
    # function recognized, and no measure over the enumerated set can see non-enumeration.
    # The census counts state-bearing declarations from the parse tree by a separate route,
    # so a struct field no enumerator here knows about still lands in the denominator and the
    # gap becomes visible. `value`, `band` and `details` are untouched: they are the fields
    # the Rust port is validated equal against, and the census is not ported yet.
    census = state_census.compare(repo, lang, len(findings), visited, judged)

    return {
        "verdict": verdict,
        "value": f"{counts[NEUTRAL]} neutral / {counts[PROMISCUOUS]} promiscuous / {counts[UNRESOLVED]} unresolved",
        "band": "n/a",
        "counts": counts,
        "coverage": coverage,
        "resolvable_fraction": resolvable,
        "silence": silence,
        "partition": partition,
        "census": census,
        "findings": findings,
        "bucketed": bucketed,
        "details": (
            f"finite-testability: {counts[NEUTRAL]} neutral, {counts[PROMISCUOUS]} promiscuous, "
            f"{counts[UNRESOLVED]} unresolved across {total} pieces of state; "
            f"resolvable fraction {resolvable}; silence {silence['fraction']}; "
            f"{partition['uncounted']} of {partition['deciding_states']} deciding partitions uncounted. "
            "Cardinality is per state and does not compose: two states that decide the same "
            "branch multiply, and this version reports each separately rather than guessing "
            "the product."
        ),
    }
