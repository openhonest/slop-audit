"""The declaration in the clause table, checked against the code the clause actually runs.

Clauses 2 and 3 were ported to the shared node vocabulary, their cross-language fixtures
passed in both languages, and the analyzer still reported them "not decided" on every
JavaScript file. The port was complete; the table still said the clause read Python's own
parser, and nothing asked the two to agree.

That is the defect this package has now found six times: a value with two owners and
nothing checking they agree. The reader is one fact stored twice, once in `CLAUSES` and
once in the function body. Deriving it at runtime from the function's names would be magic
nobody could read, so it stays declared and this file is what makes the two agree.

The evidence is the clause's own bytecode. The declaration `tree` means the clause reads
through the shared node vocabulary, and the vocabulary IS `source["spec"]`, so naming it is
the exact marker. `root` is not: it is an ordinary word for the first part of a dotted name,
and clause 16 uses it that way. The first draft of this file reported that clause as
mis-declared, which is the false positive a marker chosen for looking right rather than for
being exact will always produce.
"""

from l1_analyzer.honest_code import (
    _NOTHING,
    _PYTHON_AST,
    _REPOSITORY,
    _TEXT_READER,
    _TREE_READER,
    CLAUSES,
)


def _names(check) -> set[str]:
    """Every name the function and its own nested code objects mention.

    The string constants count, and they are the ones that matter. A clause reaches its
    reader by subscript, `source["spec"]`, and a subscript key is a constant rather than a
    name. Reading only `co_names` reported a clause that reads nothing at all.

    Nested code objects matter too: a clause whose whole reading happens inside a
    comprehension keeps those names one level down."""
    from types import CodeType

    def of(code: CodeType) -> set[str]:
        found = set(code.co_names) | set(code.co_varnames)
        for const in code.co_consts:
            if isinstance(const, str):
                found.add(const)
            elif isinstance(const, CodeType):
                found |= of(const)
        return found

    return of(check.__code__)


def test_every_clause_that_says_it_reads_the_tree_reaches_for_the_shared_vocabulary():
    """The failure that prompted this file, in the direction it failed."""
    wrong = [c["code"] for c in CLAUSES if c["reads"] == _TREE_READER
             and "spec" not in _names(c["check"])]
    assert wrong == [], (
        f"{wrong} are declared to read the shared vocabulary and never name its spec")


def test_every_clause_that_says_it_reads_pythons_parser_reaches_for_the_parsed_tree():
    """The direction clauses 2 and 3 failed in. Both had been ported and neither said so,
    so the analyzer reported them undecided on every file that was not Python."""
    wrong = [c["code"] for c in CLAUSES if c["reads"] == _PYTHON_AST
             and "spec" in _names(c["check"])]
    assert wrong == [], (
        f"{wrong} read the shared vocabulary and are still declared python-ast, so every "
        "language but Python is told nobody decided them")


def test_every_clause_that_says_it_reads_the_text_reaches_for_the_text():
    """The two browser clauses. They work on a language this package has no parser for,
    which is the whole reason they are declared apart."""
    wrong = [c["code"] for c in CLAUSES if c["reads"] == _TEXT_READER
             and "text" not in _names(c["check"])]
    assert wrong == [], f"{wrong} are declared to read the text and never name it"


def test_every_clause_declares_one_of_the_five_readers():
    """A sixth spelling would pass every test above by matching none of them.

    The fourth is `nothing`, and it earns its place: a clause that decides nothing reads
    nothing, and naming a parser there stated a capability the clause never uses. The
    undecided disclosure read that name as a port we owe, so a JavaScript repository was
    promised work on a clause that cannot be written."""
    readers = {_PYTHON_AST, _TREE_READER, _TEXT_READER, _NOTHING, _REPOSITORY}
    assert {c["reads"] for c in CLAUSES} <= readers


def test_a_clause_reading_the_repository_says_why_one_file_cannot_decide_it():
    """The fifth reader, added when References Resolve Statically got a clause. A reference
    and the thing it names are in different files by construction, so a page on its own
    cannot say whether the rule it names exists. Tying the reader to that sentence is what
    stops it becoming the quiet way past every guard in this file."""
    import inspect
    for clause in CLAUSES:
        if clause["reads"] != _REPOSITORY:
            continue
        taken = list(inspect.signature(clause["check"]).parameters)
        assert taken == ["repo"], (clause["code"], taken)
        assert "different files" in (clause["check"].__doc__ or ""), clause["code"]


def test_only_a_clause_that_decides_nothing_may_read_nothing():
    """The fourth spelling is the one a clause could hide behind: it matches no test above,
    so a checker declared this way is exempt from every guard in this file. Tying it to what
    the clause decides is what stops it being the quiet way out."""
    wrong = [c["code"] for c in CLAUSES
             if c["reads"] == _NOTHING and c["decides"] != _NOTHING]
    assert wrong == [], f"{wrong} read nothing and claim to decide something"
