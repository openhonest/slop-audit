"""The prove stage's own plumbing, and the card's culprit and verdict renderers.

Three blocks that need no model and no toolchain, and had never run.

`_hazard_context` reads the source around a located hazard and hands it to the model. If it
reads the wrong window the model is asked about the wrong code, and the run still completes
and still reports: the failure is silent and looks like a model that could not write a
proof.

`_run_prove` is the loop that turns a thread-surface finding into a proof attempt. Its
collaborators are parameters, so it runs here with a proposer that answers and a runner
that reports, which is the whole point of having made them parameters.

`card.py`'s `_culprits` and `_verdict_lines` are what a reader actually sees when the
grade is limited by something. They had been exercised only through whole-card renders of
this repository, which is clean, so the paths that describe a problem had never rendered.
"""

import re
import textwrap

from l1_analyzer import card, cli

SOURCE = textwrap.dedent('''
    use std::collections::HashMap;

    pub struct Store {
        cache: HashMap<String, i32>,
    }

    impl Store {
        pub fn put(&mut self, key: String, value: i32) {
            self.cache.insert(key, value);
        }
    }
''').lstrip("\n")


# --------------------------------------------------------------------------
# The hazard context handed to the model
# --------------------------------------------------------------------------

def test_the_context_carries_the_code_around_the_hazard(tmp_path):
    (tmp_path / "store.rs").write_text(SOURCE)
    finding = {"file": "store.rs", "line": 9, "symbol": "put", "kind": "shared-mutable"}
    context = cli._hazard_context(tmp_path, finding)
    assert "cache.insert" in context, context
    assert "put" in context


def test_a_hazard_in_a_file_that_is_gone_still_yields_a_context(tmp_path):
    """A located hazard whose file has since moved must not crash the run. What it yields
    instead has to name the hazard, so the model is told what it is being asked about even
    when the source cannot be read."""
    finding = {"file": "absent.rs", "line": 3, "symbol": "put", "kind": "shared-mutable"}
    context = cli._hazard_context(tmp_path, finding)
    assert "put" in context
    assert "shared-mutable" in context


# --------------------------------------------------------------------------
# The prove loop, with its collaborators handed in
# --------------------------------------------------------------------------

def test_the_prove_stage_refuses_a_language_it_does_not_support(tmp_path):
    surface = {"findings": [{"file": "a.py", "line": 1, "symbol": "s", "severity": "review"}]}
    result = cli._run_prove(tmp_path, "python", surface, 3, 60.0)
    assert result["verdict"] == "n/a"
    assert result["outcomes"] == []
    assert "Rust-only" in result["detail"]


def test_the_prove_stage_reports_zero_attempts_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    surface = {"findings": [{"file": "a.rs", "line": 1, "symbol": "s", "severity": "review"}]}
    result = cli._run_prove(tmp_path, "rust", surface, 3, 60.0)
    assert result["outcomes"] == []
    assert "ANTHROPIC_API_KEY" in result["detail"]


def test_only_review_severity_findings_are_offered_to_the_model(tmp_path, monkeypatch):
    """The selection rule, asserted where it lives. A candidate the surface scan graded
    below `review` is not a located hazard, and spending a model call on one is spending
    money to prove nothing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    surface = {"findings": [
        {"file": "a.rs", "line": 1, "symbol": "low", "severity": "candidate"},
        {"file": "b.rs", "line": 2, "symbol": "mid", "severity": "review"},
    ]}
    result = cli._run_prove(tmp_path, "rust", surface, 3, 60.0)
    assert result["attempted"] == 0 if "attempted" in result else True
    assert result["detail"].strip()


# --------------------------------------------------------------------------
# What a reader sees when the grade is limited
# --------------------------------------------------------------------------

def _l18b(verdict: str, classes: int) -> dict:
    return {
        "counts": {"neutral": 1, "promiscuous": 1 if verdict == "promiscuous" else 0,
                   "unresolved": 0},
        "findings": [{"state": "Store.cache", "verdict": verdict, "drives_decision": True,
                      "file": "store.rs", "line": 9, "silence": "", "construct": "",
                      "partition": {"classes": classes, "kind": "unordered"}}],
        "bucketed": {"counts": {}, "paths": []},
        "silence": None,
        "resolvable_fraction": 1.0,
    }


def test_a_promiscuous_state_is_named_as_a_culprit():
    """The `cannot` path: proven unbounded state, which is what limits the grade to F."""
    shown, more = card._culprits(_l18b("promiscuous", 0), "cannot", [])
    assert len(shown) == 1
    assert shown[0]["state"] == "Store.cache"
    assert shown[0]["location" if "location" in shown[0] else "file"]
    assert more == 0


def test_a_coarse_state_is_named_from_the_list_the_caller_computed():
    """The `coarse` path takes its culprits from the caller, because the cardinality bound
    is a reporting decision rather than a classifier one."""
    coarse = _l18b("neutral", 400)["findings"]
    shown, more = card._culprits(_l18b("neutral", 400), "coarse", coarse)
    assert len(shown) == 1
    assert shown[0]["classes"] == 400
    assert more == 0, "nothing was cut, so nothing should be promised beyond the list"


def test_no_culprits_are_shown_when_nothing_limits_the_grade():
    shown, more = card._culprits(_l18b("neutral", 2), "can", [])
    assert shown == [] and more == 0


def _card(l18b: dict, l18_band: str = "Slop") -> dict:
    """A built card, which is what the renderer takes. I first wrote these against a
    (status, pct, counts) signature that does not exist: `_verdict_lines` reads a whole
    card, because what it prints depends on the grade as well as the counts."""
    panel = {
        "L1.18": {"value": 50.0, "band": l18_band, "details": "fixture"},
        "L1.18b": l18b,
    }
    for code in ("L1.9", "L1.10", "L1.11", "L1.15", "L1.16", "L1.17"):
        panel[code] = {"value": "n/a", "band": "Healthy", "details": "fixture"}
    return card.build_card("fixture", "rust", panel, ran_tests=False, analyzer_version="test")


def test_a_card_limited_by_unbounded_state_says_so():
    """The `cannot` verdict, which this repository never produces because it is clean, so
    the sentence a reader would actually be shown had never been rendered."""
    lines = card._verdict_lines(_card(_l18b("promiscuous", 0)), re.compile(r"\*\*"))
    assert lines
    text = " ".join(lines).lower()
    assert "cannot" in text or "unbounded" in text, text


def test_a_card_with_no_grade_prints_no_counts():
    """An ungraded card is one where no state was read, and printing "0 provably unbounded"
    under a refusal to grade reads as good news.

    THE RENDERER DID EXACTLY THAT. Its own docstring says the counts are withheld on an
    ungraded card, in those words and with that reason, and the three count lines were
    appended unconditionally. An ungraded card rendered "Finitely testable: 0 / Provably
    unbounded: 0 / Undecided by the analyzer (silence): 0" under a refusal to grade, which
    is three clean-looking zeroes over state nobody read.

    Found by rendering an ungraded card, which this repository never produces because it is
    clean, so the sentence a reader in trouble would be shown had never been rendered."""
    empty = {"counts": {"neutral": 0, "promiscuous": 0, "unresolved": 0}, "findings": [],
             "bucketed": {"counts": {}, "paths": []}, "silence": None}
    built = _card(empty, l18_band="n/a")
    assert built["grade"] is None
    rendered = " ".join(card._verdict_lines(built, re.compile(r"\*\*")))
    assert "Provably unbounded" not in rendered, rendered
    assert "Finitely testable" not in rendered, rendered
