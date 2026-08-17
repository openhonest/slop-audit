"""The L1.18b attribute-level false-positive filters, verified against the shapes that must
CLEAR (a false positive suppressed to neutral) and the shapes that must KEEP (a genuine
finding). Found and proven against declaro-persistum; each KEEP case is one a filter could
wrongly clear, so a regression here is a silent loss of a real finding. Pure assertions."""

import pathlib
import tempfile

import pytest
from l1_analyzer import state_bounds


def _verdict(src: str, attr: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        return next((f["verdict"] for f in r["findings"] if f["state"] == attr), "absent")


def _construct(src: str, attr: str) -> str:
    """The syntax shape the classifier could not decide, empty on every decided finding."""
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / "m.py").write_text(src)
        r = state_bounds.classify(p, "python")
        return next((f["construct"] for f in r["findings"] if f["state"] == attr), "absent")


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
    # a builder value: assigned, methods called, returned, but it appears in no test. Neutral.
    #
    # This case used to carry a fourth method, `def page(self, k): return self._qs[k]`, and
    # asserted the whole class neutral. That assertion was wrong and it is now its own KEEP
    # case below. The builder chain is what the carried-value rule was built for and it still
    # clears; the open-key slice is a different shape that happened to share a fixture.
    src = ("class Q:\n    def __init__(self, m):\n        self._qs = m.objects\n"
           "    def filter(self, **kw):\n        n = Q(self._m)\n        n._qs = self._qs.filter(**kw)\n        return n\n")
    assert _verdict(src, "self._qs") == "neutral"


def test_carried_value_sliced_by_a_literal_still_clears():
    # The same builder read at a fixed position. A literal index cuts one class out of the
    # container and leaves a bounded question, so the carried-value rule is untouched by the
    # open-key guard here. This is the case that proves the guard reads the KEY and not the
    # presence of a subscript.
    src = ("class Q:\n    def __init__(self, m):\n        self._qs = m.objects\n"
           "    def filter(self, **kw):\n        n = Q(self._m)\n        n._qs = self._qs.filter(**kw)\n        return n\n"
           "    def head(self):\n        return self._qs[0]\n")
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


def test_unbounded_keyed_read_of_a_container_this_class_owns_keeps():
    # The miss this file existed to prevent and did not. `self.cache[k]`, k a parameter, is the
    # decision: the container answers one way per key, and the number of keys is the caller's
    # to choose, so the equivalence classes cannot be enumerated. C reports exactly this shape
    # promiscuous (tests/test_finite_testability_c.py, value-indexed-cache) because C has no
    # attribute-level filter to clear it. The carried-value rule cleared the Python spelling on
    # the grounds that no reference appears in an `if`, which reads the decision off the
    # KEYWORD rather than off the values: a subscript by an unbounded key selects among
    # unboundedly many stored values whether or not an `if` follows it.
    src = ("class S:\n    def __init__(self):\n        self.cache = {}\n"
           "    def put(self, k, v):\n        self.cache[k] = v\n"
           "    def get(self, k):\n        return self.cache[k]\n")
    assert _verdict(src, "self.cache") == "promiscuous"


def test_unbounded_keyed_read_keeps_even_with_no_second_writer():
    # The same shape with the store removed, so the attribute is write-once. Write-once argues
    # immutability, and immutability says nothing about how many classes a key cuts the
    # contents into; the read is still one answer per key. Without this case the fix above can
    # be satisfied by the write-once rule alone and the minimal spelling stays cleared.
    src = ("class S:\n    def __init__(self):\n        self.cache = {}\n"
           "    def get(self, k):\n        return self.cache[k]\n")
    assert _verdict(src, "self.cache") == "promiscuous"


def test_carried_builder_sliced_by_an_open_key_keeps():
    # A REVERSAL, recorded here rather than in a commit message. Until 2026-08-15 this exact
    # source was asserted neutral, as the carried-value rule's own fixture, on the grounds
    # that no reference to self._qs appears in an `if`. It is the same runtime shape as the
    # C fixture value-indexed-cache, which has always read promiscuous, and the two cannot
    # both be right about one behaviour. The C answer is the one kept: a slice by a key the
    # caller chooses answers one way per key, and `if` is not what makes that a decision.
    #
    # The cost of the reversal is real and belongs in the record. Every builder that exposes
    # positional access by a parameter now reads promiscuous, and the population that reads
    # that way is the population declaro-persistum was cleared out of. If the reversal is
    # wrong, it is C that has to change, not this test, because the property is one property.
    src = ("class Q:\n    def __init__(self, m):\n        self._qs = m.objects\n"
           "    def filter(self, **kw):\n        n = Q(self._m)\n        n._qs = self._qs.filter(**kw)\n        return n\n"
           "    def page(self, k):\n        return self._qs[k]\n")
    assert _verdict(src, "self._qs") == "promiscuous"


def test_literal_width_slice_of_a_carried_value_clears():
    # Found by measuring the fix rather than by predicting it: buckler/iam's
    # `self.e164_hash[:4].hex()` turned promiscuous, because tree-sitter spells `[:4]` as a
    # `slice` node and the first draft of the open-key guard asked only whether the node was
    # a literal. A slice is not a key: it takes a contiguous run at a fixed width, not one
    # stored value out of unboundedly many.
    src = ("class P:\n    def __init__(self, v):\n        self._h = hash_of(v)\n"
           "    def prefix(self):\n        return self._h[:4].hex()\n")
    assert _verdict(src, "self._h") == "neutral"


def test_variable_width_slice_of_a_carried_value_clears():
    # The same exclusion where the width comes from the caller. A run of caller-chosen
    # length is not a selection among stored values, so the guard stands aside and the
    # carried-value rule decides, exactly as it did before the guard existed. Stated as its
    # own case because it is the boundary a later reader will be tempted to move.
    src = ("class A:\n    def __init__(self):\n        self._a = []\n"
           "    def add(self, x):\n        self._a.append(x)\n"
           "    def tail(self, limit):\n        return self._a[-limit:]\n")
    assert _verdict(src, "self._a") == "neutral"


def test_keyed_read_by_state_this_class_bounds_clears():
    # The other side of the same rule, and the reason it is scoped to keys from OUTSIDE. The
    # index is `self._i`, which is state in this class and therefore carries its own finding,
    # bounded there by `self._i >= len(self._rows)`. Counting it a second time against the
    # container is double-counting one decision, which is what made the cursor a false
    # positive. A key that arrives as a parameter is carried by no other finding.
    src = ("class Cur:\n    def __init__(self, rows):\n        self._rows = rows\n        self._i = 0\n"
           "    def next(self):\n        if self._i >= len(self._rows):\n            return None\n"
           "        row = self._rows[self._i]\n        self._i += 1\n        return row\n")
    assert _verdict(src, "self._rows") == "neutral"


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


# --- slop-audit-qb5, corrected -------------------------------------------------
#
# These were written to prove three live false-NEUTRAL verdicts. Measured before and after
# the fix, all four fixtures give the identical verdict, so the claim was wrong: the
# classifier fails closed on list_splat, keyword_argument and pattern_list before the filter
# is ever asked, and a filter gap behind a fail-closed classifier cannot clear anything.
#
# What the fixes are worth keeping for is drift, not verdicts. What the tests below are worth
# keeping for is the fail-closed behaviour that made the gaps unreachable, which nothing else
# pinned, and which is the only reason the wrong answer never shipped.


@pytest.mark.parametrize("call,construct", [
    ("unknown(*self._a)", "list_splat"),
    ("unknown(rows=self._a)", "keyword_argument"),
])
def test_a_container_handed_out_through_a_wrapper_is_unresolved_not_cleared(call, construct):
    """A splat and a keyword argument each put a node between the reference and the argument
    list. The classifier has no row for either, so it fails closed and names the construct
    rather than deciding. That refusal is what stands in front of `_escapes`, which reads
    only `argument_list` and would not have seen the value leave."""
    src = ("class Q:\n    def __init__(self):\n        self._a = {}\n"
           "    def put(self, k, v):\n        self._a[k] = v\n"
           f"    def send(self):\n        return {call}\n")
    assert _verdict(src, "self._a") == "unresolved"
    assert _construct(src, "self._a") == f"attribute in {construct}"


def test_a_tuple_assignment_target_is_unresolved_not_cleared():
    """`self._a, self._b = m, m` puts a pattern_list in the target. The classifier has no row
    for it and says so, which is why `_member_writes` counting neither write could not turn
    into a write-once clear."""
    src = ("class Q:\n    def __init__(self):\n        self._a = {}\n        self._b = {}\n"
           "    def reset(self, m):\n        self._a, self._b = m, m\n"
           "    def take(self, k):\n        return self._a[k]\n")
    assert _verdict(src, "self._a") == "unresolved"
    assert _construct(src, "self._a") == "attribute in pattern_list"


def test_the_in_place_set_is_a_superset_of_the_classifier_by_construction():
    """The docstring claimed this and a hand-written list sat underneath, which drifted:
    `appendleft` was in the classifier's set and not in the filter's. The claim is now the
    construction, so this test fails only if someone replaces the derivation with a literal."""
    from l1_analyzer.lang_spec import _PY_MUTATING
    from l1_analyzer.state_bounds_filters import _IN_PLACE
    assert _PY_MUTATING <= _IN_PLACE
