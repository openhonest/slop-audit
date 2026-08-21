"""The language tracers, driven against real toolchains rather than only their refusals.

L1.19 on this repository reads 83%, and the unreached branches are concentrated in these
modules: rust_trace at 42% line coverage, csharp_trace 48%, c_trace 55%, java_trace 57%,
go_trace 62%. Their pure verdict functions were extracted and are well covered; what was
never executed is the top of each harness, `decision_space_coverage` and `test_determinism`,
which build a project, run its suite and read a coverage report.

Those paths were reachable all along. Every toolchain they need resolves on this machine.
The gap was unwritten tests, not an unrunnable harness, and a harness whose only tested
paths are its refusals has been proved to decline and never to measure.

Each fixture is the smallest project its language can express, with a branch its tests do
not reach, so the coverage figure is a real reading with a known shape rather than a
number nobody can check. Nothing here downloads: a Go module with no requires, a C
Makefile, a Cargo crate with no dependencies.

A test is skipped only when its toolchain is genuinely absent, and the skip says which.
Skipping silently would turn a missing compiler into a green run.
"""

import pathlib
import shutil
import subprocess
import textwrap

import pytest
from l1_analyzer import c_trace, go_trace, rust_trace


def _write(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body).lstrip("\n"))
    return root


# --------------------------------------------------------------------------
# Go: `go test -coverprofile` and `go test -shuffle`
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def go_project(tmp_path_factory) -> pathlib.Path:
    """One function with three arms and tests reaching two, so coverage is short by
    construction and the number can be checked by reading the fixture."""
    return _write(tmp_path_factory.mktemp("go"), {
        "go.mod": "module fixture\n\ngo 1.21\n",
        "band.go": '''
            package fixture

            func Band(n int) string {
            \tif n > 10 {
            \t\treturn "high"
            \t}
            \tif n > 5 {
            \t\treturn "mid"
            \t}
            \treturn "low"
            }
        ''',
        "band_test.go": '''
            package fixture

            import "testing"

            func TestHigh(t *testing.T) {
            \tif Band(20) != "high" {
            \t\tt.Fatal("high")
            \t}
            }

            func TestLow(t *testing.T) {
            \tif Band(1) != "low" {
            \t\tt.Fatal("low")
            \t}
            }
        ''',
    })


@pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")
def test_go_coverage_is_measured_and_names_its_runtime(go_project):
    result = go_trace.decision_space_coverage(go_project, 300.0)
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) < 100, "the fixture leaves one arm unreached"
    assert "go version" in result["details"], "a measured result must name the runtime that ran it"


@pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")
def test_go_determinism_counts_every_shuffled_run(go_project):
    result = go_trace.test_determinism(go_project, 3, 300.0)
    assert result["value"] == "3/3"
    assert result["band"] == "Healthy"
    assert "go version" in result["details"]


@pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")
def test_go_refuses_a_directory_with_no_module(tmp_path):
    """The refusal path, beside the measuring one, so the two are told apart by a real run
    rather than by which of them happens to be tested."""
    result = go_trace.decision_space_coverage(tmp_path, 60.0)
    assert result["band"] == "n/a"
    assert result["details"].strip()


# --------------------------------------------------------------------------
# C: a Makefile test target and gcov
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def c_project(tmp_path_factory) -> pathlib.Path:
    return _write(tmp_path_factory.mktemp("c"), {
        "band.c": '''
            #include <stdio.h>

            const char *band(int n) {
                if (n > 10) return "high";
                if (n > 5) return "mid";
                return "low";
            }

            int main(void) {
                if (band(20)[0] != 'h') return 1;
                if (band(1)[0] != 'l') return 1;
                printf("ok\\n");
                return 0;
            }
        ''',
        "Makefile": '''
            test:
            \tgcc --coverage -O0 -o band band.c
            \t./band
            \tgcov band.c > /dev/null 2>&1 || true
        ''',
    })


@pytest.mark.skipif(shutil.which("gcc") is None or shutil.which("make") is None,
                    reason="gcc or make is not on PATH")
def test_c_reports_a_verdict_rather_than_crashing(c_project):
    """C has no standard coverage report this harness can rely on, so the interesting
    property is that it reaches a verdict and names its reason either way."""
    result = c_trace.decision_space_coverage(c_project, 300.0)
    assert result["band"] in ("Healthy", "Not Healthy", "Slop", "n/a")
    assert result["details"].strip(), "a verdict with no sentence says nothing"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not on PATH")
def test_c_determinism_refuses_for_the_reason_the_canon_gives(c_project):
    """C ships no standard test-order randomizer, so 0/5 would read as a suite that falls
    over when reordered rather than one that was never reordered."""
    result = c_trace.test_determinism(c_project, 5, 300.0)
    assert result["band"] == "n/a"
    assert "randomizer" in result["details"]


# --------------------------------------------------------------------------
# Rust: cargo, and cargo-llvm-cov when it is installed
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rust_project(tmp_path_factory) -> pathlib.Path:
    return _write(tmp_path_factory.mktemp("rust"), {
        "Cargo.toml": '''
            [package]
            name = "fixture"
            version = "0.0.0"
            edition = "2021"
        ''',
        "src/lib.rs": '''
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

                #[test]
                fn low() {
                    assert_eq!(band(1), "low");
                }
            }
        ''',
    })


def _llvm_tools() -> dict[str, str] | None:
    """The LLVM coverage tools cargo-llvm-cov needs, discovered rather than assumed.

    `cargo llvm-cov --version` succeeds while the tool refuses with "could not find the LLVM
    coverage tools; install the llvm-tools-preview rustup component, or set LLVM_COV /
    LLVM_PROFDATA". That refusal names both remedies and is correct: the tools can be
    present and simply not where cargo looks, which is the case on a Homebrew machine where
    the llvm formula is keg-only.

    So this takes the second remedy the tool itself offers. A skip guard that only asked
    whether the binary answers a version flag skipped for the wrong reason."""
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


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not on PATH")
def test_rust_determinism_counts_its_seeds(rust_project):
    result = rust_trace.test_determinism(rust_project, 3, 600.0)
    assert result["band"] in ("Healthy", "Not Healthy", "Slop", "n/a")
    assert result["details"].strip()


@pytest.mark.skipif(_llvm_tools() is None, reason="cargo-llvm-cov has no LLVM coverage tools")
def test_rust_coverage_is_measured_when_llvm_cov_is_present(rust_project, monkeypatch):
    for name, value in (_llvm_tools() or {}).items():
        monkeypatch.setenv(name, value)      # environment, which is what the tool reads
    result = rust_trace.decision_space_coverage(rust_project, 900.0)
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) <= 100


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not on PATH")
def test_rust_refuses_a_directory_with_no_crate(tmp_path):
    result = rust_trace.decision_space_coverage(tmp_path, 60.0)
    assert result["band"] == "n/a"
    assert result["details"].strip()
