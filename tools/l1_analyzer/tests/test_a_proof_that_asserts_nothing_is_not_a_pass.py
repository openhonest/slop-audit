"""A generated proof that evaluates no assertion is not evidence the branch is correct.

Found on 2026-08-19 while exercising the retention gate against a real interpreter. The
loop asked for the BODY of a test and rendered it inside `def proof_0():`. Hand it a whole
test module instead - a plausible model reply, and the shape of every pytest file a model
has ever read - and it renders as:

    def proof_0():
        from planted.pricing import discounted_total
        def proof_bulk_order_is_discounted():
            result = discounted_total(10.0, 100)
            assert result < 10.0 * 100

pytest collects `proof_0`, runs it, and it defines a nested function and returns. Green.
The loop then counted it under `pass`, whose report reads "branch correct". Nothing was
correct: nothing was called and nothing was asserted.

This is the category this whole package exists to name, inside the package. `pass` was
inferred from the ABSENCE of a failure rather than from evidence that an assertion was
evaluated, so a proof that measured nothing published a clean bill for the branch it was
sent to cover. A model that answers in the wrong shape gets a Healthy reading, and the
wrong shape is the more familiar one.

The rule is decidable and needs no runtime: parse the body, and require at least one
assertion that will actually execute - one not sitting inside a nested function, lambda or
class that the body never calls.
"""

import textwrap

import pytest
from l1_analyzer import coverage_prove
from l1_analyzer import python_coverage_prove as pcp

REACHABLE = textwrap.dedent('''
    from planted.pricing import discounted_total
    result = discounted_total(10.0, 100)
    assert result < 1000, "a discount must lower the total"
''')

NESTED_AND_NEVER_CALLED = textwrap.dedent('''
    from planted.pricing import discounted_total

    def proof_bulk_order_is_discounted():
        result = discounted_total(10.0, 100)
        assert result < 1000, "a discount must lower the total"
''')

NO_ASSERTION_AT_ALL = textwrap.dedent('''
    from planted.pricing import discounted_total
    result = discounted_total(10.0, 100)
''')

ASSERTION_INSIDE_A_LOOP = textwrap.dedent('''
    from planted.pricing import discounted_total
    for quantity in (100, 200):
        assert discounted_total(10.0, quantity) < 10.0 * quantity
''')

ASSERTION_INSIDE_A_WITH = textwrap.dedent('''
    import pytest
    from planted.pricing import discounted_total
    with pytest.raises(TypeError):
        discounted_total(None, 100)
''')


@pytest.mark.parametrize(("body", "asserts"), [
    (REACHABLE, True),
    (ASSERTION_INSIDE_A_LOOP, True),
    (ASSERTION_INSIDE_A_WITH, True),
    (NESTED_AND_NEVER_CALLED, False),
    (NO_ASSERTION_AT_ALL, False),
])
def test_python_knows_whether_a_body_will_evaluate_an_assertion(body, asserts):
    """A loop and a `with` still execute what they hold; a function definition does not.
    `pytest.raises` counts, because the assertion is the context manager itself."""
    assert pcp.body_asserts(body) is asserts


def test_a_body_that_asserts_nothing_is_refused_before_it_is_run():
    """Refused at the proposal, not classified after the run. A body with no reachable
    assertion cannot produce evidence either way, so running it spends a subprocess to
    learn nothing and then files the nothing under `pass`."""
    check = pcp.body_asserts     # the rule is a required argument: `_valid` is shared, and
    # defaulting it would have checked Python source with Rust's rule wherever a caller forgot
    assert pcp._valid({"body": NESTED_AND_NEVER_CALLED, "explanation": "x"}, check) is None
    assert pcp._valid({"body": NO_ASSERTION_AT_ALL, "explanation": "x"}, check) is None
    assert pcp._valid({"body": REACHABLE, "explanation": "x"}, check) is not None


@pytest.mark.parametrize("module", [coverage_prove, pcp], ids=["rust", "python"])
@pytest.mark.parametrize("stage", ["propose", "repair"])
def test_both_stages_route_through_the_check_with_their_own_rule(module, stage):
    """Where the refusal has to live, asserted on the production path.

    `_prove_one` takes its proposer as a parameter and trusts what it returns, which is the
    contract: a proposer hands back a usable proposal or nothing. Re-checking inside the
    loop would be defending a contract the signature already holds. So what matters is that
    the two functions a real run uses, `propose` and `repair`, both pass their reply through
    `_valid` with THEIR OWN language's rule - and a refused proposal then arrives as None,
    which the loop already counts as a decline: it cost a model call and produced no test.
    """
    import inspect

    source = inspect.getsource(getattr(module, stage))
    assert "_valid(" in source, f"{module.__name__}.{stage} does not validate its reply"
    assert "body_asserts" in source, (
        f"{module.__name__}.{stage} validates without a reachable-assertion rule, so a body "
        "that asserts nothing would be run and filed under `pass`"
    )


@pytest.mark.parametrize(("body", "asserts"), [
    ("let result = f(1);\nassert!(result > 0, \"why\");", True),
    ("fn helper() { assert!(f(1) > 0); }", False),
    ("let result = f(1);", False),
    ("for n in 0..3 { assert_eq!(f(n), n); }", True),
])
def test_rust_knows_the_same_thing_about_its_own_bodies(body, asserts):
    """The same hole, in the language the concurrency sweep runs on. A body defining an
    `fn` that nobody calls compiles, the test passes, and cargo says nothing is wrong."""
    assert coverage_prove.body_asserts(body) is asserts


def test_rust_refuses_a_body_that_asserts_nothing():
    check = coverage_prove.body_asserts
    assert coverage_prove._valid({"body": "fn helper() { assert!(true); }", "explanation": "x"}, check) is None
    assert coverage_prove._valid({"body": "assert!(f(1) > 0);", "explanation": "x"}, check) is not None
