"""A name the repository's own specification mentions is not a name anything calls.

The dead-code reader excuses a definition nobody calls when its name turns up in a
configuration file, because an entry point can be wired by name: a YAML pointing at
`myapp.tasks:process` is a real caller the parser cannot see.

A gherkin `.feature` file is not that. Cucumber and behave bind a step to a function by
matching the STEP TEXT against a decorator's pattern, never by the function's name, so a
scenario titled after a function wires nothing at all. This package writes one scenario per
function as a commit gate, which put every function name it has into a `.feature` file, and
the reader then excused every uncalled one as possibly-wired. Four dead functions sat in
one module behind that excuse until 2026-08-31.

The same reasoning is already in this module, made once for string literals: a string is a
candidate reference when the whole string is one identifier, and "a string carrying the name
among other words is prose and carries no lookup." A scenario is a sentence, and the rule
that was true for one is true for the other.

The docs bucket has its own premise and it is a different one: a documented symbol is a
published surface, so removing it breaks callers outside the repository. That premise holds
for a name the language publishes and fails for one it marks private. Python spells private
with a leading underscore, and a private function mentioned only in the repository's own
prose is not a published surface.
"""

import pathlib
import tempfile

from l1_analyzer import dead_code


def _analyze(files: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return dead_code.analyze(root, "python")


def _named(result: dict, name: str) -> dict | None:
    for row in result.get("undecidable", []) + result.get("findings", []):
        if isinstance(row, dict) and row.get("name") == name:
            return row
    return None


_DEAD = "def _helper(n: int) -> int:\n    return n + 1\n\n\ndef used(n: int) -> int:\n    return n * 2\n"
_CALLER = "from m import used\n\n\ndef go() -> int:\n    return used(1)\n"


def test_a_function_nobody_calls_is_flagged_when_nothing_mentions_it():
    """The base case, so the two below are about the exemption and not about the reader."""
    result = _analyze({"m.py": _DEAD, "main.py": _CALLER})
    assert result["counts"]["unreferenced"] >= 1


def test_a_scenario_naming_a_function_does_not_excuse_it():
    """A gherkin file binds a step to a function by the step's text, never by the function's
    name, so a scenario titled after a function is a description and not a call."""
    result = _analyze({
        "m.py": _DEAD, "main.py": _CALLER,
        "features/m.feature": ("Feature: m\n\n"
                               "  Scenario: _helper adds one to what it is given\n"
                               "    Given a number\n"
                               "    When _helper reads it\n"
                               "    Then it comes back one larger\n"),
    })
    assert result["counts"]["unreferenced"] >= 1
    assert _named(result, "_helper") not in result.get("undecidable", [])


def test_a_yaml_naming_a_function_still_excuses_it():
    """The case the exemption was written for, unchanged. A task runner or a serverless
    handler really is wired by name, and flagging it would send someone to delete a live
    entry point."""
    result = _analyze({
        "m.py": _DEAD, "main.py": _CALLER,
        "deploy.yaml": "handler: m._helper\ntimeout: 30\n",
    })
    row = _named(result, "_helper")
    assert row is not None
    assert "wired by name" in row.get("reason", "")


# --------------------------------------------------------------------------
# A dotted string naming a module in this repository is a real reference
# --------------------------------------------------------------------------

_PLUGIN = ("def setup() -> int:\n"
           "    return helper()\n"
           "\n"
           "\n"
           "def helper() -> int:\n"
           "    return 1\n")


def test_a_module_loaded_by_a_dotted_string_is_not_an_island():
    """The shape every framework uses to load code the parser cannot follow: `-p
    pkg.plugin`, `app.main:create_app`, a task named `pkg.tasks.run`. Nothing imports the
    file, so a reference test alone reads it and everything in it as dead.

    The string resolves against the repository's own files, so this excuses only a module
    that is really there. A dotted string naming nothing in the tree still excuses nothing,
    which is what keeps the rule from becoming "any string with a dot in it"."""
    result = _analyze({
        "pkg/__init__.py": "",
        "pkg/plugin.py": _PLUGIN,
        "run.py": ('import subprocess\n\n\n'
                   'def go() -> None:\n'
                   '    subprocess.run(["pytest", "-p", "pkg.plugin"], check=True)\n'),
    })
    flagged = {f["name"] for f in result["findings"]}
    assert "setup" not in flagged
    assert "helper" not in flagged
    reason = next(u["reason"] for u in result["undecidable"] if u["name"] == "setup")
    assert "loaded by name" in reason


def test_a_dotted_string_naming_nothing_in_the_tree_excuses_nothing():
    """The other half, and the reason the rule resolves rather than pattern-matches. A
    version number, a filename and a sentence with a full stop are all dotted strings."""
    result = _analyze({
        "pkg/__init__.py": "",
        "pkg/plugin.py": _PLUGIN,
        "run.py": ('VERSION = "1.0.0"\nDOC = "see README.md"\nOTHER = "some.other.module"\n\n\n'
                   'def go() -> str:\n'
                   '    return VERSION\n'),
    })
    flagged = {f["name"] for f in result["findings"]}
    assert "setup" in flagged
