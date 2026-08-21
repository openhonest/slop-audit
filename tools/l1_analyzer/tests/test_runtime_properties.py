"""Runtime properties, watched while the suite executes.

The fifth facet kind, and the only one that cannot be read from the source. The glossary
is explicit about the discipline: Umbra counts one of these only when the test run clearly
shows it holding or breaking, and says so instead of guessing when the tests never make it
happen. Three properties.

  mutation      does the function change the data it was handed
  determinism   does the same call give the same answer twice
  idempotency   does running it again on its own output change anything

A property is enumerated as a facet only where it is a meaningful question. `band(n: int)`
cannot mutate an int, so charging its suite for unobserved mutation would put a facet in
the denominator that no test could ever close. That is the same rule that keeps an
undeclared domain out of the Silence index.

The observation is repr-based, which has one honest limit: an object with the default repr
carries its address, so two different objects never compare equal and a mutation in place
is invisible. Those calls are marked opaque and contribute to nothing. A guess about them
would be evidence nobody produced.
"""

import ast
import textwrap

import pytest
from l1_analyzer import facets as facets_module
from l1_analyzer import runtime_probe


def _fn(source: str) -> ast.FunctionDef:
    return next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef))


def _call(function: str, before: list[str], after: list[str], result: str,
          raised: str = "", opaque: bool = False, keywords: dict[str, str] | None = None,
          state: tuple[str, str] = ("{}", "{}")) -> runtime_probe.Observation:
    return {"function": function, "before": before, "after": after, "result": result,
            "raised": raised, "opaque": opaque, "keywords": keywords or {},
            "state_before": state[0], "state_after": state[1]}


# --------------------------------------------------------------------------
# Which properties a function invites
# --------------------------------------------------------------------------

def test_a_function_taking_a_mutable_argument_invites_the_mutation_question():
    assert "mutation" in runtime_probe.invites(_fn("def f(items: list) -> int:\n    return 1\n"))


def test_a_function_taking_only_immutable_arguments_does_not():
    """`band(n: int)` cannot mutate an int, so the facet would be unclosable by
    construction and belongs nowhere near the denominator."""
    assert "mutation" not in runtime_probe.invites(_fn("def f(n: int) -> str:\n    return 'x'\n"))


def test_a_function_returning_a_value_invites_the_determinism_question():
    assert "determinism" in runtime_probe.invites(_fn("def f(n: int) -> str:\n    return 'x'\n"))


def test_a_function_returning_nothing_does_not():
    assert "determinism" not in runtime_probe.invites(_fn("def f(n: int) -> None:\n    pass\n"))
    assert "determinism" not in runtime_probe.invites(_fn("def f(n: int):\n    pass\n"))


def test_a_function_whose_result_has_its_own_argument_type_invites_idempotency():
    """`normalize(s: str) -> str` can be asked whether `f(f(x)) == f(x)`. A function whose
    result is a different type cannot be fed back in, so the question does not arise."""
    assert "idempotency" in runtime_probe.invites(_fn("def f(s: str) -> str:\n    return s\n"))
    assert "idempotency" not in runtime_probe.invites(_fn("def f(s: str) -> int:\n    return 1\n"))


def test_a_function_with_no_arguments_invites_no_idempotency_question():
    assert "idempotency" not in runtime_probe.invites(_fn("def f() -> int:\n    return 1\n"))


def test_a_function_of_several_arguments_invites_no_idempotency_question():
    """`f(f(x))` only exists when `f` takes one thing. Feeding a result back as the first
    of three arguments is not running the function again on its own output, and the tool
    read `allowance(cap, ceiling, spent) -> int` as BREAKING idempotency on that basis."""
    fn = _fn("def allowance(cap: int, ceiling: int, spent: int) -> int:\n    return cap\n")
    assert "idempotency" not in runtime_probe.invites(fn)
    assert "determinism" in runtime_probe.invites(fn)


def test_calls_that_differ_only_in_their_keywords_are_different_calls():
    """A false BREAKS, and worse than a silence: it accuses a pure function of answering
    differently to the same question. Keyword arguments were not recorded, so every call
    made by keyword had an empty argument list and they all grouped together."""
    seen = [_call("allowance", [], [], "5", keywords={"cap": "5", "ceiling": "5"}),
            _call("allowance", [], [], "2", keywords={"cap": "5", "ceiling": "2"})]
    assert runtime_probe.verdicts(seen)["allowance"]["determinism"] == "unobserved"


def test_the_same_keyword_call_twice_holds_determinism():
    seen = [_call("allowance", [], [], "5", keywords={"cap": "5"}),
            _call("allowance", [], [], "5", keywords={"cap": "5"})]
    assert runtime_probe.verdicts(seen)["allowance"]["determinism"] == "holds"


# --------------------------------------------------------------------------
# What the watched run shows
# --------------------------------------------------------------------------

def test_a_function_observed_changing_its_argument_breaks_mutation():
    seen = [_call("collect", ["[]"], ["['added']"], "['added']")]
    assert runtime_probe.verdicts(seen)["collect"]["mutation"] == "breaks"


def test_a_function_observed_leaving_its_argument_alone_holds_mutation():
    seen = [_call("total", ["[1, 2]"], ["[1, 2]"], "3")]
    assert runtime_probe.verdicts(seen)["total"]["mutation"] == "holds"


def test_one_observed_mutation_outweighs_any_number_of_clean_calls():
    """A function that mutates on one path mutates. The clean calls are the paths that did
    not reach it, and averaging them would report the property as held."""
    seen = [_call("f", ["[1]"], ["[1]"], "1"), _call("f", ["[]"], ["['x']"], "None"),
            _call("f", ["[2]"], ["[2]"], "2")]
    assert runtime_probe.verdicts(seen)["f"]["mutation"] == "breaks"


def test_a_function_never_called_shows_nothing():
    assert runtime_probe.verdicts([]) == {}


def test_the_same_call_twice_with_the_same_answer_holds_determinism():
    seen = [_call("band", ["20"], ["20"], "'high'"), _call("band", ["20"], ["20"], "'high'")]
    assert runtime_probe.verdicts(seen)["band"]["determinism"] == "holds"


def test_the_same_call_twice_with_different_answers_breaks_determinism():
    seen = [_call("roll", ["6"], ["6"], "3"), _call("roll", ["6"], ["6"], "5")]
    assert runtime_probe.verdicts(seen)["roll"]["determinism"] == "breaks"


def test_a_function_called_once_leaves_determinism_unobserved():
    """The suite never made it happen, so there is nothing to report and a `holds` here
    would be a guess dressed as a measurement."""
    assert runtime_probe.verdicts([_call("band", ["20"], ["20"], "'high'")]
                                  )["band"]["determinism"] == "unobserved"


def test_calls_with_different_arguments_leave_determinism_unobserved():
    seen = [_call("band", ["20"], ["20"], "'high'"), _call("band", ["1"], ["1"], "'low'")]
    assert runtime_probe.verdicts(seen)["band"]["determinism"] == "unobserved"


def test_a_result_fed_back_in_unchanged_holds_idempotency():
    seen = [_call("strip", ["' x '"], ["' x '"], "'x'"), _call("strip", ["'x'"], ["'x'"], "'x'")]
    assert runtime_probe.verdicts(seen)["strip"]["idempotency"] == "holds"


def test_a_result_fed_back_in_and_changed_again_breaks_idempotency():
    seen = [_call("grow", ["'x'"], ["'x'"], "'xx'"), _call("grow", ["'xx'"], ["'xx'"], "'xxxx'")]
    assert runtime_probe.verdicts(seen)["grow"]["idempotency"] == "breaks"


def test_a_result_never_fed_back_in_leaves_idempotency_unobserved():
    assert runtime_probe.verdicts([_call("strip", ["' x '"], ["' x '"], "'x'")]
                                  )["strip"]["idempotency"] == "unobserved"


def test_an_opaque_call_is_evidence_for_nothing():
    """An object with the default repr carries its address, so two different objects never
    compare equal and a change in place is invisible. Counting it either way would be
    reporting evidence nobody produced, and calling it a silence would blame the suite for
    a property no test could have shown."""
    seen = [_call("f", ["<X object at 0x1>"], ["<X object at 0x1>"], "1", opaque=True),
            _call("f", ["<X object at 0x1>"], ["<X object at 0x1>"], "1", opaque=True)]
    assert runtime_probe.verdicts(seen)["f"] == {
        "mutation": "unverified", "determinism": "unverified", "purity": "holds",
        "idempotency": "unverified"}


def test_a_call_that_raised_is_not_evidence_about_the_result():
    """It is evidence about mutation, because what the arguments look like afterwards is
    still readable, and none about determinism or idempotency, because there is no result."""
    seen = [_call("f", ["[]"], ["['x']"], "", raised="ValueError"),
            _call("f", ["[]"], ["['x']"], "", raised="ValueError")]
    verdict = runtime_probe.verdicts(seen)["f"]
    assert verdict["mutation"] == "breaks"
    assert verdict["determinism"] == "unobserved"


def test_the_default_repr_is_recognised_as_opaque():
    assert runtime_probe.is_opaque("<l1_analyzer.X object at 0x104f2a3b0>") is True
    assert runtime_probe.is_opaque("[1, 2]") is False
    assert runtime_probe.is_opaque("'at 0x'") is False


# --------------------------------------------------------------------------
# Watching a real suite run
# --------------------------------------------------------------------------

MODULE = textwrap.dedent('''
    def collect(items: list) -> list:
        """Mutates what it is handed, and the suite calls it."""
        items.append("added")
        return items


    def band(n: int) -> str:
        return "high" if n > 10 else "low"


    def squeeze(text: str) -> str:
        return text.strip()
''').lstrip("\n")

TESTS = textwrap.dedent('''
    from m import band, collect, squeeze

    def test_collect():
        assert collect([]) == ["added"]

    def test_band_twice():
        assert band(20) == "high"
        assert band(20) == "high"

    def test_squeeze_twice():
        once = squeeze(" x ")
        assert squeeze(once) == "x"
''').lstrip("\n")


@pytest.fixture(scope="module")
def watched(tmp_path_factory) -> dict:
    root = tmp_path_factory.mktemp("probe")
    (root / "m.py").write_text(MODULE)
    (root / "test_m.py").write_text(TESTS)
    seen = runtime_probe.watch(root / "m.py", (root / "test_m.py",))
    assert seen["reason"] == "", seen["reason"]
    return runtime_probe.verdicts(seen["observations"])


def test_the_watched_run_sees_the_mutating_function(watched):
    assert watched["collect"]["mutation"] == "breaks", watched


def test_the_watched_run_sees_the_repeated_call(watched):
    assert watched["band"]["determinism"] == "holds", watched


def test_the_watched_run_sees_the_result_fed_back_in(watched):
    assert watched["squeeze"]["idempotency"] == "holds", watched


def test_a_property_the_watched_suite_never_exercises_is_unobserved(watched):
    """`collect` is called once, so nothing was shown about whether it answers the same
    way twice."""
    assert watched["collect"]["determinism"] == "unobserved", watched


def test_watching_a_suite_that_cannot_run_says_why_rather_than_returning_nothing(tmp_path):
    """A run that crashed used to come back as an empty list, and every runtime property
    was then reported UNOBSERVED, which reads as "your suite never exercised this" about a
    suite that was never watched at all."""
    (tmp_path / "m.py").write_text("import a_module_nobody_has\n")
    (tmp_path / "test_m.py").write_text("import m\n\n\ndef test_x():\n    assert m\n")
    result = runtime_probe.watch(tmp_path / "m.py", (tmp_path / "test_m.py",))
    assert result["observations"] == []
    assert result["reason"].strip(), result


def test_a_run_that_could_not_be_watched_makes_every_property_unverified():
    fn = _fn("def f(items: list) -> list:\n    return items\n")
    built, unverified = runtime_probe.runtime_facets(fn, {}, "the watched run failed")
    assert built == []
    assert len(unverified) == 4
    assert all("the watched run failed" in u["detail"] for u in unverified)


# --------------------------------------------------------------------------
# The facets built from it
# --------------------------------------------------------------------------

def test_a_runtime_facet_is_closed_only_by_a_property_shown_to_hold():
    """`holds` closes it. `unobserved` is a silence the suite can close, and `breaks` is a
    located violation the glossary also counts in the numerator."""
    fn = _fn("def squeeze(text: str) -> str:\n    return text\n")
    built, unverified = runtime_probe.runtime_facets(
        fn, {"determinism": "holds", "purity": "unobserved", "idempotency": "breaks"})
    silent = {f["detail"].split()[0]: f["silent"] for f in built}
    assert silent == {"determinism": False, "purity": True, "idempotency": True}, built
    assert unverified == []


def test_a_function_the_suite_never_called_has_every_invited_property_silent():
    fn = _fn("def squeeze(text: str) -> str:\n    return text\n")
    built, unverified = runtime_probe.runtime_facets(fn, {})
    assert {f["detail"].split()[0] for f in built} == {"determinism", "purity", "idempotency"}
    assert all(f["silent"] for f in built)
    assert unverified == []


def test_a_runtime_facet_names_what_the_run_showed():
    """A closed facet has to say what closed it. "determinism holds" and "determinism
    breaks" are both evidence and mean opposite things to a reader."""
    fn = _fn("def roll(n: int) -> int:\n    return n\n")
    built, _unverified = runtime_probe.runtime_facets(fn, {"determinism": "breaks"})
    determinism = next(f for f in built if f["detail"].startswith("determinism"))
    assert determinism["kind"] == "runtime_property"
    assert determinism["detail"] == "determinism breaks"


# --------------------------------------------------------------------------
# The private readers, called directly
# --------------------------------------------------------------------------

def test_only_readable_calls_are_kept():
    readable = _call("f", ["[]"], ["[]"], "1")
    assert runtime_probe._readable([readable, _call("f", ["<X object at 0x1>"], ["<X object at 0x1>"],
                                                    "1", opaque=True)]) == [readable]
    assert runtime_probe._readable([]) == []


def test_a_function_with_no_readable_call_shows_nothing_about_mutation():
    """No call at all is a silence the suite can close. A call nobody could read is not."""
    assert runtime_probe._mutation([]) == "unobserved"
    assert runtime_probe._mutation(
        [_call("f", ["<X object at 0x1>"], ["<X object at 0x2>"], "1", opaque=True)]) == "unverified"


def test_the_signature_of_a_call_carries_its_keywords_in_a_stable_order():
    """Sorted, so `f(b=1, a=2)` and `f(a=2, b=1)` are recognised as the same call rather
    than as two calls that never repeat."""
    first = runtime_probe._signature(_call("f", ["1"], ["1"], "x", keywords={"b": "1", "a": "2"}))
    second = runtime_probe._signature(_call("f", ["1"], ["1"], "x", keywords={"a": "2", "b": "1"}))
    assert first == second == ("1", "a=2", "b=1")


def test_the_readers_answer_unobserved_on_an_empty_run():
    assert runtime_probe._determinism([]) == "unobserved"
    assert runtime_probe._idempotency([]) == "unobserved"


def test_a_call_with_several_arguments_is_not_idempotency_evidence():
    """The result is fed back as the FIRST of several, which is not the function running
    again on its own output."""
    seen = [_call("f", ["1", "2"], ["1", "2"], "3"), _call("f", ["3", "2"], ["3", "2"], "5")]
    assert runtime_probe._idempotency(seen) == "unobserved"


def test_a_keyword_call_is_not_idempotency_evidence():
    seen = [_call("f", ["1"], ["1"], "2", keywords={"flag": "True"}),
            _call("f", ["2"], ["2"], "2", keywords={"flag": "True"})]
    assert runtime_probe._idempotency(seen) == "unobserved"


def test_the_module_is_wrapped_under_the_name_the_tests_import_it_by(tmp_path):
    """Wrapping a second copy loaded under another name leaves the tests calling the
    original, and the run reports a suite that exercised nothing."""
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "m.py").write_text("X = 1\n")
    assert runtime_probe.dotted_name(package / "m.py", tmp_path) == "pkg.m"
    assert runtime_probe.dotted_name(tmp_path / "loose.py", tmp_path) == "loose"


def test_watching_a_suite_with_no_test_files_yields_no_observations(tmp_path):
    (tmp_path / "m.py").write_text("def f(n: int) -> int:\n    return n\n")
    assert runtime_probe.watch(tmp_path / "m.py", ())["observations"] == []


# --------------------------------------------------------------------------
# The readers are functions, shown rather than assumed
# --------------------------------------------------------------------------

_TWICE = [
    (runtime_probe.is_opaque, ("<X object at 0x1>",)),
    (runtime_probe.is_opaque, ("",)),
    (runtime_probe._readable, ([_call("f", ["1"], ["1"], "1")],)),
    (runtime_probe._mutation, ([_call("f", ["[]"], ["['x']"], "None")],)),
    (runtime_probe._determinism, ([_call("f", ["1"], ["1"], "2"),
                                   _call("f", ["1"], ["1"], "2")],)),
    (runtime_probe._idempotency, ([_call("f", ["1"], ["1"], "1")],)),
    (runtime_probe._signature, (_call("f", ["1"], ["1"], "1"),)),
    (runtime_probe.verdicts, ([_call("f", ["1"], ["1"], "1")],)),
]


@pytest.mark.parametrize(("reader", "arguments"), _TWICE,
                         ids=[f"{r.__name__}-{n}" for n, (r, _a) in enumerate(_TWICE)])
def test_a_reader_called_twice_the_same_way_answers_the_same_way(reader, arguments):
    """Determinism, shown for the readers themselves. Each is a pure function of its input
    and nothing had ever called one twice, so the property was unobserved on the module
    that measures the property."""
    assert reader(*arguments) == reader(*arguments)


def test_invites_called_twice_answers_the_same_way():
    fn = _fn("def f(items: list) -> list:\n    return items\n")
    assert runtime_probe.invites(fn) == runtime_probe.invites(fn)


def test_runtime_facets_called_twice_answers_the_same_way():
    fn = _fn("def f(items: list) -> list:\n    return items\n")
    assert runtime_probe.runtime_facets(fn, {}) == runtime_probe.runtime_facets(fn, {})


# --------------------------------------------------------------------------
# What could not be determined, as against what nobody tried
# --------------------------------------------------------------------------

def test_a_property_that_could_not_be_read_is_not_a_silence():
    """The glossary is explicit: a property Umbra could not determine safely stays outside
    the Silence index, numerator and denominator both, and the result carries the reason.

    Charging the suite for it says "you did not test this" about a property no test could
    have shown, which is the undeclared-domain mistake in the runtime half."""
    seen = [_call("f", ["<X object at 0x1>"], ["<X object at 0x1>"], "1", opaque=True)]
    assert runtime_probe.verdicts(seen)["f"]["mutation"] == "unverified"


def test_a_function_the_suite_called_readably_but_never_repeated_is_a_silence():
    """The distinction. Nobody called it twice, and a test could. That is closeable."""
    assert runtime_probe.verdicts([_call("f", ["1"], ["1"], "1")])["f"]["determinism"] == "unobserved"


def test_an_unverified_property_yields_no_facet_and_one_reason():
    fn = _fn("def f(items: list) -> list:\n    return items\n")
    built, unverified = runtime_probe.runtime_facets(fn, {"mutation": "unverified",
                                                          "determinism": "holds",
                                                          "idempotency": "unverified"}, "")

    assert sorted(f["detail"] for f in built) == ["determinism holds", "purity unobserved"]
    assert {u["kind"] for u in unverified} == {"honesty_unverified"}
    assert len(unverified) == 2
    assert all("could not be read" in u["detail"] for u in unverified), unverified


def test_an_unverified_property_stays_out_of_the_audit_index(tmp_path):
    """End to end. The module's one argument is an object with the default repr, so no call
    can show whether it was changed in place."""
    (tmp_path / "m.py").write_text(
        "class Box:\n    def __init__(self):\n        self.items = []\n\n\n"
        "def stash(box: Box) -> Box:\n    box.items.append(1)\n    return box\n")
    (tmp_path / "test_m.py").write_text(
        "from m import Box, stash\n\n\ndef test_stash():\n    assert stash(Box()).items == [1]\n")
    result = facets_module.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    # Purity is still readable: the module's own data did not change. Mutation and
    # idempotency are not, because the argument's repr carries its address.
    silent_kinds = {f["detail"].split()[0] for f in result["facets"]
                    if f["kind"] == "runtime_property" and f["function"] == "stash"}
    assert silent_kinds == {"purity"}, silent_kinds
    unverified = {u["detail"].split()[0] for u in result["undeclared"]
                  if u["kind"] == "honesty_unverified" and u["function"] == "stash"}
    # `Box` is not a mutable builtin, so mutation is never a question about this signature.
    assert unverified == {"determinism", "idempotency"}, unverified


# --------------------------------------------------------------------------
# A demonstrated violation is a site, not a closed facet
# --------------------------------------------------------------------------

def test_a_demonstrated_violation_counts_toward_the_silence_index():
    """The glossary lists a demonstrated mutation, determinism, purity or idempotency
    violation among the kinds that form the Silence-index NUMERATOR. It is a located site
    the suite has to close, by fixing the function or by asserting the behaviour on
    purpose, and reading it as closed put a real finding on the clean side of the number.

    `holds` is the only verdict that closes a runtime facet."""
    fn = _fn("def collect(items: list) -> list:\n    return items\n")
    built, _unverified = runtime_probe.runtime_facets(fn, {"mutation": "breaks"}, "")
    breaking = next(f for f in built if f["detail"].startswith("mutation"))
    assert breaking["silent"] is True


def test_a_property_shown_to_hold_is_the_only_closed_one():
    fn = _fn("def total(items: list) -> int:\n    return len(items)\n")
    built, _unverified = runtime_probe.runtime_facets(
        fn, {"mutation": "holds", "determinism": "unobserved", "purity": "holds"}, "")
    assert {f["detail"]: f["silent"] for f in built} == {
        "mutation holds": False, "determinism unobserved": True, "purity holds": False}


# --------------------------------------------------------------------------
# Purity, the fourth property
# --------------------------------------------------------------------------

def test_the_four_properties_are_named_as_a_closed_set():
    assert runtime_probe.PROPERTIES == ("mutation", "determinism", "purity", "idempotency")


def test_every_function_that_can_be_called_invites_the_purity_question():
    """Any function can write to a module global, so the question arises for all of them,
    unlike mutation which needs a mutable argument to be about."""
    assert "purity" in runtime_probe.invites(_fn("def f() -> None:\n    pass\n"))


def test_a_call_that_left_the_module_state_alone_holds_purity():
    seen = [_call("f", ["1"], ["1"], "1", state=("{}", "{}"))]
    assert runtime_probe.verdicts(seen)["f"]["purity"] == "holds"


def test_a_call_that_changed_the_module_state_breaks_purity():
    """A write to a module global is a side effect the return value does not mention."""
    seen = [_call("f", ["1"], ["1"], "1", state=("{'CACHE': {}}", "{'CACHE': {1: 2}}"))]
    assert runtime_probe.verdicts(seen)["f"]["purity"] == "breaks"


def test_one_impure_call_outweighs_any_number_of_clean_ones():
    seen = [_call("f", ["1"], ["1"], "1", state=("{}", "{}")),
            _call("f", ["2"], ["2"], "2", state=("{}", "{'X': 1}"))]
    assert runtime_probe.verdicts(seen)["f"]["purity"] == "breaks"


def test_a_call_whose_module_state_could_not_be_read_shows_nothing_about_purity():
    seen = [_call("f", ["1"], ["1"], "1", state=("", ""))]
    assert runtime_probe.verdicts(seen)["f"]["purity"] == "unverified"


def test_the_watched_run_sees_a_write_to_a_module_global(tmp_path):
    """End to end. Nothing in the source says whether the write happened on the path the
    suite took; only the run does."""
    (tmp_path / "m.py").write_text(
        "SEEN = []\n\n\ndef remember(n: int) -> int:\n    SEEN.append(n)\n    return n\n\n\n"
        "def double(n: int) -> int:\n    return n * 2\n")
    (tmp_path / "test_m.py").write_text(
        "from m import double, remember\n\n\n"
        "def test_remember():\n    assert remember(1) == 1\n\n\n"
        "def test_double():\n    assert double(2) == 4\n")
    watched = runtime_probe.verdicts(
        runtime_probe.watch(tmp_path / "m.py", (tmp_path / "test_m.py",))["observations"])
    assert watched["remember"]["purity"] == "breaks", watched
    assert watched["double"]["purity"] == "holds", watched


def test_purity_reads_unobserved_on_no_calls_and_holds_on_a_clean_one():
    assert runtime_probe._purity([]) == "unobserved"
    assert runtime_probe._purity([_call("f", ["1"], ["1"], "1")]) == "holds"


def test_an_empty_repr_of_a_module_never_read_is_not_a_pure_call():
    """An empty state string means the module's data could not be read, which is not the
    same as a module holding nothing. `[]` is the second, and it is readable."""
    assert runtime_probe._purity([_call("f", ["1"], ["1"], "1", state=("[]", "[]"))]) == "holds"
    assert runtime_probe._purity([_call("f", ["1"], ["1"], "1", state=("", ""))]) == "unverified"


def test_determinism_on_no_readable_call_is_unverified():
    assert runtime_probe._determinism(
        [_call("f", ["<X object at 0x1>"], ["<X object at 0x1>"], "1", opaque=True)]) == "unverified"


def test_the_empty_string_is_not_an_unreadable_repr():
    assert runtime_probe.is_opaque("") is False
