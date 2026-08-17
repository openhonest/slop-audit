"""The write-only-accumulator filter in eight languages, clear cases beside keep cases.

tests/test_finite_testability_cross_language.py holds the nine languages to ONE verdict per
runtime shape. It is the right instrument for that and the wrong one for this: it says the
languages agree, not why, and a rule that cleared a shape for eight different wrong reasons
would satisfy it. This file asks each language separately, and every clear case sits beside
the neighbouring shape that must NOT clear, because a filter is only worth what it still
refuses.

Three shapes per language, and the two refusals are the ones the rule could plausibly get
wrong:

  clear   the gated per-key tally: nothing reads the count back out, and the gate's arms
          fall through to the same statement
  keep    the same tally with the count RETURNED. The decision moves one frame up into the
          caller and the finding must not evaporate with it - the compositional hole the
          classifier guards everywhere else
  keep    the same gate guarding a write to a SECOND piece of state. The presence decides
          something after all, just in a neighbouring slot rather than in a return value,
          where the result-invariance check cannot see it

C is absent by construction and says so in its own test at the bottom: it asks no membership
question and grows no container, so the gated shape cannot be written in it at all.
"""

import pathlib
import tempfile

import pytest
from l1_analyzer import state_bounds, state_ref_reads
from l1_analyzer.indicators import _get_parser
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.ts_nodes import refs as _refs
from l1_analyzer.ts_nodes import text as _text

_FILENAME = {
    "python": "case.py", "typescript": "case.ts", "javascript": "case.js",
    "java": "Case.java", "csharp": "Case.cs", "ruby": "case.rb",
    "rust": "case.rs", "go": "case.go", "c": "case.c",
}

_KEY = {
    "python": "self.hits", "rust": "self.hits",
    "typescript": "this.hits", "javascript": "this.hits",
    "java": "hits", "csharp": "hits",
    "ruby": "@hits",
    "go": "S.hits",
}

LANGUAGES = tuple(_KEY)


def _verdict(lang: str, src: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / _FILENAME[lang]).write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f["verdict"] for f in r["findings"] if f["state"] == _KEY[lang]), "absent")


# --- CLEAR: the gated per-key tally nothing reads back out ----------------------

CLEARS = {
    "python": (
        "class S:\n"
        "    def __init__(self):\n"
        "        self.hits = {}\n"
        "    def bump(self, k):\n"
        "        if k not in self.hits:\n"
        "            self.hits[k] = 0\n"
        "        self.hits[k] += 1\n"),
    "typescript": (
        "class S {\n"
        "  hits: Record<string, number> = {};\n"
        "  bump(k: string) {\n"
        "    if (!(k in this.hits)) { this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "javascript": (
        "class S {\n"
        "  hits = {};\n"
        "  bump(k) {\n"
        "    if (!(k in this.hits)) { this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "java": (
        "import java.util.*;\n"
        "class S {\n"
        "  Map<String,Integer> hits = new HashMap<>();\n"
        "  void bump(String k) {\n"
        "    if (!hits.containsKey(k)) { hits.put(k, 0); }\n"
        "    hits.put(k, hits.get(k) + 1);\n"
        "  }\n"
        "}\n"),
    "csharp": (
        "using System.Collections.Generic;\n"
        "class S {\n"
        "  Dictionary<string,int> hits = new Dictionary<string,int>();\n"
        "  void Bump(string k) {\n"
        "    if (!hits.ContainsKey(k)) { hits[k] = 0; }\n"
        "    hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "ruby": (
        "class S\n"
        "  def initialize; @hits = {}; end\n"
        "  def bump(k)\n"
        "    @hits[k] = 0 unless @hits.key?(k)\n"
        "    @hits[k] += 1\n"
        "  end\n"
        "end\n"),
    "rust": (
        "use std::collections::HashMap;\n"
        "struct S { hits: HashMap<String, i32> }\n"
        "impl S {\n"
        "  fn bump(&mut self, k: String) {\n"
        "    if !self.hits.contains_key(&k) { self.hits.insert(k.clone(), 0); }\n"
        "    *self.hits.get_mut(&k).unwrap() += 1;\n"
        "  }\n"
        "}\n"),
    "go": (
        "package main\n"
        "type S struct { hits map[string]int }\n"
        "func (s *S) Bump(k string) {\n"
        "  if _, ok := s.hits[k]; !ok {\n"
        "    s.hits[k] = 0\n"
        "  }\n"
        "  s.hits[k] += 1\n"
        "}\n"),
}


# --- KEEP: the same tally, with the count handed to the caller -----------------

RETURNED = {
    "python": (
        "class S:\n"
        "    def __init__(self):\n"
        "        self.hits = {}\n"
        "    def bump(self, k):\n"
        "        if k not in self.hits:\n"
        "            self.hits[k] = 0\n"
        "        self.hits[k] += 1\n"
        "    def count(self, k):\n"
        "        return self.hits[k]\n"),
    "typescript": (
        "class S {\n"
        "  hits: Record<string, number> = {};\n"
        "  bump(k: string) {\n"
        "    if (!(k in this.hits)) { this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "  count(k: string) { return this.hits[k]; }\n"
        "}\n"),
    "javascript": (
        "class S {\n"
        "  hits = {};\n"
        "  bump(k) {\n"
        "    if (!(k in this.hits)) { this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "  count(k) { return this.hits[k]; }\n"
        "}\n"),
    "java": (
        "import java.util.*;\n"
        "class S {\n"
        "  Map<String,Integer> hits = new HashMap<>();\n"
        "  void bump(String k) {\n"
        "    if (!hits.containsKey(k)) { hits.put(k, 0); }\n"
        "    hits.put(k, hits.get(k) + 1);\n"
        "  }\n"
        "  Integer count(String k) { return hits.get(k); }\n"
        "}\n"),
    "csharp": (
        "using System.Collections.Generic;\n"
        "class S {\n"
        "  Dictionary<string,int> hits = new Dictionary<string,int>();\n"
        "  void Bump(string k) {\n"
        "    if (!hits.ContainsKey(k)) { hits[k] = 0; }\n"
        "    hits[k] += 1;\n"
        "  }\n"
        "  int Count(string k) { return hits[k]; }\n"
        "}\n"),
    "ruby": (
        "class S\n"
        "  def initialize; @hits = {}; end\n"
        "  def bump(k)\n"
        "    @hits[k] = 0 unless @hits.key?(k)\n"
        "    @hits[k] += 1\n"
        "  end\n"
        "  def count(k); @hits[k]; end\n"
        "end\n"),
    "rust": (
        "use std::collections::HashMap;\n"
        "struct S { hits: HashMap<String, i32> }\n"
        "impl S {\n"
        "  fn bump(&mut self, k: String) {\n"
        "    if !self.hits.contains_key(&k) { self.hits.insert(k.clone(), 0); }\n"
        "    *self.hits.get_mut(&k).unwrap() += 1;\n"
        "  }\n"
        "  fn count(&self, k: &str) -> i32 { self.hits[k] }\n"
        "}\n"),
    "go": (
        "package main\n"
        "type S struct { hits map[string]int }\n"
        "func (s *S) Bump(k string) {\n"
        "  if _, ok := s.hits[k]; !ok {\n"
        "    s.hits[k] = 0\n"
        "  }\n"
        "  s.hits[k] += 1\n"
        "}\n"
        "func (s *S) Count(k string) int { return s.hits[k] }\n"),
}


# --- KEEP: the gate guards a write to a SECOND piece of state ------------------

DIVERGING = {
    "python": (
        "class S:\n"
        "    def __init__(self):\n"
        "        self.hits = {}\n"
        "        self.misses = 0\n"
        "    def bump(self, k):\n"
        "        if k not in self.hits:\n"
        "            self.misses += 1\n"
        "            self.hits[k] = 0\n"
        "        self.hits[k] += 1\n"),
    "typescript": (
        "class S {\n"
        "  hits: Record<string, number> = {};\n"
        "  misses = 0;\n"
        "  bump(k: string) {\n"
        "    if (!(k in this.hits)) { this.misses += 1; this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "javascript": (
        "class S {\n"
        "  hits = {};\n"
        "  misses = 0;\n"
        "  bump(k) {\n"
        "    if (!(k in this.hits)) { this.misses += 1; this.hits[k] = 0; }\n"
        "    this.hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "java": (
        "import java.util.*;\n"
        "class S {\n"
        "  Map<String,Integer> hits = new HashMap<>();\n"
        "  int misses = 0;\n"
        "  void bump(String k) {\n"
        "    if (!hits.containsKey(k)) { misses += 1; hits.put(k, 0); }\n"
        "    hits.put(k, hits.get(k) + 1);\n"
        "  }\n"
        "}\n"),
    "csharp": (
        "using System.Collections.Generic;\n"
        "class S {\n"
        "  Dictionary<string,int> hits = new Dictionary<string,int>();\n"
        "  int misses = 0;\n"
        "  void Bump(string k) {\n"
        "    if (!hits.ContainsKey(k)) { misses += 1; hits[k] = 0; }\n"
        "    hits[k] += 1;\n"
        "  }\n"
        "}\n"),
    "ruby": (
        "class S\n"
        "  def initialize; @hits = {}; @misses = 0; end\n"
        "  def bump(k)\n"
        "    unless @hits.key?(k)\n"
        "      @misses += 1\n"
        "      @hits[k] = 0\n"
        "    end\n"
        "    @hits[k] += 1\n"
        "  end\n"
        "end\n"),
    "rust": (
        "use std::collections::HashMap;\n"
        "struct S { hits: HashMap<String, i32>, misses: i32 }\n"
        "impl S {\n"
        "  fn bump(&mut self, k: String) {\n"
        "    if !self.hits.contains_key(&k) { self.misses += 1; self.hits.insert(k.clone(), 0); }\n"
        "    *self.hits.get_mut(&k).unwrap() += 1;\n"
        "  }\n"
        "}\n"),
    "go": (
        "package main\n"
        "type S struct { hits map[string]int; misses int }\n"
        "func (s *S) Bump(k string) {\n"
        "  if _, ok := s.hits[k]; !ok {\n"
        "    s.misses += 1\n"
        "    s.hits[k] = 0\n"
        "  }\n"
        "  s.hits[k] += 1\n"
        "}\n"),
}


@pytest.mark.parametrize("lang", LANGUAGES)
def test_the_gated_tally_clears_in_every_language(lang):
    """The shape the rule exists for. Every reference is a write or a presence test, the
    gate's two arms fall through to the same increment, and nothing reads the count out."""
    assert _verdict(lang, CLEARS[lang]) == "neutral"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_a_tally_whose_count_is_returned_keeps_in_every_language(lang):
    """The compositional hole. One accessor hands the count to the caller and the decision
    moves one frame up, out of this file's sight. A rule that cleared this would let any
    finding escape by adding a getter."""
    assert _verdict(lang, RETURNED[lang]) == "promiscuous"


@pytest.mark.parametrize("lang", LANGUAGES)
def test_a_gate_that_writes_other_state_keeps_in_every_language(lang):
    """The arms do not converge: presence decides whether a second attribute moves. The
    decision is real, it just lands in a neighbouring slot rather than in a return value, so
    the result-invariance check (which reads returns) cannot see it and only the convergence
    check can."""
    assert _verdict(lang, DIVERGING[lang]) == "promiscuous"


# --- the per-language readings, asked directly --------------------------------


def _first_ref(lang: str, src: str, predicate):
    """The first node in `src` the predicate accepts, for asking one reading directly."""
    root = _get_parser(lang).parse(src.encode()).root_node
    return next((n for n in _refs(root, predicate)), None)


def test_java_reads_a_presence_method_as_a_presence_test_and_not_as_a_value_read():
    """Java has no membership operator, so `containsKey` IS the gate. It is also in the
    keyed-read set the classifier uses, and folding the two together would make the gate
    look like a stored value inspected in a branch - which would refuse every shape the
    accumulator rule exists for. The two sets are declared apart for exactly this."""
    sp = LANG_SPEC["java"]
    src = "class S { void f(String k) { if (!hits.containsKey(k)) { hits.put(k, 0); } } }\n"
    ref = _first_ref("java", src, lambda n: n.type == "identifier" and _text(n) == "hits")
    assert state_ref_reads.is_presence_test(ref, sp) is True
    assert state_ref_reads.keyed_value_read(ref, sp) is None


def test_go_reads_the_comma_ok_binding_as_a_presence_test():
    """Go's `_, ok := d[k]` is neither an operator nor a method. It binds, in a node that is
    not one of Go's own assignment types, so nothing else in the tree recognises it. The
    value half goes to the blank identifier, which is what proves nothing was read out."""
    sp = LANG_SPEC["go"]
    src = ("package main\n"
           "func (s *S) f(k string) {\n  if _, ok := s.hits[k]; !ok {\n    s.hits[k] = 0\n  }\n}\n")
    ref = _first_ref("go", src, lambda n: n.type == "selector_expression" and _text(n) == "s.hits")
    assert state_ref_reads.is_comma_ok_presence(ref, sp) is True
    assert state_ref_reads.is_presence_test(ref, sp) is True


def test_go_keeps_the_value_when_the_comma_ok_binding_names_it():
    """`v, ok := d[k]` takes the stored value out under a name. The presence half is the
    same, and the reading must not be, because the value is now in the caller's hands."""
    sp = LANG_SPEC["go"]
    src = ("package main\n"
           "func (s *S) f(k string) int {\n  v, ok := s.hits[k]\n  if !ok {\n    return 0\n  }\n  return v\n}\n")
    ref = _first_ref("go", src, lambda n: n.type == "selector_expression" and _text(n) == "s.hits")
    assert state_ref_reads.is_comma_ok_presence(ref, sp) is False


def test_ruby_reads_a_flat_call_receiver_one_level_up_from_the_nested_grammars():
    """Ruby puts receiver, method and arguments on ONE node. A predicate written as `parent
    is a member access, grandparent is a call` reads it off by a level and finds nothing."""
    sp = LANG_SPEC["ruby"]
    src = "class S\n  def f(k)\n    @hits[k] = 0 unless @hits.key?(k)\n  end\nend\n"
    root = _get_parser("ruby").parse(src.encode()).root_node
    ivars = _refs(root, lambda n: n.type == "instance_variable" and _text(n) == "@hits")
    gate = next(r for r in ivars if r.parent is not None and r.parent.type == "call")
    call = state_ref_reads.receiver_call(gate, sp)
    assert call is not None and call.type == "call"
    assert state_ref_reads.method_name(call, sp) == "key?"
    assert state_ref_reads.is_presence_test(gate, sp) is True


def test_csharp_descends_the_bracketed_argument_list_to_reach_the_key():
    """C# wraps a subscript key in a bracketed_argument_list holding an `argument` holding
    the key. A reader that descends once finds the wrapper and calls every C# subscript an
    open-key read."""
    sp = LANG_SPEC["csharp"]
    src = "class S { void F(string k) { hits[k] = 0; } }\n"
    root = _get_parser("csharp").parse(src.encode()).root_node
    sub = next(iter(_refs(root, lambda n: n.type == "element_access_expression")))
    from l1_analyzer.ts_nodes import sub_key
    assert _text(sub_key(sub, sp)) == "k"


@pytest.mark.parametrize("lang,method", [("java", "put"), ("rust", "insert")])
def test_a_write_that_returns_the_previous_value_is_write_only_only_when_nobody_reads_it(lang, method):
    """Java's `Map.put` and Rust's `HashMap::insert` write AND hand back what was stored
    before. Discarded, that is a write and nothing else; read, it is a value the caller can
    branch on. Both are on the declared write set, and the discard check is what separates
    them."""
    sp = LANG_SPEC[lang]
    assert method in sp["write_methods"]
    assert "pop" not in sp["write_methods"] and "remove" not in sp["write_methods"]


def test_ruby_declines_a_write_method_because_it_can_never_prove_the_result_unread():
    """Ruby discards nothing syntactically: every expression is a value and only position
    decides whether anything reads it. So a Ruby write method whose result would have to be
    proven unread cannot be proven here, and the decline is declared rather than guessed."""
    assert LANG_SPEC["ruby"]["discard_types"] == ()


def test_c_asks_no_presence_question_at_all():
    """C is absent from the gated shape by construction, not by omission. It has no
    membership operator and no presence method, and a fixed array answers for every index
    whether or not anything was stored there, so the question the shape turns on cannot be
    asked. The empty declarations are the statement of that."""
    sp = LANG_SPEC["c"]
    assert sp["membership"] == "none"
    assert sp["presence_methods"] == frozenset()
    src = "static int cache[256];\nint hot(int k) { if (cache[k] > 0) { return 1; } return 0; }\n"
    ref = _first_ref("c", src, lambda n: n.type == "identifier" and _text(n) == "cache")
    assert state_ref_reads.is_presence_test(ref, sp) is False


def test_only_python_spells_a_key_removal_as_a_statement():
    """Everywhere else a removal is a call that hands the removed value back, or - in
    JavaScript - a unary_expression that collides with a wrapper already declared
    transparent. Eight languages declare no delete statement, so the accumulator rule
    declines a key removal there rather than reading one shape as another."""
    spelled = {lang for lang, sp in LANG_SPEC.items() if sp["delete_stmt_types"]}
    assert spelled == {"python"}
