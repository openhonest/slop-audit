"""Seven languages asked their toolchain its version, and the asking was written seven times.

Every measured result says which runtime measured it, because a coverage number from one
compiler is not the same evidence as the same number from another. Getting that name is
three lines: run the tool with a version flag, take the first line it printed, and say the
toolchain is unknown when the run failed.

Those three lines existed in c, csharp, go, java, javascript, ruby and rust. What differed
was the command, the sentence for an unknown one, and which stream the tool prints to. Java
prints its version to standard error and the other six to standard output.

The refusal is what makes this worth one copy rather than seven. A probe that failed must
not report a name, because the name goes into the details line beside the number and a
reader uses it to decide whether to believe the reading. Seven copies of that rule is seven
chances to return an empty string instead.
"""


import pytest
from l1_analyzer import toolchain


def test_a_toolchain_that_answered_is_named_by_its_first_line():
    """The version banner runs to several lines and only the first names the toolchain."""
    said = toolchain.named("go version go1.24.0 darwin/arm64\nmore\n", 0,
                           unknown="an unknown go toolchain")
    assert said == "go version go1.24.0 darwin/arm64"


def test_a_probe_that_failed_names_nothing_rather_than_an_empty_string():
    """The whole reason this is one function. The name goes into the details line beside the
    number, and a reader uses it to decide whether to believe the reading. An empty string
    there reads as a measurement taken by nothing at all."""
    assert toolchain.named("", 1, unknown="an unknown go toolchain") == "an unknown go toolchain"


def test_a_toolchain_that_prints_to_standard_error_is_read_from_there():
    """`java -version` prints its banner to standard error, so the Java reader hands over
    that stream. Which one a tool prints to is the caller's fact: this takes the text."""
    said = toolchain.named("openjdk version \"21.0.2\"\n", 0, unknown="an unknown JDK")
    assert said == "openjdk version \"21.0.2\""


def test_a_probe_that_answered_with_nothing_is_not_a_named_toolchain():
    """Exit zero and no output is a command that ran and said nothing. Naming the toolchain
    the empty string would put a blank where a reader looks for the runtime."""
    assert toolchain.named("   \n", 0, unknown="an unknown ruby") == "an unknown ruby"


@pytest.mark.parametrize("module", ["c_trace", "csharp_trace", "go_trace", "java_trace",
                                    "js_trace", "ruby_trace", "rust_trace"])
def test_no_language_asks_its_own_way(module):
    """The copy is what lets one of the seven drift. Each asks the shared reader now.

    Asserted on naming, not on reading an exit code. Two of the seven also ask whether a
    tool is installed at all, which is `probe.returncode == 0` and a different question with
    a boolean answer. A test that caught those would be telling them to route a yes-or-no
    through a function that returns a sentence."""
    import ast
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"l1_analyzer.{module}"))
    names = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Constant) and isinstance(node.value, str)
             and node.value.startswith("an unknown ")]
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and ast.unparse(node.func) == "toolchain.named"]
    assert len(names) == len(calls), (
        f"{module} writes {len(names)} unknown-toolchain sentences and asks the shared "
        f"reader {len(calls)} times")
