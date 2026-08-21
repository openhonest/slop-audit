"""Go coverage refuses when no test ran, instead of reporting the empty profile as 0.0%.

A directory with no Go module at all read **0.0% Slop**. `go test ./...` exits non-zero
having compiled nothing, still writes a coverage profile, and `go tool cover -func` totals
that empty profile at 0.0%. The verdict trusted the profile's existence and read the zero
as terrible coverage.

Zero is not neutral on this indicator: it is the Slop end of the scale, so a tree the
toolchain never compiled scored the worst possible reading. This is the fabricated-zero
shape the package has now found three times, and it was shipped in a language tracer.

`_ran_tests` was already in this module, written for exactly this distinction and used by
the determinism arm only: "the difference between a real determinism data point and the
suite never executing." The coverage arm needed the same question and never asked it.

Found by driving the tracers against real toolchains for the first time. Their pure verdict
functions were well covered; the tops of the harnesses had only ever been proved to refuse,
never to measure, and this defect lived between the two.
"""

import pathlib
import shutil
import textwrap

import pytest
from l1_analyzer import go_trace

pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")


@pytest.fixture(scope="module")
def go_project(tmp_path_factory) -> pathlib.Path:
    """Three arms, two reached, so a real reading is short by construction."""
    root = tmp_path_factory.mktemp("go")
    (root / "go.mod").write_text("module fixture\n\ngo 1.21\n")
    (root / "band.go").write_text(textwrap.dedent('''
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
    ''').lstrip("\n"))
    (root / "band_test.go").write_text(textwrap.dedent('''
        package fixture

        import "testing"

        func TestHigh(t *testing.T) {
        \tif Band(20) != "high" {
        \t\tt.Fatal("high")
        \t}
        }
    ''').lstrip("\n"))
    return root


def test_a_directory_with_no_module_refuses(tmp_path):
    """The defect. It read 0.0% Slop off a profile the toolchain wrote having compiled
    nothing."""
    result = go_trace.decision_space_coverage(tmp_path, 120.0, runtime_override=None)
    assert result["band"] == "n/a", (
        f"a tree with no Go module read {result['value']} {result['band']}: {result['details']}"
    )
    assert result["value"] == "n/a"


def test_a_module_with_no_test_files_refuses(tmp_path):
    """The other way to compile and run nothing, and the more likely one in a real audit:
    a Go module whose packages carry no test at all."""
    (tmp_path / "go.mod").write_text("module fixture\n\ngo 1.21\n")
    (tmp_path / "band.go").write_text("package fixture\n\nfunc Band() int { return 1 }\n")
    result = go_trace.decision_space_coverage(tmp_path, 120.0, runtime_override=None)
    assert result["band"] == "n/a", result["details"]


def test_the_refusal_says_no_test_ran(tmp_path):
    """A reader told n/a must be told which n/a: no Go here at all, or Go with no tests."""
    result = go_trace.decision_space_coverage(tmp_path, 120.0, runtime_override=None)
    assert result["details"].strip()
    assert "no test" in result["details"].lower() or "ran" in result["details"].lower()


def test_a_project_whose_tests_do_run_is_still_measured(go_project):
    """The measure must still measure, so the refusal is not a blanket one."""
    result = go_trace.decision_space_coverage(go_project, 300.0, runtime_override=None)
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) < 100
    assert "go version" in result["details"]
