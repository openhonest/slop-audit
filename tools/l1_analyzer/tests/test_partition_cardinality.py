"""D means a finite partition too coarse to cover, not "the analyzer could not tell".

Once silence moved off the grade, D was vacant. It now carries a positive finding:

    D when the reaching partition is finite, its members are unordered, and its
    cardinality exceeds a stated bound.

Both halves are needed. Cardinality alone is the wrong test, because limit testing
defeats large ORDERED domains: a 64-bit integer compared against three constants induces
four classes and boundary selection covers them with a handful of values. Size did not
defeat the tester, structure saved them. What limit testing cannot defeat is a large
UNORDERED partition: five hundred distinct string keys reaching five hundred branches have
no value "just above" a key, so covering them needs five hundred tests.

That distinction was not measurable before, because `_FINITE` was one label: a partition of
two classes and a partition of four billion came out the same. So the finite verdict now
carries a cardinality and an ordered flag, and every branch that reaches finiteness supplies
both from the route it took.

Where a count cannot be recovered, that is silence, not D. An unknown count is a limit of
ours and D is a claim about their code, which is the same rule the silence index applies.

Pure assertions over fixtures written to tmp_path, no mocks (Honest Code Rule 10).
"""

from __future__ import annotations

from l1_analyzer import card, report, state_bounds
from l1_analyzer.indicators import L1Result

_HEALTHY: dict[str, L1Result] = {
    k: {"band": "Healthy"} for k in ("L1.17", "L1.15", "L1.10", "L1.11", "L1.9", "L1.16")
}

# The shipped configuration carries NO bound: measured over the pinned corpus and nine
# supplementary trees, the widest unordered partition in real code was 14 classes and there
# was no upper tail, so the data fixes a floor for any bound and nothing above it. These
# tests therefore state the RULE by passing a bound explicitly, and the last test pins the
# shipped behaviour: with no bound configured, nothing is graded D.
BOUND = 20


def _classify(tmp_path, src: str) -> dict:
    (tmp_path / "app.py").write_text(src)
    return state_bounds.classify(tmp_path, "python")


def _partition(result: dict, state: str) -> dict:
    return next(f["partition"] for f in result["findings"] if f["state"] == state)


def _panel(l18b: dict) -> dict[str, L1Result]:
    return {"L1.18": {"band": "Healthy"}, "L1.18b": l18b, **_HEALTHY}


def test_a_comparison_chain_of_n_operators_gives_n_plus_one_ordered_classes(tmp_path):
    """The route to finiteness carries the structure. A comparison arm splits an ordered
    domain, and n distinct constants cut it into n+1 intervals that boundary values cover."""
    result = _classify(tmp_path, (
        "level = 0\n"
        "\n"
        "def bump(n):\n"
        "    global level\n"
        "    level = n\n"
        "\n"
        "def band():\n"
        "    if level > 10:\n"
        "        return 'high'\n"
        "    if level > 5:\n"
        "        return 'mid'\n"
        "    if level > 1:\n"
        "        return 'low'\n"
        "    return 'none'\n"
    ))
    p = _partition(result, "level")
    assert p["counted"] is True
    assert p["ordered"] is True
    assert p["classes"] == 4        # three operators, four intervals


def test_a_literal_keyed_read_gives_one_class_per_distinct_literal(tmp_path):
    """A map read by literal keys has no boundary between keys, so the classes are
    unordered: d distinct literals, plus the class that matches none of them."""
    result = _classify(tmp_path, (
        "handlers = {}\n"
        "\n"
        "def add(k, v):\n"
        "    handlers[k] = v\n"
        "\n"
        "def run(kind):\n"
        "    if handlers['alpha']:\n"
        "        return 1\n"
        "    if handlers['beta']:\n"
        "        return 2\n"
        "    if handlers['gamma']:\n"
        "        return 3\n"
        "    return 0\n"
    ))
    p = _partition(result, "handlers")
    assert p["counted"] is True
    assert p["ordered"] is False
    assert p["classes"] == 4        # three distinct keys, plus the miss


def test_a_closed_set_of_size_k_gives_k_plus_one_unordered_classes(tmp_path):
    """Membership against a statically fixed collection: which member the value equals,
    or none of them. Nothing orders the members, so no boundary value covers the split."""
    result = _classify(tmp_path, (
        "MODES = ('fast', 'slow', 'safe', 'debug')\n"
        "\n"
        "mode = 'fast'\n"
        "\n"
        "def set_mode(m):\n"
        "    global mode\n"
        "    mode = m\n"
        "\n"
        "def check():\n"
        "    if mode in MODES:\n"
        "        return 1\n"
        "    return 0\n"
    ))
    p = _partition(result, "mode")
    assert p["counted"] is True
    assert p["ordered"] is False
    assert p["classes"] == 5        # four members, plus none-of-them


def test_a_large_unordered_partition_grades_d_and_a_large_ordered_one_does_not(tmp_path):
    """The rule in one test. Both fixtures put the same number of classes on one piece of
    state; only the unordered one is beyond limit testing, and only it is D."""
    over = BOUND + 4
    members = ", ".join(f"'k{i}'" for i in range(over))
    unordered = _classify(tmp_path, (
        f"MODES = ({members})\n"
        "\n"
        "mode = 'k0'\n"
        "\n"
        "def set_mode(m):\n"
        "    global mode\n"
        "    mode = m\n"
        "\n"
        "def check():\n"
        "    if mode in MODES:\n"
        "        return 1\n"
        "    return 0\n"
    ))
    assert _partition(unordered, "mode")["classes"] > BOUND
    g = report.grade_summary(_panel(unordered), BOUND)
    assert g["status"] == "coarse"
    assert g["grade"] == "D"
    assert [c["state"] for c in g["coarse"]] == ["mode"]

    arms = "\n".join(f"    if level > {i}:\n        return {i}" for i in range(over))
    ordered = _classify(tmp_path, "level = 0\n\ndef bump(n):\n    global level\n    level = n\n\n"
                        f"def band():\n{arms}\n    return -1\n")
    p = _partition(ordered, "level")
    assert p["classes"] > BOUND and p["ordered"] is True
    assert report.grade_summary(_panel(ordered), BOUND)["grade"] != "D"


def test_a_partition_whose_count_cannot_be_recovered_is_silence_not_d(tmp_path):
    """An unknown count is a limit of ours. Calling it D would report our own blind spot as
    a coverage problem in their code, which is the exact fault the silence index exists to
    stop, so the same rule applies: not counted, therefore not D, and disclosed."""
    result = _classify(tmp_path, (
        "import config\n"
        "\n"
        "MODES = frozenset(config.load())\n"
        "\n"
        "mode = 'fast'\n"
        "\n"
        "def set_mode(m):\n"
        "    global mode\n"
        "    mode = m\n"
        "\n"
        "def check():\n"
        "    if mode in MODES:\n"
        "        return 1\n"
        "    return 0\n"
    ))
    p = _partition(result, "mode")
    assert p["counted"] is False
    assert result["partition"]["uncounted"] >= 1
    assert report.grade_summary(_panel(result), BOUND)["grade"] != "D"


def test_the_report_says_the_cardinality_does_not_compose_across_states(tmp_path):
    """Two states that decide the same branch multiply rather than add, and this version
    does not compose them. A per-state number that is honest beats a composed number that
    is guessed, but only while the report says which one it is."""
    members = ", ".join(f"'k{i}'" for i in range(BOUND + 4))
    result = _classify(tmp_path, (
        f"MODES = ({members})\n"
        "\n"
        "mode = 'k0'\n"
        "\n"
        "def set_mode(m):\n"
        "    global mode\n"
        "    mode = m\n"
        "\n"
        "def check():\n"
        "    if mode in MODES:\n"
        "        return 1\n"
        "    return 0\n"
    ))
    assert "does not compose" in str(result["details"])
    # Against the card, because the card is what the CLI and the site print. This assertion
    # used to run on report_markdown, which had no caller outside this suite, so it proved the
    # sentence existed and not that any reader met it. Moving it here found that the shipped
    # card carried the compose limit only inside the D note, and no repository is graded D, so
    # the claim reached nobody.
    markdown = card.card_markdown(card.build_card("x", "python", _panel(result)))
    assert "does not compose" in markdown
    # And the silence index is named beside the grade on every card, not only this one.
    assert "reported separately, as silence, and never folded into the grade" in markdown


def test_no_bound_is_configured_so_no_repository_is_graded_d(tmp_path):
    """The measurement did not support a bound, so none is set, and the shipped analyzer
    grades nothing D. A bound picked to make the feature fire would be measuring our
    impatience: the widest unordered partition anywhere in the corpus was 14 classes, and
    the shape the rule is written for - hundreds of literal keys - never appears, because a
    table read by a VARIABLE key is unbounded and already F. Absence is the finding."""
    assert report.UNORDERED_CLASS_BOUND is None
    members = ", ".join(f"'k{i}'" for i in range(BOUND + 4))
    result = _classify(tmp_path, (
        f"MODES = ({members})\n"
        "\n"
        "mode = 'k0'\n"
        "\n"
        "def set_mode(m):\n"
        "    global mode\n"
        "    mode = m\n"
        "\n"
        "def check():\n"
        "    if mode in MODES:\n"
        "        return 1\n"
        "    return 0\n"
    ))
    shipped = report.grade_summary(_panel(result), report.UNORDERED_CLASS_BOUND)
    assert shipped["coarse"] == []
    assert shipped["status"] == "can"
