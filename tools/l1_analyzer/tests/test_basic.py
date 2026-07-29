"""Basic tests for the any-language L1 analyzer."""

from pathlib import Path

import pytest

from l1_analyzer import compute_git_indicators, detect_primary_language, analyze_mutable_state

REPO = Path("/tmp/oss-analysis/requests")

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

def test_detect_lang():
    assert detect_primary_language(REPO) == "python"

def test_l1_18_python_runs():
    res = analyze_mutable_state(REPO, "python")
    assert "value" in res
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")
    assert res["value"] < 10  # requests is quite clean

def test_git_indicators_run():
    res = compute_git_indicators(REPO)
    assert "L1.1" in res
    # shallow clone may give odd numbers, but it shouldn't crash
    assert "value" in res["L1.1"]
