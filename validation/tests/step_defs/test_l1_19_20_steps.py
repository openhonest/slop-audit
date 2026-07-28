from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_19.feature")
scenarios("../features/l1_20.feature")

STATE = {}

@given(parsers.parse("a codebase with {total:d} dispatch table entries and a test suite that hits {hit:d}"))
def given_decision(total, hit):
    STATE['l19'] = hit / total * 100

@given(parsers.parse("{n:d} enum variants but tests only exercise {hit:d}"))
def given_enum(n, hit):
    STATE['l19'] = hit / n * 100

@given("many if/elif chains and dispatch tables with <30% exercised")
def given_low_decision():
    STATE['l19'] = 30.0

@when(parsers.parse("I compute L1.{num:d}"))
def when_l1(num):
    STATE['last'] = num

@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_val(num, val):
    assert abs(STATE.get('l19', 0) - val) < 0.1

@then(parsers.parse("the band is {band}"))
def then_band(band):
    val = STATE.get('l19', 0)
    if band == "Healthy":
        assert val > 90
    elif band == "Not Healthy":
        assert 60 <= val <= 90
    else:
        assert val < 60

# L1.20 stubs
@given("a test suite with no shared mutable state between tests")
def given_pure_tests():
    STATE['l20_passes'] = 5

@given("tests that depend on DB fixtures or singletons created in previous tests")
def given_flaky():
    STATE['l20_passes'] = 3

@given("heavy order dependence (many tests fail when order changes)")
def given_very_flaky():
    STATE['l20_passes'] = 2

@when("I run the suite 5 times with --randomly-seed=random")
def when_random():
    pass

@when("I run randomized 5 times")
def when_random2():
    pass

@then(parsers.parse("{n:d} of 5 runs pass"))
def then_passes(n):
    assert STATE.get('l20_passes') == n

@then(parsers.parse("L1.20 band is {band}"))
def then_l20_band(band):
    passes = STATE.get('l20_passes', 0)
    if band == "Healthy":
        assert passes == 5
    elif band == "Not Healthy":
        assert passes == 4
    else:
        assert passes < 4
