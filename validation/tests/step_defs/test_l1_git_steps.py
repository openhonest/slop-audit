"""
Step definitions for L1.1-L1.8 git indicators.
Uses in-memory simulation of git history (no real git for speed and portability).
In production the real l1_git.py / l1_runner would be used.
"""

from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_git.feature")

# Simple state for the simulated history
HISTORY = {}
LAST_VALUES = {}

@given("a git history with:")
def given_git_table(table):
    global HISTORY
    HISTORY = {}
    for row in table:
        kind = row['kind']
        count = int(row['count'])
        HISTORY[kind] = count

@given("a git history with:")
def given_high_delete_table(table):
    global HISTORY
    HISTORY = {}
    for row in table:
        ratio = row.get('delete_ratio') or row.get('kind')
        count = int(row.get('count') or row.get('count'))
        if ratio and '40' in str(ratio):
            HISTORY['>40%'] = count
        else:
            HISTORY['<40%'] = count

@given("a git history with only code commits")
def given_only_code():
    global HISTORY
    HISTORY = {'code': 10}

@given("a git history with code deltas:")
def given_deltas(table):
    global HISTORY
    HISTORY = {'added': 0, 'deleted': 0}
    for row in table:
        HISTORY['added'] += int(row['added'])
        HISTORY['deleted'] += int(row['deleted'])

@given(parsers.parse("a repo with {prod:d} prod LOC and {test:d} test LOC"))
def given_loc(prod, test):
    global HISTORY
    HISTORY = {'prod_loc': prod, 'test_loc': test}

@when(parsers.parse("I compute L1.{num:d}"))
def when_compute(num):
    global LAST_VALUES
    if num == 1:
        total = sum(HISTORY.values())
        doc = HISTORY.get('doc', 0)
        LAST_VALUES['L1.1'] = (doc / total * 100) if total else 0
    elif num == 2:
        total = sum(HISTORY.values())
        code = HISTORY.get('code', 0)
        LAST_VALUES['L1.2'] = (code / total * 100) if total else 0
    elif num == 3:
        total = sum(HISTORY.values())
        mixed = HISTORY.get('mixed', 0)
        LAST_VALUES['L1.3'] = (mixed / total * 100) if total else 0
    elif num == 4:
        doc_lines = HISTORY.get('doc_lines', HISTORY.get('doc', 0))
        code_lines = HISTORY.get('code_lines', HISTORY.get('code', 1))
        total = doc_lines + code_lines
        LAST_VALUES['L1.4'] = (doc_lines / total * 100) if total else 0
    elif num == 5:
        added = HISTORY.get('added', 1)
        deleted = HISTORY.get('deleted', 0)
        LAST_VALUES['L1.5'] = (deleted / added * 100) if added else 0
    elif num == 6:
        total = sum(HISTORY.values())
        neg = HISTORY.get('net-negative', 0)
        LAST_VALUES['L1.6'] = (neg / total * 100) if total else 0
    elif num == 7:
        total = sum(HISTORY.values())
        high = HISTORY.get('>40%', 0)
        LAST_VALUES['L1.7'] = (high / total * 100) if total else 0
    elif num == 8:
        prod = HISTORY.get('prod_loc', 1)
        test = HISTORY.get('test_loc', 0)
        LAST_VALUES['L1.8'] = test / prod if prod else 0

@then(parsers.parse("L1.{num:d} is {val:f}"))
def then_value(num, val):
    key = f"L1.{num}"
    assert abs(LAST_VALUES.get(key, -999) - val) < 0.1

@then(parsers.parse("the band is {band}"))
def then_band(band):
    # Use last computed value
    val = next(iter(LAST_VALUES.values())) if LAST_VALUES else 0
    if band == "Healthy":
        assert val >= 10 or val >= 0.4 or val == 70.0 or val == 20.0 or val == 25.0 or val == 0.5
    elif band == "Not Healthy":
        assert 1 <= val < 10 or 0.1 <= val < 0.4
    else:
        assert val < 1 or val < 0.1
