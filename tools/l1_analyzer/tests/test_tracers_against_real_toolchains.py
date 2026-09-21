"""The language tracers, driven against real toolchains rather than only their refusals.

L1.19 on this repository reads 83%, and the unreached branches are concentrated in these
modules: rust_trace at 42% line coverage, csharp_trace 48%, c_trace 55%, java_trace 57%,
go_trace 62%. Their pure verdict functions were extracted and are well covered; what was
never executed is the top of each harness, `decision_space_coverage` and `test_determinism`,
which build a project, run its suite and read a coverage report.

Those paths were reachable all along. Every toolchain they need resolves on this machine.
The gap was unwritten tests, not an unrunnable harness, and a harness whose only tested
paths are its refusals has been proved to decline and never to measure.

Each fixture is the smallest project its language can express, with four decision branches
and a test reaching two, so every harness that measures anything here reads 50 per cent and
a figure that is not 50 is a figure somebody can go and check. Go, C and Rust download
nothing. C#, JavaScript, Java and Ruby each fetch their test framework on a cold cache,
which is what those four languages cost to run a suite at all.

Seven languages measure here and one refuses: `node --test` has no way to vary the order it
runs in, so JavaScript determinism is a refusal rather than a score.

A test is skipped only when its toolchain is genuinely absent, and the skip says which.
Skipping silently would turn a missing compiler into a green run.

What is still unheld, and needs software nobody has installed here: the version-manager
paths. `resolve_via_shim` asks rbenv, jenv, asdf or mise which runtime a repository wants,
and none of the four is on this machine.

Two defects came out of writing these. The Java harness read Maven's console for the line
that says how many tests ran, and both its commands pass `-q`, which deletes that line; so
every Maven project was reported as never having run its suite. And Ruby was filed as
blocked on a version manager when its fixture's Gemfile was simply missing rake and
minitest: bundler hides the default gems, and the LoadError that follows reads like a
broken Ruby.
"""

import pathlib
import shutil
import subprocess
import textwrap

import pytest
from l1_analyzer import c_trace, go_trace, rust_trace
from l1_analyzer.boundary import boundary


@boundary
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
    result = go_trace.decision_space_coverage(go_project, 300.0, runtime_override=None)
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) < 100, "the fixture leaves one arm unreached"
    assert "go version" in result["details"], "a measured result must name the runtime that ran it"


@pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")
def test_go_determinism_counts_every_shuffled_run(go_project):
    result = go_trace.test_determinism(go_project, 3, 300.0, runtime_override=None)
    assert result["value"] == "3/3"
    assert result["band"] == "Healthy"
    assert "go version" in result["details"]


@pytest.mark.skipif(shutil.which("go") is None, reason="go is not on PATH")
def test_go_refuses_a_directory_with_no_module(tmp_path):
    """The refusal path, beside the measuring one, so the two are told apart by a real run
    rather than by which of them happens to be tested."""
    result = go_trace.decision_space_coverage(tmp_path, 60.0, runtime_override=None)
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
    result = c_trace.decision_space_coverage(c_project, 300.0, runtime_override=None)
    assert result["band"] in ("Healthy", "Not Healthy", "Slop", "n/a")
    assert result["details"].strip(), "a verdict with no sentence says nothing"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not on PATH")
def test_c_determinism_refuses_for_the_reason_the_canon_gives(c_project):
    """C ships no standard test-order randomizer, so 0/5 would read as a suite that falls
    over when reordered rather than one that was never reordered."""
    result = c_trace.test_determinism(c_project, 5, 300.0, runtime_override=None)
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


@boundary
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
    result = rust_trace.decision_space_coverage(rust_project, 900.0, ())
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) <= 100


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo is not on PATH")
def test_rust_refuses_a_directory_with_no_crate(tmp_path):
    result = rust_trace.decision_space_coverage(tmp_path, 60.0, ())
    assert result["band"] == "n/a"
    assert result["details"].strip()


# --------------------------------------------------------------------------
# C#: `dotnet test --collect "XPlat Code Coverage"` and a Cobertura report
#
# This fixture restores NuGet packages, so it reaches the network on a machine whose cache
# is cold. Go, C and Rust above need nothing; this one does, and saying so beats a comment
# claiming the whole file is offline when one quarter of it is not.
#
# Two projects and a solution file, because that is the shape a C# repository has and the
# harness runs `dotnet test` at the repository root. A single test project put the code
# under test inside the test assembly, which coverlet excludes, and the harness said so in
# as many words; that refusal is held below rather than designed around.
# --------------------------------------------------------------------------

@boundary
def _dotnet_project(root: pathlib.Path) -> pathlib.Path:
    """A library with three branches and a test that reaches one of them.

    Scaffolded with `dotnet new` rather than written out, because the template carries the
    package references and the target framework this SDK expects, and pinning either here
    would make the fixture stale the next time the SDK moves."""
    lib, tests = root / "lib", root / "tests"
    lib.mkdir()
    tests.mkdir()
    subprocess.run(["dotnet", "new", "classlib", "-o", "."], cwd=lib, check=True,
                   capture_output=True)
    subprocess.run(["dotnet", "new", "xunit", "-o", "."], cwd=tests, check=True,
                   capture_output=True)
    (lib / "Class1.cs").unlink(missing_ok=True)
    (tests / "UnitTest1.cs").unlink(missing_ok=True)
    _write(root, {
        "lib/Classify.cs": '''
            namespace Lib;

            public static class Classify
            {
                public static string Band(int n)
                {
                    if (n < 0) { return "neg"; }
                    if (n == 0) { return "zero"; }
                    return "pos";
                }
            }
        ''',
        "tests/ClassifyTests.cs": '''
            using Lib;

            namespace Tests;

            public class ClassifyTests
            {
                [Fact]
                public void PositiveIsPositive() { Assert.Equal("pos", Classify.Band(3)); }
            }
        ''',
    })
    subprocess.run(["dotnet", "add", "reference", str(lib / "lib.csproj")],
                   cwd=tests, check=True, capture_output=True)
    # The solution file through `dotnet` rather than written out. A hand-rolled one parsed
    # and then produced no coverage, and the harness reported that as a missing collector,
    # which sent the reader to the test project rather than to the solution.
    subprocess.run(["dotnet", "new", "sln", "-n", "fixture"], cwd=root, check=True,
                   capture_output=True)
    subprocess.run(["dotnet", "sln", "add", str(lib / "lib.csproj"), str(tests / "tests.csproj")],
                   cwd=root, check=True, capture_output=True)
    return root


@pytest.fixture(scope="module")
def csharp_project(tmp_path_factory) -> pathlib.Path:
    return _dotnet_project(tmp_path_factory.mktemp("csharp"))


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet is not on PATH")
def test_csharp_coverage_is_read_from_a_real_cobertura_report(csharp_project):
    """The whole path: build, run the suite, drive the data collector, find the report it
    wrote and read its branch counts. Every one of those steps was proved only through a
    fake before this."""
    from l1_analyzer import csharp_trace

    result = csharp_trace.decision_space_coverage(csharp_project, 900.0, None)
    assert result["band"] != "n/a", result["details"]
    assert result["value"] == 50.0, result["details"]
    assert "2/4 decision branches" in result["details"]
    assert "dotnet" in result["details"], "the reading does not name the runtime that took it"


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet is not on PATH")
def test_csharp_determinism_counts_every_run(csharp_project):
    """`dotnet test` has no seed flag, so the runs vary by scheduler rather than by seed and
    the sentence has to say which. A reader comparing this against a language that does seed
    its runs would otherwise read the same words for two different guarantees."""
    from l1_analyzer import csharp_trace

    result = csharp_trace.test_determinism(csharp_project, 3, 900.0, runtime_override=None)
    assert result["value"] == "3/3"
    assert result["band"] == "Healthy"
    assert "not seed-controlled" in result["details"]


@pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet is not on PATH")
def test_csharp_refuses_a_directory_with_no_project(tmp_path):
    """The refusal beside the measurement, so a real run tells them apart rather than which
    of the two somebody remembered to test."""
    from l1_analyzer import csharp_trace

    result = csharp_trace.decision_space_coverage(tmp_path, 120.0, None)
    assert result["band"] == "n/a"
    assert result["details"].strip()


# --------------------------------------------------------------------------
# JavaScript: c8 over `node --test`, and the refusal when no runner shuffles
#
# This fixture installs one package, so it reaches the network on a cold cache, like the
# C# one above. The harness will not install anything itself and says so when node_modules
# is missing, which is the right refusal and is held below.
# --------------------------------------------------------------------------

@boundary
@pytest.fixture(scope="module")
def js_project(tmp_path_factory) -> pathlib.Path:
    """Three branches, a test that reaches one, and c8 to measure it."""
    root = _write(tmp_path_factory.mktemp("js"), {
        "package.json": '''
            {
              "name": "fixture",
              "version": "1.0.0",
              "type": "module",
              "scripts": { "test": "node --test" },
              "devDependencies": { "c8": "^10.1.3" }
            }
        ''',
        "band.js": '''
            export function band(n) {
              if (n < 0) return "neg";
              if (n === 0) return "zero";
              return "pos";
            }
        ''',
        "band.test.js": '''
            import { test } from "node:test";
            import assert from "node:assert";
            import { band } from "./band.js";
            test("positive", () => { assert.equal(band(3), "pos"); });
        ''',
    })
    subprocess.run(["npm", "install", "--silent", "--no-audit", "--no-fund"],
                   cwd=root, check=True, capture_output=True)
    return root


@pytest.mark.skipif(shutil.which("npm") is None or shutil.which("node") is None,
                    reason="node or npm is not on PATH")
def test_javascript_coverage_is_read_from_a_real_c8_summary(js_project):
    """Run the suite under c8, find the summary it wrote, read its branch percentage. Proved
    only through a fake before this."""
    from l1_analyzer import js_trace

    result = js_trace.decision_space_coverage(js_project, 900.0, runtime_override=None)
    assert result["band"] != "n/a", result["details"]
    assert result["value"] == 50.0, result["details"]
    assert "c8" in result["details"] and "v" in result["details"]


@pytest.mark.skipif(shutil.which("npm") is None or shutil.which("node") is None,
                    reason="node or npm is not on PATH")
def test_javascript_determinism_refuses_a_runner_that_cannot_shuffle(js_project):
    """The refusal that matters most here. `node --test` runs in one order and offers no way
    to vary it, so five identical runs would say nothing about determinism and a score over
    them would be a number nobody earned. It names the runner it found."""
    from l1_analyzer import js_trace

    result = js_trace.test_determinism(js_project, 3, 900.0, runtime_override=None)
    assert result["band"] == "n/a"
    assert "node --test" in result["details"]
    assert "shuffle" in result["details"] or "seed" in result["details"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_javascript_refuses_a_project_whose_dependencies_are_not_installed(tmp_path):
    """The harness runs a repository's own suite and does not install anything for it. A
    project with no node_modules is told that, rather than being measured at zero."""
    from l1_analyzer import js_trace

    (tmp_path / "package.json").write_text('{"name": "x", "scripts": {"test": "node --test"}}')
    result = js_trace.decision_space_coverage(tmp_path, 120.0, runtime_override=None)
    assert result["band"] == "n/a"
    assert "node_modules" in result["details"]


# --------------------------------------------------------------------------
# Java: JaCoCo over Maven, and Surefire's randomized run order
#
# Maven fetches JUnit and the JaCoCo plugin into ~/.m2 on a cold cache, so this fixture
# reaches the network the first time, like the C# and JavaScript ones above.
#
# The determinism test below is why this section exists. Both Maven commands pass `-q` to
# keep an untrusted project's build chatter out of the result, `-q` suppresses Surefire's
# `Tests run:` summary, and the harness was reading that summary to decide whether any test
# had executed. So every Maven project got "the suite did not run", and no test caught it
# because no test had ever run Maven.
# --------------------------------------------------------------------------

_JAVA_POM = '''
    <project xmlns="http://maven.apache.org/POM/4.0.0">
      <modelVersion>4.0.0</modelVersion>
      <groupId>fixture</groupId>
      <artifactId>band</artifactId>
      <version>1.0</version>
      <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
      </properties>
      <dependencies>
        <dependency>
          <groupId>org.junit.jupiter</groupId>
          <artifactId>junit-jupiter</artifactId>
          <version>5.10.2</version>
          <scope>test</scope>
        </dependency>
      </dependencies>
      <build><plugins>
        <plugin>
          <groupId>org.jacoco</groupId>
          <artifactId>jacoco-maven-plugin</artifactId>
          <version>0.8.12</version>
          <executions>
            <execution><goals><goal>prepare-agent</goal></goals></execution>
            <execution><id>report</id><phase>test</phase><goals><goal>report</goal></goals></execution>
          </executions>
        </plugin>
      </plugins></build>
    </project>
'''


@pytest.fixture(scope="module")
def java_project(tmp_path_factory) -> pathlib.Path:
    """Four branches, a test reaching two, and JaCoCo in the build to count them."""
    return _write(tmp_path_factory.mktemp("java"), {
        "pom.xml": _JAVA_POM,
        "src/main/java/band/Band.java": '''
            package band;

            public final class Band {
                public static String classify(int n) {
                    if (n < 0) { return "neg"; }
                    if (n == 0) { return "zero"; }
                    return "pos";
                }
            }
        ''',
        "src/test/java/band/BandTest.java": '''
            package band;

            import static org.junit.jupiter.api.Assertions.assertEquals;
            import org.junit.jupiter.api.Test;

            class BandTest {
                @Test void positive() { assertEquals("pos", Band.classify(3)); }
            }
        ''',
    })


@pytest.mark.skipif(shutil.which("mvn") is None, reason="Maven (mvn) is not on PATH")
def test_java_coverage_is_read_from_a_real_jacoco_report(java_project):
    """Build, run the suite under the JaCoCo agent, read the BRANCH counters it wrote."""
    from l1_analyzer import java_trace

    result = java_trace.decision_space_coverage(java_project, 900.0, None)
    assert result["band"] != "n/a", result["details"]
    assert result["value"] == 50.0, result["details"]
    assert "2/4 decision branches" in result["details"]
    assert "openjdk" in result["details"] or "java" in result["details"]


@pytest.mark.skipif(shutil.which("mvn") is None, reason="Maven (mvn) is not on PATH")
def test_java_determinism_sees_a_suite_that_ran(java_project):
    """A suite that runs and passes three times is 3/3, not a refusal.

    Against the harness as it stood, this read "the suite did not run", because the only
    place it looked for a test count was a console line `-q` had already deleted. The fix
    reads the XML Surefire writes for machines, which `-q` does not touch, so a passing run
    now looks like one."""
    from l1_analyzer import java_trace

    result = java_trace.test_determinism(java_project, 3, 900.0, runtime_override=None)
    assert result["value"] == "3/3", result["details"]
    assert result["band"] == "Healthy"
    assert "did not run" not in result["details"]


@pytest.mark.skipif(shutil.which("mvn") is None, reason="Maven (mvn) is not on PATH")
def test_java_determinism_refuses_a_module_with_no_tests(tmp_path):
    """A pom that compiles and runs nothing is not five clean runs. It is nothing to score,
    and the refusal says so rather than banding an empty suite Healthy."""
    from l1_analyzer import java_trace

    _write(tmp_path, {
        "pom.xml": _JAVA_POM,
        "src/main/java/band/Band.java": '''
            package band;

            public final class Band {
                public static String classify(int n) { return n < 0 ? "neg" : "pos"; }
            }
        ''',
    })
    result = java_trace.test_determinism(tmp_path, 2, 900.0, runtime_override=None)
    assert result["band"] == "n/a"
    assert "did not run" in result["details"]


def test_java_refuses_a_gradle_project(tmp_path):
    """Named as not yet supported rather than measured at zero. No toolchain needed, so this
    one runs everywhere and the Maven tests above are what get skipped."""
    from l1_analyzer import java_trace

    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    result = java_trace.decision_space_coverage(tmp_path, 120.0, None)
    assert result["band"] == "n/a"
    assert "Gradle" in result["details"]


# --------------------------------------------------------------------------
# Ruby: SimpleCov branch coverage, and Minitest's seed
#
# This section was filed as blocked on a version manager. It was not. The system Ruby is
# 2.6 and the failures looked like a shim problem, but the fixture's Gemfile was simply
# missing rake and minitest: bundler hides the default gems, so a project that declares
# neither gets a LoadError that reads like a broken install. Both harness paths run here
# against the Ruby that ships with the machine.
#
# `bundle install` reaches the network on a cold cache, and it installs into the project
# rather than the system gem directory, which is not writable.
# --------------------------------------------------------------------------

_RUBY_SOURCE = {
    "Gemfile": '''
        source "https://rubygems.org"
        gem "rake"
        gem "minitest"
        gem "simplecov"
    ''',
    "Rakefile": '''
        require "rake/testtask"
        Rake::TestTask.new(:test) do |t|
          t.libs << "lib" << "test"
          t.test_files = FileList["test/**/*_test.rb"]
        end
    ''',
    "lib/band.rb": '''
        def band(n)
          return "neg" if n < 0
          return "zero" if n == 0
          "pos"
        end
    ''',
}

# The suite, with SimpleCov started before anything is required, and the same suite without
# it. SimpleCov cannot be injected into a project from outside, which is why the harness
# refuses rather than reporting zero, and the pair below is what proves both readings.
_RUBY_MEASURED = '''
    require "simplecov"
    SimpleCov.enable_coverage :branch
    SimpleCov.start
    require "minitest/autorun"
    require "band"
    class BandTest < Minitest::Test
      def test_positive
        assert_equal "pos", band(3)
      end
    end
'''
_RUBY_UNMEASURED = '''
    require "minitest/autorun"
    require "band"
    class BandTest < Minitest::Test
      def test_positive
        assert_equal "pos", band(3)
      end
    end
'''


# The two projects, which differ by their suite file and nothing else: one has SimpleCov
# started and one does not.
_RUBY_SUITES = {"measured": _RUBY_MEASURED, "unmeasured": _RUBY_UNMEASURED}


@boundary
def _bundled(root: pathlib.Path, suite: str) -> pathlib.Path:
    """A Ruby project with its gems installed into itself."""
    _write(root, dict(_RUBY_SOURCE, **{"test/band_test.rb": suite}))
    subprocess.run(["bundle", "install", "--path", "vendor/bundle"],
                   cwd=root, check=True, capture_output=True)
    return root


@pytest.fixture(scope="module")
def ruby_projects(tmp_path_factory) -> dict[str, pathlib.Path]:
    """Both Ruby projects, built once each from the table above. Four branches and a test
    reaching two, measured under SimpleCov in one and unrecorded in the other."""
    return {name: _bundled(tmp_path_factory.mktemp(f"ruby_{name}"), suite)
            for name, suite in _RUBY_SUITES.items()}


@pytest.mark.skipif(shutil.which("bundle") is None or shutil.which("ruby") is None,
                    reason="ruby or bundler is not on PATH")
def test_ruby_coverage_is_read_from_a_real_simplecov_resultset(ruby_projects):
    """Run the suite under SimpleCov, find the result set it wrote and read its branch
    counts. Proved only through a fake before this."""
    from l1_analyzer import ruby_trace

    result = ruby_trace.decision_space_coverage(ruby_projects["measured"], 900.0, None)
    assert result["band"] != "n/a", result["details"]
    assert result["value"] == 50.0, result["details"]
    assert "2/4 decision branches" in result["details"]
    assert "ruby" in result["details"]


@pytest.mark.skipif(shutil.which("bundle") is None or shutil.which("ruby") is None,
                    reason="ruby or bundler is not on PATH")
def test_ruby_refuses_a_suite_that_ran_without_simplecov(ruby_projects):
    """The refusal this harness exists for. The suite runs and passes; nothing recorded what
    it covered. Reporting zero would read as a project with terrible coverage rather than as
    a project nobody measured, and SimpleCov has to be started by the project itself."""
    from l1_analyzer import ruby_trace

    result = ruby_trace.decision_space_coverage(ruby_projects["unmeasured"], 900.0, None)
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"
    assert "SimpleCov" in result["details"]


@pytest.mark.skipif(shutil.which("bundle") is None or shutil.which("ruby") is None,
                    reason="ruby or bundler is not on PATH")
def test_ruby_determinism_runs_the_suite_once_per_seed(ruby_projects):
    """Minitest takes a seed, so each run really is a different order rather than the same
    one counted three times."""
    from l1_analyzer import ruby_trace

    result = ruby_trace.test_determinism(ruby_projects["measured"], 3, 900.0, None)
    assert result["value"] == "3/3", result["details"]
    assert result["band"] == "Healthy"


def test_ruby_refuses_a_directory_with_no_suite(tmp_path):
    """No spec directory, no test directory with a Rakefile, nothing to run. Named, rather
    than measured at zero. No toolchain needed, so this one runs everywhere."""
    from l1_analyzer import ruby_trace

    (tmp_path / "Gemfile").write_text('source "https://rubygems.org"\n')
    result = ruby_trace.decision_space_coverage(tmp_path, 120.0, None)
    assert result["band"] == "n/a"
    assert "Minitest" in result["details"] or "RSpec" in result["details"]
