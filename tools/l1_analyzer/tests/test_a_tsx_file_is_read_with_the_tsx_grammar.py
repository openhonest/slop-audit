"""A React file must be read by the grammar that can read React.

TypeScript has two grammars and tree-sitter ships both. Plain TypeScript cannot parse JSX,
so `.tsx` read as `.ts` is not a file with a few odd nodes in it: every component body
collapses into ERROR nodes and the reader walks wreckage.

`.tsx` was in the TypeScript extension list and the parser was the plain TypeScript one, so
that is what happened to every React repository the tool has ever measured. It did not
complain. It reported a confident, empty reading with nothing marked unread, which is the
same defect as the panel that printed a god-file share it never measured.

The size of it, from the 200-repository run of 2026-09-05. Median pieces of state read:
Java 3,073, C# 3,042, Python 1,436, TypeScript 372. Three TypeScript repositories reported
zero state read AND zero unread: OpenCut, screenshot-to-code and the FastAPI full-stack
template. chakra-ui reported 10. Docusaurus reported 19. All of them are React.

Per extension, not per language, because the two grammars disagree on purpose. `<T>x` is a
type assertion in a .ts file and a JSX element in a .tsx one, and no single grammar can be
right about both. This is what tsc itself does.
"""

from __future__ import annotations

import subprocess

import pytest

_COMPONENT = """import React from "react";

export const Counter = ({label}: {label: string}) => {
  const [count, setCount] = React.useState(0);
  const seen: Record<string, number> = {};
  if (count > 3) { return <span>{label}</span>; }
  return <button onClick={() => setCount(count + 1)}>{label} {count}</button>;
};
"""

_COMPONENT_WITH_MODULE_STATE = _COMPONENT + """
export const CACHE: Record<string, number> = {};
export let hits = 0;
"""

_PLAIN = """export class Cache {
  private store: Map<string, number> = new Map();
  read(k: string): number | undefined { return this.store.get(k); }
}
"""


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
@pytest.fixture
def react_repo(tmp_path):
    (tmp_path / "Counter.tsx").write_text(_COMPONENT)
    (tmp_path / "cache.ts").write_text(_PLAIN)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _errors(root) -> int:
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            count += 1
        stack.extend(node.children)
    return count


def test_a_react_file_parses_without_error(react_repo):
    """The reading underneath every other number. Five error nodes in five lines of an
    ordinary component, and nothing downstream could tell that from a component with
    nothing in it."""
    from l1_analyzer.indicators import parser_for

    source = (react_repo / "Counter.tsx").read_bytes()
    root = parser_for(".tsx", "typescript").parse(source).root_node
    assert not root.has_error
    assert _errors(root) == 0


def test_a_plain_typescript_file_still_gets_the_plain_grammar(react_repo):
    """The other direction, and the reason this is per extension. `<T>x` is a type assertion
    in a .ts file and a JSX element in a .tsx one. One grammar for both would have to be
    wrong about one of them."""
    from l1_analyzer.indicators import _get_parser, parser_for

    assert (parser_for(".ts", "typescript").language
            == _get_parser("typescript").language)


def test_the_module_shape_of_a_react_file_survives_the_parse():
    """What the wreckage cost, stated as the tree rather than as a count downstream.

    Read by the plain grammar this file has seven top-level nodes and the component is not
    one of them: its name, its parameter list, its body's declaration and its return
    statement are each hoisted to module scope as loose siblings, and a piece of state local
    to the component sits at the top of the file. Read by the right grammar it is an import
    and three exports, which is what the file says."""
    from l1_analyzer.indicators import _get_parser, parser_for

    source = _COMPONENT_WITH_MODULE_STATE.encode()
    right = parser_for(".tsx", "typescript").parse(source).root_node
    wrong = _get_parser("typescript").parse(source).root_node
    assert not right.has_error
    assert [c.type for c in right.named_children] == [
        "import_statement", "export_statement", "export_statement", "export_statement"]
    assert wrong.has_error
    assert "lexical_declaration" in [c.type for c in wrong.named_children], (
        "state local to a component was not hoisted to module scope, so this fixture no "
        "longer shows what the wrong grammar does")
