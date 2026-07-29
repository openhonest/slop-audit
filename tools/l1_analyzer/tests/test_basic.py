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
