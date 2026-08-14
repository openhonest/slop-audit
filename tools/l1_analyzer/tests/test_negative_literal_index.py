"""A negated literal index is a literal index, in every language (L1.18b).

The regression this file locks down: `self._stack[-1]` was graded PROMISCUOUS while
`self._stack[0]` was graded NEUTRAL, on files identical but for one character. Every
grammar in the table parses `s[-1]` as a unary node wrapping the integer, and
`_is_unbounded_value` asked only whether the index node's own type was a literal type,
so the wrapper hid the literal and the meter read a constant index as an unbounded
lookup. A stack-based parser is the commonest shape that trips it, and the cost is a
false F on a whole repository, so the vectors below are the shape that was reported.

Three sources per language, identical but for the index token:

  [0]   the control: a positive literal index, already NEUTRAL before the fix
  [-1]  the regression: must reach the same verdict as [0]
  [i]   the guard: a variable index, which must STAY promiscuous. Unwrapping peels
        `-i` to an identifier, so a wrapper never launders a variable into a literal.

C carries a fourth vector. Its grammar folds an adjacent sign into a single signed
`number_literal`, so `s[-1]` never had the defect; the fold is whitespace-sensitive,
and `s[- 1]` is a `unary_expression` like everywhere else. Both are asserted, because
the one that reads as safe is safe only by lexing accident.
"""

import pytest
from l1_analyzer import state_bounds

# lang -> (filename, state key, source template with INDEX to substitute)
CASES = {
    "python": ("case.py", "self._stack", (
        "class P:\n"
        "    def __init__(self):\n"
        "        self._stack = []\n"
        "\n"
        "    def open(self, tag):\n"
        "        self._stack.append(tag)\n"
        "\n"
        "    def close(self, tag, i):\n"
        "        while len(self._stack) > 1:\n"
        "            top = self._stack[INDEX]\n"
        "            if top == tag:\n"
        "                return True\n"
        "        return False\n"
    )),
    "typescript": ("case.ts", "this.stack", (
        "class P {\n"
        "  stack: string[] = [];\n"
        "  open(tag: string) { this.stack.push(tag); }\n"
        "  close(tag: string, i: number) {\n"
        "    const top = this.stack[INDEX];\n"
        "    if (top === tag) { return true; }\n"
        "    return false;\n"
        "  }\n"
        "}\n"
    )),
    "javascript": ("case.js", "this.stack", (
        "class P {\n"
        "  stack = [];\n"
        "  open(tag) { this.stack.push(tag); }\n"
        "  close(tag, i) {\n"
        "    const top = this.stack[INDEX];\n"
        "    if (top === tag) { return true; }\n"
        "    return false;\n"
        "  }\n"
        "}\n"
    )),
    "java": ("Case.java", "stack", (
        "class P {\n"
        "  String[] stack;\n"
        "  boolean close(String tag, int i) {\n"
        "    String top = stack[INDEX];\n"
        "    if (top == tag) { return true; }\n"
        "    return false;\n"
        "  }\n"
        "}\n"
    )),
    "csharp": ("Case.cs", "stack", (
        "class P {\n"
        "  string[] stack;\n"
        "  bool Close(string tag, int i) {\n"
        "    var top = stack[INDEX];\n"
        "    if (top == tag) { return true; }\n"
        "    return false;\n"
        "  }\n"
        "}\n"
    )),
    "rust": ("case.rs", "self.stack", (
        "struct P { stack: Vec<i32> }\n"
        "impl P {\n"
        "  fn close(&self, tag: i32, i: usize) -> bool {\n"
        "    let top = self.stack[INDEX];\n"
        "    if top == tag { return true; }\n"
        "    false\n"
        "  }\n"
        "}\n"
    )),
    "ruby": ("case.rb", "@stack", (
        "class P\n"
        "  def initialize\n"
        "    @stack = []\n"
        "  end\n"
        "\n"
        "  def close(tag, i)\n"
        "    top = @stack[INDEX]\n"
        "    return true if top == tag\n"
        "    false\n"
        "  end\n"
        "end\n"
    )),
    "c": ("case.c", "stack", (
        "static int stack[10];\n"
        "int close_tag(int tag, int i) {\n"
        "  int top = stack[INDEX];\n"
        "  if (top == tag) { return 1; }\n"
        "  return 0;\n"
        "}\n"
    )),
    "go": ("case.go", "P.stack", (
        "package p\n"
        "\n"
        "type P struct{ stack []int }\n"
        "\n"
        "func (p *P) Close(tag int, i int) bool {\n"
        "\ttop := p.stack[INDEX]\n"
        "\tif top == tag {\n"
        "\t\treturn true\n"
        "\t}\n"
        "\treturn false\n"
        "}\n"
    )),
}

# Rust has no unary plus, so `+1` is a parse error there, not a literal.
_POSITIVE_UNARY = {lang: "+1" for lang in CASES if lang != "rust"}

LANGS = sorted(CASES)


def _verdict(tmp_path, lang, index):
    name, state, template = CASES[lang]
    (tmp_path / name).write_text(template.replace("INDEX", index))
    result = state_bounds.classify(tmp_path, lang)
    f = next((f for f in result["findings"] if f["state"] == state), None)
    assert f is not None, f"{lang}: state {state!r} not surfaced for index {index!r}"
    return f["verdict"]


@pytest.mark.parametrize("lang", LANGS)
def test_positive_literal_index_is_neutral(tmp_path, lang):
    """The control. If this ever fails the rest of the file proves nothing."""
    assert _verdict(tmp_path, lang, "0") == "neutral"


@pytest.mark.parametrize("lang", LANGS)
def test_negative_literal_index_matches_positive(tmp_path, lang):
    """The regression: one character must not move the verdict."""
    assert _verdict(tmp_path, lang, "-1") == _verdict(tmp_path, lang, "0") == "neutral"


@pytest.mark.parametrize("lang", sorted(_POSITIVE_UNARY))
def test_unary_plus_literal_index_matches_bare(tmp_path, lang):
    assert _verdict(tmp_path, lang, _POSITIVE_UNARY[lang]) == "neutral"


@pytest.mark.parametrize("lang", LANGS)
def test_variable_index_stays_promiscuous(tmp_path, lang):
    """The guard the fix must not break: an unbounded key is still unbounded."""
    assert _verdict(tmp_path, lang, "i") == "promiscuous"


@pytest.mark.parametrize("lang", LANGS)
def test_negated_variable_index_stays_promiscuous(tmp_path, lang):
    """Unwrapping peels the wrapper, it does not whitelist it: `-i` is still a variable."""
    assert _verdict(tmp_path, lang, "-i") == "promiscuous"


def test_c_spaced_sign_is_the_case_the_lexer_does_not_fold(tmp_path):
    """`s[-1]` in C is one signed number_literal, so C looked immune. `s[- 1]` is a
    unary_expression, so C had the same hole, reachable by whitespace alone."""
    assert _verdict(tmp_path, "c", "- 1") == "neutral"


@pytest.mark.parametrize("lang", LANGS)
def test_binary_expression_index_stays_unbounded(tmp_path, lang):
    """Scope line: the unwrap covers unary operators only. `s[1 - 1]` is a constant a
    human can see, but the meter does not fold arithmetic, and staying promiscuous is
    the conservative side of that line (never a false green)."""
    assert _verdict(tmp_path, lang, "1 - 1") == "promiscuous"
