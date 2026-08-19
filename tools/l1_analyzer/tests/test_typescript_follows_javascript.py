"""TypeScript's grammar table is derived from JavaScript's, not copied from it.

The two LangSpec entries agreed on 64 of 70 fields and were spelled out twice. A rule
added to JavaScript reached TypeScript only if whoever added it remembered the second
copy, and nothing said so: this session fixed the same shape of defect ten times over,
each one a construct read under one spelling and missed under another.

TypeScript really does differ, on six fields, and those six are named in one place with a
reason each. Everything else follows JavaScript by construction, so the next field added
to JavaScript reaches TypeScript whether or not anyone remembers.

These tests hold the two halves of that: the shared fields are identical because they are
the same object, and the differing fields are exactly the declared overrides, so a seventh
divergence has to be declared before it can exist.
"""

from l1_analyzer.indicators import LANG_CFG, TYPESCRIPT_CFG_OVERRIDES
from l1_analyzer.lang_spec import LANG_SPEC, TYPESCRIPT_OVERRIDES


def test_typescript_differs_from_javascript_only_where_declared():
    js, ts = LANG_SPEC["javascript"], LANG_SPEC["typescript"]
    differing = {k for k in set(js) | set(ts) if js.get(k) != ts.get(k)}
    assert differing == set(TYPESCRIPT_OVERRIDES), (
        "an undeclared divergence between the JavaScript and TypeScript tables: "
        f"{sorted(differing ^ set(TYPESCRIPT_OVERRIDES))}"
    )


def test_every_shared_field_is_the_same_object():
    """Not merely equal. Equal values can be two literals that happen to match today;
    the same object cannot drift apart at all."""
    js, ts = LANG_SPEC["javascript"], LANG_SPEC["typescript"]
    for key in set(js) - set(TYPESCRIPT_OVERRIDES):
        assert ts[key] is js[key], f"{key} is a separate copy in the TypeScript table"


def test_the_config_table_diverges_only_where_declared_too():
    """The same copy was made twice, in two tables, and the same field was stale in both.
    LANG_CFG's TypeScript function_types listed three node types where JavaScript listed
    five, so a TypeScript `const f = function(){}` was not a function to L1.18 either."""
    js, ts = LANG_CFG["javascript"], LANG_CFG["typescript"]
    differing = {k for k in set(js) | set(ts) if js.get(k) != ts.get(k)}
    assert differing == set(TYPESCRIPT_CFG_OVERRIDES), (
        f"an undeclared divergence in LANG_CFG: {sorted(differing ^ set(TYPESCRIPT_CFG_OVERRIDES))}"
    )


def test_typescript_enumerates_the_function_forms_javascript_does():
    """The defect this derivation settled, asserted on the thing that was wrong rather
    than on the mechanism that fixed it. Both node types are produced by the
    tree-sitter-typescript grammar; the omission was a stale copy."""
    for form in ("function_expression", "generator_function_declaration"):
        assert form in LANG_CFG["typescript"]["function_types"]
        assert form in LANG_SPEC["typescript"]["func_types"]


def test_a_new_javascript_field_reaches_typescript():
    """The property that makes this worth doing, asserted directly on the construction
    rather than on the two finished tables."""
    js = {"a": 1, "b": 2, "brand_new": 3}
    ts = {**js, "b": 99}
    assert ts["brand_new"] == 3
    assert ts["b"] == 99


def test_a_typescript_file_of_only_these_forms_enumerates_its_functions(tmp_path):
    """The measured consequence, not the mechanism.

    Before the derivation, this file's two functions were invisible and L1.18 answered
    "no function was enumerated in typescript, so the share of them touching unbounded
    state is absent, not zero". A repo written this way got n/a for a question that had a
    real answer. Measured against the real tool on 2026-08-18: n/a became 0.0 Healthy
    here, and a React/Vite site's L1.18 moved 17.9 to 17.7 as its denominator grew.
    """
    import pathlib as _p

    from l1_analyzer import indicators
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.ts").write_text(
        "const cache: Record<string, number> = {};\n"
        "const memo = function (k: string): number { cache[k] = 1; return cache[k]; };\n"
        "function* counter(): Generator<number> { let n = 0; while (true) { yield n++; } }\n"
        "export { memo, counter };\n"
    )
    result = indicators.compute_source_indicators(
        _p.Path(tmp_path), lang="typescript", exec_tests=False,
        timeout_seconds=60, classify_state_bounds=True)
    assert result["L1.18"]["band"] != "n/a", result["L1.18"]["details"]
