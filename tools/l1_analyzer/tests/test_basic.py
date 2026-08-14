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
        res = analyze_mutable_state(tmp_path, "python")   # bytes reader
    finally:
        blocked.chmod(0o644)
    assert "unreadable" in res["details"]


def test_unreadable_file_surfaced_by_text_reader(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("x = 1\n")
    blocked = tmp_path / "blocked.py"
    blocked.write_text("y = 2\n")
    blocked.chmod(0o000)
    try:
        res = indicators._trailing_whitespace(tmp_path)   # text reader
    finally:
        blocked.chmod(0o644)
    assert "unreadable" in res["details"]


# --- a directory is not a file: neither measured nor disclosed ---------------

def test_directory_named_like_a_source_file_is_ignored_by_every_reader(tmp_path):
    """rglob yields directories too. node_modules/decimal.js is a real directory whose
    name ends in a source extension; it used to reach the readers, raise
    IsADirectoryError and be reported as an unreadable file. It is neither."""
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "decimal.js").mkdir()
    (tmp_path / "pkg.py").mkdir()

    files, skipped = indicators._read_source_bytes(tmp_path, (".py",), ())
    assert skipped == 0
    assert [p.name for p, _ in files] == ["ok.py"]

    text_files, text_skipped = indicators._read_text_files(tmp_path, frozenset({".py", ".js"}), ())
    assert text_skipped == 0
    assert [p.name for p, _ in text_files] == ["ok.py"]

    res = indicators._god_files(tmp_path)
    assert "unreadable" not in res["details"]
    assert res["details"].startswith("0/1 files >1k LOC")


def test_a_directory_does_not_hide_a_genuinely_unreadable_file(tmp_path):
    """The honest disclosure survives the fix: a file the process cannot read is still
    counted and surfaced, and the directory beside it adds nothing to that count."""
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    (tmp_path / "ok.py").write_text("x = 1\n")
    (tmp_path / "decimal.js").mkdir()
    blocked = tmp_path / "blocked.py"
    blocked.write_text("y = 2\n")
    blocked.chmod(0o000)
    try:
        god = indicators._god_files(tmp_path)
        _, skipped = indicators._read_source_bytes(tmp_path, (".py",), ())
        _, text_skipped = indicators._read_text_files(tmp_path, frozenset({".py", ".js"}), ())
    finally:
        blocked.chmod(0o644)
    assert "1 file(s) unreadable and excluded" in god["details"]
    assert skipped == 1
    assert text_skipped == 1


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


def test_l1_15_a_type_token_inside_a_string_is_data(tmp_path):
    """`("Any",)` in a pattern table does not opt out of a type checker. The meter used
    to charge itself for its own vocabulary, and would charge any C# repo for every
    string that says "object"."""
    res = _escapes(tmp_path, "python", "a.py", 'PATTERNS = ("Any",)\nLABEL = "Any"\nx = 1\n')
    assert res["details"].startswith("0 escapes")


def test_l1_15_a_comment_explaining_the_marker_is_documentation(tmp_path):
    """A suppression BEGINS with the marker. A comment that mentions it mid-sentence is
    prose about the rule, which is how this meter came to report on its own docstrings."""
    res = _escapes(tmp_path, "python", "a.py",
                   "# the marker is # type: ignore, written at the head of a line\nx = 1\n")
    assert res["details"].startswith("0 escapes")


def test_l1_15_still_counts_a_real_suppression_with_a_code(tmp_path):
    """Tightening to a prefix must not cost a real suppression its count."""
    res = _escapes(tmp_path, "python", "a.py", "x = 1  # type: ignore[attr-defined]\n")
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


# --- L1.12/13/14 external tools: real stub binaries on a controlled PATH -----
# Not mocks - genuine executables at the process boundary, the way the real
# tools are invoked. PATH is set to a dir we own so presence is deterministic.

def _stub(bin_dir, name, body):
    bin_dir.mkdir(parents=True, exist_ok=True)
    f = bin_dir / name
    f.write_text("#!/bin/sh\n" + body + "\n")
    f.chmod(0o755)


def test_external_tools_absent_are_na(tmp_path, monkeypatch):
    bind = tmp_path / "bin"
    bind.mkdir()
    monkeypatch.setenv("PATH", str(bind))  # no gitleaks/vulture/jscpd on PATH
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.14"]["band"] == "n/a"
    assert res["L1.12"]["band"] == "n/a"
    assert res["L1.13"]["band"] == "n/a"


def test_l1_14_gitleaks_present_counts_findings(tmp_path, monkeypatch):
    bind = tmp_path / "bin"
    _stub(bind, "gitleaks", "printf '{\"RuleID\":\"a\"}\\n{\"RuleID\":\"b\"}\\n'")
    monkeypatch.setenv("PATH", str(bind))
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.14"]["value"] == 2
    assert res["L1.14"]["band"] == "Not Healthy"  # band(2, 1, 3, lower-is-better)


def test_l1_12_vulture_present_and_non_python(tmp_path, monkeypatch):
    bind = tmp_path / "bin"
    _stub(bind, "vulture", "printf 'a\\nb\\nc\\n'")
    monkeypatch.setenv("PATH", str(bind))
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.12"]["value"] == 3 and res["L1.12"]["band"] == "Healthy"
    # non-Python has no dead-code tool wired
    res_go = indicators._compute_external_indicators(tmp_path, "go")
    assert res_go["L1.12"]["band"] == "n/a" and "no dead-code tool" in res_go["L1.12"]["details"]


def test_l1_13_jscpd_present_parseable_and_not(tmp_path, monkeypatch):
    bind = tmp_path / "bin"
    _stub(bind, "jscpd", "echo 'Total duplication: 4.5 %'")
    monkeypatch.setenv("PATH", str(bind))
    assert indicators._compute_external_indicators(tmp_path, "python")["L1.13"]["value"] == 4.5
    _stub(bind, "jscpd", "echo 'no percentage in this output'")
    assert indicators._compute_external_indicators(tmp_path, "python")["L1.13"]["band"] == "n/a"


# --- L1.8 / L1.15 / L1.19 remaining branches --------------------------------

def test_l1_8_no_production_files_is_na(tmp_path):
    (tmp_path / "test_only.py").write_text("def test_x():\n    assert True\n")
    assert indicators._test_to_prod_ratio(tmp_path)["band"] == "n/a"


def test_l1_15_density_over_a_kloc_is_slop(tmp_path):
    (tmp_path / "a.py").write_text("v: Any = 1\n" * 1100)  # >1000 LOC, all escapes
    res = indicators._compute_type_escapes(tmp_path, "python")
    assert res["value"] > 0 and res["band"] == "Slop"


def test_l1_19_falls_back_to_static_when_no_tests(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    res = indicators._decision_space_l19(tmp_path, "python", exec_tests=True, timeout_seconds=60.0)
    assert res["band"] == "n/a" and "coverage not measured" in res["details"]
    assert isinstance(res["value"], int) and res["value"] >= 1


# --- pytest_trace edge paths (real execution) -------------------------------

def test_l1_19_no_tests_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    res = pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)
    assert res["band"] == "n/a" and "no tests" in res["details"]


def test_l1_19_no_branches_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")  # straight-line, no branches
    (tmp_path / "test_m.py").write_text("from m import f\ndef test_f():\n    assert f() == 1\n")
    res = pytest_trace.decision_space_coverage(tmp_path, "python", 60.0)
    assert res["band"] == "n/a" and "no enumerable decision branches" in res["details"]


def test_l1_19_timeout_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    (tmp_path / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(3)\n    assert True\n")
    res = pytest_trace.decision_space_coverage(tmp_path, "python", 0.5)  # far too short
    assert res["band"] == "n/a" and "timed out" in res["details"]


def test_l1_20_no_tests_is_na(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    assert pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)["band"] == "n/a"


def test_l1_20_not_run_when_exec_disabled(tmp_path):
    res = indicators._test_determinism_l20(tmp_path, "python", exec_tests=False, timeout_seconds=30.0)
    assert res["value"] == "not run" and res["band"] == "n/a"


def test_l1_20_order_dependent_scores_below_five(tmp_path):
    (tmp_path / "test_order.py").write_text("_s = {'x': False}\ndef test_a():\n    _s['x'] = True\ndef test_b():\n    assert _s['x'] is True\n")
    res = pytest_trace.test_determinism(tmp_path, "python", 5, 60.0)
    assert res["value"] != "5/5" and res["band"] in ("Not Healthy", "Slop")


def test_l1_20_timeout_is_na(tmp_path):
    (tmp_path / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(3)\n    assert True\n")
    res = pytest_trace.test_determinism(tmp_path, "python", 5, 0.5)
    assert res["band"] == "n/a" and "timed out" in res["details"]


def test_l1_14_detect_secrets_fallback(tmp_path, monkeypatch):
    # gitleaks absent, detect-secrets present -> the elif branch
    bind = tmp_path / "bin"
    _stub(bind, "detect-secrets", "printf '\"is_verified\": false\\n\"is_verified\": false\\n'")
    monkeypatch.setenv("PATH", str(bind))
    res = indicators._compute_external_indicators(tmp_path, "python")
    assert res["L1.14"]["value"] == 2 and res["L1.14"]["details"].startswith("detect-secrets")


def test_git_indicators_binary_file_numstat(tmp_path):
    # a binary file yields "-\t-\tpath" numstat, exercising the non-digit branch
    _git(tmp_path, "init", "-q")
    (tmp_path / "data.bin").write_bytes(bytes(range(256)))
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "add code and binary")
    res = compute_git_indicators(tmp_path, None, None)
    assert res["L1.2"]["band"] in ("Healthy", "Not Healthy", "Slop")


def test_git_indicators_empty_repo_is_na(tmp_path):
    _git(tmp_path, "init", "-q")  # initialized but no commits
    res = compute_git_indicators(tmp_path, None, None)
    assert res["L1.1"]["band"] == "n/a"


def test_git_indicators_bad_path_is_na(tmp_path):
    # git cannot chdir here -> non-zero exit -> the failure branch
    res = compute_git_indicators(tmp_path / "does-not-exist", None, None)
    assert res["L1.1"]["band"] == "n/a" and "git log failed" in res["L1.1"]["details"]


def test_git_indicators_since_bound_is_applied(tmp_path):
    # a past --since keeps the commit; exercises the `if since:` append branch
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    res = compute_git_indicators(tmp_path, "2000-01-01", None)
    assert res["L1.1"]["band"] in ("Healthy", "Not Healthy", "Slop")


def test_git_indicators_until_past_leaves_no_commits(tmp_path):
    # a past --until filters out every commit -> the "no commits in range" path
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    res = compute_git_indicators(tmp_path, None, "2000-01-01")
    assert res["L1.1"]["band"] == "n/a" and "no commits" in res["L1.1"]["details"]


# --- Rust and C configs (advertised languages, previously untested) ---------

def test_l1_18_rust_static_mut_global_is_detected(tmp_path):
    # A `static mut` global read is mutable-state access; a pure fn is not. The
    # old smoke test only checked the band string and missed that Rust detected
    # nothing at all (0/2). This pins the real discrimination.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "a.rs").write_text(
        "static mut counter: i32 = 0;\n"
        "fn bump() { unsafe { counter += 1; } }\n"
        "fn pure(a: i32, b: i32) -> i32 { a + b }\n"
    )
    assert detect_primary_language(tmp_path) == "rust"
    res = analyze_mutable_state(tmp_path, "rust")
    assert res["value"] == 50.0
    assert res["details"].startswith("1/2") and res["details"].endswith("(rust)")
    assert mutable_function_names(tmp_path, "rust") == ["bump"]


def test_l1_18_rust_receiver_mutation_is_detected(tmp_path):
    # An `impl` method taking `&mut self` and touching `self.field` references
    # external mutable state; a pure associated fn does not.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "a.rs").write_text(
        "struct Counter { count: i32 }\n"
        "impl Counter {\n"
        "    fn increment(&mut self) { self.count += 1; }\n"
        "    fn pure(a: i32, b: i32) -> i32 { a + b }\n"
        "}\n"
    )
    res = analyze_mutable_state(tmp_path, "rust")
    assert res["value"] == 50.0
    assert mutable_function_names(tmp_path, "rust") == ["increment"]


def test_l1_18_rust_const_is_not_mutable_state(tmp_path):
    # `const` and plain `static` are immutable; only `static mut` counts.
    (tmp_path / "a.rs").write_text(
        "const MAX: i32 = 10;\n"
        "fn check(x: i32) -> bool { x < MAX }\n"
    )
    assert analyze_mutable_state(tmp_path, "rust")["value"] == 0.0


def test_l1_18_declared_boundary_is_excluded(tmp_path):
    # A function that declares itself an I/O boundary is excluded from the ratio,
    # numerator and denominator, even though it touches a module global. An
    # unmarked reader of the same global is still counted. Recognition is by
    # declaration, never by guessing.
    from l1_analyzer.indicators import mutable_function_names
    (tmp_path / "m.py").write_text(
        "CACHE = []\n"
        "def handler():\n"
        "    # honest: boundary\n"
        "    print(CACHE)\n"
        "    return len(CACHE)\n"
        "def reader():\n"
        "    return CACHE[0]\n"
    )
    res = analyze_mutable_state(tmp_path, "python")
    assert res["details"].startswith("1/1")          # handler excluded; only reader counts
    assert mutable_function_names(tmp_path, "python") == ["reader"]


def test_l1_18_analyzer_is_self_clean(tmp_path):
    # Dogfooding: the analyzer's own source passes its own L1.18. Guards the
    # path_cover refactor (its stateful CFG builder used to score 11.7%).
    from pathlib import Path

    from l1_analyzer import indicators
    pkg = Path(indicators.__file__).parent
    assert analyze_mutable_state(pkg, "python")["value"] == 0.0


def test_l1_18_java_interface_method_has_no_body(tmp_path):
    # An abstract interface method has no block, exercising the no-body path.
    (tmp_path / "I.java").write_text(
        "interface I {\n"
        "    int compute(int x);\n"                       # no body
        "    default int twice(int x) { return x * 2; }\n"  # has a body
        "}\n"
    )
    res = analyze_mutable_state(tmp_path, "java")
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")


def test_l1_18_go_receiver_and_plain_function(tmp_path):
    # A method has a receiver; a plain function does not - both receiver paths.
    (tmp_path / "a.go").write_text(
        "package main\n"
        "type Box struct { n int }\n"
        "func (b *Box) Set(v int) { b.n = v }\n"   # receiver -> mutable
        "func Add(a, b int) int { return a + b }\n"  # plain function -> pure
    )
    res = analyze_mutable_state(tmp_path, "go")
    assert res["details"].startswith("1/2")


def test_l1_18_c_config_runs(tmp_path):
    (tmp_path / "a.c").write_text(
        "int g;\n"
        "void touch(void) { g = 1; }\n"
        "int add(int a, int b) { return a + b; }\n"
    )
    assert detect_primary_language(tmp_path) == "c"
    res = analyze_mutable_state(tmp_path, "c")
    assert res["band"] in ("Healthy", "Not Healthy", "Slop")


# --- CLI end to end (exercises cli.main's argument dispatch) ----------------

def test_cli_git_and_config_json(tmp_path, capsys):
    from l1_analyzer import cli
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    rc = cli.main([str(tmp_path), "--indicators", "1,9,10", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"L1.1"' in out and '"L1.9"' in out


def test_cli_source_indicators_no_exec_text(tmp_path, capsys):
    from l1_analyzer import cli
    (tmp_path / "m.py").write_text("def f(x):\n    if x:\n        return 1\n    return 0\n")
    rc = cli.main([str(tmp_path), "--indicators", "16,17,18,19", "--lang", "python", "--no-exec"])
    assert rc == 0
    out = capsys.readouterr().out
    # The default CLI output is the full Slop Audit report (grade + verdict + audit checks).
    assert "Slop Audit" in out and "finitely testable" in out


def test_cli_all_indicators_auto_lang(tmp_path, capsys):
    from l1_analyzer import cli
    _git(tmp_path, "init", "-q")
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    _git(tmp_path, "add", "-A")
    _commit(tmp_path, "init")
    rc = cli.main([str(tmp_path), "--indicators", "all", "--no-exec"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Slop Audit" in out and "(python)" in out  # the report titles with the language


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
