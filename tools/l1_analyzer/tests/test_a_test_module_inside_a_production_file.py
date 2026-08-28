"""Rust keeps its tests in the file they test, and we graded them as production code.

Every other language this tool reads puts tests in their own file, so the scope module can
tell one from the other by name and by directory. Rust puts a test module inside the file it
tests, behind a compile-time marker, and the file is production by every name it carries. So
the tests were handed to every production clause.

Found by opening L1.21's door to the languages the vocabulary already covered: the first Rust
file it read reported three of this repository's own test functions as three functions of one
shape. They are three tests differing in their data, which is what a table of cases looks
like, and the clause was right about the shape and wrong about the code.

The marker is a language fact, so the vocabulary holds it. A language that keeps tests
elsewhere names none, and nothing changes for it.
"""

import pytest
from l1_analyzer import honest_code_read as read
from l1_analyzer import honest_code_rules as rules
from l1_analyzer.lang_spec import LANG_SPEC

_RUST = '''pub fn count(lang: &str, src: &str) -> usize {
    lang.len() + src.len()
}

#[cfg(test)]
mod tests {
    use super::count;

    #[test]
    fn java_annotation_is_counted() {
        assert_eq!(count("java", "a"), 5);
    }

    #[test]
    fn java_annotation_counts_once() {
        assert_eq!(count("java", "bb"), 6);
    }

    #[test]
    fn java_comment_is_documentation() {
        assert_eq!(count("java", "ccc"), 7);
    }
}
'''


def test_the_functions_a_production_clause_reads_exclude_the_test_module():
    tree = read.read_tree(_RUST, "rust")
    named = [read.node_text(f.child_by_field_name("name"), tree["raw"])
             for f in read.function_nodes(tree["root"], tree["spec"])]
    assert named == ["count"], named


def test_three_tests_differing_only_in_their_data_are_not_three_functions_of_one_shape():
    """The finding that started this. They are a table of cases, which is the shape the
    clause asks for, written the way the language writes it."""
    found = rules.dispatch_chains(read.read_tree(_RUST, "rust")) or []
    assert [f for f in found if f["clause"] == "L1.21.1"] == [], found


def test_a_production_function_beside_the_test_module_is_still_read():
    """The direction that must not move. Excluding the module must not exclude the file."""
    tree = read.read_tree(_RUST, "rust")
    assert read.function_nodes(tree["root"], tree["spec"]), "the file's own code went missing"


def test_the_marker_is_a_language_fact_the_table_holds():
    assert "cfg(test)" in " ".join(LANG_SPEC["rust"]["test_module_markers"])


@pytest.mark.parametrize("lang", ["python", "javascript", "java", "csharp", "go", "ruby", "c"])
def test_a_language_that_keeps_its_tests_elsewhere_names_no_marker(lang):
    """Nothing changes for them, and a marker invented here would start excluding code."""
    assert LANG_SPEC[lang]["test_module_markers"] == ()
