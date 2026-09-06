"""A generated file must not end the run with a traceback.

Machine-written source nests deeper than hand-written source. A vocabulary emitted as one
literal, a long chain of binary operators, a generated fixture: each is an ordinary file to
its own compiler and a two-thousand-deep tree to a reader that recurses on children.

The five largest repositories in the 200-repo corpus were missing for this reason and
nothing said so. The run did not report them as unread, it died, and a corpus runner
recorded the death as an analysis error indistinguishable from a repository that would not
clone.

Two things are checked here, and they are different. A reader that walks over an explicit
stack does not care how deep the tree is, which is the repair. And a reader that still
recurses costs one indicator rather than the whole panel, which is what keeps the next one
from doing this again.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


DEPTH = 2000


@boundary
@pytest.fixture
def generated(tmp_path) -> pathlib.Path:
    """One nested literal, the shape that took the run down. Two thousand deep, which is
    over CPython's default limit of a thousand and well under what a generated table
    reaches."""
    (tmp_path / "gen.py").write_text("DATA = " + "[" * DEPTH + "1" + "]" * DEPTH + "\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_the_data_table_rule_reads_a_deep_literal_without_recursing(generated):
    """The reader that crashed. It asked whether a declaration is data all the way down by
    calling itself on each container, so the answer cost one stack frame per level."""
    from l1_analyzer import data_tables, indicators

    parser = indicators._get_parser("python")
    root = parser.parse((generated / "gen.py").read_bytes()).root_node
    containers = frozenset(indicators._LITERAL_NODES["python"])
    literals = data_tables.literal_types("python")
    assert data_tables.declares_a_table(root.named_children[0], containers, literals)


def test_the_panel_reports_a_reading_rather_than_a_traceback(generated, capsys):
    """The whole point of the repair, at the level a person sees. The panel runs and prints
    its rows; it does not raise."""
    from l1_analyzer import cli

    assert cli.main([str(generated), "--lang", "python"]) == 0
    assert "L1.17 · god-file concentration" in capsys.readouterr().out


# One deep file per language the spec covers. Python and Ruby spell the shape as a nested
# literal; the C-family languages nest parentheses inside a function, which every one of
# them parses the same way. Five of the nine crashed on this and four did not, so a fixture
# in one language would have reported the repair finished when it was half done.
_DEEP = {
    "python": ("gen.py", "DATA = " + "[" * DEPTH + "1" + "]" * DEPTH + "\n"),
    "ruby": ("gen.rb", "DATA = " + "[" * DEPTH + "1" + "]" * DEPTH + "\n"),
    "javascript": ("gen.js", "const DATA = " + "[" * DEPTH + "1" + "]" * DEPTH + ";\n"),
    "typescript": ("gen.ts", "const DATA = " + "[" * DEPTH + "1" + "]" * DEPTH + ";\n"),
    "rust": ("gen.rs", "fn f() -> i32 {\n    " + "(" * DEPTH + "1" + ")" * DEPTH + "\n}\n"),
    "go": ("gen.go", "package main\n\nfunc f() int {\n\treturn "
           + "(" * DEPTH + "1" + ")" * DEPTH + "\n}\n"),
    "java": ("Gen.java", "class Gen {\n  int f() { return "
             + "(" * DEPTH + "1" + ")" * DEPTH + "; }\n}\n"),
    "csharp": ("Gen.cs", "class Gen {\n  int F() { return "
               + "(" * DEPTH + "1" + ")" * DEPTH + "; }\n}\n"),
    "c": ("gen.c", "int f(void) { return " + "(" * DEPTH + "1" + ")" * DEPTH + "; }\n"),
}


@boundary
@pytest.fixture
def deep_repo(tmp_path, request) -> pathlib.Path:
    name, text = _DEEP[request.param]
    (tmp_path / name).write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.mark.parametrize("deep_repo", sorted(_DEEP), indirect=True)
def test_every_language_reads_a_deep_file_rather_than_dying_on_it(deep_repo, request, capsys):
    """Five of the nine died here: Rust, Go, Java, C# and C. Python, Ruby, JavaScript and
    TypeScript did not, and the difference was which reader happened to answer first, not
    anything about the languages."""
    from l1_analyzer import cli

    lang = request.node.callspec.params["deep_repo"]
    assert cli.main([str(deep_repo), "--lang", lang]) == 0
    assert "Slop Audit" in capsys.readouterr().out


def test_no_reader_walks_a_parse_tree_by_calling_itself():
    """The rule, so the next reader written here cannot bring the crash back.

    Twenty-two functions across fourteen modules each held their own copy of the walk on
    2026-09-05, every one recursive, and every one therefore had a depth ceiling set by the
    file being audited rather than by anyone who chose it. Nine of them sat on the panel's
    own path, so the tool died on a generated file in five of the nine languages it claims
    to read.

    They are one function now, `ts_nodes.descendants`, over an explicit stack. A walk that
    stops early cannot be that function and keeps its own stack, which is the shape the
    comment beside each one names.

    This reads the package rather than a list of names, because a list would go stale in the
    quiet direction: the walk somebody adds tomorrow is exactly the one no list has."""
    import ast

    package = pathlib.Path(__file__).resolve().parents[1] / "l1_analyzer"
    recursive = []
    for path in sorted(package.glob("*.py")):
        for fn in [n for n in ast.walk(ast.parse(path.read_text()))
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            calls = {n.func.id for n in ast.walk(fn)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            if fn.name not in calls:
                continue
            reads = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
            if reads & {"children", "named_children"}:
                recursive.append(f"{path.name}:{fn.lineno} {fn.name}")
    assert recursive == [], (
        "these walk a parse tree by calling themselves, so their depth ceiling is the "
        f"audited file's to set: {recursive}")
