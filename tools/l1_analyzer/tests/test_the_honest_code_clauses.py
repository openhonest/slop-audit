"""L1.21's nineteen clause checkers, one per Honest Code principle.

The numbering is the Honest Framework's, so a clause number means one thing across every
Open Honest artifact.

Every checker is a pure function of a parsed source. That matters more here than anywhere
else in this tool: a conformity score is only worth having if each finding can be read at
the site, and a checker that had to run something could not be put behind a hook that fires
on every write.

The tests come in pairs on purpose. One says what the clause FINDS, and one says what it
leaves alone, because a clause that fires on everything is as useless as one that fires on
nothing. Rule 11's own warning applies to this file: an ordinary conditional is not a
dispatch chain, and counting it as one would teach a reader to ignore the number.
"""

import ast

import pytest
from l1_analyzer import honest_code_edges as edges
from l1_analyzer import honest_code_python_rules as python_rules
from l1_analyzer import honest_code_read as read
from l1_analyzer import honest_code_rules as rules


def _tree(text: str) -> dict:
    """A source read through the shared node vocabulary, which the ported clauses read.

    The cases below it are the ones a second language would spell identically or not at all,
    so they stayed here when their clause moved. The both-direction fixtures live in
    test_a_clause_means_the_same_in_every_language.py."""
    return read.read_tree(text, "python")


def _module(text: str) -> dict:
    """The commonest case, named rather than defaulted. `_source` used to supply the path
    and the language itself, and this file's own clause 14 said so."""
    return _source(text, "m.py", "python")


def _source(text: str, path: str, language: str) -> dict:
    """A parsed source, as the runner builds one.

    Only Python is parsed into a tree. The two browser clauses read the text, because this
    tool has no JavaScript parser it could hand them and pretending otherwise would put an
    empty tree where a reader expects a parsed one."""
    return {"path": path, "language": language, "text": text,
            "tree": ast.parse(text) if language == "python" else ast.parse(""),
            "readable": True, "unreadable_reason": ""}


# --------------------------------------------------------------------------
# 1, 2 and 3. Dict-lookup polymorphism, TypedDicts over classes, pure functions over methods
#
# Their cases live in test_a_clause_means_the_same_in_every_language.py now. All three read
# the shared node vocabulary, so their fixtures have to run in every language that
# vocabulary covers and assert both directions in each, which the cases here could not do.
#
# Clauses 2 and 3 moved together because they read the same four shapes:
# the classes, the definitions in each, the constructor among those, and whether a method
# reaches the receiver for more than data. Porting one and leaving the other would have put
# two readings of "a method touches self" in this package.
#
# The declared shapes Python spells stayed in test_the_project_declares_its_own_shapes.py,
# beside the exception root that file is about.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 4. I/O at the boundary
# --------------------------------------------------------------------------

def test_io_in_a_function_a_sibling_calls_is_found():
    """The I/O has been pushed inward: `price` cannot be tested without a filesystem, and
    `total` cannot be tested without mocking one."""
    found = edges.io_below_the_boundary(_tree(
        "def price(path):\n    return int(path.read_text())\n\n\n"
        "def total(path):\n    return price(path) * 2\n"))
    assert [f["symbol"] for f in found] == ["price"]


def test_io_in_an_entry_point_is_the_boundary():
    """Nothing in the module calls it, so it IS the edge, which is where the I/O belongs."""
    assert edges.io_below_the_boundary(_tree(
        "def load(path):\n    return path.read_text()\n")) == []


# --------------------------------------------------------------------------
# 5. Flat composition over inheritance
#
# Its cases live in test_a_clause_means_the_same_in_every_language.py now, for the same
# reason clause 1's did: it reads the shared node vocabulary, so its fixtures have to run
# in every language that vocabulary covers and assert both directions in each. The cases
# for a root this project declares for itself stayed in
# test_the_project_declares_its_own_shapes.py, because only Python spells that root.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 6 and 7. The two browser clauses
# --------------------------------------------------------------------------

def test_a_store_library_in_a_browser_file_is_found():
    found = rules.client_side_state(_source(
        "import { createStore } from 'redux';\nconst store = createStore(reducer);\n",
        path="app.js", language="javascript"))
    assert found


def test_the_browser_clauses_are_not_applicable_to_a_python_file():
    """Not applicable is a third answer beside pass and fail. A Python file has no DOM to
    keep a second copy of state in, and reporting it clean would count a question nobody
    asked as a question answered."""
    source = _module("def f(n: int) -> int:\n    return n\n")
    assert rules.client_side_state(source) is None
    assert rules.imperative_dom(source) is None


def test_driving_the_dom_by_hand_is_found():
    found = rules.imperative_dom(_source(
        "document.querySelector('#x').addEventListener('click', go);\n",
        path="app.js", language="javascript"))
    assert found


# --------------------------------------------------------------------------
# 8. Typed exceptions at the boundary
# --------------------------------------------------------------------------

@pytest.mark.parametrize("body", ["pass", "return None", "return []", "return 0"])
def test_a_handler_that_swallows_is_found(body):
    found = edges.swallowed_exceptions(_tree(
        f"def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        {body}\n"))
    assert found, body


def test_a_handler_that_reraises_is_left_alone():
    assert edges.swallowed_exceptions(_tree(
        "def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        raise\n")) == []


def test_a_handler_that_maps_the_error_is_left_alone():
    """The boundary catching and turning the type into a response is the rule, not the
    violation."""
    assert edges.swallowed_exceptions(_tree(
        "def route(x):\n    try:\n        return g(x)\n"
        "    except ValueError as error:\n        return respond(400, str(error))\n")) == []


# --------------------------------------------------------------------------
# 9. SQL over application caches
# --------------------------------------------------------------------------

def test_a_memoising_decorator_is_found():
    found = python_rules.unmeasured_caches(_module(
        "from functools import lru_cache\n\n\n@lru_cache\ndef price(sku):\n    return query(sku)\n"))
    assert found


def test_the_cache_clause_says_what_it_cannot_see():
    """Whether anyone profiled the query first is not in any file. The clause reports the
    cache and names the half it cannot decide, rather than implying the whole rule was
    checked."""
    found = python_rules.unmeasured_caches(_module(
        "import redis\n\n\ndef price(sku):\n    return redis.get(sku)\n"))
    assert found
    assert "profil" in found[0]["undecided"].lower()


def test_a_file_with_no_cache_finds_nothing():
    assert python_rules.unmeasured_caches(_module("def price(sku):\n    return query(sku)\n")) == []


# --------------------------------------------------------------------------
# 10. Pure-function assertions over mocks
# --------------------------------------------------------------------------
# 10. Pure function assertions over mocks
#
# Ported to the shared node vocabulary, so all three cases moved to
# test_a_clause_means_the_same_in_every_language.py, where they are asserted for Python and
# for the five other languages that can now decide the clause.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 11. Trust the contract in the interior
#
# Ported to the shared node vocabulary, so both cases moved to
# test_a_clause_means_the_same_in_every_language.py where they are asserted for Python and
# for the four other languages that can now decide the clause.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 12. Context managers over instance state
#
# Ported to the shared node vocabulary, so both cases moved to
# test_a_clause_means_the_same_in_every_language.py, where they are asserted for Python and
# for the five other languages that can now decide the clause.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 13. Configuration as parameters
# --------------------------------------------------------------------------

# Its cases live in test_a_clause_means_the_same_in_every_language.py now. The clause reads
# the shared node vocabulary, and every case it carried is about a write and a read rather
# than about anything Python spells.


# --------------------------------------------------------------------------
# 14. No implicit defaults
# --------------------------------------------------------------------------

# Its cases live in test_a_clause_means_the_same_in_every_language.py now. The clause reads
# the shared node vocabulary, and the kinds of literal it must catch are the same kinds in
# every language that has default parameters at all.


# --------------------------------------------------------------------------
# 15. Simple gherkin steps
# --------------------------------------------------------------------------

def test_a_step_carrying_thirty_lines_of_setup_is_found():
    body = "\n".join(f"    line_{n} = {n}" for n in range(31))
    found = python_rules.heavy_step_definitions(_source(
        f"@given('a user')\ndef step(context):\n{body}\n", path="test_steps.py", language="python"))
    assert found


def test_a_step_that_calls_and_checks_is_left_alone():
    assert python_rules.heavy_step_definitions(_source(
        "@when('it runs')\ndef step(context):\n    context.result = band(20)\n",
        path="test_steps.py", language="python")) == []


# --------------------------------------------------------------------------
# 16. Declarative equivalents over framework lifecycle hooks
#
# Ported to the shared node vocabulary, so all six cases moved to
# test_a_clause_means_the_same_in_every_language.py, where they are asserted for Python and
# for the four other languages that can now decide the clause.
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# 17. Strangler pattern — the clause nothing decides
# --------------------------------------------------------------------------

def test_the_strangler_clause_never_returns_a_verdict():
    """It is a property of how work is sequenced over weeks. No file, and no set of files,
    carries the sequence of the work that produced them, so a pass here would be a claim
    nobody could support.

    It used to say so by returning None, which a caller cannot tell from a clause that ran
    and found nothing. The refusal is loud now, and the two tests below say why: the gate
    answers before this is reached, so reaching it is itself the defect."""
    with pytest.raises(NotImplementedError):
        python_rules.strangler_migration(_module("def f(n: int) -> int:\n    return n\n"))


# --------------------------------------------------------------------------
# 18. Dispatch tables close open input
# --------------------------------------------------------------------------

# Its cases live in test_a_clause_means_the_same_in_every_language.py now. The clause reads
# the shared node vocabulary. Two languages pass the fallback as an argument and two put it
# to the right of the lookup as an operator, so a fixture in one language alone would leave
# half the rule unmeasured.


# --------------------------------------------------------------------------
# 19. Atomic test-and-set over check-then-act
# --------------------------------------------------------------------------

# Its cases live in test_a_clause_means_the_same_in_every_language.py now. The clause reads
# the shared node vocabulary, and a read followed by a write of something two callers share
# is the same race in every language that has one.

# --------------------------------------------------------------------------
# What the clauses learned from being pointed at themselves
# --------------------------------------------------------------------------
# When the catch IS the assertion
# --------------------------------------------------------------------------

def test_a_catch_that_is_the_assertion_is_not_a_swallow():
    """Reported from real work, and the diagnosis is exact. The call is EXPECTED to raise.
    The statement after it records a failure and runs only if it did NOT raise, so the
    `except ... pass` is the SUCCESS condition and the defect would be reaching the append.

    Keying on the bare `pass` is what made both readings look alike. The last statement of
    the try is what separates them."""
    source = ("def check(bad):\n"
              "    try:\n"
              "        startup_check(path, on_error='raise')\n"
              "        bad.append('startup_check should have raised')\n"
              "    except HonestCheckError:\n"
              "        pass\n")
    assert edges.swallowed_exceptions(_tree(source)) == []


@pytest.mark.parametrize("recorder", [
    "bad.append('should have raised')",
    "failures.add('should have raised')",
    "problems.extend(['should have raised'])",
    "pytest.fail('should have raised')",
    "assert False, 'should have raised'",
    "raise AssertionError('should have raised')",
])
def test_the_shapes_that_count_as_recording_a_failure(recorder):
    source = (f"def check(bad):\n    try:\n        risky()\n        {recorder}\n"
              "    except ValueError:\n        pass\n")
    assert edges.swallowed_exceptions(_tree(source)) == [], recorder


def test_a_try_whose_last_statement_does_not_record_a_failure_is_still_a_swallow():
    """The distinction has to cut. A try that ends in ordinary work and then discards the
    error is the shape the clause exists for."""
    source = ("def load(path):\n    try:\n        raw = path.read_text()\n"
              "        return parse(raw)\n    except ValueError:\n        pass\n")
    assert edges.swallowed_exceptions(_tree(source))


def test_a_single_statement_try_is_still_a_swallow():
    """There is no statement after the call, so nothing records a failure and nothing makes
    the catch an assertion."""
    source = "def load(p):\n    try:\n        return parse(p)\n    except ValueError:\n        pass\n"
    assert edges.swallowed_exceptions(_tree(source))


@pytest.mark.parametrize("signal", ["SystemExit", "KeyboardInterrupt", "GeneratorExit"])
def test_a_control_flow_signal_is_not_an_error_this_clause_names(signal):
    """`except SystemExit: pass` around `cli_main(["--help"])` is argparse's normal exit for
    help, so it is the expected terminal state of the thing under test rather than a
    failure going somewhere to be forgotten.

    What this does NOT decide: a program that swallows an exit it did not intend has a real
    defect, and it is a different one from the silent failure this clause names."""
    source = f"def probe():\n    try:\n        cli_main(['--help'])\n    except {signal}:\n        pass\n"
    assert edges.swallowed_exceptions(_tree(source)) == []


def test_an_ordinary_exception_is_still_caught_by_the_clause():
    source = "def probe():\n    try:\n        cli_main(['--help'])\n    except ValueError:\n        pass\n"
    assert edges.swallowed_exceptions(_tree(source))


def test_the_clause_nothing_decides_is_never_asked():
    """`_skip_reason` answers `never` for clause 17 before any checker runs, so its body is
    unreachable during a normal assessment. A stub checker flagged the empty return and was
    right for a better reason than it knew: not unwritten, never run."""
    from l1_analyzer import honest_code

    asked = []
    original = honest_code.CLAUSES
    honest_code.CLAUSES = tuple(
        {**c, "check": lambda _source, code=c["code"]: asked.append(code)}
        if c["code"] == "L1.21.17" else c
        for c in original)
    try:
        honest_code.assess(honest_code.read_source_text("def f(n: int) -> int:\n    return n\n",
                                                        "m.py"))
    finally:
        honest_code.CLAUSES = original
    assert asked == []


def test_reaching_the_clause_nothing_decides_is_itself_a_defect():
    """It returned None, which reads to a caller exactly like a clause that ran and found
    nothing. Reaching it means the gate that answers `never` has stopped working, and a
    silent None would let that failure arrive somewhere else as a clean result."""
    with pytest.raises(NotImplementedError):
        python_rules.strangler_migration(_module("def f(n: int) -> int:\n    return n\n"))
