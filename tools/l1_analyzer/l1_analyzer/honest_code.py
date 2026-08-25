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
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from tree_sitter import Language, Node, Parser

from l1_analyzer import honest_code_python_rules as python_rules
from l1_analyzer import honest_code_rules as rules
from l1_analyzer.honest_code_read import read_tree
from l1_analyzer.honest_code_rules import BROWSER_LANGUAGES, Finding
from l1_analyzer.lang_spec import LANG_SPEC

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

# The languages the shared node vocabulary covers. A ported clause can be decided for any
# of them; an unported one is limited to `_PARSED` above.
_VOCABULARY = frozenset(LANG_SPEC)

# What decides each clause. `tree` means a syntax tree decides it; `partly` means half of
# the rule is readable and the checker names the other half; `nothing` means no reading of
# any file at any moment decides it.
_TREE, _PARTLY, _NOTHING = "tree", "partly", "nothing"

# Why a clause was not decided, as a VALUE rather than as prose. `decided: False` was one
# bucket for facts that mean different things: a rule nothing will ever decide, a question
# that did not arise for this file, and a file the audit could not read. The third is a
# failure and the other two are not, and a consumer counting undecided clauses has to be
# able to tell them apart without parsing an English sentence.
#
# Prompted by an adopter finding the same shape in their own reader: it bucketed every
# verdict that was not `fired` into `declined`, so a hook that had just held three files
# displayed as "0 fired (0%)". A third state collapsed into a second reports nothing
# happening about the exact case the instrument exists for.
NEVER, NOT_APPLICABLE, UNREADABLE = "never", "not applicable", "unreadable"
UNDECIDED_KINDS = (NEVER, NOT_APPLICABLE, UNREADABLE)


# What a clause reads. Two axes, not one: `decides` says whether the RULE is decidable at
# all, and `reads` says what this checker needs in front of it. Conflating them is what let
# seventeen tree clauses run against the empty tree a JavaScript file produces, find
# nothing, and count as holding.
# Three readers, not two, for as long as the port is unfinished.
#
# `_PYTHON_AST` is a clause still written against Python's own parser, so it can be decided
# for Python and nothing else. `_TREE_READER` is a clause read through the shared
# per-language node vocabulary, so it can be decided for every language that vocabulary
# covers. `_TEXT_READER` needs no tree at all.
#
# The middle one is where clauses arrive as they are ported. When none are left in the
# first, that constant and this comment go.
_PYTHON_AST, _TREE_READER, _TEXT_READER = "python-ast", "tree", "text"


class Clause(TypedDict):
    """One subclause of L1.21: which principle, what decides it, what it reads, and who
    checks it."""

    code: str
    rule: int
    name: str
    decides: str
    reads: str
    languages: frozenset[str]
    check: Callable[[dict], list[Finding] | None]


class Allowed(TypedDict):
    """One site the author declared an exception, and why.

    Never dropped. An exception nobody can see is indistinguishable from a rule nobody
    checked, which is the thing this instrument is built to name."""

    file: str
    clause: str
    symbol: str
    line: int
    detail: str
    reason: str


class Assessed(TypedDict):
    """One clause after it ran, or the reason it did not."""

    code: str
    name: str
    decided: bool
    undecided: str
    reason: str
    findings: list[Finding]
    allowed: list[Allowed]
    declared: list[Allowed]


# How much of a string constant has to parse as another language before it is worth
# naming. Five lines, because one line of something that parses is a fragment rather than
# content nobody examined, and a reader told about fragments stops reading the notices.
_BLOCK_LINES = 5

# A cheap gate before nine grammars are tried on a string. Trying them all on every long
# docstring cost 203ms on this package's most fixture-heavy file, over the budget that keeps
# this usable behind a write hook.
#
# Its only failure mode is SILENCE. A block that carries none of these is not reported, which
# is exactly what happened before any of this existed; it can never invent a block that is not
# there. That direction is the reason it is acceptable and the reason it is written down.
_CODE_MARKS = (";", "{", "}", "=>", "<", "func ", "def ", "class ", "fn ", "public ", "var ")

# Grammars this reader uses that no clause reads. They are deliberately NOT in LANG_SPEC:
# that table is the clause vocabulary, and an entry there would tell nineteen clauses they
# can read markup.
#
# Page content is why they are here. The same JavaScript reported bare went silent once
# wrapped in a script tag, because the tags are not JavaScript and the whole-grammar test
# rejected the block. That is the commonest way embedded source arrives.
_MARKUP = "html"
_STYLESHEET = "css"

# The element types whose text is another language. Read by node type, so nothing is
# stripped and nothing is matched by pattern: a wrapper removed by hand is the guess this
# whole test exists to avoid.
_EMBEDDING_ELEMENTS = ("script_element", "style_element")



def _grammars() -> dict[str, Language]:
    """The grammars for the languages no clause reads, loaded once and stated.

    Built here rather than imported inside the parse, so a caller asks the table what is
    present instead of parsing and catching to find out. A grammar that failed to install
    is then a missing key at the one call that wanted it, not a rejection indistinguishable
    from the grammar reading the text and saying no."""
    import tree_sitter_css
    import tree_sitter_html

    return {_MARKUP: Language(tree_sitter_html.language()),
            _STYLESHEET: Language(tree_sitter_css.language())}


GRAMMARS = _grammars()


class Unexamined(TypedDict):
    """A block inside a readable file that no clause looked at.

    Not a clause and not graded. The Python in a file holding a JavaScript widget really
    does hold every clause that read it, and saying otherwise would invent a violation.
    This says the other true thing: the file's substance was never examined.

    THE FINDINGS ARE THE POINT, NOT THE LANGUAGE. A twelve-line SQL query inside a database
    driver is accepted whole by the ruby grammar, there is no SQL grammar, so that name can
    never be right and a driver holds dozens of such queries. Reporting a guessed name and
    nothing else teaches a reader to skip the field, which costs the embedded-widget case it
    was built for.

    So the clauses are run on the block and travel with it. A misnamed block reports nothing,
    because it is not that language and has none of that language's shapes. A real one
    reports what a reader can act on, and the name it was given stops mattering."""

    language: str
    line: int
    lines: int
    findings: list[Finding]
    # The other grammars that also took this block whole. A name is a pick among these, and
    # a reader discounting a finding needs to see how much of a pick it was.
    also_accepted_by: list[str]


class Assessment(TypedDict):
    """One file, measured against every clause that applies to it."""

    path: str
    language: str
    clauses: list[Assessed]
    conformity: float | None
    band: str
    decided_clauses: int
    unexamined: list[Unexamined]
    unreadable_reason: str


def _clause(rule: int, name: str, decides: str, check: Callable[[dict], list[Finding] | None],
            languages: frozenset[str] = _ALL, reads: str = _PYTHON_AST) -> Clause:
    return {"code": f"L1.21.{rule}", "rule": rule, "name": name, "decides": decides,
            "reads": reads, "languages": languages, "check": check}


# The table IS the measure. Adding a principle is adding a row, which is rule 1 applied to
# the module that checks rule 1.
CLAUSES: tuple[Clause, ...] = (
    # Ported to the shared vocabulary: decided for every language the spec covers.
    _clause(1, "Dict-lookup polymorphism over if/elif chains", _TREE, rules.dispatch_chains,
            reads=_TREE_READER),
    _clause(2, "Typed dicts over classes", _TREE, rules.data_classes,
            reads=_TREE_READER),
    _clause(3, "Pure functions over methods", _TREE, rules.methods_wearing_a_class,
            reads=_TREE_READER),
    _clause(4, "I/O at the boundary", _TREE, python_rules.io_below_the_boundary),
    _clause(5, "Flat composition over inheritance", _TREE, rules.inheritance_for_reuse,
            reads=_TREE_READER),
    # The only two that read the file's TEXT, which is why they work on a language this
    # package has no parser for.
    _clause(6, "DOM as state", _TREE, rules.client_side_state, BROWSER_LANGUAGES,
            reads=_TEXT_READER),
    _clause(7, "HTML attributes over imperative DOM", _TREE, rules.imperative_dom,
            BROWSER_LANGUAGES, reads=_TEXT_READER),
    _clause(8, "Typed exceptions at the boundary", _TREE, rules.swallowed_exceptions,
            reads=_TREE_READER),
    _clause(9, "SQL over application caches", _PARTLY, python_rules.unmeasured_caches),
    _clause(10, "Pure-function assertions over mocks", _TREE, python_rules.mock_heavy_tests),
    _clause(11, "Type declarations over imperative validation", _TREE,
            python_rules.imperative_validation),
    _clause(12, "Context managers over instance state", _TREE, python_rules.unscoped_resources),
    _clause(13, "Configuration as parameters", _TREE, rules.hidden_configuration,
            reads=_TREE_READER),
    _clause(14, "No implicit defaults", _TREE, rules.implicit_defaults,
            reads=_TREE_READER),
    _clause(15, "Simple gherkin steps signal honest architecture", _TREE,
            python_rules.heavy_step_definitions),
    _clause(16, "Declarative equivalents over lifecycle hooks", _TREE, python_rules.lifecycle_hooks),
    _clause(17, "Strangler pattern for migration", _NOTHING, python_rules.strangler_migration),
    _clause(18, "Dispatch tables close open input", _TREE, rules.open_dispatch,
            reads=_TREE_READER),
    _clause(19, "Atomic test-and-set over check-then-act", _TREE, python_rules.check_then_act),
)

_WHY_NOT = {
    _NOTHING: ("nothing decides this one. It is a property of how work is sequenced over "
               "weeks, and no file carries the sequence of the work that produced it"),
}

_BANDS = ((95.0, "Healthy"), (75.0, "Not Healthy"))

# How an author declares that a clause does not apply at one site. The reason is required:
# a suppression nobody justified is the silent skip this whole instrument exists to name,
# and it has to cost the author a sentence.
_ALLOW = re.compile(r"honest-code-allow:\s*(L1\.21\.\d+)\s*[-\u2014:]+\s*(\S.*?)\s*$")

# How far below the comment the site it covers may sit.
#
# Three lines, not one. A decorator sits between the comment and the def it annotates, and
# every cache clause 9 fires on is decorated by definition, so a shorter reach put the
# declaration out of range of exactly the findings that need one. It still stops well short
# of the next function, or one comment would excuse everything beneath it.
_ALLOW_REACH = 4


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
    # The shared tree, for every clause already reading the per-language vocabulary. It is
    # built for any language the vocabulary covers, which is what lets a ported clause see
    # a JavaScript file that Python's own parser cannot.
    if language in _VOCABULARY:
        source.update(read_tree(text, language))
        source["unreadable_reason"] = ""
    if language not in _PARSED:
        # No Python tree, and that is not a failure to read: the clauses that apply here
        # read either the shared tree or the text.
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


def allowances(text: str) -> dict[int, dict[str, str]]:
    """The exceptions a file declares, keyed by the line the comment sits on.

    Each names one clause and carries the reason it does not apply there. A declaration
    with no reason is not returned at all: a suppression nobody justified is the silent
    skip this instrument exists to name."""
    declared: dict[int, dict[str, str]] = {}
    for number, line in enumerate(text.split("\n"), start=1):
        found = _ALLOW.search(line)
        if found:
            declared.setdefault(number, {})[found.group(1)] = found.group(2)
    return declared


def allowed_reason(finding: Finding, declared: dict[int, dict[str, str]]) -> str:
    """Why this finding was declared an exception, or the empty string.

    The comment may sit on the site's own line or just above it, and no further: a comment
    cannot reach past the thing it was written about."""
    for offset in range(_ALLOW_REACH):
        reasons = declared.get(finding["line"] - offset, {})
        if finding["clause"] in reasons:
            return reasons[finding["clause"]]
    return ""


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
    declared = allowances(source["text"])
    assessed: list[Assessed] = []
    for clause in CLAUSES:
        kind, reason = _skip_reason(clause, source)
        findings = None if reason else clause["check"](source)
        for finding in findings or ():
            # Filled in here, where the path is known. A checker reads a tree and the tree
            # does not know which file it came from.
            finding["file"] = source["path"]
        if findings is None and not reason:
            kind = NOT_APPLICABLE
            reason = (f"not applicable to a {source['language']} file, so nothing here was "
                      "checked")
        kept, allowed, by_declaration = _split_withheld(findings or [], declared)
        assessed.append({
            "code": clause["code"], "name": clause["name"],
            "decided": reason == "", "undecided": "" if reason == "" else kind,
            "reason": reason, "findings": kept, "allowed": allowed,
            "declared": by_declaration,
        })
    return assessed


_DECLARED_REASON = ("a boundary declaration on the function withheld this; the call graph "
                    "inference would otherwise have reported it")


def _split_withheld(findings: list[Finding], declared: dict[int, dict[str, str]]
                    ) -> tuple[list[Finding], list[Allowed], list[Allowed]]:
    """The violations, the sites an allow comment excused, and the sites a boundary
    declaration excused.

    Three lists, because the two suppressions are different acts and a reader has to be
    able to tell them apart: a comment carries a written reason, a declaration carries an
    architectural claim.

    Set apart rather than dropped, and the declaration half was dropped until now. A
    consumer counting suppressions had to infer them from the presence of a decorator, and
    on one real package that inference was wrong three times in four: 62 of 82 markers sat
    on functions this clause would never have spoken about. Only a withheld finding is
    recorded here, so a marker that suppressed nothing costs its package nothing."""
    kept: list[Finding] = []
    allowed: list[Allowed] = []
    by_declaration: list[Allowed] = []
    for finding in findings:
        reason = allowed_reason(finding, declared)
        if reason:
            allowed.append(_withheld(finding, reason))
        elif finding["withheld_by"] == "declaration":
            by_declaration.append(_withheld(finding, _DECLARED_REASON))
        else:
            kept.append(finding)
    return kept, allowed, by_declaration


def _withheld(finding: Finding, reason: str) -> Allowed:
    """One finding that was withheld, and what withheld it."""
    return {"file": finding["file"], "clause": finding["clause"], "symbol": finding["symbol"],
            "line": finding["line"], "detail": finding["detail"], "reason": reason}


def _skip_reason(clause: Clause, source: dict) -> tuple[str, str]:
    """Which KIND of undecided this clause is, and the sentence for a reader.

    The kind is what a consumer buckets on. The sentence is what a person reads, and it
    used to be the only thing separating three facts that mean different things."""
    if clause["decides"] == _NOTHING:
        return NEVER, _WHY_NOT[_NOTHING]
    if not source["readable"]:
        return UNREADABLE, source["unreadable_reason"] or "the file could not be read"
    # A clause that reads a TREE needs one. Only Python is parsed here, so every tree clause
    # on any other language was running against an empty tree, finding nothing, and counting
    # as holding: a clean bill of health on a file nobody parsed.
    #
    # UNREADABLE rather than NOT APPLICABLE, and the distinction is the point. These clauses
    # DO apply to JavaScript. This reader cannot read it, which is a gap in the instrument
    # rather than a question that did not arise, and only one of those two is a failure.
    if clause["reads"] == _PYTHON_AST and source["language"] not in _PARSED:
        return UNREADABLE, (
            f"this clause is still written against Python's own parser, so it has no way "
            f"to read {source['language']} yet")
    if clause["reads"] == _TREE_READER and source["language"] not in _VOCABULARY:
        return UNREADABLE, (
            f"the shared node vocabulary does not cover {source['language']}, so this "
            "clause had no tree to decide it from")
    if source["language"] not in clause["languages"]:
        return NOT_APPLICABLE, (
            f"asks about a browser, and this is a {source['language']} file with no DOM "
            "to keep a second copy of state in")
    return "", ""


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
        "unexamined": unexamined_blocks(source),
        "unreadable_reason": source["unreadable_reason"],
    }


def assess_file(path: Path) -> Assessment:
    """One file on disk, measured."""
    path = Path(path)
    return assess_file_text(path.read_text(errors="replace"), str(path))


def unexamined_blocks(source: dict) -> list[Unexamined]:
    """Substantial string constants that parse cleanly as another language this tool knows.

    A Python file holding a JavaScript widget scored 100 per cent with fourteen clauses
    decided and no findings, and the JavaScript in it had a dispatch chain and a swallowed
    error. Every clause examined the Python correctly; nothing examined the substance.

    Nothing is guessed from resemblance. A block is named only when a real grammar accepts
    the WHOLE of it with no error node, which is what keeps prose out: run over this
    package's own source, 355 long string literals produced eleven hits and every one was
    genuine embedded source held as a test fixture."""
    if not source["readable"] or source["language"] not in _PARSED:
        return []
    documentation = _docstrings(source["tree"])
    found: list[Unexamined] = []
    for node in ast.walk(source["tree"]):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in documentation:
            continue
        lines = node.value.count("\n") + 1
        if lines < _BLOCK_LINES or not any(mark in node.value for mark in _CODE_MARKS):
            continue
        found += _blocks_in(node.value, source["language"], node.lineno)
    examined: list[Unexamined] = []
    for block in found:
        # The block's own text travels only this far. A reader wants the findings, and
        # carrying every embedded block's source into the published record would put the
        # file back into the report that is about the file.
        text = block.pop("text")
        examined.append({**block, "findings": _findings_in(block, text)})
    return examined


def _findings_in(block: Unexamined, text: str) -> list[Finding]:
    """What every clause that reads the shared vocabulary says about one embedded block.

    Only those clauses: the ones written against Python's own parser would be handed a tree
    the runner did not build for this text. A clause that raises on the block is skipped
    rather than reported, because a reader cannot act on this reader's own failure to parse
    something it already said it could parse."""
    # An unnamed block has no clauses to run: nobody knows which language's vocabulary to
    # read it through, which is exactly what the empty name records.
    if block["language"] not in _VOCABULARY:
        return []
    source = read_tree(text, block["language"])
    source.update({"path": "", "language": block["language"], "text": text,
                   "readable": True, "unreadable_reason": ""})
    found: list[Finding] = []
    for clause in CLAUSES:
        if clause["reads"] != _TREE_READER:
            continue
        found += clause["check"](source) or []
    return [{**f, "line": f["line"] + block["line"] - 1} for f in found]


def _blocks_in(text: str, own: str, line: int) -> list[Unexamined]:
    """Every block of another language inside this text, one entry per element.

    One entry per BLOCK was wrong and it was wrong quietly. Page content usually carries a
    style element and a script element together, and returning a single language reported
    whichever was found first while dropping the other, so a record read as though the
    block had been accounted for. Which one survived depended on the order they came out of
    the tree.

    Each entry carries its own line and its own size. Reporting the whole block's size
    against one language says the entire string was that language, and giving both elements
    line 1 makes a reader search for the one that starts on line 6."""
    wrapper = _accepts_whole(text, _MARKUP)
    if wrapper is not None:
        parts = _markup_parts(wrapper, text)
        found = [block for part, offset in parts
                 for block in _blocks_in(part, own, line + offset)]
        if found:
            return found
        # Markup carrying no embedded source this reader knows is still content nothing
        # examined, and naming it as markup is truer than naming it as a language it does
        # not contain.
        #
        # It is named BEFORE the other grammars are tried, and that order settles an
        # ambiguity between grammars rather than expressing a preference. The JavaScript and
        # TypeScript grammars both accept JSX, so any tag-shaped text parses cleanly as
        # JavaScript: a plain block of divs was reported as JavaScript and an unterminated
        # script tag as TypeScript, and which one won came down to the alphabetical order of
        # the language names.
        #
        # What it costs, stated because it is a real cost: genuine JSX held in a Python
        # string is named markup. The block is unexamined content either way and only the
        # name is wrong, which is the direction to be wrong in.
        if any(n.type == "element" for n in rules.walk(wrapper)):
            return [{"language": _MARKUP, "line": line, "lines": text.count("\n") + 1,
                     "findings": [], "text": text, "also_accepted_by": []}]

    accepted = _accepted_by(text, own)
    if not accepted:
        return []
    # The name is a pick among candidates, and the candidates travel with it. Counting them
    # was tried first, on the theory that many acceptors means the name is a coin flip: two
    # one-line functions are taken whole by five grammars, and naming that block `c` gave a
    # finding whose symbols read "function, function". But a REAL embedded widget is taken
    # by three, csharp among them, so any cut that refused the five refused the widget too,
    # and the widget is the case this field exists for.
    #
    # So the pick stands and the ambiguity is disclosed beside it rather than acted on. A
    # missed widget is the silence this was built to stop; a finding under a doubtful name
    # is noise a reader can discount, once they are told.
    language = accepted[0]
    return [{"language": language, "line": line,
             "lines": text.count("\n") + 1, "findings": [], "text": text,
             "also_accepted_by": accepted[1:]}]


def _docstrings(tree: ast.AST) -> set[int]:
    """The string constants this file declares as documentation.

    Skipped, because a docstring IS declared documentation and source inside one is an
    example rather than shipped content. It is also where nearly all the cost was: 342 of
    this package's 355 long string literals are docstrings and not one of its eleven real
    embedded blocks is, so trying nine grammars on each of them bought nothing and cost
    25 milliseconds a file.

    The limit, stated because its failure mode is silence: a template genuinely held in a
    docstring is missed."""
    declared: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)) or not body:
            continue
        first = body[0]
        if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            declared.add(id(first.value))
    return declared


def _accepted_by(text: str, own: str) -> list[str]:
    """Every grammar OTHER than the file's own that takes this text whole, in name order.

    A parse with no error node and some named structure in it. tree-sitter accepts almost
    anything and reports the trouble as error nodes rather than as a failure, so the absence
    of them is the test.

    The LIST rather than a winner, because the count is the evidence. Returning one name
    made "nothing accepted this" and "everything accepted this" the same answer, and they
    are opposite facts: the first is not a block at all, the second is a block whose name
    nobody can know.

    Markup is not tried here. Its caller tries it first and goes one grammar deeper when it
    finds an element, because it is the most permissive grammar in this set and would
    otherwise claim blocks a stricter one should have."""
    return [language for language in sorted({*_VOCABULARY, _STYLESHEET} - {own})
            if (root := _accepts_whole(text, language)) is not None
            and root.named_child_count]


def _markup_parts(root: "Node", text: str) -> list[tuple[str, int]]:
    """The text inside each script and style element, with the line each starts on.

    Found by NODE TYPE. Nothing is stripped and nothing is matched by pattern: a wrapper
    removed by hand is the guess this whole test exists to avoid, so the markup grammar has
    to accept the block whole first and the element is then located the way the grammar
    names it.

    The line travels with the text because a reader given the block's own line has to search
    for the element inside it, and two elements would carry the same one."""
    raw = text.encode()
    parts: list[tuple[str, int]] = []
    for node in rules.walk(root):
        if node.type not in _EMBEDDING_ELEMENTS:
            continue
        for child in node.children:
            if child.type == "raw_text":
                inner = raw[child.start_byte:child.end_byte].decode(errors="replace")
                parts.append((inner, child.start_point[0]))
    return sorted(parts, key=lambda part: part[1])


def _accepts_whole(text: str, language: str) -> "Node | None":
    """The root a grammar produced, when it accepted the WHOLE text with no error node.

    None means one thing only: that grammar read the text and rejected it. A language with
    no grammar here raises, because a caller cannot tell a rejection from an absence and the
    absence is the expensive one. It makes every block in that language vanish, so the file
    reports nothing unexamined and the share claims to cover what it never read."""
    root = _grammar_root(text, language)
    if any(n.type == "ERROR" or n.is_missing for n in rules.walk(root)):
        return None
    return root


def _grammar_root(text: str, language: str) -> "Node":
    """One parse, by whichever grammar owns this language.

    The clause vocabulary is asked first. Markup and stylesheets are not in it, because
    that table is what tells a clause it can read a language and no clause reads these."""
    if language in _VOCABULARY:
        return read_tree(text, language)["root"]

    return Parser(GRAMMARS[language]).parse(text.encode()).root_node


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
    for block in assessment["unexamined"]:
        # The language is named only where the findings corroborate it. A block that fires
        # nothing may well not be the language a grammar accepted it as: twelve lines of SQL
        # are accepted whole by the ruby grammar, there is no SQL grammar, and a database
        # driver holds dozens of them. Printing that guess dozens of times teaches a reader
        # to skip the field, which costs the embedded-widget case it exists for.
        if not block["findings"]:
            lines += [(f"> line {block['line']}: {block['lines']} lines are not this file's "
                       "language. Every clause that could read them found nothing, and they "
                       "are outside the share above either way."), ""]
            continue
        lines += [(f"> line {block['line']}: {block['lines']} lines of {block['language']} "
                   f"that the share above does not cover. {len(block['findings'])} finding(s) "
                   "in them:"), ""]
        for finding in block["findings"]:
            lines.append(f"- `{finding['clause']}:{finding['line']}` — {finding['detail']}")
        lines.append("")

    broken = [c for c in assessment["clauses"] if c["decided"] and c["findings"]]
    held = [c for c in assessment["clauses"] if c["decided"] and not c["findings"]]
    undecided = [c for c in assessment["clauses"] if not c["decided"]]
    declared = [a for c in assessment["clauses"] for a in c["allowed"]]
    by_declaration = [a for c in assessment["clauses"] for a in c["declared"]]

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
    if declared:
        lines += [f"## declared exceptions ({len(declared)})", "",
                  ("> Sites the author stated a reason for. They are not violations and "
                   "they are not invisible: a reader audits the reason here."), ""]
        for entry in declared:
            lines.append(f"- `{entry['clause']}:{entry['line']}` — {entry['reason']}")
        lines.append("")
    if by_declaration:
        lines += [f"## boundary declarations ({len(by_declaration)})", "",
                  ("> Sites a boundary decorator withheld. The declaration overrode this "
                   "reader's call-graph inference, which is the case worth seeing; a "
                   "declaration that agreed with it withheld nothing and is not listed."), ""]
        for entry in by_declaration:
            lines.append(f"- `{entry['symbol']}:{entry['line']}` — {entry['detail']}")
        lines.append("")
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
    for block in assessment["unexamined"]:
        # A block that fires nothing is not worth an agent's attention mid-edit. It was read
        # by every clause that could read it and they found nothing, and the language it was
        # named as may well be wrong: a database driver's SQL is accepted whole by the ruby
        # grammar and there is no SQL grammar. Printing that guess on every query is what
        # teaches an agent to skip the output.
        for finding in block["findings"]:
            lines.append(f"{name}:{finding['line']} {finding['clause']} "
                         f"in embedded {block['language']}: {finding['detail']}")
            lines.append(f"    instead: {finding['instead']}")
    for clause in assessment["clauses"]:
        for finding in clause["findings"]:
            lines.append(f"{name}:{finding['line']} {clause['code']} {finding['detail']}")
            lines.append(f"    instead: {finding['instead']}")
    return "\n".join(lines)


def _named_under(repo: Path, path: Path) -> str:
    """One file's name, relative to the repository being audited.

    The same string however the caller spelled the repository. `analyze` reported
    `tools/x/y.py` when handed `.` and `/Users/.../tools/x/y.py` when handed the same
    directory absolutely, and every consumer keys findings on that string, so one file read
    as two and a rule tracked across runs looked like it had moved rather than persisted.

    Relative rather than resolved, because that is the only spelling stable across machines
    as well as across callers. An absolute path also names one file, and names a different
    one on the next machine.

    A path outside the repository keeps the spelling it arrived with. Nothing here produces
    one, and inventing a name for it would be worse than saying what was read."""
    try:
        return str(path.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(path)


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
    declared_exceptions: list[Allowed] = []
    boundary_declarations: list[Allowed] = []
    unreadable = 0
    unexamined_blocks_seen = 0
    for read, wanted in ((production, False), (tests, True)):
        for path, text in read:
            assessed = assess_file_text(text, _named_under(repo, path))
            if wanted is False and assessed["unreadable_reason"]:
                unreadable += 1
            if wanted is False:
                unexamined_blocks_seen += len(assessed["unexamined"])
            for clause in assessed["clauses"]:
                if (clause["code"] in TEST_SCOPED) != wanted or not clause["decided"]:
                    continue
                decided.add(clause["code"])
                declared_exceptions += clause["allowed"]
                boundary_declarations += clause["declared"]
                if clause["findings"]:
                    broken.setdefault(clause["code"], []).extend(clause["findings"])

    files = production + tests
    never_decided = sorted({c["code"] for c in CLAUSES} - decided)
    if not decided:
        nothing = ("no file here could be measured against any clause, so there is no "
                   "conformity to report. Not decided: " + ", ".join(never_decided))
        return {"value": "n/a", "band": "n/a", "details": nothing,
                "findings": [], "undecided": never_decided,
                "allowed": declared_exceptions, "declared": boundary_declarations,
                "unreadable_files": unreadable, "unexamined": unexamined_blocks_seen}

    share = round((len(decided) - len(broken)) / len(decided) * 100, 1)
    # The count is stated even when it is zero, and with no conditional anywhere in the
    # sentence. Writing the clause only when there were some published an empty string into
    # `details`, so a reader saw nothing where a reading belongs; spelling the plural with
    # a conditional then published a bare "s" the same way. Both were convictions the
    # vacuity check was right to make, and the repair for each is to stop branching.
    detail = (f"{len(decided) - len(broken)} of {len(decided)} decided clauses hold across "
              f"{len(files)} files. Declared exceptions: {len(declared_exceptions)}. "
              f"{unreadable} file(s) could not be read. "
              f"{len(boundary_declarations)} boundary declaration"
              f"{'' if len(boundary_declarations) == 1 else 's'} withheld a finding. "
              f"{unexamined_blocks_seen} block"
              f"{'' if unexamined_blocks_seen == 1 else 's'} of another language were not "
              "examined. "
              f"Not decided ({len(never_decided)}): " + ", ".join(never_decided))
    return {"value": share, "band": band_of(share), "details": detail,
            "findings": [f for group in broken.values() for f in group],
            "undecided": never_decided, "allowed": declared_exceptions,
            "declared": boundary_declarations, "unreadable_files": unreadable,
            "unexamined": unexamined_blocks_seen}
