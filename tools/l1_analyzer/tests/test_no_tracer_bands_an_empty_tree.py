"""No language tracer bands a tree it never compiled.

Go did. `go test ./...` over a directory with no module exits non-zero having compiled
nothing, still writes a coverage profile, and `go tool cover -func` totals that empty
profile at 0.0% - the Slop end of the scale, for a tree the toolchain never touched.

That was the third appearance of the fabricated-zero shape in two days, so the answer is
not to fix one tracer. Every language's coverage tool has its own idea of what to emit when
there was nothing to measure, and reasoning about nine of them from their source is exactly
how Go's was missed: its refusal existed, was written for this case, and guarded the other
arm.

So this asks each of them, with the real toolchain, on the two shapes an audit actually
meets: a directory holding no source of that language at all, and a project of that
language whose packages carry no test. Neither can produce a band. A verdict of Healthy,
Not Healthy or Slop is a claim about code that ran, and no code ran.

A language is skipped only when its toolchain is genuinely absent, and the skip names it.
"""

import pathlib
import shutil

import pytest
from l1_analyzer import (
    c_trace,
    csharp_trace,
    go_trace,
    java_trace,
    js_trace,
    pytest_trace,
    ruby_trace,
    rust_trace,
)

# tracer, the binary its harness needs, and a source file that compiles but has no test.
LANGUAGES = [
    ("go", go_trace, "go", "band.go", "package fixture\n\nfunc Band() int { return 1 }\n"),
    ("rust", rust_trace, "cargo", "src/lib.rs", "pub fn band() -> i32 { 1 }\n"),
    ("c", c_trace, "gcc", "band.c", "int band(void) { return 1; }\n"),
    ("csharp", csharp_trace, "dotnet", "Band.cs", "public class Band { public int V => 1; }\n"),
    ("java", java_trace, "mvn", "src/main/java/Band.java", "public class Band { public int v() { return 1; } }\n"),
    ("javascript", js_trace, "node", "band.js", "module.exports = () => 1;\n"),
    ("ruby", ruby_trace, "ruby", "band.rb", "def band\n  1\nend\n"),
    ("python", pytest_trace, "python3", "band.py", "def band():\n    return 1\n"),
]

BANDS = ("Healthy", "Not Healthy", "Slop")


def _skip_unless(binary: str) -> None:
    if shutil.which(binary) is None:
        pytest.skip(f"{binary} is not on PATH")


def _coverage(tracer, repo: pathlib.Path) -> dict:
    """Each tracer's L1.19 entry point, whose signature differs by one argument."""
    if tracer is pytest_trace:
        return tracer.decision_space_coverage(repo, "python", 120.0, python_executable=None)
    if tracer is rust_trace:
        # Rust selects its toolchain from the crate, so this harness takes neither hint.
        return tracer.decision_space_coverage(repo, 120.0)
    return tracer.decision_space_coverage(repo, 120.0, runtime_override=None)


@pytest.mark.parametrize(("name", "tracer", "binary", "_path", "_source"), LANGUAGES,
                         ids=[row[0] for row in LANGUAGES])
def test_an_empty_directory_is_never_banded(name, tracer, binary, _path, _source, tmp_path):
    """The shape Go failed on: nothing of this language anywhere."""
    _skip_unless(binary)
    result = _coverage(tracer, tmp_path)
    assert result["band"] not in BANDS, (
        f"{name} banded an empty directory {result['band']} at {result['value']}: "
        f"{result['details']}"
    )


@pytest.mark.parametrize(("name", "tracer", "binary", "path", "source"), LANGUAGES,
                         ids=[row[0] for row in LANGUAGES])
def test_source_with_no_tests_is_never_banded(name, tracer, binary, path, source, tmp_path):
    """The likelier shape in a real audit: the language is there and the tests are not."""
    _skip_unless(binary)
    target = tmp_path / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    if name == "go":
        (tmp_path / "go.mod").write_text("module fixture\n\ngo 1.21\n")
    if name == "rust":
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "fixture"\nversion = "0.0.0"\nedition = "2021"\n')

    result = _coverage(tracer, tmp_path)
    assert result["band"] not in BANDS, (
        f"{name} banded a project with no tests {result['band']} at {result['value']}: "
        f"{result['details']}"
    )


@pytest.mark.parametrize(("name", "tracer", "binary", "_path", "_source"), LANGUAGES,
                         ids=[row[0] for row in LANGUAGES])
def test_the_refusal_gives_a_reason(name, tracer, binary, _path, _source, tmp_path):
    """A refusal with no sentence sends a reader nowhere. Every one of these has to name
    what was missing, because 'n/a' alone cannot be told from a tool that broke."""
    _skip_unless(binary)
    assert _coverage(tracer, tmp_path)["details"].strip()
