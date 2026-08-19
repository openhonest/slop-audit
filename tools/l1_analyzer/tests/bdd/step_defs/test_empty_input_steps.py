"""Behavioural spec for what every measure says when it read nothing, wired to the REAL
analyzer.

The feature file stated the rule and enforced nothing: ten scenarios, no step definitions,
no `scenarios()` call, no reference to it anywhere in the repository. It said in its own
words that "a measure that examined nothing must not report a property" and could not
fail when one did.

Every scenario is written from the intended behaviour, and its own comments record what
the code did at the time it was written. Where a comment says "today this reports X" and
the assertion now passes, the defect it describes was repaired between then and now: the
dead-code empty-denominator on 2026-08-18, among others.
"""


from l1_analyzer import (
    dead_code,
    state_bounds,
    state_bounds_filters,
    state_census,
    state_partition,
    vacuity,
)
from pytest_bdd import given, scenarios, then, when

scenarios("../features/empty_input.feature")


@given("the analyzer is available via import")
def analyzer_available():
    assert dead_code and vacuity and state_census and state_partition and state_bounds_filters


# --- L1.12 dead code --------------------------------------------------------

@given("a repository containing two Python files of zero length", target_fixture="repo")
def two_empty_files(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    return tmp_path


@given("a repository containing one Python file with a referenced function", target_fixture="repo")
def one_referenced_function(tmp_path):
    (tmp_path / "a.py").write_text("def used():\n    return 1\n\n\nprint(used())\n")
    return tmp_path


@when("I run the dead-code analysis on it", target_fixture="result")
def run_dead_code(repo):
    return dead_code.analyze(repo, "python")


@then('the value is "n/a"')
def value_is_na(result):
    assert result["value"] == "n/a", result.get("details")


@then('the band is "n/a"')
def band_is_na(result):
    assert result["band"] == "n/a", result.get("details")


@then("the details say that no production lines were read")
def details_say_no_lines(result):
    assert "no production" in str(result["details"]).lower()


@then("the value is a number")
def value_is_number(result):
    assert isinstance(result["value"], (int, float))


@then('the band is "Healthy"')
def band_is_healthy(result):
    assert result["band"] == "Healthy", result.get("details")


# --- vacuity ----------------------------------------------------------------

@given("a repository containing no Python source at all", target_fixture="repo")
def no_python_source(tmp_path):
    (tmp_path / "README.md").write_text("# nothing to read\n")
    return tmp_path


@given("a repository containing one Python file with no vacuous path", target_fixture="repo")
def one_clean_python_file(tmp_path):
    (tmp_path / "a.py").write_text("def add(a, b):\n    return a + b\n")
    return tmp_path


@when("I run the vacuity check on it", target_fixture="result")
def run_vacuity(repo):
    return vacuity.check(repo)


@then("the reach reports zero files read")
def reach_zero_files(result):
    assert result["reach"]["files_read"] == 0, result["reach"]


@then("the reach reports zero languages read")
def reach_zero_languages(result):
    reach = result["reach"]
    read = reach.get("languages_read")
    assert read == 0, f"languages_read is {read!r}: a checker that opened no file read no language"


@then('the result has exactly the keys "findings" and "reach"')
def exactly_two_keys(result):
    assert set(result) == {"findings", "reach"}


@then('the rendered report contains none of the words "Healthy", "clean", "pass", "OK"')
def report_has_no_affirmative(result):
    rendered = vacuity.render(result)
    for word in ("Healthy", "clean", "pass", "OK"):
        assert word not in rendered, f"{word!r} is an affirmative this check has no field for"


@then("the rendered report states the reach beside the count")
def report_states_reach(result):
    rendered = vacuity.render(result)
    assert "reach" in rendered.lower()


# --- state census -----------------------------------------------------------

@given("a repository in a language the census has no spec for", target_fixture="census")
def census_without_spec(tmp_path):
    (tmp_path / "a.txt").write_text("not source\n")
    # Through classify, which is the only caller: `compare` takes the classifier's own
    # visited and judged sets, so calling it with a repository alone would be measuring a
    # signature rather than the census.
    return state_bounds.classify(tmp_path, "klingon")["census"]


@given("a Python file with one TypedDict of five fields and one module-level dict",
       target_fixture="census")
def census_of_a_read_record(tmp_path):
    (tmp_path / "a.py").write_text(
        "from typing import TypedDict\n\n\n"
        "class Row(TypedDict):\n    a: int\n    b: int\n    c: int\n    d: int\n    e: int\n\n\n"
        "CACHE = {}\n\n\ndef put(k, v):\n    CACHE[k] = v\n")
    return state_bounds.classify(tmp_path, "python")["census"]


@when("I take the census", target_fixture="result")
def take_census(census):
    return census


@when("I take the census beside what the classifier admitted", target_fixture="result")
def take_census_beside(census):
    return census


@then("the declared count is None")
def declared_is_none(result):
    assert result["declared"] is None, result


@then("the visited fraction is None")
def visited_is_none(result):
    assert result["visited_fraction"] is None, result


@then("the visited fraction is 1.0")
def visited_is_one(result):
    assert result["visited_fraction"] == 1.0, result


@then("the judged fraction is less than 1.0")
def judged_below_one(result):
    assert result["judged_fraction"] < 1.0, result


# --- state-bounds filters ---------------------------------------------------

@given("a Python class whose attribute has no membership test on it", target_fixture="probe")
def attribute_without_membership(tmp_path):
    return _invariance_probe(
        tmp_path,
        "class Q:\n    def __init__(self):\n        self._a = {}\n"
        "    def put(self, k, v):\n        self._a[k] = v\n")


@given("a Python class whose accessor returns None when the key is absent", target_fixture="probe")
def accessor_returning_none(tmp_path):
    return _invariance_probe(
        tmp_path,
        "class Q:\n    def __init__(self):\n        self._a = {}\n"
        "    def get(self, k):\n        if k in self._a:\n            return self._a[k]\n"
        "        return None\n")


def _invariance_probe(tmp_path, source):
    from l1_analyzer.indicators import LANG_CFG
    from l1_analyzer.state_bounds import LANG_SPEC, _refs, _text
    from tree_sitter import Parser
    parser = Parser()
    parser.language = LANG_CFG["python"]["language"]
    root = parser.parse(source.encode()).root_node
    refs = _refs(root, lambda n: n.type == "attribute" and _text(n).endswith("_a"))
    return ("_a", refs, LANG_SPEC["python"])


@when("I ask whether the result is invariant under presence", target_fixture="result")
def ask_invariance(probe):
    attr, refs, spec = probe
    return state_bounds_filters._result_invariant(attr, refs, spec)


@then("the answer is that the question does not apply")
def answer_is_inapplicable(result):
    assert result is None, (
        f"{result!r}: a predicate with no membership test to examine must say the question "
        "does not apply, not answer it")


@then('the answer is not the same value as "invariant"')
def answer_is_not_invariant(result):
    assert result is not True


@then("the answer is that the result varies with presence")
def answer_varies(result):
    assert result is False


# --- state partition --------------------------------------------------------

@given("a list of reaches containing no finite reach", target_fixture="reaches")
def reaches_without_finite():
    return [state_partition.output(), state_partition.write()]


@when("I roll them up into a partition", target_fixture="result")
def roll_up(reaches):
    return state_partition.roll_up(reaches)


@then("the partition has one class")
def partition_one_class(result):
    assert result["classes"] == 1, result


@then("the partition is counted")
def partition_counted(result):
    assert result["counted"] is True, result


@given("a partition whose count could not be recovered", target_fixture="partition")
def unknown_partition():
    return state_partition.UNKNOWN


@when("I ask whether it is coarse", target_fixture="result")
def ask_coarse(partition):
    return state_partition.is_coarse(partition, True, 5)


@then("the answer is no")
def answer_is_no(result):
    assert result is False
