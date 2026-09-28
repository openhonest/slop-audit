"""A Rust unit test lives in the file it tests, and eight indicators read it as production code.

Every other rule that sets tests aside works on a path: a directory named tests, a file stem
ending in _test or .spec. Rust writes `#[cfg(test)] mod tests { ... }` inside the module under
test, so no path names it. Counted under the production scope, 2,532 of uuid-rs/uuid's 9,821
lines are inside a test module and 4,300 of the Rust port's own 21,633 are.

The region comes out as spaces of the same length, newlines kept, so a reader that reports line
391 still means line 391 of the file the author wrote. The tests below hold that promise, hold
the cfg predicate apart from the word test, and hold the three readers that divide by a line
count to the lines that are left.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import indicators, test_regions
from l1_analyzer.boundary import boundary
from l1_analyzer.scope import PRODUCTION, WHOLE_REPO, _read_source_bytes

A_CRATE = '''pub fn band(n: i32) -> &'static str {
    if n < 0 { "neg" } else { "pos" }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn negatives_are_neg() {
        assert_eq!(band(-1), "neg");
    }
}
'''

# The two orders an item's attributes come in, and the item bare in between. Taking the
# marking attribute and its next sibling left `fn guid_to_uuid` standing with no attribute in
# front of it, so the dead-code reader called somebody's example dead. uuid-rs/uuid writes
# three of these and the 68 crates write 391.
# The bodies differ, which the fixture does not need and a reader does: two functions of one
# shape are a finding in this package's own L1.21.1, and a fixture that has to be waived reads
# as a rule bending for its author.
BOTH_ORDERS = '''#[test]
#[cfg(windows)]
fn guid_to_uuid() { assert_eq!(1 + 1, 2); }

#[cfg(windows)]
#[test]
fn uuid_to_guid() { let n: i32 = 3; assert!(n > 0, "{n}"); }

pub fn shipped() -> i32 { 1 }
'''

# The trap. `any` means the item ships whenever either condition holds, so a build with the
# std feature on includes it, and excluding it would delete production code from the
# measurement. Thirteen items on that machine are written this way.
SHIPS_ANYWAY = '''#[cfg(any(test, feature = "std"))]
pub fn with_std() -> i32 { 1 }

#[cfg(feature = "test_debug")]
pub fn debug_only() -> String { "debug".to_string() }

#[cfg(doctest)]
pub fn doc_only(n: i32) -> i32 { n * 3 }
'''


@boundary
def a_crate(tmp_path: Path, source: str) -> Path:
    """A one-file crate under src, where no path rule can call the file a test."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(source)
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "sample"\nversion = "0.1.0"\n')
    return tmp_path


def test_a_test_module_comes_out_and_the_production_function_stays():
    out, region_lines = test_regions.blanked(A_CRATE.encode("utf8"), ".rs")
    text = out.decode("utf8")
    assert "pub fn band" in text
    assert "negatives_are_neg" not in text
    assert "mod tests" not in text
    # Lines 5 to 13 of the fixture, the attribute and the module it marks. The blank line
    # inside the module is in the region too, because it is a line of the module: comparing
    # bytes could not see it, and it stayed in the denominator.
    assert region_lines == frozenset(range(5, 14)), sorted(region_lines)


def test_every_line_number_is_still_the_authors():
    """Spaces rather than deletion. A reader that says line 391 must mean the author's 391."""
    out, _ = test_regions.blanked(A_CRATE.encode("utf8"), ".rs")
    assert len(out) == len(A_CRATE.encode("utf8"))
    assert out.count(b"\n") == A_CRATE.encode("utf8").count(b"\n")
    assert out.decode("utf8").splitlines()[0] == A_CRATE.splitlines()[0]


def test_an_attribute_run_goes_with_the_item_it_marks():
    """Both orders, because the marking attribute need not be the one next to the function."""
    out, _ = test_regions.blanked(BOTH_ORDERS.encode("utf8"), ".rs")
    text = out.decode("utf8")
    assert "guid_to_uuid" not in text
    assert "uuid_to_guid" not in text
    assert "cfg(windows)" not in text, "an attribute left in front of nothing is not Rust"
    assert "pub fn shipped" in text


def test_a_cfg_that_mentions_test_but_ships_anyway_is_left_alone():
    """Missing a test region leaves the old answer. Excluding a production item deletes
    somebody's code from the measurement, which is the worse of the two."""
    out, region_lines = test_regions.blanked(SHIPS_ANYWAY.encode("utf8"), ".rs")
    text = out.decode("utf8")
    assert "with_std" in text
    assert "debug_only" in text
    assert "doc_only" in text
    assert region_lines == frozenset()


def test_a_comment_between_an_attribute_and_its_item_stays_inside_the_region():
    """A comment written there is Rust, and it is common.

    tree-sitter gives it its own named node, so the run of attributes ended at the attributes
    and the comment was read as the item they marked. The function was left bare and private
    and called by nothing, which is the dead-code false positive the attribute run already
    fixed from the other end."""
    src = (b"#[test]\n#[cfg(windows)]\n// why this one is windows-only\n"
           b"fn guid_to_uuid() { assert!(true); }\n\npub fn shipped() -> i32 { 1 }\n")
    out, region_lines = test_regions.blanked(src, ".rs")
    text = out.decode("utf8")
    assert "guid_to_uuid" not in text, text
    assert "windows" not in text, text
    assert "pub fn shipped" in text, text
    assert region_lines == frozenset({1, 2, 3, 4}), sorted(region_lines)


def test_the_other_eight_languages_come_back_untouched():
    """One language has a row in the table, and the emptiness of the rest is the finding."""
    python = b"def band(n):\n    return 'neg' if n < 0 else 'pos'\n"
    assert test_regions.blanked(python, ".py") == (python, frozenset())
    assert test_regions.blanked(b"func Band() int { return 1 }\n", ".go")[1] == frozenset()


def test_a_reader_under_the_production_scope_never_sees_the_test_lines(tmp_path):
    repo = a_crate(tmp_path, A_CRATE)
    files, _skipped, test_lines = _read_source_bytes(repo, (".rs",), scope=PRODUCTION)
    (path, src), = files
    assert b"negatives_are_neg" not in src
    assert test_lines[path] == 9


def test_the_whole_repo_scope_still_sees_them(tmp_path):
    """L1.8 and L1.16 measure the test code on purpose, so that scope declares no stripping
    and a test file's own lines stay readable to them."""
    repo = a_crate(tmp_path, A_CRATE)
    files, _skipped, test_lines = _read_source_bytes(repo, (".rs",), scope=WHOLE_REPO)
    (_path, src), = files
    assert b"negatives_are_neg" in src
    assert test_lines == {}


def test_the_correction_is_per_file_so_a_dropped_file_drops_its_own(tmp_path):
    """The dead-code reader subtracts a file the grammar could not parse from the count it
    publishes as analyzed. One repository total cannot say which file's lines those were, and
    subtracting the total twice published a negative."""
    repo = a_crate(tmp_path, A_CRATE)
    (repo / "src" / "other.rs").write_text(A_CRATE)
    _files, _skipped, test_lines = _read_source_bytes(repo, (".rs",), scope=PRODUCTION)
    assert sorted(p.name for p in test_lines) == ["lib.rs", "other.rs"]
    assert set(test_lines.values()) == {9}


def test_the_god_file_line_measures_the_production_half(tmp_path):
    """A 1,302-line file holding 402 lines of test module is a 900-line production file. This
    reader opens files itself rather than through the scope's reader, so it is the one place
    the declaration and the behaviour can drift apart."""
    logic = "".join(f"pub fn f{n}() -> i32 {{ {n} }}\n" for n in range(900))
    tests = ("#[cfg(test)]\nmod tests {\n"
             + "".join(f"    #[test]\n    fn t{n}() {{ assert_eq!(f{n}(), {n}); }}\n"
                       for n in range(200))
             + "}\n")
    repo = a_crate(tmp_path, logic + tests)
    assert len((logic + tests).splitlines()) > 1300
    result = indicators._god_files(repo)
    assert result["value"] == 0.0, result["details"]
    assert "0/1 files >1k LOC" in result["details"], result["details"]
