"""Tests for the any-language L1 analyzer.

Self-contained: every test builds its own fixture under tmp_path, so nothing
depends on an external checkout. Pure assertions, no mocks (Honest Code Rule 10).
"""

import os
import subprocess

import pytest
from l1_analyzer import indicators, pytest_trace
from l1_analyzer.indicators import (
    analyze_mutable_state,
    band,
    compute_git_indicators,
    detect_primary_language,
)

# One sample per supported language: a stateful method (references external
# mutable state) plus a pure function that must NOT be counted. This locks in
# that L1.18 both runs and discriminates for every language we advertise.
LANG_SAMPLES = {
    "java": ("Acc.java", "class Acc { private int total; int add(int x){ this.total += x; return this.total; } static int pure(int a, int b){ return a + b; } }"),
    "csharp": ("Acc.cs", "class Acc { private int total; int Add(int x){ this.total += x; return this.total; } static int Pure(int a, int b){ return a + b; } }"),
    "javascript": ("acc.js", "let counter = 0;\nclass Acc { add(x){ this.total += x; return this.total; } }\nfunction pure(a, b){ return a + b; }\n"),
    "ruby": ("acc.rb", "class Acc\n  def add(x)\n    @total += x\n  end\n  def self.pure(a, b)\n    a + b\n  end\nend\n"),
    "go": ("acc.go", "package main\ntype Acc struct { total int }\nfunc (a *Acc) Add(x int) int { a.total += x; return a.total }\nfunc Pure(a, b int) int { return a + b }\n"),
    "python": ("acc.py", "G = 0\nclass Acc:\n    def add(self, x):\n        self.total += x\n        return self.total\n\ndef pure(a, b):\n    return a + b\n"),
}


# --- pure scoring (Honest Code: band is a pure function of counts) -----------

def test_band_higher_is_better():
    assert band(95, 90, 60, higher_is_better=True) == "Healthy"
    assert band(75, 90, 60, higher_is_better=True) == "Not Healthy"
    assert band(50, 90, 60, higher_is_better=True) == "Slop"


def test_band_lower_is_better():
    assert band(5, 15, 40, higher_is_better=False) == "Healthy"
    assert band(20, 15, 40, higher_is_better=False) == "Not Healthy"
    assert band(60, 15, 40, higher_is_better=False) == "Slop"


# --- honest handling of the unknown / empty case ----------------------------

def test_detect_unknown_when_no_source(tmp_path):
    (tmp_path / "README.md").write_text("# docs only, no source")
    assert detect_primary_language(tmp_path) == "unknown"


def test_unknown_language_is_na_not_guessed(tmp_path):
    (tmp_path / "acc.py").write_text("x = 1\n")
    # An unknown language must NOT be silently analyzed as Python.
    assert analyze_mutable_state(tmp_path, "klingon")["band"] == "n/a"
    assert indicators._compute_type_escapes(tmp_path, "klingon")["band"] == "n/a"
    assert indicators._compute_decision_space(tmp_path, "klingon")["band"] == "n/a"


# --- config integrity: direct cfg[...] access is safe -----------------------

def test_every_language_config_has_required_keys():
    required = ("language", "extensions", "function_types", "class_types",
               "member_access", "this_ident", "module_level_assign", "type_escape_patterns")
    for lang, cfg in indicators.LANG_CFG.items():
        for key in required:
            assert key in cfg, f"{lang} missing required LANG_CFG key {key}"


# --- no silent swallow of arguments -----------------------------------------

def test_compute_source_indicators_rejects_unexpected_kwargs(tmp_path):
    (tmp_path / "acc.py").write_text("x = 1\n")
    with pytest.raises(TypeError):
        indicators.compute_source_indicators(tmp_path, lang="python", exec_tests=False, timeout_seconds=5.0, bogus=1)


# --- skipped files are surfaced, never silently dropped ---------------------

def test_unreadable_file_is_counted_not_swallowed(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("def f(x):\n    return x\n")
    blocked = tmp_path / "blocked.py"
    blocked.write_text("def g(x):\n    return x\n")
    blocked.chmod(0o000)
    try:
        res = analyze_mutable_state(tmp_path, "python")
    finally:
        blocked.chmod(0o644)
    assert "unreadable" in res["details"]


# --- git indicators run on a real, self-contained repo ----------------------

def test_git_indicators_run(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    (tmp_path / "README.md").write_text("# doc\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    res = compute_git_indicators(tmp_path, None, None)
    assert "L1.1" in res and "value" in res["L1.1"]


# --- L1.19 / L1.20 runtime harness ------------------------------------------

def test_l1_19_l1_20_non_python_is_na(tmp_path):
    cov = pytest_trace.decision_space_coverage(tmp_path, "go", 30.0)
    det = pytest_trace.test_determinism(tmp_path, "go", 5, 30.0)
    assert cov["band"] == "n/a" and det["band"] == "n/a"


def test_l1_19_static_fallback_when_exec_disabled(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    res = indicators._decision_space_l19(tmp_path, "python", exec_tests=False, timeout_seconds=30.0)
    assert res["band"] == "n/a"
    assert "coverage not measured" in res["details"]
    assert isinstance(res["value"], int) and res["value"] >= 1


# --- band boundary values (Honest Test: exercise the exact cutoffs) ---------

def test_band_boundaries_higher_is_better():
    assert band(10, 10, 1, higher_is_better=True) == "Healthy"       # == healthy cutoff
    assert band(1, 10, 1, higher_is_better=True) == "Not Healthy"    # == slop cutoff
    assert band(0.9, 10, 1, higher_is_better=True) == "Slop"


def test_band_boundaries_lower_is_better():
    assert band(14.9, 15, 40, higher_is_better=False) == "Healthy"
    assert band(15, 15, 40, higher_is_better=False) == "Not Healthy"  # == healthy cutoff
    assert band(40, 15, 40, higher_is_better=False) == "Slop"         # == slop cutoff


# --- L1.15 type escapes: real detection + regression for the string bug ------

def _escapes(tmp_path, lang, fname, code):
    (tmp_path / fname).write_text(code)
    return indicators._compute_type_escapes(tmp_path, lang)


def test_l1_15_detects_python_any(tmp_path):
    res = _escapes(tmp_path, "python", "a.py", "from typing import Any\ndef f(x: Any) -> Any:\n    return x\n")
    assert res["details"].startswith("3 escapes")  # import + param + return


def test_l1_15_string_literal_is_not_a_false_positive(tmp_path):
    # A string that merely contains the ignore-marker must NOT be counted.
    # This is the bug honest testing surfaced: the marker check used to run on
    # every node's text, so this module's own pattern list scored as escapes.
    res = _escapes(tmp_path, "python", "a.py", 'MARKER = "# type: ignore lives here"\nx = 1\n')
    assert res["details"].startswith("0 escapes")


def test_l1_15_counts_ignore_comment(tmp_path):
    res = _escapes(tmp_path, "python", "a.py", "x = 1  # type: ignore\n")
    assert res["details"].startswith("1 escapes")


def test_l1_15_typescript_any_and_unknown(tmp_path):
    res = _escapes(tmp_path, "typescript", "a.ts", "let x: any = 1;\nlet y: unknown = 2;\n")
    assert res["details"].startswith("2 escapes")


def test_l1_15_untyped_language_is_na(tmp_path):
    res = _escapes(tmp_path, "ruby", "a.rb", "x = 1\n")
    assert res["band"] == "n/a"


# --- L1.16 / L1.17 indicators -----------------------------------------------

def test_l1_16_trailing_whitespace(tmp_path):
    (tmp_path / "a.py").write_text("x = 1  \ny = 2\n")  # one trailing-ws line
    res = indicators._trailing_whitespace(tmp_path)
    assert res["value"] > 0 and res["band"] in ("Healthy", "Not Healthy", "Slop")


def test_l1_17_god_files(tmp_path):
    (tmp_path / "big.py").write_text("x = 1\n" * 1500)
    assert "1/1 files >1k LOC" in indicators._god_files(tmp_path)["details"]
    (tmp_path / "huge.py").write_text("x = 1\n" * 4100)
    assert indicators._god_files(tmp_path)["band"] == "Slop"  # any >4k file forces Slop


# --- L1.18 module-global reference and malformed input ----------------------

def test_l1_18_counts_mutable_module_global_but_not_constant(tmp_path):
    # `counter` (lowercase, reassigned) is mutable module state; `LIMIT`
    # (uppercase) is a constant and must NOT be counted as mutable-state access.
    (tmp_path / "m.py").write_text(
        "counter = 0\nLIMIT = 100\n"
        "def bump():\n    return counter + 1\n"      # reads mutable global -> counted
        "def bounded(x):\n    return x < LIMIT\n"     # reads constant only -> not counted
        "def pure(a, b):\n    return a + b\n"
    )
    res = analyze_mutable_state(tmp_path, "python")
    assert res["details"].startswith("1/3")  # only bump() references mutable state
    assert res["value"] == pytest.approx(33.3, abs=0.1)


def test_l1_18_malformed_source_does_not_crash(tmp_path):
    (tmp_path / "broken.py").write_bytes(b"\xff\xfe def f( : : :\n\x00 ??? (((")
    res = analyze_mutable_state(tmp_path, "python")
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")


# --- L1.1-L1.7 git band logic on a crafted history --------------------------

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _commit(repo, msg):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg], check=True, capture_output=True)


def test_git_indicators_classify_and_score(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "doc.md").write_text("# doc\nline\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "doc only")
    (tmp_path / "app.py").write_text("def f():\n    return 1\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "code only")
    (tmp_path / "app.py").write_text("def f():\n    return 2\n    # note\n")
    (tmp_path / "doc.md").write_text("# doc\nline\nmore\n")
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "mixed")
    (tmp_path / "app.py").write_text("x = 1\n")  # net-negative, delete-heavy
    _git(tmp_path, "add", "-A"); _commit(tmp_path, "shrink")

    res = compute_git_indicators(tmp_path, None, None)
    # 4 commits: 1 doc-only, 2 code-only, 1 mixed
    assert res["L1.1"]["value"] == 25.0
    assert res["L1.2"]["value"] == 50.0
    assert res["L1.3"]["value"] == 25.0
    assert res["L1.6"]["value"] > 0  # at least one net-negative commit
    for k in ("L1.1", "L1.2", "L1.3", "L1.4", "L1.5", "L1.6", "L1.7", "L1.8"):
        assert res[k]["band"] in ("Healthy", "Not Healthy", "Slop", "n/a")


def test_git_indicators_non_repo_is_na(tmp_path):
    res = compute_git_indicators(tmp_path, None, None)  # not a git repo
    assert res["L1.1"]["band"] == "n/a"


# --- L1.9-L1.11 config presence ---------------------------------------------

def test_config_indicators_present(tmp_path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n")
    res = indicators.compute_config_indicators(tmp_path)
    assert res["L1.9"]["band"] == "Healthy"
    assert res["L1.10"]["value"] == 1
    assert res["L1.11"]["band"] == "Healthy"


def test_config_indicators_absent(tmp_path):
    res = indicators.compute_config_indicators(tmp_path)
    assert res["L1.9"]["band"] == "Slop"
    assert res["L1.11"]["band"] == "Slop"


# --- L1.19 / L1.20 runtime harness happy path (real execution) --------------

def test_l1_19_l1_20_pass_on_a_clean_fixture(tmp_path):
    (tmp_path / "m.py").write_text("def classify(x):\n    if x < 0:\n        return 'n'\n    return 'p'\n")
    (tmp_path / "test_m.py").write_text("from m import classify\ndef test_neg():\n    assert classify(-1) == 'n'\ndef test_pos():\n    assert classify(1) == 'p'\n")
    cov = pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)
    assert cov["value"] == 100.0 and cov["band"] == "Healthy"  # both branches exercised
    det = pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)
    assert det["value"] == "5/5" and det["band"] == "Healthy"


# --- per-language L1.18 (runs and discriminates) ----------------------------

@pytest.mark.parametrize("lang", sorted(LANG_SAMPLES))
def test_l1_18_runs_and_discriminates_per_language(tmp_path, lang):
    fname, code = LANG_SAMPLES[lang]
    (tmp_path / fname).write_text(code)

    assert detect_primary_language(tmp_path) == lang

    res = analyze_mutable_state(tmp_path, lang)
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")
    # exactly one of the two functions touches external mutable state
    assert res["details"].startswith("1/2"), res["details"]
    assert res["value"] == 50.0
