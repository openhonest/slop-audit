"""L1.21: mechanical conformity with the Honest Code principles.

Nineteen principles, nineteen subclauses, L1.21.1 through L1.21.19. The numbering is the
Honest Framework's, so a clause number means one thing across every Open Honest artifact.

What makes the number worth reading is that it says which clauses it decided. Fifteen are
decidable from a Python syntax tree. Two are questions about a browser and are not
applicable to a Python file at all. One is decidable only in part: a cache is readable, and
whether anyone profiled the query first is not. One is not decidable by anything, ever,
because it is a property of how work is sequenced rather than of code.

A clause nobody could check stays outside the numerator AND the denominator, carrying its
reason. It is never reported as passing. That is the same rule the Silence index follows
and it is the whole reason to trust a conformity share: the score is over the clauses
actually decided, so it cannot be raised by looking away.

The second thing this has to be is FAST. It sits behind a hook that fires on every write,
so it parses one file and runs nineteen pure functions over the tree. Nothing here starts a
process, reads a second file, or asks the network.
"""

import ast
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from l1_analyzer import honest_code_rules as rules
from l1_analyzer.honest_code_rules import BROWSER_LANGUAGES, Finding

# Clauses that are ABOUT tests: how many mocks one carries, how much setup a step needs.
# Measured over the test files rather than the production ones, because measuring only
# production left both permanently undecided and two of the nineteen were never checked.
TEST_SCOPED = frozenset({"L1.21.10", "L1.21.15"})

# Every language this reader can parse into a tree. A file in anything else is read as text
# by the two clauses that only need text, and is not applicable to the rest.
_PARSED = frozenset({"python"})

_SUFFIXES = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".html": "html",
}

_ALL = frozenset({"python", *BROWSER_LANGUAGES})

# What decides each clause. `tree` means a syntax tree decides it; `partly` means half of
# the rule is readable and the checker names the other half; `nothing` means no reading of
# any file at any moment decides it.
_TREE, _PARTLY, _NOTHING = "tree", "partly", "nothing"


class Clause(TypedDict):
    """One subclause of L1.21: which principle, what decides it, and who checks it."""

    code: str
    rule: int
    name: str
    decides: str
    languages: frozenset[str]
    check: Callable[[dict], list[Finding] | None]


class Assessed(TypedDict):
    """One clause after it ran, or the reason it did not."""

    code: str
    name: str
    decided: bool
    reason: str
    findings: list[Finding]


class Assessment(TypedDict):
    """One file, measured against every clause that applies to it."""

    path: str
    language: str
    clauses: list[Assessed]
    conformity: float | None
    band: str
    decided_clauses: int
    unreadable_reason: str


def _clause(rule: int, name: str, decides: str, check: Callable[[dict], list[Finding] | None],
            languages: frozenset[str] = _ALL) -> Clause:
    return {"code": f"L1.21.{rule}", "rule": rule, "name": name, "decides": decides,
            "languages": languages, "check": check}


# The table IS the measure. Adding a principle is adding a row, which is rule 1 applied to
# the module that checks rule 1.
CLAUSES: tuple[Clause, ...] = (
    _clause(1, "Dict-lookup polymorphism over if/elif chains", _TREE, rules.dispatch_chains),
    _clause(2, "Typed dicts over classes", _TREE, rules.data_classes),
    _clause(3, "Pure functions over methods", _TREE, rules.methods_wearing_a_class),
    _clause(4, "I/O at the boundary", _TREE, rules.io_below_the_boundary),
    _clause(5, "Flat composition over inheritance", _TREE, rules.inheritance_for_reuse),
    _clause(6, "DOM as state", _TREE, rules.client_side_state, BROWSER_LANGUAGES),
    _clause(7, "HTML attributes over imperative DOM", _TREE, rules.imperative_dom,
            BROWSER_LANGUAGES),
    _clause(8, "Typed exceptions at the boundary", _TREE, rules.swallowed_exceptions),
    _clause(9, "SQL over application caches", _PARTLY, rules.unmeasured_caches),
    _clause(10, "Pure-function assertions over mocks", _TREE, rules.mock_heavy_tests),
    _clause(11, "Type declarations over imperative validation", _TREE,
            rules.imperative_validation),
    _clause(12, "Context managers over instance state", _TREE, rules.unscoped_resources),
    _clause(13, "Configuration as parameters", _TREE, rules.hidden_configuration),
    _clause(14, "No implicit defaults", _TREE, rules.implicit_defaults),
    _clause(15, "Simple gherkin steps signal honest architecture", _TREE,
            rules.heavy_step_definitions),
    _clause(16, "Declarative equivalents over lifecycle hooks", _TREE, rules.lifecycle_hooks),
    _clause(17, "Strangler pattern for migration", _NOTHING, rules.strangler_migration),
    _clause(18, "Dispatch tables close open input", _TREE, rules.open_dispatch),
    _clause(19, "Atomic test-and-set over check-then-act", _TREE, rules.check_then_act),
)

_WHY_NOT = {
    _NOTHING: ("nothing decides this one. It is a property of how work is sequenced over "
               "weeks, and no file carries the sequence of the work that produced it"),
}

_BANDS = ((95.0, "Healthy"), (75.0, "Not Healthy"))


def read_source_text(text: str, path: str) -> dict:
    """One file's text, parsed into what every clause needs.

    A file that does not parse comes back unreadable rather than empty. A file nobody could
    read is not a file with no violations, and reporting it clean is the exact failure this
    instrument exists to name."""
    # An unknown suffix is its own case, returned here, rather than a default folded into
    # the lookup. Clause 18 flagged the `.get(suffix, "")` this used to be and was right to:
    # a default files an input nobody wrote a rule for under an answer written for a
    # different one. Ruff's SIM401 asks for the `.get` back, and the two rules genuinely
    # disagree; this shape satisfies both by naming the unknown case instead of collapsing
    # it.
    suffix = Path(path).suffix
    blank = {"path": str(path), "text": text, "tree": ast.parse(""), "readable": False}
    if suffix not in _SUFFIXES:
        return {**blank, "language": "",
                "unreadable_reason": f"no reader here parses a {suffix} file"}

    language = _SUFFIXES[suffix]
    source = {**blank, "language": language, "unreadable_reason": ""}
    if language not in _PARSED:
        # Nothing to parse, and that is not a failure to read: the two clauses that apply to
        # a browser file read its text.
        source["readable"] = True
        return source
    try:
        source["tree"] = ast.parse(text)
        source["readable"] = True
    except SyntaxError as error:
        source["unreadable_reason"] = f"the file does not parse: {error.msg} at line {error.lineno}"
    return source


def read_source(path: Path) -> dict:
    """The one function here that touches the filesystem, so every clause below it stays a
    pure function of a tree."""
    path = Path(path)
    return read_source_text(path.read_text(errors="replace"), str(path))


def applies_to(clause: Clause, source: dict) -> bool:
    """Whether this clause can be decided for this file at all.

    Not applicable is a third answer beside pass and fail. A clause nobody ran is not a
    clause that passed."""
    return source["readable"] and source["language"] in clause["languages"]


def assess(source: dict) -> list[Assessed]:
    """Every clause, run over one parsed source.

    A clause that could not be decided never carries findings: not applicable and not
    decidable are both silence, and a finding under either would be a claim about something
    nobody read."""
    assessed: list[Assessed] = []
    for clause in CLAUSES:
        reason = _skip_reason(clause, source)
        findings = None if reason else clause["check"](source)
        if findings is None and not reason:
            reason = (f"not applicable to a {source['language']} file, so nothing here was "
                      "checked")
        assessed.append({
            "code": clause["code"], "name": clause["name"],
            "decided": reason == "", "reason": reason,
            "findings": findings or [],
        })
    return assessed


def _skip_reason(clause: Clause, source: dict) -> str:
    """Why a clause was not run, or the empty string when it was."""
    if clause["decides"] == _NOTHING:
        return _WHY_NOT[_NOTHING]
    if not source["readable"]:
        return source["unreadable_reason"] or "the file could not be read"
    if source["language"] not in clause["languages"]:
        return (f"asks about a browser, and this is a {source['language']} file with no DOM "
                "to keep a second copy of state in")
    return ""


def conformity(assessed: list[Assessed]) -> float | None:
    """The share of DECIDED clauses that hold.

    One clause with nine findings is one clause: counting findings would let a single noisy
    rule swamp the other eighteen. A file where nothing could be decided has no conformity
    rather than a perfect one, because a share of nothing is not a hundred percent."""
    decided = [c for c in assessed if c["decided"]]
    if not decided:
        return None
    holding = len([c for c in decided if not c["findings"]])
    return round(holding / len(decided) * 100, 1)


def band_of(share: float | None) -> str:
    """The panel's own bands. An absent share is n/a rather than the worst band, because
    unmeasured is not the same as bad."""
    if share is None:
        return "n/a"
    for floor, name in _BANDS:
        if share >= floor:
            return name
    return "Slop"


def assess_file_text(text: str, path: str) -> Assessment:
    """One file's text, measured. This is the pure entry point the hook path uses."""
    source = read_source_text(text, path)
    assessed = assess(source)
    share = conformity(assessed)
    return {
        "path": str(path), "language": source["language"], "clauses": assessed,
        "conformity": share, "band": band_of(share),
        "decided_clauses": len([c for c in assessed if c["decided"]]),
        "unreadable_reason": source["unreadable_reason"],
    }


def assess_file(path: Path) -> Assessment:
    """One file on disk, measured."""
    path = Path(path)
    return assess_file_text(path.read_text(errors="replace"), str(path))


def report(assessment: Assessment) -> str:
    """The per-clause result a person reads.

    The clauses nobody could decide are listed apart from the score, each with its reason,
    so a reader can see what the number covers rather than assume it covered everything."""
    lines = [f"# L1.21 — Honest Code conformity — {Path(assessment['path']).name}", ""]
    share = assessment["conformity"]
    shown = f"{share}%" if share is not None else "not measured"
    lines += [(f"Conformity: {shown} ({assessment['band']}), over "
               f"{assessment['decided_clauses']} of 19 clauses that were decided"), ""]
    if assessment["unreadable_reason"]:
        lines += [f"> {assessment['unreadable_reason']}", ""]

    broken = [c for c in assessment["clauses"] if c["decided"] and c["findings"]]
    held = [c for c in assessment["clauses"] if c["decided"] and not c["findings"]]
    undecided = [c for c in assessment["clauses"] if not c["decided"]]

    for clause in broken:
        lines.append(f"## {clause['code']} — {clause['name']} ({len(clause['findings'])})")
        lines.append("")
        for finding in clause["findings"]:
            lines.append(f"- `{finding['symbol']}:{finding['line']}` — {finding['detail']}")
            lines.append(f"      instead: {finding['instead']}")
            if finding["undecided"]:
                lines.append(f"      not decided: {finding['undecided']}")
        lines.append("")
    if held:
        lines += ["## clauses that hold", "", ", ".join(c["code"] for c in held), ""]
    if undecided:
        lines += [f"## clauses not decided ({len(undecided)})", "",
                  ("> These are outside the share, numerator and denominator both. A clause "
                   "nobody checked is not a clause that passed."), ""]
        for clause in undecided:
            lines.append(f"- {clause['code']} — {clause['name']}: {clause['reason']}")
        lines.append("")
    return "\n".join(lines)


def hook_report(assessment: Assessment) -> str:
    """The one thing an agent needs mid-edit: where, which clause, and what to do instead.

    Two lines per finding rather than one. The locator has to be readable at a glance, and
    the instruction has to be complete enough to act on; welding them into a single
    two-hundred-character line makes neither.

    Silence on a clean write is the correct output. A hook that congratulates the agent on
    every file teaches it to skip the output, and then the one that matters is skipped
    too."""
    name = assessment["path"]
    lines: list[str] = []
    for clause in assessment["clauses"]:
        for finding in clause["findings"]:
            lines.append(f"{name}:{finding['line']} {clause['code']} {finding['detail']}")
            lines.append(f"    instead: {finding['instead']}")
    return "\n".join(lines)


def analyze(repo: Path, lang: str) -> dict:
    """L1.21 over a whole repository.

    A clause is broken for the repository if ANY file breaks it, because one dishonest site
    is what a reader needs to find. Optional in the full audit: nineteen clauses over a
    large tree is a cost a caller chooses rather than one imposed on every run."""
    from l1_analyzer import scope

    repo = Path(repo)
    extensions = frozenset(_SUFFIXES)
    production, _skipped = scope._read_text_files(repo, extensions, scope.PRODUCTION)
    everything, _also = scope._read_text_files(repo, extensions, scope.WHOLE_REPO)
    produced = {str(path) for path, _text in production}
    tests = [(path, text) for path, text in everything if str(path) not in produced]

    broken: dict[str, list[Finding]] = {}
    decided: set[str] = set()
    # A production clause over a test file would make the score about the suite rather than
    # about the code, and a test clause over a production file has no tests to read.
    for read, wanted in ((production, False), (tests, True)):
        for path, text in read:
            for clause in assess_file_text(text, str(path))["clauses"]:
                if (clause["code"] in TEST_SCOPED) != wanted or not clause["decided"]:
                    continue
                decided.add(clause["code"])
                if clause["findings"]:
                    broken.setdefault(clause["code"], []).extend(clause["findings"])

    files = production + tests
    never_decided = sorted({c["code"] for c in CLAUSES} - decided)
    if not decided:
        nothing = ("no file here could be measured against any clause, so there is no "
                   "conformity to report. Not decided: " + ", ".join(never_decided))
        return {"value": "n/a", "band": "n/a", "details": nothing,
                "findings": [], "undecided": never_decided}

    share = round((len(decided) - len(broken)) / len(decided) * 100, 1)
    detail = (f"{len(decided) - len(broken)} of {len(decided)} decided clauses hold across "
              f"{len(files)} files. Not decided ({len(never_decided)}): "
              + ", ".join(never_decided))
    return {"value": share, "band": band_of(share), "details": detail,
            "findings": [f for group in broken.values() for f in group],
            "undecided": never_decided}
