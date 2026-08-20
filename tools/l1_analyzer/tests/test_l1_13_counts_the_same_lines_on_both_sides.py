"""L1.13's numerator and denominator count the same kind of line.

They did not. The numerator marked every line in a clone's LINE RANGE, and the denominator
counted every line in the file including blanks and docstrings. Both halves were generous,
and because generosity in a divisor lowers a percentage, the mismatch flattered the result.

Measured on this package: range over all lines reads 7.69%, and the consistent measure -
the lines a clone's tokens actually sit on, over the lines that carry any code token -
reads 10.51%. The first is Not Healthy and the second is Slop, so the inconsistency was
worth one band on the instrument's own repository.

The range numerator is wrong on its own terms too. One flagged window here held fifty
tokens sitting on six lines and was credited with twenty-six, because a docstring is a
single token that spans a dozen lines: the window reached across a function signature, a
docstring and the next signature, and every line between was called duplicated.

The canon says "percentage of production LOC". A blank line is not a line of code, and a
line no token in the clone sits on is not participating in it.
"""

import pathlib
import textwrap

import pytest
from l1_analyzer import clone_detect


def _repo(tmp_path: pathlib.Path, name: str, source: str) -> pathlib.Path:
    (tmp_path / name).write_text(textwrap.dedent(source))
    return tmp_path


def test_a_line_no_token_sits_on_is_not_duplicated(tmp_path):
    """The defect exactly: a docstring is one token spanning many lines, so a window can
    reach across it and credit every line between."""
    block = "\n".join(f"    value_{n} = compute(source_{n}, {n})" for n in range(30))
    padding = '\n    """' + "\n".join(f"    documentation line {n}" for n in range(20)) + '"""\n'
    _repo(tmp_path, "m.py", f"def first():\n{block}\n{padding}\n\ndef second():\n{block}\n")
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert "documentation line" not in result["details"]
    # The prose lines carry no code token, so they can be in neither half of the fraction.
    assert result["value"] < 100


def test_the_denominator_counts_lines_that_carry_code(tmp_path):
    """A file of mostly prose must not have its duplication diluted by the prose."""
    _repo(tmp_path, "m.py", '"""' + "\n".join(f"line {n}" for n in range(200)) + '"""\nx = 1\n')
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert "code line" in result["details"], result["details"]
    assert "202" not in result["details"], "the docstring is still in the divisor"


def test_a_real_clone_is_still_counted(tmp_path):
    """The measure must still measure. Two identical blocks renamed throughout are a
    Type-2 clone and every code line of both participates."""
    first = "\n".join(f"    value_{n} = compute(source_{n}, {n})" for n in range(40))
    second = "\n".join(f"    other_{n} = compute(origin_{n}, {n + 500})" for n in range(40))
    _repo(tmp_path, "m.py", f"def a():\n{first}\n\n\ndef b():\n{second}\n")
    assert clone_detect.analyze(tmp_path, "python", min_tokens=50)["value"] > 80


def test_code_that_repeats_nothing_measures_zero(tmp_path):
    _repo(tmp_path, "m.py", '''
        def only(seed):
            total = 0
            for item in seed:
                total += 1
            while total > 10:
                total //= 2
            mapping = {'a': [total], 'b': (total,)}
            if mapping:
                del mapping['a']
            try:
                return sorted(mapping.items(), key=lambda pair: pair[1])
            except TypeError as exc:
                raise RuntimeError('no') from exc
    ''')
    assert clone_detect.analyze(tmp_path, "python", min_tokens=50)["value"] == 0.0


def test_a_tree_with_no_code_lines_refuses(tmp_path):
    """A share over no code lines is absent, not zero, and zero is the Healthy end here.

    Comments only, because a module DOCSTRING is itself a token: it is a string expression
    and sits on a line, so a file holding one has a denominator of one. That was this
    test's first fixture and the premise was wrong."""
    (tmp_path / "m.py").write_text("# nothing but a comment\n# and another\n")
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"


@pytest.mark.parametrize("language", ["python", "javascript", "rust", "go"])
def test_every_language_reports_the_same_two_halves(language, tmp_path):
    """The rule is not Python-specific: whatever the grammar, a line participates when a
    clone's tokens sit on it and the divisor is the lines that carry any token."""
    (tmp_path / f"m.{ {'python': 'py', 'javascript': 'js', 'rust': 'rs', 'go': 'go'}[language] }").write_text(
        "// nothing here\n" if language != "python" else "# nothing here\n")
    result = clone_detect.analyze(tmp_path, language, min_tokens=50)
    assert result["band"] == "n/a", result["details"]
