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
from l1_analyzer import honest_code_rules as rules


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
# 1. Dict-lookup polymorphism over if/elif chains
#
# Its cases live in test_a_clause_means_the_same_in_every_language.py now. That clause
# reads the shared node vocabulary, so its fixtures have to run in every language the
# vocabulary covers and assert both directions in each, which the cases here could not do.
# --------------------------------------------------------------------------

def test_a_class_that_only_holds_data_is_found():
    found = rules.data_classes(_module(
        "class User:\n"
        "    def __init__(self, email, name):\n        self.email = email\n        self.name = name\n"
        "    def get_email(self):\n        return self.email\n"))
    assert [f["symbol"] for f in found] == ["User"]


@pytest.mark.parametrize("base", ["TypedDict", "Protocol", "Exception", "Enum", "NamedTuple"])
def test_a_declared_shape_is_not_a_data_class(base):
    """The rule allows exactly these. Flagging them would flag the recommended alternative."""
    assert rules.data_classes(_module(
        f"class User({base}):\n    email: str\n    name: str\n")) == []


def test_a_class_wrapping_a_resource_is_left_alone():
    """Acceptable when it wraps a stateful external resource, in the rule's own words."""
    assert rules.data_classes(_module(
        "class Pool:\n"
        "    def __init__(self, dsn):\n        self.conn = connect(dsn)\n"
        "    def close(self):\n        self.conn.close()\n")) == []


# --------------------------------------------------------------------------
# 3. Pure functions over methods
# --------------------------------------------------------------------------

def test_a_method_that_only_reads_self_is_found():
    found = rules.methods_wearing_a_class(_module(
        "class User:\n"
        "    def validate(self):\n        return len(self.email) > 3\n"))
    assert [f["symbol"] for f in found] == ["User.validate"]


def test_a_method_that_writes_self_is_left_alone():
    """It is doing something a free function taking the data could not."""
    assert rules.methods_wearing_a_class(_module(
        "class Counter:\n"
        "    def bump(self):\n        self.n = self.n + 1\n")) == []


def test_a_method_that_calls_another_method_is_left_alone():
    assert rules.methods_wearing_a_class(_module(
        "class User:\n"
        "    def check(self):\n        return self.validate()\n")) == []


# --------------------------------------------------------------------------
# 4. I/O at the boundary
# --------------------------------------------------------------------------

def test_io_in_a_function_a_sibling_calls_is_found():
    """The I/O has been pushed inward: `price` cannot be tested without a filesystem, and
    `total` cannot be tested without mocking one."""
    found = rules.io_below_the_boundary(_module(
        "def price(path):\n    return int(path.read_text())\n\n\n"
        "def total(path):\n    return price(path) * 2\n"))
    assert [f["symbol"] for f in found] == ["price"]


def test_io_in_an_entry_point_is_the_boundary():
    """Nothing in the module calls it, so it IS the edge, which is where the I/O belongs."""
    assert rules.io_below_the_boundary(_module(
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
    found = rules.swallowed_exceptions(_module(
        f"def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        {body}\n"))
    assert found, body


def test_a_handler_that_reraises_is_left_alone():
    assert rules.swallowed_exceptions(_module(
        "def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        raise\n")) == []


def test_a_handler_that_maps_the_error_is_left_alone():
    """The boundary catching and turning the type into a response is the rule, not the
    violation."""
    assert rules.swallowed_exceptions(_module(
        "def route(x):\n    try:\n        return g(x)\n"
        "    except ValueError as error:\n        return respond(400, str(error))\n")) == []


# --------------------------------------------------------------------------
# 9. SQL over application caches
# --------------------------------------------------------------------------

def test_a_memoising_decorator_is_found():
    found = rules.unmeasured_caches(_module(
        "from functools import lru_cache\n\n\n@lru_cache\ndef price(sku):\n    return query(sku)\n"))
    assert found


def test_the_cache_clause_says_what_it_cannot_see():
    """Whether anyone profiled the query first is not in any file. The clause reports the
    cache and names the half it cannot decide, rather than implying the whole rule was
    checked."""
    found = rules.unmeasured_caches(_module(
        "import redis\n\n\ndef price(sku):\n    return redis.get(sku)\n"))
    assert found
    assert "profil" in found[0]["undecided"].lower()


def test_a_file_with_no_cache_finds_nothing():
    assert rules.unmeasured_caches(_module("def price(sku):\n    return query(sku)\n")) == []


# --------------------------------------------------------------------------
# 10. Pure-function assertions over mocks
# --------------------------------------------------------------------------

def test_a_test_carrying_three_mocks_is_found():
    found = rules.mock_heavy_tests(_source(
        "def test_order():\n"
        "    a = Mock()\n    b = MagicMock()\n    c = patch('x')\n"
        "    assert place(a, b, c)\n", path="test_m.py", language="python"))
    assert [f["symbol"] for f in found] == ["test_order"]


def test_a_test_with_two_mocks_is_ordinary_isolation():
    assert rules.mock_heavy_tests(_source(
        "def test_order():\n    a = Mock()\n    b = Mock()\n    assert place(a, b)\n",
        path="test_m.py", language="python")) == []


def test_the_mock_clause_only_reads_test_files():
    """A file that is not a test has no tests to count mocks in, and a production file
    naming Mock is doing something else."""
    assert rules.mock_heavy_tests(_source(
        "def build():\n    return Mock(), Mock(), Mock()\n", path="m.py", language="python")) is None


# --------------------------------------------------------------------------
# 11. Type declarations over imperative validation
# --------------------------------------------------------------------------

def test_a_check_the_signature_already_made_is_found():
    """Re-checking a value the signature types is distrust of your own contract."""
    found = rules.imperative_validation(_module(
        "def f(name: str) -> str:\n"
        "    if not isinstance(name, str):\n        raise TypeError('no')\n    return name\n"))
    assert found


def test_a_check_on_an_untyped_value_is_left_alone():
    """It arrived from outside with no contract, which is where validation belongs."""
    assert rules.imperative_validation(_module(
        "def f(payload):\n"
        "    if not isinstance(payload, dict):\n        raise TypeError('no')\n    return payload\n")) == []


# --------------------------------------------------------------------------
# 12. Context managers over instance state
# --------------------------------------------------------------------------

def test_a_resource_stored_on_self_is_found():
    found = rules.unscoped_resources(_module(
        "class Client:\n    def __init__(self, dsn):\n        self.connection = connect(dsn)\n"))
    assert [f["symbol"] for f in found] == ["Client.connection"]


def test_a_class_that_is_a_context_manager_has_scoped_it():
    assert rules.unscoped_resources(_module(
        "class Client:\n"
        "    def __enter__(self):\n        self.connection = connect(self.dsn)\n        return self\n"
        "    def __exit__(self, *a):\n        self.connection.close()\n")) == []


# --------------------------------------------------------------------------
# 13. Configuration as parameters
# --------------------------------------------------------------------------

def test_a_setting_somebody_turns_is_found():
    """The WRITE is what makes it configuration. Without one it is a fact about the world,
    and flagging that would make this clause demand the opposite of clauses 1 and 18."""
    found = rules.hidden_configuration(_module(
        "SETTINGS = {'timeout': 30}\n\n\n"
        "def configure(n):\n    SETTINGS['timeout'] = n\n\n\n"
        "def fetch(url):\n    return get(url, SETTINGS['timeout'])\n"))
    assert found


def test_a_constant_nothing_can_change_is_not_configuration():
    """Nothing about it can differ between two calls, so no caller's behaviour depends on
    something they cannot see."""
    assert rules.hidden_configuration(_module(
        "TIMEOUT = 30\n\n\ndef fetch(url):\n    return get(url, TIMEOUT)\n")) == []


# --------------------------------------------------------------------------
# 14. No implicit defaults
# --------------------------------------------------------------------------

@pytest.mark.parametrize("default", ["30", "'utf-8'", "True", "None", "[]", "{}"])
def test_a_literal_default_is_found(default):
    found = rules.implicit_defaults(_module(f"def f(x, timeout={default}):\n    return x\n"))
    assert found, default


def test_a_default_that_binds_a_collaborator_is_left_alone():
    """The opposite failure. A collaborator in the signature is a dependency made visible,
    which is what rule 13 asks for, and flagging it would push the code back toward the
    module-level lookup the rule exists to remove."""
    assert rules.implicit_defaults(_module(
        "def observe(fn, reader=describe):\n    return reader(fn)\n")) == []


# --------------------------------------------------------------------------
# 15. Simple gherkin steps
# --------------------------------------------------------------------------

def test_a_step_carrying_thirty_lines_of_setup_is_found():
    body = "\n".join(f"    line_{n} = {n}" for n in range(31))
    found = rules.heavy_step_definitions(_source(
        f"@given('a user')\ndef step(context):\n{body}\n", path="test_steps.py", language="python"))
    assert found


def test_a_step_that_calls_and_checks_is_left_alone():
    assert rules.heavy_step_definitions(_source(
        "@when('it runs')\ndef step(context):\n    context.result = band(20)\n",
        path="test_steps.py", language="python")) == []


# --------------------------------------------------------------------------
# 16. Declarative equivalents over lifecycle hooks
# --------------------------------------------------------------------------

@pytest.mark.parametrize("registration", [
    "atexit.register(cleanup)", "signal.signal(signal.SIGTERM, stop)",
])
def test_behaviour_parked_in_a_hook_is_found(registration):
    found = rules.lifecycle_hooks(_module(f"def setup():\n    {registration}\n"))
    assert found, registration


def test_a_call_at_the_place_it_happens_is_not_a_hook():
    assert rules.lifecycle_hooks(_module("def run():\n    cleanup()\n")) == []


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
        rules.strangler_migration(_module("def f(n: int) -> int:\n    return n\n"))


# --------------------------------------------------------------------------
# 18. Dispatch tables close open input
# --------------------------------------------------------------------------

def test_a_lookup_with_a_default_is_found():
    """It files an input nobody wrote a rule for under an answer written for a different
    input, and the default re-opens the space while the code still reads closed."""
    found = rules.open_dispatch(_module(
        "HANDLERS = {'a': one, 'b': two}\n\n\ndef run(kind):\n    return HANDLERS.get(kind, one)(1)\n"))
    assert found


def test_a_subscript_lets_an_unknown_key_raise():
    assert rules.open_dispatch(_module(
        "HANDLERS = {'a': one}\n\n\ndef run(kind):\n    return HANDLERS[kind](1)\n")) == []


# --------------------------------------------------------------------------
# 19. Atomic test-and-set over check-then-act
# --------------------------------------------------------------------------

def test_a_read_then_write_of_a_shared_value_is_found():
    found = rules.check_then_act(_module(
        "LOCKS = {}\n\n\ndef claim(key):\n"
        "    if key in LOCKS:\n        return False\n    LOCKS[key] = True\n    return True\n"))
    assert found


def test_an_await_between_the_two_is_named_as_certain():
    """Between the read and the write another caller reads the same answer. An await makes
    that certain rather than occasional, and the finding has to say which it found."""
    found = rules.check_then_act(_module(
        "LOCKS = {}\n\n\nasync def claim(key):\n"
        "    if key in LOCKS:\n        return False\n"
        "    await settle()\n    LOCKS[key] = True\n    return True\n"))
    assert found
    assert "certain" in found[0]["detail"]


def test_reading_a_shared_value_without_writing_it_is_not_a_race():
    assert rules.check_then_act(_module(
        "LOCKS = {}\n\n\ndef held(key):\n    return key in LOCKS\n")) == []


# --------------------------------------------------------------------------
# What the clauses learned from being pointed at themselves
# --------------------------------------------------------------------------

def test_a_dict_lookup_is_not_io():
    """`_SUFFIXES.get(suffix)` was reported as I/O below the boundary, because `get` is
    also how an HTTP client fetches a page. A bare name cannot tell the two apart, so the
    ambiguous ones are matched on the whole dotted call instead."""
    assert rules.io_below_the_boundary(_module(
        "TABLE = {'a': 1}\n\n\n"
        "def look(key):\n    return TABLE.get(key)\n\n\n"
        "def top(key):\n    return look(key)\n")) == []


@pytest.mark.parametrize("call", ["requests.get(url)", "httpx.post(url)", "session.get(url)",
                                  "subprocess.run(cmd)", "path.read_text()"])
def test_a_named_client_call_is_still_io(call):
    found = rules.io_below_the_boundary(_module(
        f"def fetch(url, cmd, path, session, requests, httpx, subprocess):\n    return {call}\n\n\n"
        "def top(*a):\n    return fetch(*a)\n"))
    assert found, call


def test_a_table_nobody_writes_is_not_hidden_configuration():
    """Clause 13 flagged every dispatch table in this tool, which would mean clause 13
    demands the opposite of clauses 1 and 18. Two clauses of one instrument must not ask
    for opposite things.

    A table nobody writes is a fact about the world. Configuration is a knob, and a knob is
    one somebody turns."""
    assert rules.hidden_configuration(_module(
        "SUFFIXES = {'.py': 'python'}\n\n\ndef language(path):\n    return SUFFIXES[path]\n")) == []


def test_a_module_level_value_a_function_writes_is_hidden_configuration():
    """Somebody turns this one, so two callers can get different behaviour for a reason
    neither of them can see at the call site."""
    found = rules.hidden_configuration(_module(
        "SETTINGS = {'timeout': 30}\n\n\n"
        "def configure(n):\n    SETTINGS['timeout'] = n\n\n\n"
        "def fetch(url):\n    return get(url, SETTINGS['timeout'])\n"))
    assert [f["symbol"].split("(")[0] for f in found] == ["fetch"]


def test_the_configuration_clause_says_what_it_cannot_see():
    """Whether a knob was disguised as a fact is not decidable from a file. The clause
    reports the tables somebody writes and names the half it cannot read."""
    found = rules.hidden_configuration(_module(
        "SETTINGS = {'t': 30}\n\n\ndef configure(n):\n    SETTINGS['t'] = n\n\n\n"
        "def fetch(u):\n    return get(u, SETTINGS['t'])\n"))
    assert found
    assert found[0]["undecided"].strip()


def test_a_handler_that_returns_a_reason_is_not_swallowing():
    """The opposite of a swallow. `return "could not query rustup toolchains"` names the
    failure and hands it to a caller that discloses it, which is what the whole of this
    tool does with an absent measurement.

    Found by pointing the clause at this repository: it flagged three handlers and one of
    them was doing exactly the right thing."""
    assert rules.swallowed_exceptions(_module(
        "def toolchains():\n    try:\n        return run(['rustup']).stdout\n"
        "    except OSError:\n        return 'could not query rustup toolchains'\n")) == []


@pytest.mark.parametrize("stand_in", ["None", "False", "0", "''", "[]", "{}"])
def test_a_handler_that_returns_a_falsy_stand_in_is_still_swallowing(stand_in):
    """A value indistinguishable from a successful empty result. The caller cannot tell
    "there were none" from "I could not look"."""
    found = rules.swallowed_exceptions(_module(
        f"def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        return {stand_in}\n"))
    assert found, stand_in


def test_a_default_derived_from_the_key_records_the_gap():
    """Rule 18's objection is that a default files an input nobody wrote a rule for UNDER
    AN ANSWER WRITTEN FOR A DIFFERENT INPUT. A default that is the key itself does the
    opposite: the unknown key comes back as itself, so it cannot be mistaken for a row
    somebody wrote, and a reader sees exactly which key had no rule.

    Three sites in this package do that deliberately, one of them with a docstring saying
    so in almost these words, and the clause was convicting all three."""
    assert rules.open_dispatch(_module(
        "COPY = {'a': 'A'}\n\n\ndef render(key):\n    return COPY.get(key, key)\n")) == []


def test_a_default_that_names_the_key_in_a_message_records_the_gap():
    assert rules.open_dispatch(_module(
        "REASONS = {2: 'interrupted'}\n\n\n"
        "def why(code):\n    return REASONS.get(code, f'unknown exit {code}')\n")) == []


def test_a_default_that_is_a_shared_constant_is_still_open():
    """`_BAND_WORD.get(band, "No data")` is the shape the rule is about: a band the card
    does not know renders identically to a band that was never measured."""
    found = rules.open_dispatch(_module(
        "WORDS = {'Healthy': 'good'}\n\n\ndef word(band):\n    return WORDS.get(band, 'No data')\n"))
    assert found


def test_a_default_naming_a_different_row_is_still_open():
    found = rules.open_dispatch(_module(
        "HANDLERS = {'a': one, 'b': two}\n\n\ndef run(kind):\n    return HANDLERS.get(kind, one)\n"))
    assert found


def test_a_decorator_that_merely_mentions_a_hook_is_not_a_hook():
    """Found by the write hook, on this very file. A `parametrize` decorator carrying the
    string "atexit.register(cleanup)" as test DATA was read as a registration, because the
    clause matched the unparsed decorator as text and the arguments are part of that text.

    What a decorator does is decided by what it calls, not by what it carries."""
    source = ("@pytest.mark.parametrize('registration', ['atexit.register(cleanup)'])\n"
              "def test_it(registration):\n    assert registration\n")
    assert rules.lifecycle_hooks(_source(source, path="test_m.py", language="python")) == []


def test_a_decorator_that_is_a_hook_registration_is_still_found():
    assert rules.lifecycle_hooks(_module(
        "@atexit.register\ndef cleanup():\n    pass\n"))


def test_a_framework_event_decorator_is_still_found():
    assert rules.lifecycle_hooks(_module(
        "@app.on_event('startup')\ndef begin():\n    pass\n"))


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
    assert rules.swallowed_exceptions(_module(source)) == []


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
    assert rules.swallowed_exceptions(_module(source)) == [], recorder


def test_a_try_whose_last_statement_does_not_record_a_failure_is_still_a_swallow():
    """The distinction has to cut. A try that ends in ordinary work and then discards the
    error is the shape the clause exists for."""
    source = ("def load(path):\n    try:\n        raw = path.read_text()\n"
              "        return parse(raw)\n    except ValueError:\n        pass\n")
    assert rules.swallowed_exceptions(_module(source))


def test_a_single_statement_try_is_still_a_swallow():
    """There is no statement after the call, so nothing records a failure and nothing makes
    the catch an assertion."""
    source = "def load(p):\n    try:\n        return parse(p)\n    except ValueError:\n        pass\n"
    assert rules.swallowed_exceptions(_module(source))


@pytest.mark.parametrize("signal", ["SystemExit", "KeyboardInterrupt", "GeneratorExit"])
def test_a_control_flow_signal_is_not_an_error_this_clause_names(signal):
    """`except SystemExit: pass` around `cli_main(["--help"])` is argparse's normal exit for
    help, so it is the expected terminal state of the thing under test rather than a
    failure going somewhere to be forgotten.

    What this does NOT decide: a program that swallows an exit it did not intend has a real
    defect, and it is a different one from the silent failure this clause names."""
    source = f"def probe():\n    try:\n        cli_main(['--help'])\n    except {signal}:\n        pass\n"
    assert rules.swallowed_exceptions(_module(source)) == []


def test_an_ordinary_exception_is_still_caught_by_the_clause():
    source = "def probe():\n    try:\n        cli_main(['--help'])\n    except ValueError:\n        pass\n"
    assert rules.swallowed_exceptions(_module(source))


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
        rules.strangler_migration(_module("def f(n: int) -> int:\n    return n\n"))
