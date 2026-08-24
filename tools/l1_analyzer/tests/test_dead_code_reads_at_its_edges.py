"""Clause 4 on the dead-code reader: the classifying lifted out of the walking.

`_read_corpus` walked the repository, read every file, and decided what each one
contributed, all in one loop. So the deciding could not be exercised without a filesystem,
and a question as ordinary as "does a binary file contribute words" needed a temporary
directory to ask.

The walk is a boundary and stays one. What comes out is the classifying, which decides from
one file's bytes and its suffix and touches nothing.
"""

import pathlib

from l1_analyzer import dead_code


def _empty() -> dict:
    return {"hard": {}, "words": {"strings": set(), "config": set(), "docs": set()},
            "unreadable": 0}


def test_a_documentation_file_contributes_its_words_as_documentation():
    corpus = _empty()
    dead_code.classify_into(corpus, "README.md", ".md", b"see run_report for details")
    assert "run_report" in corpus["words"]["docs"]
    assert corpus["words"]["config"] == set()


def test_a_configuration_file_contributes_its_words_as_configuration():
    corpus = _empty()
    dead_code.classify_into(corpus, "ci.yml", ".yml", b"run: run_report --now")
    assert "run_report" in corpus["words"]["config"]
    assert corpus["words"]["docs"] == set()


def test_a_binary_file_contributes_nothing():
    """It used to need a temporary directory to ask this."""
    corpus = _empty()
    dead_code.classify_into(corpus, "logo.png", ".png", b"\x89PNG\x00\x00run_report")
    assert corpus["words"]["config"] == set() and corpus["words"]["docs"] == set()


def test_source_is_parsed_rather_than_word_matched():
    corpus = _empty()
    dead_code.classify_into(corpus, "m.py", ".py", b"def run_report():\n    return 1\n")
    assert corpus["words"]["config"] == set()
    assert corpus["hard"] or corpus["words"]["strings"] is not None


def test_the_classifier_touches_nothing():
    """What makes the walk's declaration honest rather than a stamp."""
    source = pathlib.Path(dead_code.__file__).read_text()
    body = source.split("def classify_into")[1].split("\ndef ")[0]
    for reach in ("read_text", "read_bytes", "open(", "rglob", "stat("):
        assert reach not in body, reach


# ---------------------------------------------------------------------------
# The repository facts: two decisions inside one walk
# ---------------------------------------------------------------------------

def test_the_entry_points_a_package_manifest_declares_are_read_from_its_data():
    repo = pathlib.Path("/r")
    data = {"main": "lib/index.js", "types": "lib/index.d.ts",
            "bin": {"tool": "bin/tool.js"}, "version": "1.0.0"}
    assert dead_code.entry_paths_in(data, repo / "pkg", repo) == {
        "pkg/lib/index.js", "pkg/lib/index.d.ts", "pkg/bin/tool.js"}


def test_a_manifest_declaring_no_entry_point_declares_none():
    assert dead_code.entry_paths_in({"version": "1.0.0"}, pathlib.Path("/r"),
                                    pathlib.Path("/r")) == set()


def test_a_bin_that_is_a_bare_string_is_not_read_as_a_map():
    """`"bin": "tool.js"` is legal npm and is not a map of names to paths. Reading it as one
    would iterate the characters of the string."""
    assert dead_code.entry_paths_in({"bin": "tool.js"}, pathlib.Path("/r"),
                                    pathlib.Path("/r")) == set()


def test_the_metaprogramming_marker_is_read_from_the_text():
    assert dead_code.metaprogramming_in("class X\n  define_method(:go) { 1 }\nend\n")
    assert dead_code.metaprogramming_in("class X\n  def go\n    1\n  end\nend\n") == ""


def test_the_repository_fact_deciders_touch_nothing():
    source = pathlib.Path(dead_code.__file__).read_text()
    for name in ("entry_paths_in", "metaprogramming_in"):
        body = source.split(f"def {name}")[1].split("\ndef ")[0]
        for reach in ("read_text", "read_bytes", "open(", "rglob", "stat("):
            assert reach not in body, (name, reach)


# ---------------------------------------------------------------------------
# The island rule: two more decisions inside one walk
# ---------------------------------------------------------------------------

def test_the_declared_console_scripts_are_read_from_the_manifest_text():
    text = '[project.scripts]\nslop-audit-l1 = "l1_analyzer.cli:run"\nother = "pkg.tool:main"\n'
    assert dead_code.declared_scripts_in(text) == {"cli", "tool"}


def test_a_manifest_declaring_no_script_declares_none():
    assert dead_code.declared_scripts_in('[project]\nname = "x"\n') == set()


def test_a_module_with_a_main_guard_can_be_run():
    assert dead_code.can_be_run('if __name__ == "__main__":\n    main()\n')


def test_a_module_doing_work_at_import_time_can_be_run():
    """A module-level CALL is a script doing its work when imported. This is the clause that
    separates a script from a subsystem."""
    assert dead_code.can_be_run("import sys\n\nmain()\n")


def test_a_module_that_only_declares_cannot_be_run():
    """`TABLE = {...}` and `_WORD = re.compile(...)` build a value and bind it. Without this
    distinction a module written in the dispatch-table style certified itself: name forty
    functions in a table at module level and all forty became roots."""
    assert not dead_code.can_be_run('TABLE = {"a": handler}\n_WORD = re.compile("x")\n')


def test_the_island_deciders_touch_nothing():
    source = pathlib.Path(dead_code.__file__).read_text()
    for name in ("declared_scripts_in", "can_be_run"):
        body = source.split(f"def {name}")[1].split("\ndef ")[0]
        for reach in ("read_text", "read_bytes", "open(", "rglob", "is_file("):
            assert reach not in body, (name, reach)
