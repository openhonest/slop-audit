"""The retention gate, exercised against a real interpreter and real source.

Every existing test of this loop injects BOTH the proposer and the runner:
`run_fn=lambda *a: (1, _FAILED_ASSERT)` hands back a canned pytest transcript. That proves
the classifier can read a string. It does not prove that running a real test against real
code produces a transcript the classifier reads as a divergence, and that is the whole
claim the loop makes.

So these run the real `_run`: the test source is written to a real file, a real interpreter
executes it against a real module, and the real output is classified. Only the proposer is
injected, and what it returns is a test a person wrote rather than a canned verdict. That
is the honest line. Substituting the model's AUTHORSHIP leaves every mechanism under test
intact; substituting the RUN removes the mechanism and asserts the fixture.

The module under test carries a planted defect at a branch its own suite never covers,
which is the shape the loop exists to find: `discounted_total` adds a bulk discount instead
of subtracting it, and the suite tests only small orders.
"""

import pathlib
import subprocess
import sys
import textwrap

import pytest
from l1_analyzer import python_coverage_prove as pcp

SOURCE = textwrap.dedent('''
    def discounted_total(unit_price, quantity):
        """Total price with a 10% discount on orders of 100 units or more."""
        if quantity >= 100:
            return unit_price * quantity * 1.1     # PLANTED: adds the discount
        return unit_price * quantity
''')

# What a correct reading of the docstring asserts. A discount makes the total SMALLER, and
# the planted code makes it larger, so this fails when executed. It is written here rather
# than generated because the model's authorship is the one thing these tests substitute.
# A BODY, not a module. The loop renders it inside `def proof_0():`, so a nested `def` here
# would define a function nobody calls and pass vacuously. That shape is what this fixture
# was written as first, and it is what found the defect now fixed in
# test_a_proof_that_asserts_nothing_is_not_a_pass.py.
CORRECT_ASSERTION = textwrap.dedent('''
    from planted.pricing import discounted_total
    result = discounted_total(10.0, 100)
    assert result < 10.0 * 100, "a discount must lower the total"
''')

WRONG_ASSERTION = textwrap.dedent('''
    from planted.pricing import discounted_total
    result = discounted_total(10.0, 5)
    assert result == 50.0
''')

BROKEN_SETUP = textwrap.dedent('''
    from planted.pricing import discounted_total
    result = discounted_total(missing_fixture, 100)
    assert result < 1000
''')


@pytest.fixture(scope="module")
def planted(tmp_path_factory) -> pathlib.Path:
    """A package with the planted defect, importable by a real interpreter."""
    repo = tmp_path_factory.mktemp("planted")
    package = repo / "planted"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "pricing.py").write_text(SOURCE)
    return repo


def _run_for_real(repo: pathlib.Path, source: str) -> tuple[int, str]:
    """The real runner, against the real interpreter running these tests.

    Two arguments, because these tests call it directly. The LOOP calls `_run` itself with
    all four, so nothing is wrapped on that path: `run_fn=pcp._run` is the production
    function, unaltered."""
    return pcp._run(repo, sys.executable, pcp.render_test(source), timeout_seconds=60.0)


def test_a_correct_assertion_against_planted_code_really_fails(planted):
    """The premise everything else rests on, asserted without the loop: the defect is real
    and a correct assertion about it does not pass."""
    returncode, output = _run_for_real(planted, CORRECT_ASSERTION)
    assert returncode != 0
    assert "AssertionError" in output


def test_a_real_failing_run_is_classified_as_a_divergence(planted):
    """Real transcript, real classifier. The canned transcripts every other test uses were
    written by hand and could drift from what pytest actually prints."""
    returncode, output = _run_for_real(planted, CORRECT_ASSERTION)
    assert pcp._classify(output, returncode) == "divergence"


def test_a_real_passing_run_is_not_retained(planted):
    returncode, output = _run_for_real(planted, WRONG_ASSERTION)
    assert returncode == 0
    assert pcp._classify(output, returncode) == "pass"


def test_a_real_setup_failure_is_noise_and_not_a_proof(planted):
    """The distinction that keeps the loop honest: a test that could not run is not
    evidence of a bug. Any exception but AssertionError is the tool's own noise."""
    returncode, output = _run_for_real(planted, BROKEN_SETUP)
    assert returncode != 0
    assert pcp._classify(output, returncode) == "incidental"


def test_the_loop_retains_a_proof_when_the_run_is_real(planted):
    """End to end with only the author substituted. This path has never fired: every prior
    test of it faked the run, and no live sweep has yet retained anything."""
    gap = {"function": "discounted_total", "line": 4, "kind": "if", "is_method": False,
           "function_source": SOURCE, "parameters": [], "return_type": ""}
    retained, outcomes = pcp._prove_module(
        planted, "planted/pricing.py", sys.executable, [gap], 0, 60.0,
        propose_fn=lambda g, path: {"body": CORRECT_ASSERTION,
                                    "explanation": "a discount lowers the total"},
        repair_fn=lambda *a: None,
        run_fn=pcp._run,      # the production runner itself, not a wrapper
    )
    assert outcomes["divergence"] == 1
    assert len(retained) == 1
    assert retained[0]["location"] == "planted/pricing.py:4"
    assert retained[0]["explanation"] == "a discount lowers the total"
    assert "discounted_total" in retained[0]["test_source"]


def test_the_retained_proof_is_a_test_that_actually_runs(planted):
    """A retained proof is offered to a person as an adoptable test. If it does not execute
    on its own, the offer is empty."""
    gap = {"function": "discounted_total", "line": 4, "kind": "if", "is_method": False,
           "function_source": SOURCE, "parameters": [], "return_type": ""}
    retained, _ = pcp._prove_module(
        planted, "planted/pricing.py", sys.executable, [gap], 0, 60.0,
        propose_fn=lambda g, path: {"body": CORRECT_ASSERTION, "explanation": "why"},
        repair_fn=lambda *a: None,
        run_fn=pcp._run,      # the production runner itself, not a wrapper
    )
    proof = planted / "adopted_test.py"
    proof.write_text(retained[0]["test_source"])
    run = subprocess.run([sys.executable, "-m", "pytest", str(proof), "-q",
                          "-o", "python_functions=proof_*", "-p", "no:cacheprovider"],
                         cwd=planted, capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode != 0, "the retained proof passed, so it proves nothing"
    assert "AssertionError" in (run.stdout + run.stderr)
