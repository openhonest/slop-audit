"""The Rust coverage readers, run against a real llvm-cov report.

`_llvm_cov_report`, `repo_uncovered_lines` and `module_uncovered_lines` are 42 of
rust_trace's 55 uncovered lines. They are what the coverage-prove loop calls to find out
which lines a Rust suite never reached, so a gap here is the loop being pointed at the
wrong lines, and it would look exactly like a model that could not write a useful test.

Nothing had run them because the skip guard asked whether cargo-llvm-cov answers a version
flag. It does, and then refuses for want of the LLVM tools, which on a Homebrew machine are
present and simply not where cargo looks. The tool's own refusal names that remedy.

The crate here has one function with three arms and a test reaching one, so the uncovered
lines are known by reading the fixture rather than by trusting the reader under test.
"""

import pathlib
import shutil
import subprocess
import textwrap

import pytest
from l1_analyzer import rust_trace


def _llvm_tools() -> dict[str, str] | None:
    """The LLVM tools cargo-llvm-cov needs, discovered rather than assumed."""
    if shutil.which("cargo") is None:
        return None
    if shutil.which("llvm-profdata") and shutil.which("llvm-cov"):
        return {}
    brew = shutil.which("brew")
    if brew is None:
        return None
    prefix = subprocess.run([brew, "--prefix", "llvm"], capture_output=True, text=True, check=False)
    if prefix.returncode != 0:
        return None
    binaries = pathlib.Path(prefix.stdout.strip()) / "bin"
    if not (binaries / "llvm-profdata").exists():
        return None
    return {"LLVM_COV": str(binaries / "llvm-cov"), "LLVM_PROFDATA": str(binaries / "llvm-profdata")}


pytestmark = pytest.mark.skipif(
    _llvm_tools() is None, reason="cargo-llvm-cov has no LLVM coverage tools")


@pytest.fixture(scope="module")
def crate(tmp_path_factory) -> pathlib.Path:
    """Three arms, one reached. The `mid` arm is uncovered by construction, so a reader
    that reports it is right and one that does not is wrong, and neither answer has to be
    taken on trust."""
    root = tmp_path_factory.mktemp("crate")
    (root / "Cargo.toml").write_text(
        '[package]\nname = "fixture"\nversion = "0.0.0"\nedition = "2021"\n')
    (root / "src").mkdir()
    (root / "src" / "lib.rs").write_text(textwrap.dedent('''
        pub fn band(n: i32) -> &'static str {
            if n > 10 {
                return "high";
            }
            if n > 5 {
                return "mid";
            }
            "low"
        }

        #[cfg(test)]
        mod tests {
            use super::*;

            #[test]
            fn high() {
                assert_eq!(band(20), "high");
            }
        }
    ''').lstrip("\n"))
    return root


@pytest.fixture(autouse=True)
def _tools(monkeypatch):
    for name, value in (_llvm_tools() or {}).items():
        monkeypatch.setenv(name, value)


def test_the_repo_reader_measures_and_names_its_files(crate):
    result = rust_trace.repo_uncovered_lines(crate, 900.0)
    assert result["measured"] is True, result.get("reason")
    assert any(rel.endswith("lib.rs") for rel in result["files"]), sorted(result["files"])


def test_the_repo_reader_finds_the_arm_the_test_never_reaches(crate):
    """The fixture's `mid` arm. Its line is known by reading the source, so this asserts a
    fact about the crate rather than whatever the reader happened to return."""
    result = rust_trace.repo_uncovered_lines(crate, 900.0)
    lines = next(v for k, v in result["files"].items() if k.endswith("lib.rs"))
    source = (crate / "src" / "lib.rs").read_text().split("\n")
    uncovered_text = " ".join(source[n - 1] for n in sorted(lines) if n <= len(source))
    assert "mid" in uncovered_text, f"lines {sorted(lines)} were reported uncovered"


def test_the_module_reader_answers_for_one_file(crate):
    result = rust_trace.module_uncovered_lines(crate, "src/lib.rs", 900.0)
    assert result["measured"] is True, result.get("reason")
    assert result["uncovered_lines"], "a crate with an unreached arm reported none"


def test_the_module_reader_refuses_a_path_the_crate_does_not_hold(crate):
    """A module nobody has is not a module with full coverage."""
    result = rust_trace.module_uncovered_lines(crate, "src/absent.rs", 900.0)
    assert result["measured"] is False
    assert result["reason"].strip()


def test_the_readers_refuse_a_directory_that_is_not_a_crate(tmp_path):
    repo = rust_trace.repo_uncovered_lines(tmp_path, 120.0)
    assert repo["measured"] is False
    assert repo["reason"].strip()
    module = rust_trace.module_uncovered_lines(tmp_path, "src/lib.rs", 120.0)
    assert module["measured"] is False
    assert module["reason"].strip()
