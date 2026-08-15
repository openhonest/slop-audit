"""The published grade computation: the single A-F grade, the verifiability verdict
(CAN / COARSE / CANNOT), the finitely-testable share, and the basis that can withhold all
three. One source, read by the CLI and by the site through card.py.

This module renders nothing. It held two renderers and the model that fed them until
2026-08-15, when they were deleted: neither had a production caller, card.py has always been
the one that ships, and three tests were asserting published content against output nobody
ran. Migrating those assertions to the card is what exposed the content that reached no
reader at all - the note that cardinalities do not compose, and the reason beside each silent
site - and both now live in card.py. The mapping function went with the renderers, since
nothing was left to render its model.

The grade rule (published, not hidden): verifiability first. CANNOT is F, COARSE is D, and
above the silence floor there is no grade at all. When every piece of state is finitely
testable and coverable, A/B/C is the weighted health of the audit checks - god-files and
type-escapes weigh most.
"""

from __future__ import annotations

from typing import TypedDict

from l1_analyzer import state_census, state_partition

_HYGIENE_WEIGHTS = {"L1.17": 3, "L1.15": 3, "L1.10": 2, "L1.11": 1, "L1.9": 1, "L1.16": 1}
_BAND_POINTS = {"Healthy": 1.0, "Not Healthy": 0.5, "Slop": 0.0}
_A_MIN, _B_MIN = 0.85, 0.60

# Above this share of undecided state, no grade is issued at all. The number is measured,
# not chosen: see candidate-methods/silence-index-for-finite-testability.md for the
# distribution it comes from. It gates only the good grades - a proven unbounded state is
# still F above the floor, because a proof stands whatever else went unread.
#
# It sits just above the worst silence the analyzer produces on the pinned corpus (libuv,
# 0.458), so no repository is refused a grade for a limit of OUR reading. That makes it a
# ratchet, not a quality bar: every builtin we teach the analyzer lowers observed silence,
# and this number comes down with it.
SILENCE_FLOOR = 0.50

# Why the floor above cannot catch a repository the analyzer never read, and what does.
#
# Silence, the resolvable fraction and the section-7 partition count are all computed over
# the state the classifier RECOGNIZED. Nothing measured over the enumerated set can see
# non-enumeration: zero undecided of zero total is 0%, so the floor structurally cannot fire
# on a repository that produced no findings at all, and the card read that empty denominator
# as maximum confidence and issued an affirmative "none of the data this code keeps can grow
# without limit". The state_census module supplies the independent denominator - state-bearing
# declarations counted straight from the parse tree - and `basis` below is what the comparison
# decides.
#
# THE GAP IS AN EMPTY REACHABLE DENOMINATOR, AND NO FRACTIONAL BOUND IS SET. That is the
# measurement result, not an omission.
#
# The threshold used to be zero admitted against declared, and that conflated two opposite
# facts, because no rule existing and every rule saying no both produce zero. `struct Store
# { int cache[256]; }` in C declares one field and admits none, and the C enumerator has no
# field rule at all, so refusing is right. The analyzer package in this repository declares
# 480 and admits none, of which 231 are TypedDict bodies and 249 are all-caps module
# constants the enumerator read and declined; a planted `self.cache = {}` beside them is
# admitted. Same two numbers, opposite facts. Four repositories were refused a grade on the
# second reading, this tool's own package among them.
#
# The denominator is therefore `reachable`, the declarations whose KIND the enumerator has a
# rule capable of matching, and the census measures capability with a fixture per (language,
# kind) run through the real classifier. Three pairs come back with no rule at all: a C
# struct field, a C# auto-property, and a name bound in a Python class body. Narrowing
# `declared` instead was tried and measured - raw, minus TypedDict shapes, minus immutables,
# over ten Python trees - and it moves nothing, because shrinking a denominator never turns
# an admitted count of zero into anything else.
#
# admitted/declared over the same seventeen trees the silence floor
# was measured on (the six pinned corpus repositories, this repository, the analyzer package,
# and nine local Python trees):
#
#   gson 1.000  junit4 0.997  Newtonsoft.Json 0.471  json-c 0.348  RestSharp 0.280
#   multicardz 0.161  libuv 0.158  declaro 0.139  honest-starter 0.069  slop-audit-web 0.068
#   honest-framework 0.036  open-vrm-app 0.034  umbra 0.007
#   slop-audit 0.000  l1_analyzer 0.000  weights-watch 0.000  challenge 0.000
#
# The positive values are a continuum from 0.007 to 1.0 with no gap to cut at. The widest
# interior gap is 0.471 to 0.997, which would put a bound near 0.7 and refuse to grade fifteen
# of the seventeen - measuring the reach of our reading rather than the obscurity of their
# code, which is the same argument that rejected a 0.10 silence floor. A bound at 0.10 refuses
# eight of seventeen on the same grounds. Any number in that range would be invented here.
#
# An empty reachable denominator is not a small fraction, it is a different fact: nothing
# here is written in a form any rule can reach, so the reading never started and the report
# has no evidence to grade. That boundary is where the defect lives and it needs no number.
# The residual blind spot is named rather than closed: a repository that declares one
# reachable site and a hundred unreachable ones is graded on the one, and only teaching the
# enumerator the missing kind fixes that. What would settle a fractional bound is a
# labelled set - repositories where a human has enumerated the state by hand - so the ratio
# could be scored against a known truth instead of against itself. Until that exists, a thin
# reading and a thorough one are told apart only at zero, and the census publishes the ratio
# on every report so a reader can see how thin the reading was.
NO_SOURCE, UNREAD, SILENT, MEASURED = "no-source", "unread", "silent", "measured"

# A finite, unordered partition wider than this is D. NO NUMBER IS SET, and that is the
# measurement result, not an omission.
#
# Measured over the six pinned corpus repositories and nine supplementary Python trees:
# 36 unordered partitions over state that decides something, distributed
# {2:6, 3:7, 4:7, 5:4, 6:1, 7:2, 8:4, 12:2, 13:2, 14:1}. The widest anything reached was 14.
# There is no upper tail at all. The distribution therefore fixes a FLOOR for any bound - a
# bound of 14 or less would put ordinary production state in D, which would be measuring our
# impatience rather than their testability - and says nothing whatever about where above 15
# to put it. Picking 20, or 100, would be inventing the number the data was supposed to give.
#
# The reason the tail is empty is worth stating, because it is a limit of the instrument and
# not a fact about code. The five-hundred-string-key dispatch table the rule was written for
# reaches this meter as a keyed read with a VARIABLE key, which is unbounded and already F.
# A partition is only counted here when the literals are written out one at a time, and
# nobody writes five hundred of those. So D as specified is close to unreachable by the
# current measurement, and a bound would be a rule with no observed instances.
#
# Set an integer here (or pass one to grade_summary) to switch D on. Until the measurement
# can see the shape the rule is about, None keeps the analyzer from issuing a grade it
# cannot support.
UNORDERED_CLASS_BOUND: int | None = None

def _meter_ran(l18b: dict) -> bool:
    return isinstance(l18b, dict) and isinstance(l18b.get("resolvable_fraction"), (int, float))


def silence_fraction(counts: dict) -> float:
    """The share of state whose disposition the analyzer could not decide.

    Derived from the same counts the status is derived from, rather than read from a
    second key, so the number that suppresses a grade and the number that sets it can
    never disagree about the same repository."""
    total = sum(counts.values())
    return (counts.get("unresolved", 0) / total) if total else 0.0


def census_unread(census: object) -> bool:
    """True when the parser found state-bearing declarations, NONE of them of a kind the
    classifier's enumerator has a rule capable of matching, and the classifier produced no
    finding whatever. The two counts come from different readings on purpose: a shared
    enumerator would make them agree by construction and this gap could never open.

    `reachable` rather than `declared` is the denominator, and that correction is the whole
    of this function's history. The first version asked whether `admitted` was zero against
    `declared`, which conflates two opposite facts: no rule existed, and every rule said no.
    A C struct field is the first, so refusing is right. A codebase whose state is TypedDict
    shapes and all-caps constants is the second - every kind it declares is one the
    enumerator reads, it read them and declined them on the merits - and refusing there
    reported a limit of ours that was not there. It refused this repository's own analyzer
    package, and three more.

    `admitted == 0` stays in the conjunction for the invariant `_basis` relies on: a
    repository with any finding at all, a promiscuous proof included, is never UNREAD. It
    also makes the change a one-way relaxation, so no repository can move from graded to
    refused by this rule.

    A census without `reachable` is not a census, and reads here as "not counted", the same
    as `declared` of None. Nothing downstream may treat a missing capability answer as a
    capability."""
    if not isinstance(census, dict):
        return False
    declared, reachable = census.get("declared"), census.get("reachable")
    return (isinstance(declared, int) and declared > 0
            and isinstance(reachable, int) and reachable == 0
            and census.get("admitted") == 0)


def unread_kinds_phrase(census: object) -> str:
    """The declaration kinds this repository spells and the enumerator cannot match, in
    prose. Read from the census rather than re-derived, so the sentence a reader acts on and
    the count that withheld the grade come from one measurement."""
    kinds = census.get("unread_kinds") if isinstance(census, dict) else None
    return state_census.kind_phrase(kinds)


def _basis(band: str, counts: dict, meter_ran: bool, census: object) -> str:
    """What evidence the report actually has. Four cases, and three of them forbid a grade.

    The order is the argument. A promiscuous finding is a PROOF, and a proof does not need
    coverage of everything else to stand: one state that provably reaches an unbounded
    decision means no finite suite covers the code, however much of the rest went unread.
    So the silence floor is consulted after it. The floor exists to stop obscurity buying a
    GOOD grade; letting it erase a proven bad one would be the same error backwards.

    The census check sits above the proof and does not compete with it. `admitted == 0` is
    part of the condition, so a repository with any finding at all - a proof included - is
    never UNREAD, and the two branches cannot both apply to one repository."""
    if not meter_ran or band == "n/a":
        return NO_SOURCE
    if census_unread(census):
        return UNREAD
    if counts.get("promiscuous", 0) > 0:
        return MEASURED
    if silence_fraction(counts) > SILENCE_FLOOR:
        return SILENT
    return MEASURED


def _status(basis: str, counts: dict, coarse: bool) -> str:
    """The verifiability status, decided on OBSERVED state only.

    An undecided state used to produce `might`, and `might` graded D, so one call the
    analyzer could not read capped a whole repository at D. That reported a limit of ours
    as a defect in their code. Undecided state now leaves the status alone and is published
    as the silence index instead.

    The two ways of showing the analyzer nothing are the poka-yoke, and they are the part
    that cannot be dropped. Grading on observed state alone would hand an A to code that
    shows the analyzer nothing, because zero observed state is vacuously clean. Hiding state
    behind an unreadable boundary trips the silence floor; hiding it in a construct the
    enumerator does not know about trips the census. Either way there is no grade, so
    obscurity buys silence rather than a good letter."""
    if basis != MEASURED:
        return "na"
    if counts.get("promiscuous", 0) > 0:
        return "cannot"
    # D, now that silence has vacated it: the reaching partition is finite and countable,
    # its members are unordered, and there are more of them than the bound. Limit testing
    # defeats a large ORDERED domain with a handful of boundary values and defeats a large
    # unordered one with nothing, so cardinality alone was never the test.
    if coarse:
        return "coarse"
    return "can"


def _hygiene(results: dict) -> float | None:
    num = den = 0.0
    for key, weight in _HYGIENE_WEIGHTS.items():
        points = _BAND_POINTS.get(str((results.get(key) or {}).get("band")))
        if points is None:
            continue
        num += weight * points
        den += weight
    return (num / den) if den else None


def _grade(status: str, pct: int | None, hygiene: float | None) -> str | None:
    if status == "na" or pct is None:
        return None
    if status == "cannot":
        return "F"
    if status == "coarse":
        return "D"
    if hygiene is None:
        return "A"
    return "A" if hygiene >= _A_MIN else "B" if hygiene >= _B_MIN else "C"


def coarse_states(l18b: dict, bound: int | None) -> list[dict]:
    """State whose reaching partition is finite, unordered, and wider than the bound.

    The bound lives here rather than in the classifier because it is a reporting decision:
    the classifier measures the cardinality, and how many unordered cases are too many to
    cover is a judgement about who is doing the testing. A finding whose count could not be
    recovered is excluded, because an unknown count is a limit of ours, not a finding about
    their code. `bound` of None is the explicit "no bound configured" case: D is switched
    off and no state is coarse, which is different from every state being fine and is why
    absence is a case here rather than a default filled in somewhere out of sight."""
    if bound is None:
        return []
    flagged = [
        f for f in (l18b.get("findings") or [])
        if f.get("verdict") == "neutral"
        and state_partition.is_coarse(f.get("partition") or state_partition.UNKNOWN,
                                      bool(f.get("drives_decision")), bound)
    ]
    flagged.sort(key=lambda f: (-f["partition"]["classes"], f.get("file", ""), f.get("line", 0)))
    return flagged


class GradeSummary(TypedDict):
    status: str                 # can | coarse | cannot | na
    basis: str                  # measured | unread | silent | no-source: why na, when na
    counts: dict[str, int]      # neutral / promiscuous / unresolved
    testable_pct: int | None    # share of DECIDED state that is finitely testable
    hygiene: float | None       # weighted health of the audit checks, 0..1
    grade: str | None           # A/B/C (can), D (coarse), F (cannot), None (na)
    silence: float              # share of state the analyzer could not decide
    census: dict[str, object]   # declared vs admitted: the independent denominator
    coarse: list[dict]          # the states that made the verdict coarse, widest first


def grade_summary(results: dict, unordered_class_bound: int | None) -> GradeSummary:
    """The published grade computation - the SINGLE SOURCE of the A-F grade, used by both
    the CLI report and the web card. Verifiability first: CANNOT is F, COARSE is D, above
    the silence floor no grade at all, and when every piece of state is finitely testable
    and coverable, A/B/C is the weighted health of the audit checks.

    `unordered_class_bound` is policy, not a fact about the repository, so it is passed in
    rather than read from here: how many unordered cases are too many depends on who is
    doing the testing, and that answer belongs to whoever is publishing the grade."""
    l18 = results.get("L1.18") or {"band": "n/a"}
    band = str(l18.get("band", "n/a"))
    l18b = results.get("L1.18b") or {}
    counts = (l18b.get("counts") if isinstance(l18b, dict) else None) or {"neutral": 0, "promiscuous": 0, "unresolved": 0}
    coarse = coarse_states(l18b if isinstance(l18b, dict) else {}, unordered_class_bound)
    census = l18b.get("census") if isinstance(l18b, dict) else None
    basis = _basis(band, counts, _meter_ran(l18b), census)
    status = _status(basis, counts, bool(coarse))
    # The denominator is DECIDED state, not all state. Undecided state is no longer held
    # against the grade, so holding it against the published percentage would put the same
    # blind spot back through a second door.
    decided = counts.get("neutral", 0) + counts.get("promiscuous", 0)
    pct = None if status == "na" else (100 if decided == 0 else round(counts.get("neutral", 0) / decided * 100))
    hygiene = _hygiene(results)
    return {"status": status, "basis": basis, "counts": counts, "testable_pct": pct,
            "hygiene": hygiene, "grade": _grade(status, pct, hygiene),
            "silence": silence_fraction(counts),
            "census": census if isinstance(census, dict) else {}, "coarse": coarse}
