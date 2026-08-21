"""Each language's definition collector is driven over the shapes it claims to read.

L1.12 divides definitions nothing references by production lines, so a shape the collector
never sees is a definition that cannot be called dead. Forty lines across twelve collectors
had never executed, and each is a declaration form real code uses constantly: a Ruby class,
a Go const block, a C file-scope variable, a Rust inner module.

That is worse than an untested branch. A collector blind to a shape does not fail; it
returns a smaller denominator and a smaller numerator, and reports a ratio over the subset
it happened to understand. Nothing says so.

These need no toolchain. The collectors are tree-sitter walks over source text, so the
fixtures are strings, and every one is a declaration form its language spells this way by
convention rather than a corner someone had to invent.
"""

import pathlib
import textwrap

import pytest
from l1_analyzer import dead_code


def _defs(tmp_path: pathlib.Path, name: str, source: str, lang: str) -> dict:
    (tmp_path / name).write_text(textwrap.dedent(source).lstrip("\n"))
    return dead_code.analyze(tmp_path, lang)


def _names(result: dict) -> set[str]:
    everything = result["findings"] + result["undecidable"] + result["test_only"]
    return {f["name"] for f in everything}


# --------------------------------------------------------------------------
# Ruby: a class, a module and a constant assignment
# --------------------------------------------------------------------------

def test_ruby_sees_classes_modules_and_constants(tmp_path):
    """Nine of this collector's twenty-five lines had never run, and they are the three
    ways Ruby declares something at the top level besides a method."""
    result = _defs(tmp_path, "shapes.rb", '''
        class Reader
          def read
            1
          end
        end

        module Helpers
          def self.help
            2
          end
        end

        LIMIT = 10
    ''', "ruby")
    assert result["band"] != "n/a", result["details"]
    found = _names(result)
    assert {"Reader", "Helpers", "LIMIT"} <= found, sorted(found)


# --------------------------------------------------------------------------
# Go: type and const blocks, which declare through a spec node
# --------------------------------------------------------------------------

def test_go_sees_type_and_const_blocks(tmp_path):
    """`type ( ... )` and `const ( ... )` put each name inside a spec, which is a level the
    walk had to descend and nothing had made it descend."""
    (tmp_path / "go.mod").write_text("module fixture\n\ngo 1.21\n")
    result = _defs(tmp_path, "shapes.go", '''
        package fixture

        type (
        \tReader struct{}
        \tWriter struct{}
        )

        const (
        \tLimit = 10
        \tFloor = 1
        )
    ''', "go")
    assert result["band"] != "n/a", result["details"]
    found = _names(result)
    assert {"Reader", "Writer", "Limit", "Floor"} <= found, sorted(found)


# --------------------------------------------------------------------------
# C: a file-scope variable, and main as an entry point
# --------------------------------------------------------------------------

def test_c_sees_a_file_scope_variable(tmp_path):
    """The variable has to be UNREFERENCED to appear in a dead list. The first version of
    this fixture had `bump` read the counter, so the collector saw it, correctly judged it
    live, and left it out of every list this test reads - which looked like a blind spot
    and was the collector working."""
    result = _defs(tmp_path, "shapes.c", '''
        static int unused_counter = 0;

        static int bump(void) {
            return 1;
        }
    ''', "c")
    assert result["band"] != "n/a", result["details"]
    assert "unused_counter" in _names(result), sorted(_names(result))


def test_c_excludes_main_as_an_entry_point(tmp_path):
    """`main` is reached by the runtime, not by a reference, so calling it dead would be
    the collector reporting its own blind spot as a finding."""
    result = _defs(tmp_path, "shapes.c", '''
        int helper(void) { return 1; }

        int main(void) { return helper(); }
    ''', "c")
    dead = {f["name"] for f in result["findings"]}
    assert "main" not in dead, "main was reported as unreferenced"


# --------------------------------------------------------------------------
# Rust: an inner module, and a test module that must be excluded
# --------------------------------------------------------------------------

def test_rust_descends_into_an_inner_module(tmp_path):
    """A `mod` body holds declarations, and the walk had to enter it."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "fixture"\nversion = "0.0.0"\nedition = "2021"\n')
    source = tmp_path / "src"
    source.mkdir()
    result = _defs(source, "lib.rs", '''
        pub mod inner {
            pub fn deep() -> i32 {
                1
            }
        }

        pub fn shallow() -> i32 {
            1
        }
    ''', "rust")
    assert result["band"] != "n/a", result["details"]
    assert "deep" in _names(result), sorted(_names(result))


def test_rust_does_not_walk_into_a_test_module(tmp_path):
    """A `#[cfg(test)]` module is not production code, so its helpers are not definitions
    the ratio should count in either half."""
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "fixture"\nversion = "0.0.0"\nedition = "2021"\n')
    source = tmp_path / "src"
    source.mkdir()
    result = _defs(source, "lib.rs", '''
        pub fn band() -> i32 {
            1
        }

        #[cfg(test)]
        mod tests {
            fn only_a_test_helper() -> i32 {
                2
            }
        }
    ''', "rust")
    assert "only_a_test_helper" not in {f["name"] for f in result["findings"]}


# --------------------------------------------------------------------------
# The property all of them share
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("name", "lang", "source"), [
    ("shapes.rb", "ruby", "class A\n  def m\n    1\n  end\nend\n"),
    ("shapes.c", "c", "static int v = 0;\nint f(void) { return v; }\n"),
])
def test_a_collector_that_sees_a_shape_counts_it_in_the_denominator(name, lang, source, tmp_path):
    """Why a blind spot is worse than a failure. A collector that cannot see a declaration
    shrinks BOTH halves of the ratio and reports a number over the subset it understood,
    with nothing saying which subset that was."""
    result = _defs(tmp_path, name, source, lang)
    assert result["band"] != "n/a"
    assert result["counts"], result["details"]
    assert sum(result["counts"].values()) > 0, "nothing was enumerated at all"
