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


def _source(text: str, path: str = "m.py", language: str = "python") -> dict:
    """A parsed source, as the runner builds one.

    Only Python is parsed into a tree. The two browser clauses read the text, because this
    tool has no JavaScript parser it could hand them and pretending otherwise would put an
    empty tree where a reader expects a parsed one."""
    return {"path": path, "language": language, "text": text,
            "tree": ast.parse(text) if language == "python" else ast.parse(""),
            "readable": True, "unreadable_reason": ""}


# --------------------------------------------------------------------------
# 1. Dict-lookup polymorphism over if/elif chains
# --------------------------------------------------------------------------

def test_a_chain_dispatching_on_one_value_is_found():
    found = rules.dispatch_chains(_source(
        "def send(channel, data):\n"
        "    if channel == 'email':\n        return send_email(data)\n"
        "    elif channel == 'sms':\n        return send_sms(data)\n"
        "    elif channel == 'push':\n        return send_push(data)\n"
        "    return None\n"))
    assert len(found) == 1
    assert found[0]["line"] == 2


def test_an_ordinary_conditional_is_not_a_dispatch_chain():
    """The rule says so itself: bounds checks, null guards and boolean logic are ordinary
    conditionals. A clause that fires on every function with a condition teaches a reader
    to ignore the number."""
    assert rules.dispatch_chains(_source(
        "def clamp(n, low, high):\n"
        "    if n < low:\n        return low\n"
        "    elif n > high:\n        return high\n"
        "    return n\n")) == []


def test_a_two_armed_test_on_one_value_is_not_yet_a_table():
    """One `if` and one `else` is a binary choice. A table starts where the third case
    would otherwise be another arm."""
    assert rules.dispatch_chains(_source(
        "def f(kind):\n    if kind == 'a':\n        return one()\n    return two()\n")) == []


# --------------------------------------------------------------------------
# 2. Typed dicts over classes
# --------------------------------------------------------------------------

def test_a_class_that_only_holds_data_is_found():
    found = rules.data_classes(_source(
        "class User:\n"
        "    def __init__(self, email, name):\n        self.email = email\n        self.name = name\n"
        "    def get_email(self):\n        return self.email\n"))
    assert [f["symbol"] for f in found] == ["User"]


@pytest.mark.parametrize("base", ["TypedDict", "Protocol", "Exception", "Enum", "NamedTuple"])
def test_a_declared_shape_is_not_a_data_class(base):
    """The rule allows exactly these. Flagging them would flag the recommended alternative."""
    assert rules.data_classes(_source(
        f"class User({base}):\n    email: str\n    name: str\n")) == []


def test_a_class_wrapping_a_resource_is_left_alone():
    """Acceptable when it wraps a stateful external resource, in the rule's own words."""
    assert rules.data_classes(_source(
        "class Pool:\n"
        "    def __init__(self, dsn):\n        self.conn = connect(dsn)\n"
        "    def close(self):\n        self.conn.close()\n")) == []


# --------------------------------------------------------------------------
# 3. Pure functions over methods
# --------------------------------------------------------------------------

def test_a_method_that_only_reads_self_is_found():
    found = rules.methods_wearing_a_class(_source(
        "class User:\n"
        "    def validate(self):\n        return len(self.email) > 3\n"))
    assert [f["symbol"] for f in found] == ["User.validate"]


def test_a_method_that_writes_self_is_left_alone():
    """It is doing something a free function taking the data could not."""
    assert rules.methods_wearing_a_class(_source(
        "class Counter:\n"
        "    def bump(self):\n        self.n = self.n + 1\n")) == []


def test_a_method_that_calls_another_method_is_left_alone():
    assert rules.methods_wearing_a_class(_source(
        "class User:\n"
        "    def check(self):\n        return self.validate()\n")) == []


# --------------------------------------------------------------------------
# 4. I/O at the boundary
# --------------------------------------------------------------------------

def test_io_in_a_function_a_sibling_calls_is_found():
    """The I/O has been pushed inward: `price` cannot be tested without a filesystem, and
    `total` cannot be tested without mocking one."""
    found = rules.io_below_the_boundary(_source(
        "def price(path):\n    return int(path.read_text())\n\n\n"
        "def total(path):\n    return price(path) * 2\n"))
    assert [f["symbol"] for f in found] == ["price"]


def test_io_in_an_entry_point_is_the_boundary():
    """Nothing in the module calls it, so it IS the edge, which is where the I/O belongs."""
    assert rules.io_below_the_boundary(_source(
        "def load(path):\n    return path.read_text()\n")) == []


# --------------------------------------------------------------------------
# 5. Flat composition over inheritance
# --------------------------------------------------------------------------

def test_a_class_inheriting_an_implementation_is_found():
    found = rules.inheritance_for_reuse(_source("class Admin(User):\n    pass\n"))
    assert [f["symbol"] for f in found] == ["Admin"]


@pytest.mark.parametrize("base", ["TypedDict", "Protocol", "Exception", "ABC", "Enum"])
def test_inheriting_a_declared_shape_is_not_reuse(base):
    assert rules.inheritance_for_reuse(_source(f"class Thing({base}):\n    pass\n")) == []


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
    source = _source("def f(n: int) -> int:\n    return n\n")
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
    found = rules.swallowed_exceptions(_source(
        f"def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        {body}\n"))
    assert found, body


def test_a_handler_that_reraises_is_left_alone():
    assert rules.swallowed_exceptions(_source(
        "def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        raise\n")) == []


def test_a_handler_that_maps_the_error_is_left_alone():
    """The boundary catching and turning the type into a response is the rule, not the
    violation."""
    assert rules.swallowed_exceptions(_source(
        "def route(x):\n    try:\n        return g(x)\n"
        "    except ValueError as error:\n        return respond(400, str(error))\n")) == []


# --------------------------------------------------------------------------
# 9. SQL over application caches
# --------------------------------------------------------------------------

def test_a_memoising_decorator_is_found():
    found = rules.unmeasured_caches(_source(
        "from functools import lru_cache\n\n\n@lru_cache\ndef price(sku):\n    return query(sku)\n"))
    assert found


def test_the_cache_clause_says_what_it_cannot_see():
    """Whether anyone profiled the query first is not in any file. The clause reports the
    cache and names the half it cannot decide, rather than implying the whole rule was
    checked."""
    found = rules.unmeasured_caches(_source(
        "import redis\n\n\ndef price(sku):\n    return redis.get(sku)\n"))
    assert found
    assert "profil" in found[0]["undecided"].lower()


def test_a_file_with_no_cache_finds_nothing():
    assert rules.unmeasured_caches(_source("def price(sku):\n    return query(sku)\n")) == []


# --------------------------------------------------------------------------
# 10. Pure-function assertions over mocks
# --------------------------------------------------------------------------

def test_a_test_carrying_three_mocks_is_found():
    found = rules.mock_heavy_tests(_source(
        "def test_order():\n"
        "    a = Mock()\n    b = MagicMock()\n    c = patch('x')\n"
        "    assert place(a, b, c)\n", path="test_m.py"))
    assert [f["symbol"] for f in found] == ["test_order"]


def test_a_test_with_two_mocks_is_ordinary_isolation():
    assert rules.mock_heavy_tests(_source(
        "def test_order():\n    a = Mock()\n    b = Mock()\n    assert place(a, b)\n",
        path="test_m.py")) == []


def test_the_mock_clause_only_reads_test_files():
    """A file that is not a test has no tests to count mocks in, and a production file
    naming Mock is doing something else."""
    assert rules.mock_heavy_tests(_source(
        "def build():\n    return Mock(), Mock(), Mock()\n", path="m.py")) is None


# --------------------------------------------------------------------------
# 11. Type declarations over imperative validation
# --------------------------------------------------------------------------

def test_a_check_the_signature_already_made_is_found():
    """Re-checking a value the signature types is distrust of your own contract."""
    found = rules.imperative_validation(_source(
        "def f(name: str) -> str:\n"
        "    if not isinstance(name, str):\n        raise TypeError('no')\n    return name\n"))
    assert found


def test_a_check_on_an_untyped_value_is_left_alone():
    """It arrived from outside with no contract, which is where validation belongs."""
    assert rules.imperative_validation(_source(
        "def f(payload):\n"
        "    if not isinstance(payload, dict):\n        raise TypeError('no')\n    return payload\n")) == []


# --------------------------------------------------------------------------
# 12. Context managers over instance state
# --------------------------------------------------------------------------

def test_a_resource_stored_on_self_is_found():
    found = rules.unscoped_resources(_source(
        "class Client:\n    def __init__(self, dsn):\n        self.connection = connect(dsn)\n"))
    assert [f["symbol"] for f in found] == ["Client.connection"]


def test_a_class_that_is_a_context_manager_has_scoped_it():
    assert rules.unscoped_resources(_source(
        "class Client:\n"
        "    def __enter__(self):\n        self.connection = connect(self.dsn)\n        return self\n"
        "    def __exit__(self, *a):\n        self.connection.close()\n")) == []


# --------------------------------------------------------------------------
# 13. Configuration as parameters
# --------------------------------------------------------------------------

def test_a_setting_somebody_turns_is_found():
    """The WRITE is what makes it configuration. Without one it is a fact about the world,
    and flagging that would make this clause demand the opposite of clauses 1 and 18."""
    found = rules.hidden_configuration(_source(
        "SETTINGS = {'timeout': 30}\n\n\n"
        "def configure(n):\n    SETTINGS['timeout'] = n\n\n\n"
        "def fetch(url):\n    return get(url, SETTINGS['timeout'])\n"))
    assert found


def test_a_constant_nothing_can_change_is_not_configuration():
    """Nothing about it can differ between two calls, so no caller's behaviour depends on
    something they cannot see."""
    assert rules.hidden_configuration(_source(
        "TIMEOUT = 30\n\n\ndef fetch(url):\n    return get(url, TIMEOUT)\n")) == []


# --------------------------------------------------------------------------
# 14. No implicit defaults
# --------------------------------------------------------------------------

@pytest.mark.parametrize("default", ["30", "'utf-8'", "True", "None", "[]", "{}"])
def test_a_literal_default_is_found(default):
    found = rules.implicit_defaults(_source(f"def f(x, timeout={default}):\n    return x\n"))
    assert found, default


def test_a_default_that_binds_a_collaborator_is_left_alone():
    """The opposite failure. A collaborator in the signature is a dependency made visible,
    which is what rule 13 asks for, and flagging it would push the code back toward the
    module-level lookup the rule exists to remove."""
    assert rules.implicit_defaults(_source(
        "def observe(fn, reader=describe):\n    return reader(fn)\n")) == []


# --------------------------------------------------------------------------
# 15. Simple gherkin steps
# --------------------------------------------------------------------------

def test_a_step_carrying_thirty_lines_of_setup_is_found():
    body = "\n".join(f"    line_{n} = {n}" for n in range(31))
    found = rules.heavy_step_definitions(_source(
        f"@given('a user')\ndef step(context):\n{body}\n", path="test_steps.py"))
    assert found


def test_a_step_that_calls_and_checks_is_left_alone():
    assert rules.heavy_step_definitions(_source(
        "@when('it runs')\ndef step(context):\n    context.result = band(20)\n",
        path="test_steps.py")) == []


# --------------------------------------------------------------------------
# 16. Declarative equivalents over lifecycle hooks
# --------------------------------------------------------------------------

@pytest.mark.parametrize("registration", [
    "atexit.register(cleanup)", "signal.signal(signal.SIGTERM, stop)",
])
def test_behaviour_parked_in_a_hook_is_found(registration):
    found = rules.lifecycle_hooks(_source(f"def setup():\n    {registration}\n"))
    assert found, registration


def test_a_call_at_the_place_it_happens_is_not_a_hook():
    assert rules.lifecycle_hooks(_source("def run():\n    cleanup()\n")) == []


# --------------------------------------------------------------------------
# 17. Strangler pattern — the clause nothing decides
# --------------------------------------------------------------------------

def test_the_strangler_clause_never_returns_a_verdict():
    """It is a property of how work is sequenced over weeks. No file, and no set of files,
    carries the sequence of the work that produced them, so a pass here would be a claim
    nobody could support."""
    assert rules.strangler_migration(_source("def f(n: int) -> int:\n    return n\n")) is None


# --------------------------------------------------------------------------
# 18. Dispatch tables close open input
# --------------------------------------------------------------------------

def test_a_lookup_with_a_default_is_found():
    """It files an input nobody wrote a rule for under an answer written for a different
    input, and the default re-opens the space while the code still reads closed."""
    found = rules.open_dispatch(_source(
        "HANDLERS = {'a': one, 'b': two}\n\n\ndef run(kind):\n    return HANDLERS.get(kind, one)(1)\n"))
    assert found


def test_a_subscript_lets_an_unknown_key_raise():
    assert rules.open_dispatch(_source(
        "HANDLERS = {'a': one}\n\n\ndef run(kind):\n    return HANDLERS[kind](1)\n")) == []


# --------------------------------------------------------------------------
# 19. Atomic test-and-set over check-then-act
# --------------------------------------------------------------------------

def test_a_read_then_write_of_a_shared_value_is_found():
    found = rules.check_then_act(_source(
        "LOCKS = {}\n\n\ndef claim(key):\n"
        "    if key in LOCKS:\n        return False\n    LOCKS[key] = True\n    return True\n"))
    assert found


def test_an_await_between_the_two_is_named_as_certain():
    """Between the read and the write another caller reads the same answer. An await makes
    that certain rather than occasional, and the finding has to say which it found."""
    found = rules.check_then_act(_source(
        "LOCKS = {}\n\n\nasync def claim(key):\n"
        "    if key in LOCKS:\n        return False\n"
        "    await settle()\n    LOCKS[key] = True\n    return True\n"))
    assert found
    assert "certain" in found[0]["detail"]


def test_reading_a_shared_value_without_writing_it_is_not_a_race():
    assert rules.check_then_act(_source(
        "LOCKS = {}\n\n\ndef held(key):\n    return key in LOCKS\n")) == []


# --------------------------------------------------------------------------
# What the clauses learned from being pointed at themselves
# --------------------------------------------------------------------------

def test_a_dict_lookup_is_not_io():
    """`_SUFFIXES.get(suffix)` was reported as I/O below the boundary, because `get` is
    also how an HTTP client fetches a page. A bare name cannot tell the two apart, so the
    ambiguous ones are matched on the whole dotted call instead."""
    assert rules.io_below_the_boundary(_source(
        "TABLE = {'a': 1}\n\n\n"
        "def look(key):\n    return TABLE.get(key)\n\n\n"
        "def top(key):\n    return look(key)\n")) == []


@pytest.mark.parametrize("call", ["requests.get(url)", "httpx.post(url)", "session.get(url)",
                                  "subprocess.run(cmd)", "path.read_text()"])
def test_a_named_client_call_is_still_io(call):
    found = rules.io_below_the_boundary(_source(
        f"def fetch(url, cmd, path, session, requests, httpx, subprocess):\n    return {call}\n\n\n"
        "def top(*a):\n    return fetch(*a)\n"))
    assert found, call


def test_a_table_nobody_writes_is_not_hidden_configuration():
    """Clause 13 flagged every dispatch table in this tool, which would mean clause 13
    demands the opposite of clauses 1 and 18. Two clauses of one instrument must not ask
    for opposite things.

    A table nobody writes is a fact about the world. Configuration is a knob, and a knob is
    one somebody turns."""
    assert rules.hidden_configuration(_source(
        "SUFFIXES = {'.py': 'python'}\n\n\ndef language(path):\n    return SUFFIXES[path]\n")) == []


def test_a_module_level_value_a_function_writes_is_hidden_configuration():
    """Somebody turns this one, so two callers can get different behaviour for a reason
    neither of them can see at the call site."""
    found = rules.hidden_configuration(_source(
        "SETTINGS = {'timeout': 30}\n\n\n"
        "def configure(n):\n    SETTINGS['timeout'] = n\n\n\n"
        "def fetch(url):\n    return get(url, SETTINGS['timeout'])\n"))
    assert [f["symbol"].split("(")[0] for f in found] == ["fetch"]


def test_the_configuration_clause_says_what_it_cannot_see():
    """Whether a knob was disguised as a fact is not decidable from a file. The clause
    reports the tables somebody writes and names the half it cannot read."""
    found = rules.hidden_configuration(_source(
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
    assert rules.swallowed_exceptions(_source(
        "def toolchains():\n    try:\n        return run(['rustup']).stdout\n"
        "    except OSError:\n        return 'could not query rustup toolchains'\n")) == []


@pytest.mark.parametrize("stand_in", ["None", "False", "0", "''", "[]", "{}"])
def test_a_handler_that_returns_a_falsy_stand_in_is_still_swallowing(stand_in):
    """A value indistinguishable from a successful empty result. The caller cannot tell
    "there were none" from "I could not look"."""
    found = rules.swallowed_exceptions(_source(
        f"def f(x):\n    try:\n        return g(x)\n    except ValueError:\n        return {stand_in}\n"))
    assert found, stand_in
