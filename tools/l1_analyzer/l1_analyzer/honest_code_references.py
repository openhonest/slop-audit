"""References Resolve Statically: an emitted reference with nothing at the other end.

The principle, from the canon: every identifier a rendered artifact names is a reference
across a boundary. An `hx-get` names a route, a `class` names a stylesheet rule, an include
names a template. Asserting the artifact contains the string proves it was written, not that
it resolves, so two green tests can describe a button and a menu that never connect.

Two of the three are decidable from the repository alone and this clause decides those two.
A template naming a file that is not there. A class attribute naming a rule no stylesheet
defines.

The third is not, and saying so is the point. Where a project declares its routes is a
convention this reader does not know, and a guess would report every link in every
repository whose framework we guessed wrong.

This reads whole files rather than one parsed source, because a reference and its definition
are in different files by construction. That is what makes it the only clause here taking a
repository, and it is also why it cannot be decided from a single file the way the others
are: a page alone cannot say whether the rule it names exists.
"""

import re
from pathlib import Path

from l1_analyzer.boundary import boundary
from l1_analyzer.honest_code_read import Finding, _finding

# How a template names another template. Three directives across the engines that spell it
# this way, and the file it names is the quoted string after the word.
_NAMES_A_TEMPLATE = re.compile(
    r"\{%-?\s*(?:include|extends|import|from)\s+[\"']([^\"']+)[\"']")

# A class attribute, and the rules a stylesheet defines. Both plain enough to read without a
# grammar: the attribute is quoted and a rule begins with a dot.
_CLASS_ATTRIBUTE = re.compile(r"""\bclass\s*=\s*["']([^"']+)["']""")
_DEFINES_A_RULE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")

_PAGES = (".html", ".htm", ".jinja", ".jinja2", ".j2")
_STYLESHEETS = (".css", ".scss", ".sass", ".less")

# Directories holding somebody else's code or this run's leavings, by NAME rather than as
# text with slashes, so the answer does not depend on how the caller spelled the path.
_NOT_OURS = frozenset({".venv", "venv", "node_modules", ".git", "__pycache__",
                       ".pytest_cache", "site-packages", "build", "dist", "target"})


def ours(path: Path) -> bool:
    """Whether a file is this repository's own rather than a dependency's."""
    return not (set(path.parts) & _NOT_OURS)


def pages_and_stylesheets(repo: Path) -> tuple[list[Path], list[Path]]:
    """The rendered artifacts and the stylesheets they can resolve against.

    Both together, because neither is a finding on its own: a page with no stylesheet
    anywhere has nothing to resolve a class against, and reporting every class in it would
    be a finding about this reader."""
    pages, sheets = [], []
    for found in repo.rglob("*"):
        if not found.is_file() or not ours(found):
            continue
        if found.suffix.lower() in _PAGES:
            pages.append(found)
        elif found.suffix.lower() in _STYLESHEETS:
            sheets.append(found)
    return sorted(pages), sorted(sheets)


def rules_defined_in(stylesheets: list[str]) -> set[str]:
    """Every class name these stylesheets define, decided from their text.

    Takes the text rather than the paths. Reading them here put a disk under the decision,
    and this package's own rule about I/O at the boundary said so on the first run: every
    test of what counts as a defined rule had to build a directory to ask."""
    defined: set[str] = set()
    for sheet in stylesheets:
        defined |= set(_DEFINES_A_RULE.findall(sheet))
    return defined


@boundary
def boundary_in_text_of(paths: list[Path]) -> list[str]:
    """Read these files, and decide nothing. One unreadable file contributes nothing rather
    than stopping the rest."""
    texts: list[str] = []
    for path in paths:
        try:
            texts.append(path.read_text(errors="ignore"))
        except OSError:
            continue
    return texts


def templates_named_in(text: str) -> list[str]:
    """Every template this one names, in the order it names them."""
    return _NAMES_A_TEMPLATE.findall(text)


# An attribute the template computes rather than writes out. Either mark makes the whole
# attribute undecidable, because what it renders to depends on values this reader does not
# have.
_COMPUTED = ("{{", "{%", "${", "<%")


def classes_named_in(text: str) -> list[str]:
    """Every class name this page writes out, from the attributes it writes out.

    A single attribute holds several names separated by spaces, and each is its own
    reference. An attribute the template computes is refused WHOLE. Dropping only the
    fragments carrying a brace left the pieces between them standing as class names, and the
    first run on this package reported thirty-two of those: `card.status`, `lower`, a pipe
    and a pair of closing braces, each reported as a rule no stylesheet defines. A computed
    class cannot be resolved without rendering the page, and not rendering it is the point.

    An attribute beside a computed one is still read: refusing one must not silence the
    rest of the file."""
    named: list[str] = []
    for attribute in _CLASS_ATTRIBUTE.findall(text):
        if any(mark in attribute for mark in _COMPUTED):
            continue
        named += [part for part in attribute.split() if part]
    return named


def a_template_exists(named: str, page: Path, repo: Path) -> bool:
    """Whether a named template is somewhere a template engine would find it.

    Beside the page that names it, or under any directory between the page and the root.
    Where an engine looks is configuration this reader does not have, so it accepts any of
    them: a false yes leaves one reference unchecked, and a false no reports a template that
    is there, which sends a reader to fix nothing."""
    here = page.parent
    while True:
        if (here / named).is_file():
            return True
        if here == repo or repo not in here.parents:
            return False
        here = here.parent


def unresolved_references(repo: Path) -> list[Finding] | None:
    """Every emitted reference this reader can resolve, that resolves to nothing.

    Takes the repository rather than one parsed source, because a reference and the thing it
    names are in different files by construction. A page on its own cannot say whether the
    rule it names exists, so a clause reading one file could not decide this at all.

    Not decided for a repository with no rendered artifact: it was not measured against a
    rule about rendered artifacts, and an empty list would say it was read and found clean.

    Not decided for a route. Where a project declares its routes is a convention this reader
    does not know, and every `hx-get`, `href` and `action` is therefore passed over rather
    than resolved against a guess.

    Not decided for a class a stylesheet builds rather than writes. A rule assembled by a
    preprocessor, or emitted by a utility framework that generates rules on demand, is not in
    any file here, so a page naming one is left alone only when some stylesheet exists to
    resolve against; where none does, no class is decided at all."""
    pages, sheets = pages_and_stylesheets(repo)
    if not pages:
        return None
    defined = rules_defined_in(boundary_in_text_of(sheets))
    found: list[Finding] = []
    for page, text in zip(pages, boundary_in_text_of(pages), strict=False):
        where = str(page.relative_to(repo)) if repo in page.parents else str(page)
        for named in templates_named_in(text):
            if not a_template_exists(named, page, repo):
                found.append(_finding(
                    "L1.21.21", named, 1,
                    f"{where} names the template `{named}`, which resolves to nothing here",
                    "point it at a template that exists, or make the page and the template "
                    "from one declaration so they cannot disagree", ""))
        if not sheets:
            continue
        for named in classes_named_in(text):
            if named not in defined:
                found.append(_finding(
                    "L1.21.21", named, 1,
                    f"{where} names the class `{named}`, which resolves to nothing: no "
                    "stylesheet here defines a rule for it",
                    "add the rule to a stylesheet, or generate the markup and the "
                    "stylesheet from one declaration so they cannot disagree", ""))
    return found
