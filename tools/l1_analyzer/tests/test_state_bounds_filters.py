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


def test_memoization_cache_spread_across_methods_with_a_returning_setter_clears():
    # The real declaro shape: the cache is used across four methods, and a setter returns the
    # stored value. result-invariance must be scoped to the membership-gated accessor, not
    # every method that touches the attribute, or this regresses (the setter's `return token`
    # is not the keyed value). This is the case a self-only, whole-class scan gets wrong.
    src = ("class Pool:\n    def __init__(self):\n        self._t: dict = {}\n"
           "    def set(self, k, token):\n        self._t[k] = token\n        return token\n"
           "    def get(self, k):\n        if k not in self._t:\n            self._t[k] = mint(k)\n"
           "        return self._t[k]\n    def forget(self, k):\n        self._t.pop(k, None)\n"
           "    def close(self):\n        self._t.clear()\n")
    assert _verdict(src, "self._t") == "neutral"


def test_write_once_read_by_a_bounded_index_clears_even_when_promiscuous():
    # A once-assigned list read by an internal position index reads promiscuous (indexed
    # access), but it is immutable and drives only bounded decisions (position vs len). It
    # must clear - the value-indexed-cache below, which returns None on a miss, must not.
    src = ("class Cur:\n    def __init__(self, rows):\n        self._rows = rows\n        self._i = 0\n"
           "    def next(self):\n        if self._i >= len(self._rows):\n            return None\n"
           "        row = self._rows[self._i]\n        self._i += 1\n        return row\n")
    assert _verdict(src, "self._rows") == "neutral"


def test_carried_value_that_drives_no_decision_clears():
    # a builder value: assigned, sliced, methods called, but it appears in no test. Neutral.
    src = ("class Q:\n    def __init__(self, m):\n        self._qs = m.objects\n"
           "    def filter(self, **kw):\n        n = Q(self._m)\n        n._qs = self._qs.filter(**kw)\n        return n\n"
           "    def page(self, k):\n        return self._qs[k]\n")
    assert _verdict(src, "self._qs") == "neutral"


def test_write_only_counter_clears():
    # A per-key counter. The accumulator filter is what clears this, and nothing else does:
    # the membership test puts a reference in a condition, so the carried rule declines, and
    # the augmented assignment reads and rewrites the stored value, so the memoization rule
    # declines too. That refusal is right - a counter is not a memo cache - but it left the
    # counter with no shape to match. Nothing ever reads the count back out, and the gate's
    # two arms fall through to the same statement, so no test can distinguish them.
    #
    # Until the `not in` token fix this test passed for the wrong reason: the negated
    # membership went unrecognised, so the reference was graded a finite ordered comparison
    # and never became a finding. Spelling the gate `k in self._h` would have flagged it.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n")
    assert _verdict(src, "self._h") == "neutral"


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


def test_counted_value_read_into_a_branch_keeps():
    # the same counter, but now the count drives a branch (self._h[k] > 10): the value is
    # unbounded and inspected, so it stays promiscuous - the memoization filter must not clear it.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def hot(self, k):\n        if k in self._h and self._h[k] > 10:\n            return True\n"
           "        return False\n    def bump(self, k):\n        self._h[k] = self._h.get(k, 0) + 1\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_counter_read_into_a_branch_elsewhere_keeps():
    # The same gated counter, but a second method reads the count into a condition. The
    # accumulator rule must see every reference to the attribute, not only the ones in the
    # method that writes it, or the decision hides one method away.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n"
           "    def hot(self, k):\n        if self._h[k] > 10:\n            alert(k)\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_counter_returned_to_the_caller_keeps():
    # The count leaves the method. The caller can branch on it, so the decision has moved one
    # frame up rather than disappeared; a filter that cleared this would erase the finding by
    # refusing to look across the call. This is the half of the rule the escape check carries.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n"
           "    def count(self, k):\n        return self._h[k]\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_counter_handed_to_an_unknown_callee_keeps():
    # The same escape by the other route: the count is passed out as an argument. report()
    # can branch on it and this analyser cannot see inside report(), so the decision is real
    # and merely invisible. Passing the whole container (report(self._h)) is stopped earlier,
    # by the classifier itself, and reads unresolved rather than promiscuous; the keyed read
    # is the form that reaches this rule and has to be refused here.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n"
           "    def flush(self, k):\n        report(self._h[k])\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_counter_read_into_a_local_before_leaving_keeps():
    # A one-hop launder: the count lands in a local and the local is returned. A rule that
    # only looked at the reference's immediate parent would call this confined. The whitelist
    # refuses any keyed read that is not a store target, which covers the hop.
    src = ("class N:\n    def __init__(self):\n        self._h = {}\n"
           "    def bump(self, k):\n        if k not in self._h:\n            self._h[k] = 0\n        self._h[k] += 1\n"
           "    def count(self, k):\n        n = self._h[k]\n        return n\n")
    assert _verdict(src, "self._h") == "promiscuous"


def test_gate_that_writes_other_state_keeps():
    # The gate's arms do not converge: presence decides whether a second attribute moves. The
    # decision is real, it just lands in a neighbouring slot instead of in a return value, so
    # the module guard's result-invariance check (which reads returns) cannot see it.
    src = ("class N:\n    def __init__(self):\n        self._seen = {}\n        self._misses = 0\n"
           "    def note(self, k):\n        if k not in self._seen:\n            self._misses += 1\n"
           "            self._seen[k] = 0\n        self._seen[k] += 1\n")
    assert _verdict(src, "self._seen") == "promiscuous"


def test_invoked_only_collaborator_clears():
    # Single writer, invoked as a callable, result returned. Invoking state is not a decision
    # ON that state: nothing reads its value to select an arm, so its reaching-set is empty.
    # This was the shape that capped every repo with an injected collaborator at unresolved.
    src = ("class R:\n    def __init__(self, handler):\n        self._h = handler\n"
           "    def route(self, req):\n        return self._h(req)\n")
    assert _verdict(src, "self._h") == "neutral"


def test_rebound_call_target_keeps():
    # The same shape with a second binding site: which callee is live at the call depends on
    # invisible history (runtime rebinding of dispatch), so the premise fails and it stays.
    src = ("class R:\n    def __init__(self, handler):\n        self._h = handler\n"
           "    def swap(self, handler):\n        self._h = handler\n"
           "    def route(self, req):\n        return self._h(req)\n")
    assert _verdict(src, "self._h") == "unresolved"


def test_collaborator_mutated_through_the_slot_keeps():
    # Bound once and invoked, but the host writes through the slot, so the collaborator at
    # the call site is not provably the value that was injected. The premise fails.
    src = ("class R:\n    def __init__(self, sink):\n        self._s = sink\n"
           "    def configure(self):\n        self._s.limit = 10\n"
           "    def run(self, req):\n        return self._s(req)\n")
    assert _verdict(src, "self._s") == "unresolved"


def test_passed_to_unknown_callee_keeps_write_once_but_escapes():
    # single writer, never mutated here, but handed to an unknown callee that could mutate it.
    src = ("class P:\n    def __init__(self, buf):\n        self._b = buf\n"
           "    def run(self):\n        helper(self._b)\n")
    assert _verdict(src, "self._b") == "unresolved"
