"""Tests for the Rust runtime harness (L1.19 region coverage, L1.20 determinism).

The output-parsing (`_tests_run`) is pure and always tested. The execution paths
run real `cargo`, so they are integration tests skipped when no toolchain is
present (e.g. a CI runner without Rust). Pure assertions, no mocks.

decision_space_coverage's no-toolchain refusal is proved by nothing. Its old test
replaced rust_trace._cargo with a lambda returning None. Reaching that path
honestly means emptying PATH, the way test_basic.py does.
"""

import shutil

import pytest
from l1_analyzer import rust_trace

_HAS_CARGO = shutil.which("cargo") is not None


# --- pure: parsing cargo-test result lines ---------------------------------

def test_tests_run_sums_passed_failed_ignored_across_lines():
    out = (
        "test result: ok. 2 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out\n"
        "test result: FAILED. 3 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out\n"
    )
    total, failed = rust_trace._tests_run(out)
    assert total == 7          # (2+0+1) + (3+1+0)
    assert failed == 1


def test_tests_run_zero_when_no_result_line():
    assert rust_trace._tests_run("Compiling probe v0.1.0\nFinished") == (0, 0)


def test_tests_run_counts_a_clean_single_suite():
    total, failed = rust_trace._tests_run("test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out")
    assert (total, failed) == (5, 0)


# --- integration: real cargo (skipped without a toolchain) -----------------

_LIB = """\
pub fn classify(n: i32) -> &'static str {
    if n < 0 { "neg" } else if n == 0 { "zero" } else { "pos" }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn neg() { assert_eq!(classify(-1), "neg"); }
    #[test] fn pos() { assert_eq!(classify(5), "pos"); }
}
"""


def _crate(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(_LIB)
    return tmp_path


@pytest.mark.skipif(not _HAS_CARGO, reason="needs a Rust toolchain (cargo)")
def test_determinism_runs_the_suite_and_reports_five_of_five(tmp_path):
    result = rust_trace.test_determinism(_crate(tmp_path), runs=5, timeout_seconds=120)
    assert result["value"] == "5/5"
    assert result["band"] == "Healthy"


@pytest.mark.skipif(not _HAS_CARGO, reason="needs a Rust toolchain (cargo)")
def test_determinism_is_na_when_no_tests(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "empty"\nversion = "0.1.0"\nedition = "2021"\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("pub fn f() {}\n")
    result = rust_trace.test_determinism(tmp_path, runs=5, timeout_seconds=120)
    assert result["band"] == "n/a"
    assert "no tests" in result["details"]
