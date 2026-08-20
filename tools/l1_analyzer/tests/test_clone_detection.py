"""L1.13 measured natively, instead of reporting n/a because a tool is not installed.

The canon: the percentage of production LOC participating in a Type-2 or Type-3 clone
class of at least 50 tokens, with identifiers and literals normalized. It named
`pmd cpd --ignore-identifiers --ignore-literals --minimum-tokens 50` as the reference tool
and jscpd in weak mode as an alternative, and this package shelled out to jscpd. jscpd is
not installed on any machine that has run the panel, so L1.13 has reported n/a on every
repository ever measured, including both validation controls.

An indicator that has never produced a number is not a lenient indicator. It is a column
in a published panel that nobody has ever read, and the fraction it belongs to counts it
out on both halves, so the panel silently measures nineteen things and says twenty.

Normalization is what makes it Type-2 rather than exact: every identifier becomes one
token and every literal becomes one token, so a block copied and renamed still matches.
"""


import pytest
from l1_analyzer import clone_detect, indicators


def _tokens(source: str, lang: str = "python") -> list[str]:
    root = indicators._get_parser(lang).parse(source.encode()).root_node
    return [tok for tok, _line in clone_detect.normalized_tokens(root, lang)]


def test_an_identifier_is_normalized_to_one_token():
    """Two functions differing only in their names produce the same token stream, which is
    the whole of a Type-2 clone."""
    assert _tokens("def alpha(x):\n    return x + 1\n") == _tokens("def beta(y):\n    return y + 1\n")


def test_a_literal_is_normalized_to_one_token():
    assert _tokens("a = 1\n") == _tokens("a = 99999\n") == _tokens('a = "text"\n')


def test_structure_still_separates_two_different_shapes():
    """Normalization must not erase the code. A loop is not an assignment."""
    assert _tokens("a = 1\n") != _tokens("for a in b:\n    pass\n")


def test_a_repeated_block_is_counted_and_a_structurally_different_one_is_not(tmp_path):
    """The measurement, end to end, on a file whose duplication is known by construction.

    The third function has to differ in SHAPE, not in its names. An earlier version of
    this fixture wrote thirty lines of `other_{i} = distinct_call_{i}({i}, {i})` and
    expected them to read as unique; every one of them normalizes to `I = I ( L , L )`, so
    the whole file measured 100% duplicated. That is the detector working: identifiers and
    literals are exactly what Type-2 detection is meant to see through, and thirty repeats
    of one line shape are thirty repeats whatever the names are."""
    block = "\n".join(f"    value_{i} = compute(source_{i}, {i})" for i in range(30))
    varied = ("    total = 0\n"
              "    for item in collection:\n"
              "        if item:\n"
              "            total += len(item)\n"
              "        else:\n"
              "            while total > 0:\n"
              "                total -= 1\n"
              "    try:\n"
              "        return {k: [v] for k, v in mapping.items()}\n"
              "    except KeyError:\n"
              "        raise RuntimeError from None\n")
    (tmp_path / "m.py").write_text(
        f"def first():\n{block}\n\n\ndef second():\n{block}\n\n\ndef third():\n{varied}\n")
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert result["band"] != "n/a", result["details"]
    assert 0 < float(result["value"]) < 100, result["details"]


def test_a_file_with_no_duplication_measures_zero(tmp_path):
    # Every line a different SHAPE, since names and literals are what normalization
    # removes. Sixty repeats of one line shape is duplication however the names read.
    lines = ("def only(seed):\n"
             "    total = 0\n"
             "    for item in seed:\n"
             "        total += 1\n"
             "    while total > 10:\n"
             "        total //= 2\n"
             "    mapping = {'a': [total], 'b': (total,)}\n"
             "    if mapping:\n"
             "        del mapping['a']\n"
             "    try:\n"
             "        return sorted(mapping.items(), key=lambda pair: pair[1])\n"
             "    except TypeError as exc:\n"
             "        raise RuntimeError('no') from exc\n")
    (tmp_path / "m.py").write_text(lines)
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert float(result["value"]) == 0.0
    assert result["band"] == "Healthy"


def test_a_tree_with_no_production_source_refuses_rather_than_reporting_zero(tmp_path):
    """Zero percent duplicated over zero files is the zero-denominator lie this package
    exists to refuse: it would band Healthy for a repository nobody read."""
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"


@pytest.mark.parametrize("lang", ["python", "javascript", "typescript", "java", "go",
                                  "ruby", "rust", "c", "csharp"])
def test_every_language_can_be_tokenized(lang):
    """The vocabulary is per language and each row must actually resolve, since a language
    whose literals nobody declared would silently compare unnormalized text."""
    assert clone_detect.literal_types(lang)


def test_a_large_data_table_is_not_counted_as_duplicated_code(tmp_path):
    """The first real run found this and it is not a special case: L1.17 already discounts
    large container literals, on the stated ground that a god-file is a pile of logic and a
    data table is not.

    A per-language vocabulary table is nine rows of the same keys. Normalize the
    identifiers and the literals and every row reads identically, so the table measured as
    duplicated code: lang_spec.py contributed 390 lines and lang_cfg.py 142 on the first
    measurement of this package. Neither is duplicated code. Both are one table with a row
    per language, which is the shape this project tells other people to separate data into.
    """
    row = ('    "{lang}": {{"class_types": ("class_declaration",), '
           '"func_types": ("function_declaration",), "assign_left": "left", '
           '"assign_right": "right", "member_op": ".", "receiver_scan": "fixed"}},')
    # More rows than _MIN_TABLE_LINES, which is 12: the discount applies to a LARGE
    # container literal, and a short one is as likely to be code as data.
    table = "\n".join(row.format(lang=f"lang_{n}") for n in range(20))
    (tmp_path / "table.py").write_text(f"TABLE = {{\n{table}\n}}\n")
    result = clone_detect.analyze(tmp_path, "python", min_tokens=50)
    assert float(result["value"]) == 0.0, result["details"]
    assert "data" in result["details"]


def test_duplicated_logic_beside_a_data_table_is_still_counted(tmp_path):
    """The discount must not become a hiding place. Code repeated next to a table is code."""
    row = '    "{lang}": {{"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 7}},'
    table = "\n".join(row.format(lang=f"lang_{n}") for n in range(20))
    block = "\n".join(f"    value_{i} = compute(source_{i}, {i})" for i in range(30))
    (tmp_path / "m.py").write_text(
        f"TABLE = {{\n{table}\n}}\n\n\ndef first():\n{block}\n\n\ndef second():\n{block}\n")
    assert float(clone_detect.analyze(tmp_path, "python", min_tokens=50)["value"]) > 0
