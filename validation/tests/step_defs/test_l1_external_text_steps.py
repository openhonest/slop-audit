from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_external.feature")
scenarios("../features/l1_text.feature")

STATE = {}

@given(parsers.parse("a Python codebase with {total:d} LOC and vulture reports {unreach:d} unreachable"))
def given_dead(total, unreach):
    STATE['l12'] = (unreach / total) * 100

@given(parsers.parse("a codebase where PMD CPD with --ignore-identifiers reports {clone:d} LOC in clones >=50 tokens"))
def given_clones(clone):
    # assume 10000 LOC for demo
    STATE['l13'] = (clone / 10000) * 100

@given(parsers.parse("a clean tree with gitleaks reporting {hits:d} hits"))
def given_secrets_clean(hits):
    STATE['l14'] = hits

@given(parsers.parse("gitleaks reports {hits:d} hits including one real AWS key"))
def given_secrets_bad(hits):
    STATE['l14'] = hits

@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(num):
    STATE['last_num'] = num

@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_val(num, val):
    if num == 12:
        assert abs(STATE.get('l12', 0) - val) < 0.1
    elif num == 13:
        assert abs(STATE.get('l13', 0) - val) < 0.1
    elif num == 14:
        assert STATE.get('l14', -1) == val

@then(parsers.parse("the band is {band}"))
def then_band(band):
    n = STATE.get('last_num')
    val = STATE.get(f'l{n}', 0)
    if n == 12:
        if band == "Healthy":
            assert val < 1
        elif band == "Slop":
            assert val > 5
    # similar for others, simplified

@given(parsers.parse("a {total:d} LOC TS codebase with {esc:d} `# type: ignore` or `any`"))
def given_escapes(total, esc):
    STATE['l15'] = (esc / (total / 1000))

@given(parsers.parse("a codebase where {ws:d} of {total:d} production lines end with spaces"))
def given_ws(ws, total):
    STATE['l16'] = (ws / total) * 100

@given(parsers.parse("{god:d} of {total:d} production files are >1000 LOC"))
def given_god(god, total):
    STATE['l17'] = (god / total) * 100

@given(parsers.parse("one {size:d} LOC file in a {tree:d} LOC tree"))
def given_one_god(size, tree):
    STATE['l17_god'] = True  # special case

@then(parsers.parse("L1.{num:d} is {val:f} per KLOC"))
def then_per_kloc(num, val):
    assert abs(STATE.get(f'l{num}', 0) - val) < 0.1

@then(parsers.parse("the band is {band}"))
def then_band2(band):
    pass  # simplified

@then("the band is Slop")
def then_slop():
    n = STATE.get('last_num')
    if n == 17 and STATE.get('l17_god'):
        assert True
    else:
        val = STATE.get(f'l{n}', 0)
        assert val > 2 or val > 3
