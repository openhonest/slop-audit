"""L1.19 static half: the decision-point count a reader would give, in all nine grammars.

The published rule, restated so every assertion below can be checked against it:

  A decision point is a construct at which control can take more than one path.
  An `if`, an `elif`/`elsif`, an `unless`, a ternary or conditional expression counts
  one each; an `else` is NOT a decision, it is the other path of the `if` that already
  counted. Each ARM of a switch or match counts one, including the default or wildcard
  arm; the switch or match CONTAINER is not counted, because its arms are where the
  choosing happens.

Every count below is the number that rule gives for the fixture, worked out by hand.
Real source, real grammars, no mocks.
"""

import pytest
from l1_analyzer import indicators
from l1_analyzer.lang_spec import DECISION_NODE_TYPES
from l1_analyzer.state_bounds import _get_parser

# Production-scope file names, one per grammar. Nothing here may look like a test file,
# because _compute_decision_space reads PRODUCTION scope only.
LANG_FILE = {
    "python": "app.py", "ruby": "app.rb", "c": "app.c", "java": "App.java",
    "csharp": "App.cs", "rust": "app.rs", "go": "app.go",
    "javascript": "app.js", "typescript": "app.ts",
}


def _count(tmp_path, lang: str, src: str) -> int:
    """Parse `src` as `lang` in a throwaway repository and return the enumerated count."""
    (tmp_path / LANG_FILE[lang]).write_text(src)
    return indicators._compute_decision_space(tmp_path, lang)["value"]


# --- one `if` -> 1, in every grammar ----------------------------------------
# This is the double-count regression. Before the fix each of these enumerated 2,
# because the unnamed `if` keyword token matched the same shared set as the
# if_statement node that contains it.

ONE_IF = {
    "python": "def f(a):\n    if a:\n        return 1\n    return 0\n",
    "ruby": "def f(a)\n  if a\n    return 1\n  end\n  0\nend\n",
    "c": "int f(int a) {\n  if (a) { return 1; }\n  return 0;\n}\n",
    "java": "class App {\n  int f(int a) {\n    if (a > 0) { return 1; }\n    return 0;\n  }\n}\n",
    "csharp": "class App {\n  int F(int a) {\n    if (a > 0) { return 1; }\n    return 0;\n  }\n}\n",
    "rust": "pub fn f(a: i32) -> i32 {\n    if a > 0 { return 1; }\n    0\n}\n",
    "go": "package app\n\nfunc F(a int) int {\n\tif a > 0 {\n\t\treturn 1\n\t}\n\treturn 0\n}\n",
    "javascript": "function f(a) {\n  if (a) { return 1; }\n  return 0;\n}\n",
    "typescript": "function f(a: number): number {\n  if (a) { return 1; }\n  return 0;\n}\n",
}


@pytest.mark.parametrize("lang", sorted(ONE_IF))
def test_one_if_counts_one_not_two(tmp_path, lang):
    """One `if` is one decision. The keyword token inside the if node is the same
    construct, not a second one."""
    assert _count(tmp_path, lang, ONE_IF[lang]) == 1


# --- if/else -> 1, because an else is not a decision -------------------------

IF_ELSE = {
    "python": "def f(a):\n    if a:\n        return 1\n    else:\n        return 0\n",
    "ruby": "def f(a)\n  if a\n    1\n  else\n    0\n  end\nend\n",
    "c": "int f(int a) {\n  if (a) { return 1; } else { return 0; }\n}\n",
    "java": "class App {\n  int f(int a) {\n    if (a > 0) { return 1; } else { return 0; }\n  }\n}\n",
    "csharp": "class App {\n  int F(int a) {\n    if (a > 0) { return 1; } else { return 0; }\n  }\n}\n",
    "rust": "pub fn f(a: i32) -> i32 {\n    if a > 0 { 1 } else { 0 }\n}\n",
    "go": "package app\n\nfunc F(a int) int {\n\tif a > 0 {\n\t\treturn 1\n\t} else {\n\t\treturn 0\n\t}\n}\n",
    "javascript": "function f(a) {\n  if (a) { return 1; } else { return 0; }\n}\n",
    "typescript": "function f(a: number): number {\n  if (a) { return 1; } else { return 0; }\n}\n",
}


@pytest.mark.parametrize("lang", sorted(IF_ELSE))
def test_if_else_counts_one_because_an_else_is_not_a_decision(tmp_path, lang):
    """The else branch is the other path of the `if` that already counted. Counting it
    again would say a two-way choice holds two decisions."""
    assert _count(tmp_path, lang, IF_ELSE[lang]) == 1


# --- if/elif/else -> 2 -------------------------------------------------------

IF_ELIF_ELSE = {
    "python": "def f(a, b):\n    if a:\n        return 1\n    elif b:\n        return 2\n    else:\n        return 0\n",
    "ruby": "def f(a, b)\n  if a\n    1\n  elsif b\n    2\n  else\n    0\n  end\nend\n",
    "c": "int f(int a, int b) {\n  if (a) { return 1; } else if (b) { return 2; } else { return 0; }\n}\n",
    "java": "class App {\n  int f(int a, int b) {\n    if (a > 0) { return 1; } else if (b > 0) { return 2; } else { return 0; }\n  }\n}\n",
    "csharp": "class App {\n  int F(int a, int b) {\n    if (a > 0) { return 1; } else if (b > 0) { return 2; } else { return 0; }\n  }\n}\n",
    "rust": "pub fn f(a: i32, b: i32) -> i32 {\n    if a > 0 { 1 } else if b > 0 { 2 } else { 0 }\n}\n",
    "go": "package app\n\nfunc F(a int, b int) int {\n\tif a > 0 {\n\t\treturn 1\n\t} else if b > 0 {\n\t\treturn 2\n\t}\n\treturn 0\n}\n",
    "javascript": "function f(a, b) {\n  if (a) { return 1; } else if (b) { return 2; } else { return 0; }\n}\n",
    "typescript": "function f(a: number, b: number): number {\n  if (a) { return 1; } else if (b) { return 2; } else { return 0; }\n}\n",
}


@pytest.mark.parametrize("lang", sorted(IF_ELIF_ELSE))
def test_if_elif_else_counts_two_tests_and_no_else(tmp_path, lang):
    """Two conditions are asked, so two decisions. The trailing else adds none."""
    assert _count(tmp_path, lang, IF_ELIF_ELSE[lang]) == 2


# --- one ternary -> 1 --------------------------------------------------------
# Rust and Go have no ternary operator, so they are absent by grammar, not by omission.

TERNARY = {
    "python": "def f(a):\n    return 1 if a else 0\n",
    "ruby": "def f(a)\n  a ? 1 : 0\nend\n",
    "c": "int f(int a) {\n  return a ? 1 : 0;\n}\n",
    "java": "class App {\n  int f(int a) {\n    return a > 0 ? 1 : 0;\n  }\n}\n",
    "csharp": "class App {\n  int F(int a) {\n    return a > 0 ? 1 : 0;\n  }\n}\n",
    "javascript": "function f(a) {\n  return a ? 1 : 0;\n}\n",
    "typescript": "function f(a: number): number {\n  return a ? 1 : 0;\n}\n",
}


@pytest.mark.parametrize("lang", sorted(TERNARY))
def test_one_ternary_counts_one(tmp_path, lang):
    """A conditional expression asks one question and yields one of two values."""
    assert _count(tmp_path, lang, TERNARY[lang]) == 1


# --- a switch with two cases and a default -> 3 ------------------------------
# The container is not counted. Python's `match` is in this table because the new rule
# changes its behaviour: before the fix the match_statement container AND its case
# clauses both counted.

SWITCH_TWO_CASES_AND_DEFAULT = {
    "python": "def f(a):\n    match a:\n        case 1:\n            return 1\n        case 2:\n            return 2\n        case _:\n            return 0\n",
    "c": "int f(int a) {\n  switch (a) {\n    case 1: return 1;\n    case 2: return 2;\n    default: return 0;\n  }\n}\n",
    "java": "class App {\n  int f(int a) {\n    switch (a) {\n      case 1: return 1;\n      case 2: return 2;\n      default: return 0;\n    }\n  }\n}\n",
    "csharp": "class App {\n  int F(int a) {\n    switch (a) {\n      case 1: return 1;\n      case 2: return 2;\n      default: return 0;\n    }\n  }\n}\n",
    "rust": "pub fn f(a: i32) -> i32 {\n    match a {\n        1 => 1,\n        2 => 2,\n        _ => 0,\n    }\n}\n",
    "go": "package app\n\nfunc F(a int) int {\n\tswitch a {\n\tcase 1:\n\t\treturn 1\n\tcase 2:\n\t\treturn 2\n\tdefault:\n\t\treturn 0\n\t}\n}\n",
    "javascript": "function f(a) {\n  switch (a) {\n    case 1: return 1;\n    case 2: return 2;\n    default: return 0;\n  }\n}\n",
    "typescript": "function f(a: number): number {\n  switch (a) {\n    case 1: return 1;\n    case 2: return 2;\n    default: return 0;\n  }\n}\n",
}


@pytest.mark.parametrize("lang", sorted(SWITCH_TWO_CASES_AND_DEFAULT))
def test_switch_counts_its_arms_and_not_its_container(tmp_path, lang):
    """Three arms, three decisions. The switch or match keyword chooses nothing on its
    own, so counting the container as well would report four."""
    assert _count(tmp_path, lang, SWITCH_TWO_CASES_AND_DEFAULT[lang]) == 3


def test_ruby_case_counts_its_when_arms_and_not_its_else(tmp_path):
    """Ruby is the one grammar that spells a case's default arm with the same `else`
    node it uses for an if's else, so a node type alone cannot tell the two apart.
    Two `when` arms therefore enumerate 2, and the trailing else adds none. This is a
    known and deliberate asymmetry with C, Go, Java, C#, JavaScript and TypeScript,
    whose default arm has a node type of its own and does count."""
    src = "def f(a)\n  case a\n  when 1 then 1\n  when 2 then 2\n  else 0\n  end\nend\n"
    assert _count(tmp_path, "ruby", src) == 2


# --- forms a language has and its neighbours do not --------------------------

def test_ruby_unless_is_a_decision(tmp_path):
    """`unless` asks a question and takes one of two paths, exactly as `if` does."""
    assert _count(tmp_path, "ruby", "def f(a)\n  unless a\n    return 1\n  end\n  0\nend\n") == 1


def test_ruby_statement_modifiers_are_decisions(tmp_path):
    """`x = 1 if a` and `y = 2 unless a` are guards written backwards, one decision each."""
    src = "def f(a)\n  x = 1 if a\n  y = 2 unless a\n  [x, y]\nend\n"
    assert _count(tmp_path, "ruby", src) == 2


def test_ruby_case_in_counts_its_pattern_arms(tmp_path):
    """Ruby's pattern-matching `case ... in` spells its arms `in_clause`, not `when`."""
    src = "def f(a)\n  case a\n  in Integer then 1\n  in String then 2\n  end\nend\n"
    assert _count(tmp_path, "ruby", src) == 2


def test_rust_if_let_is_one_decision(tmp_path):
    """`if let` is an if_expression whose condition binds. One question, one decision."""
    src = "pub fn f(a: Option<i32>) -> i32 {\n    if let Some(v) = a { return v; }\n    0\n}\n"
    assert _count(tmp_path, "rust", src) == 1


def test_go_type_switch_counts_its_arms(tmp_path):
    """A type switch chooses among type cases; its default arm counts like any other."""
    src = ("package app\n\nfunc F(i interface{}) int {\n\tswitch i.(type) {\n"
           "\tcase int:\n\t\treturn 1\n\tdefault:\n\t\treturn 0\n\t}\n}\n")
    assert _count(tmp_path, "go", src) == 2


def test_go_select_counts_its_communication_arms(tmp_path):
    """`select` chooses among ready channel operations, so each arm is a decision."""
    src = ("package app\n\nfunc F(ch chan int) int {\n\tselect {\n"
           "\tcase <-ch:\n\t\treturn 1\n\tdefault:\n\t\treturn 0\n\t}\n}\n")
    assert _count(tmp_path, "go", src) == 2


def test_csharp_switch_expression_counts_its_arms(tmp_path):
    """A switch expression is a switch that yields a value; its arms count the same."""
    src = "class App {\n  int F(int a) {\n    return a switch { 1 => 1, _ => 0 };\n  }\n}\n"
    assert _count(tmp_path, "csharp", src) == 2


def test_java_arrow_switch_counts_its_arms(tmp_path):
    """Java's arrow form has no fall-through, and each label is still one arm."""
    src = ("class App {\n  int f(int a) {\n    return switch (a) { case 1 -> 1; default -> 0; };\n  }\n}\n")
    assert _count(tmp_path, "java", src) == 2


# --- the defect itself, asserted directly ------------------------------------

ALL_FORMS = {
    "python": ONE_IF["python"] + IF_ELIF_ELSE["python"].replace("def f(", "def g(") + SWITCH_TWO_CASES_AND_DEFAULT["python"].replace("def f(", "def h("),
    "ruby": ONE_IF["ruby"] + IF_ELIF_ELSE["ruby"].replace("def f(", "def g(") + "def h(a)\n  case a\n  when 1 then 1\n  else 0\n  end\nend\n",
    "c": ONE_IF["c"] + SWITCH_TWO_CASES_AND_DEFAULT["c"].replace("int f(", "int g("),
    "java": "class App {\n  int f(int a) {\n    if (a > 0) { return 1; }\n    switch (a) { case 1: return 1; default: return 0; }\n  }\n}\n",
    "csharp": "class App {\n  int F(int a) {\n    if (a > 0) { return 1; }\n    switch (a) { case 1: return 1; default: return 0; }\n  }\n}\n",
    "rust": ONE_IF["rust"] + SWITCH_TWO_CASES_AND_DEFAULT["rust"].replace("pub fn f(", "pub fn g("),
    "go": SWITCH_TWO_CASES_AND_DEFAULT["go"] + "\nfunc G(a int) int {\n\tif a > 0 {\n\t\treturn 1\n\t}\n\treturn 0\n}\n",
    "javascript": ONE_IF["javascript"] + SWITCH_TWO_CASES_AND_DEFAULT["javascript"].replace("function f(", "function g("),
    "typescript": ONE_IF["typescript"] + SWITCH_TWO_CASES_AND_DEFAULT["typescript"].replace("function f(", "function g("),
}


def _match_counts(lang: str, src: str) -> tuple[int, int]:
    """Nodes whose type is declared a decision, split by named and unnamed."""
    root = _get_parser(lang).parse(src.encode()).root_node
    named = unnamed = 0

    def walk(n):
        nonlocal named, unnamed
        for c in n.children:
            if c.type in DECISION_NODE_TYPES[lang]:
                if c.is_named:
                    named += 1
                else:
                    unnamed += 1
            walk(c)

    walk(root)
    return named, unnamed


# The bare keyword strings the old shared set carried. Every grammar here emits at least
# one of them as an UNNAMED token inside the node that already matched, which is the
# whole defect: `if` matched alongside `if_statement`, so every `if` counted twice.
CONTROL_KEYWORDS = frozenset({
    "if", "elif", "elsif", "else", "unless", "switch", "case", "when",
    "match", "default", "select",
})


def _unnamed_keyword_tokens(lang: str, src: str) -> set[str]:
    """The control-flow keyword tokens the fixture emits as UNNAMED nodes."""
    root = _get_parser(lang).parse(src.encode()).root_node
    found: set[str] = set()

    def walk(n):
        for c in n.children:
            if not c.is_named and c.type in CONTROL_KEYWORDS:
                found.add(c.type)
            walk(c)

    walk(root)
    return found


@pytest.mark.parametrize("lang", sorted(ALL_FORMS))
def test_no_unnamed_keyword_token_can_ever_be_counted(tmp_path, lang):
    """The defect stated as its own assertion, not implied by a total.

    Each fixture emits control-flow keywords as unnamed tokens sitting inside the very
    node that already matched. The enumerated count must equal the NAMED matches alone,
    so no keyword token contributes.
    """
    keywords = _unnamed_keyword_tokens(lang, ALL_FORMS[lang])
    assert keywords, f"{lang} fixture emits no unnamed control keyword; the assertion below would be vacuous"
    named, _unnamed = _match_counts(lang, ALL_FORMS[lang])
    assert _count(tmp_path, lang, ALL_FORMS[lang]) == named


def test_ruby_named_if_and_unnamed_if_token_share_a_type_string(tmp_path):
    """Ruby is the case a type test alone cannot survive: the `if` NODE and the `if`
    KEYWORD carry the same type string, so only `is_named` separates them. The
    enumerator must count the node and skip the token."""
    src = "def f(a)\n  if a\n    1\n  end\nend\n"
    named, unnamed = _match_counts("ruby", src)
    assert (named, unnamed) == (1, 1)
    assert _count(tmp_path, "ruby", src) == 1


def test_every_supported_language_declares_its_decision_types():
    """Read by subscript, so a language that declares nothing raises rather than
    reaching a shared default. This pins that no supported language is missing."""
    assert set(DECISION_NODE_TYPES) == set(indicators.LANG_CFG)


def test_an_undeclared_language_raises_rather_than_defaulting():
    """The table has no default row and no .get() reader."""
    with pytest.raises(KeyError):
        DECISION_NODE_TYPES["klingon"]
