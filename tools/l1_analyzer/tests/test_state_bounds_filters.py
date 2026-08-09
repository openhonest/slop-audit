"""The L1.18b attribute-level false-positive filters, verified against the shapes that must
CLEAR (a false positive suppressed to neutral) and the shapes that must KEEP (a genuine
finding). Found and proven against declaro-persistum; each KEEP case is one a filter could
wrongly clear, so a regression here is a silent loss of a real finding. Pure assertions."""

import pathlib
import tempfile

from l1_analyzer import state_bounds


def _verdict(src: str, attr: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        return next((f["verdict"] for f in r["findings"] if f["state"] == attr), "absent")


# --- CLEAR: provable false positives, suppressed to neutral ---------------------

def test_memoization_cache_clears():
    # presence-gated, result-invariant (always returns the cached value), value never in a
    # condition -> a cache, not a decision. Neutral.
    src = ("class M:\n    def __init__(self):\n        self._t = {}\n"
           "    def get(self, k):\n        if k not in self._t:\n            self._t[k] = mint(k)\n"
           "        return self._t[k]\n    def close(self):\n        self._t.clear()\n")
    assert _verdict(src, "self._t") == "neutral"


def test_carried_value_that_drives_no_decision_clears():
    # a builder value: assigned, sliced, methods called, but it appears in no test. Neutral.
    src = ("class Q:\n    def __init__(self, m):\n        self._qs = m.objects\n"
           "    def filter(self, **kw):\n        n = Q(self._m)\n        n._qs = self._qs.filter(**kw)\n        return n\n"
           "    def page(self, k):\n        return self._qs[k]\n")
    assert _verdict(src, "self._qs") == "neutral"


def test_write_once_immutable_clears():
    # assigned once (unknown-typed arg -> unresolved), never mutated, handed out only as a copy.
    src = ("class C:\n    def __init__(self, rows):\n        self._rows = rows\n"
           "    def all(self):\n        return list(self._rows)\n")
    assert _verdict(src, "self._rows") == "neutral"


# --- KEEP: genuine findings a filter must NOT clear ----------------------------

def test_value_inspected_in_condition_keeps():
    # the stored value drives a branch (now - t >= 3600): promiscuous, not a cache.
    src = ("class W:\n    def __init__(self):\n        self._f = {}\n"
           "    def check(self, k, now):\n        if k not in self._f:\n            self._f[k] = now\n"
           "        elif now - self._f[k] >= 3600:\n            crit(k)\n")
    assert _verdict(src, "self._f") == "promiscuous"


def test_dedup_set_keeps_result_is_not_invariant():
    # presence IS the answer (returns False vs True by presence): a dedup set, not a cache.
    src = ("class D:\n    def __init__(self):\n        self._s = {}\n"
           "    def first(self, k):\n        if k in self._s:\n            return False\n"
           "        self._s[k] = True\n        return True\n")
    assert _verdict(src, "self._s") == "promiscuous"


def test_value_indexed_lookup_keeps_returns_none_on_miss():
    # returns the value on hit, None on miss: the presence changes the answer -> promiscuous.
    src = ("class Cache:\n    def __init__(self):\n        self._c = {}\n"
           "    def get(self, k):\n        if k in self._c:\n            return self._c[k]\n        return None\n")
    assert _verdict(src, "self._c") == "promiscuous"


def test_write_only_counter_is_already_bounded_no_filter_needed():
    # A per-key counter whose value is never read into a branch is already neutral before any
    # filter: the membership is binary and the augmented value drives no decision. The filter
    # must not be needed here, and must not mis-handle it.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n")
    assert _verdict(src, "self._h") == "neutral"


def test_counted_value_read_into_a_branch_keeps():
    # the same counter, but now the count drives a branch (self._h[k] > 10): the value is
    # unbounded and inspected, so it stays promiscuous - the memoization filter must not clear it.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def hot(self, k):\n        if k in self._h and self._h[k] > 10:\n            return True\n"
           "        return False\n    def bump(self, k):\n        self._h[k] = self._h.get(k, 0) + 1\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_dynamic_dispatch_keeps_write_once_but_invoked():
    # single writer, but the attribute is invoked as a callable: undecidable, stays unresolved.
    src = ("class R:\n    def __init__(self, handler):\n        self._h = handler\n"
           "    def route(self, req):\n        return self._h(req)\n")
    assert _verdict(src, "self._h") == "unresolved"


def test_passed_to_unknown_callee_keeps_write_once_but_escapes():
    # single writer, never mutated here, but handed to an unknown callee that could mutate it.
    src = ("class P:\n    def __init__(self, buf):\n        self._b = buf\n"
           "    def run(self):\n        helper(self._b)\n")
    assert _verdict(src, "self._b") == "unresolved"
