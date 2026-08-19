"""A proof the card renders has a declared shape.

The card read `o.get("symbol", "?")` and `p.get("function", "?")` and built a location
from `o.get('file', '?')` and `o.get('line', 0)`. The dicts behind those reads were typed
`dict[str, object]`, so there was nothing to read them against and the card guessed.

Guessing shows up on the page. A retained proof whose function name went missing rendered
as a question mark next to a real test source, which reads as a proof of something nobody
can name rather than as a broken record. And the two coverage producers, one for Rust and
one for Python, each built their entry by hand with no declared shape holding them to the
same five keys.

Declaring them is what makes the card's reads safe to subscript and what stops the two
producers from drifting apart.
"""

import pathlib
import re

from l1_analyzer import card, coverage_prove, prove, python_coverage_prove


def test_the_concurrency_record_shape_is_declared():
    assert set(prove.ProofRecord.__required_keys__) == {
        "file", "line", "symbol", "verdict", "detail", "generated_test"}


def test_the_record_and_the_outcome_are_two_names():
    """They are two shapes. prove_hazard returns the outcome, which carries the request it
    was made from; the CLI records the hazard flattened into a file, a line and a symbol.
    Writing the record as ProofOutcome silently shadowed the outcome, and the tests went on
    passing because nothing subscripted the shadowed one."""
    assert prove.ProofRecord is not prove.ProofOutcome
    assert "request" in prove.ProofOutcome.__required_keys__
    assert "request" not in prove.ProofRecord.__required_keys__


def test_the_coverage_proof_shape_is_declared():
    assert set(coverage_prove.CoverageProof.__required_keys__) == {
        "function", "language", "location", "explanation", "test_source"}


def test_both_coverage_producers_build_the_declared_shape():
    """Rust and Python each built the entry by hand. They agree today; nothing held them."""
    for module in (coverage_prove, python_coverage_prove):
        source = pathlib.Path(module.__file__).read_text()
        assert "CoverageProof" in source, f"{module.__name__} builds a proof with no declared shape"


def test_the_card_does_not_guess_at_a_proof_field():
    declared = ({"file", "line", "symbol", "verdict", "detail", "generated_test"}
                | {"function", "language", "location", "explanation", "test_source"})
    offenders = []
    for number, line in enumerate(pathlib.Path(card.__file__).read_text().split("\n"), start=1):
        code = line.split("#", 1)[0]
        for match in re.finditer(r'\.get\(\s*[\'"](\w+)[\'"]\s*,', code):
            if match.group(1) in declared:
                offenders.append(f"card.py:{number} {match.group(1)}")
    assert not offenders, f"proof fields the card still guesses at: {offenders}"


def test_no_module_defines_the_same_name_twice():
    """The guard for what happened while writing this file.

    A second `class ProofOutcome` was added to prove.py above the first. Python takes the
    last definition and says nothing, so the new shape vanished and every reader kept
    getting the old one. The suite stayed green, because nothing subscribed a field only
    the new shape had.

    A name defined twice in one module is always one of two things: a shadow nobody meant,
    or a rename somebody half-finished. Neither is worth the silence.
    """
    import ast

    offenders = []
    for path in sorted(pathlib.Path(card.__file__).parent.glob("*.py")):
        seen: dict[str, int] = {}
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if node.name in seen:
                offenders.append(f"{path.name}:{node.name} at lines {seen[node.name]} and {node.lineno}")
            seen[node.name] = node.lineno
    assert not offenders, f"names defined twice in one module: {offenders}"
