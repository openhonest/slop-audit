"""Cross-language conformance: one runtime shape, one verdict, in all nine languages.

L1.18b measures a property of the code AT RUNTIME - whether the decisions reaching a piece
of state partition its domain into a statically-enumerable finite set. Nothing in that
question mentions a language. It follows that the same runtime shape must resolve to the
same verdict in Python, Rust, C, Java, TypeScript, C#, JavaScript, Ruby and Go, and that
where two of them disagree one of them is wrong. No argument from language design excuses a
divergence: access control, static typing and memory safety change what a language makes
DIFFICULT, not how many equivalence classes a value's consumers cut it into.

The per-language suites next to this file each state their own expected verdict, case by
case, so nothing in the tree compared one language against another. That is how a Python
false-positive filter came to clear `return self.cache[k]` while C reported the identical
shape promiscuous, and how the two stayed apart with a green suite. This file is the
comparison that was missing.

Every shape below declares ONE verdict, as a property of the behaviour, and each language
supplies its own spelling of that behaviour. A language that cannot express a shape declares
None and says why in the prose, which is the only sanctioned way for a language to be absent:
writing a different expected verdict per language would make the suite agree with whatever
the tool currently does, which is the failure it exists to catch.

Two assertions per shape, and they fail differently on purpose:

  unanimity  every language that expresses the shape returns the same verdict. This is the
             regression guard. It names both sides of any split.
  property   that shared verdict is the one the shape's behaviour entails. This is the
             correctness guard, and it can fail while unanimity passes - nine languages
             agreeing on a wrong answer is a real state of the world.
"""

import pytest
from l1_analyzer import state_bounds

# --- how each language spells a file and a state key --------------------------------
#
# The state KEY is the enumerator's own vocabulary and differs per language for reasons that
# are purely notational: Python and Rust address instance state through `self`, TS and JS
# through `this`, Ruby with a sigil, Java and C# by bare field name, Go by <Type>.<field>,
# and C has no instance state at all so a file-scope static is the nearest thing. None of
# that is a semantic difference, so it is spelled out here once rather than repeated inside
# every shape, where it would look like a per-language expectation.

_FILENAME = {
    "python": "case.py", "typescript": "case.ts", "javascript": "case.js",
    "java": "Case.java", "csharp": "Case.cs", "ruby": "case.rb",
    "rust": "case.rs", "go": "case.go", "c": "case.c",
}

_KEY = {
    "python": "self.{}", "rust": "self.{}",
    "typescript": "this.{}", "javascript": "this.{}",
    "java": "{}", "csharp": "{}", "c": "{}",
    "ruby": "@{}",
    "go": "S.{}",
}

LANGUAGES = tuple(_FILENAME)


# --- the shapes ---------------------------------------------------------------------

SHAPES = [
    {
        "id": "open-key-read-into-branch",
        "attr": "cache",
        "verdict": "promiscuous",
        # A container that grows one entry per key, read back by a key the caller chooses,
        # and the answer decides a branch. The number of behaviours is the number of keys,
        # which no one can enumerate from inside the class.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.cache = {}\n"
                "    def put(self, k, v):\n"
                "        self.cache[k] = v\n"
                "    def hot(self, k):\n"
                "        if self.cache[k]:\n"
                "            return 1\n"
                "        return 0\n"),
            "typescript": (
                "class S {\n"
                "  cache: Record<string, number> = {};\n"
                "  put(k: string, v: number) { this.cache[k] = v; }\n"
                "  hot(k: string) { if (this.cache[k]) { return 1; } return 0; }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  cache = {};\n"
                "  put(k, v) { this.cache[k] = v; }\n"
                "  hot(k) { if (this.cache[k]) { return 1; } return 0; }\n"
                "}\n"),
            "java": (
                "import java.util.*;\n"
                "class S {\n"
                "  Map<String,Integer> cache = new HashMap<>();\n"
                "  void put(String k, int v) { cache.put(k, v); }\n"
                "  int hot(String k) { if (cache.get(k) > 0) { return 1; } return 0; }\n"
                "}\n"),
            "csharp": (
                "using System.Collections.Generic;\n"
                "class S {\n"
                "  Dictionary<string,int> cache = new Dictionary<string,int>();\n"
                "  void Put(string k, int v) { cache[k] = v; }\n"
                "  int Hot(string k) { if (cache[k] > 0) { return 1; } return 0; }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @cache = {}; end\n"
                "  def put(k, v); @cache[k] = v; end\n"
                "  def hot(k)\n"
                "    return 1 if @cache[k]\n"
                "    0\n"
                "  end\n"
                "end\n"),
            "rust": (
                "use std::collections::HashMap;\n"
                "struct S { cache: HashMap<String, i32> }\n"
                "impl S {\n"
                "  fn put(&mut self, k: String, v: i32) { self.cache.insert(k, v); }\n"
                "  fn hot(&self, k: &str) -> i32 { if self.cache[k] > 0 { return 1; } 0 }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { cache map[string]int }\n"
                "func (s *S) Put(k string, v int) { s.cache[k] = v }\n"
                "func (s *S) Hot(k string) int {\n"
                "  if s.cache[k] > 0 {\n"
                "    return 1\n"
                "  }\n"
                "  return 0\n"
                "}\n"),
            "c": (
                "static int cache[256];\n"
                "void put(int k, int v) { cache[k] = v; }\n"
                "int hot(int k) { if (cache[k] > 0) { return 1; } return 0; }\n"),
        },
    },
    {
        "id": "open-key-read-returned",
        "attr": "cache",
        "verdict": "promiscuous",
        # The same container and the same open key, with the read RETURNED instead of tested.
        # Nothing about the partition changed: the selection by an unbounded key is the
        # decision, and moving the `if` into the caller does not remove it. This is the shape
        # that was neutral in Python and promiscuous in C on 2026-08-15, which is why it is
        # here as a shape in its own right rather than a variant of the one above.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.cache = {}\n"
                "    def put(self, k, v):\n"
                "        self.cache[k] = v\n"
                "    def get(self, k):\n"
                "        return self.cache[k]\n"),
            "typescript": (
                "class S {\n"
                "  cache: Record<string, number> = {};\n"
                "  put(k: string, v: number) { this.cache[k] = v; }\n"
                "  get(k: string) { return this.cache[k]; }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  cache = {};\n"
                "  put(k, v) { this.cache[k] = v; }\n"
                "  get(k) { return this.cache[k]; }\n"
                "}\n"),
            "java": (
                "import java.util.*;\n"
                "class S {\n"
                "  Map<String,Integer> cache = new HashMap<>();\n"
                "  void put(String k, int v) { cache.put(k, v); }\n"
                "  Integer get(String k) { return cache.get(k); }\n"
                "}\n"),
            "csharp": (
                "using System.Collections.Generic;\n"
                "class S {\n"
                "  Dictionary<string,int> cache = new Dictionary<string,int>();\n"
                "  void Put(string k, int v) { cache[k] = v; }\n"
                "  int Get(string k) { return cache[k]; }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @cache = {}; end\n"
                "  def put(k, v); @cache[k] = v; end\n"
                "  def get(k); @cache[k]; end\n"
                "end\n"),
            "rust": (
                "use std::collections::HashMap;\n"
                "struct S { cache: HashMap<String, i32> }\n"
                "impl S {\n"
                "  fn put(&mut self, k: String, v: i32) { self.cache.insert(k, v); }\n"
                "  fn get(&self, k: &str) -> i32 { self.cache[k] }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { cache map[string]int }\n"
                "func (s *S) Put(k string, v int) { s.cache[k] = v }\n"
                "func (s *S) Get(k string) int { return s.cache[k] }\n"),
            "c": (
                "static int cache[256];\n"
                "void put(int k, int v) { cache[k] = v; }\n"
                "int get(int k) { return cache[k]; }\n"),
        },
    },
    {
        "id": "literal-key-only",
        "attr": "cache",
        "verdict": "neutral",
        # The same container touched only at fixed positions. Each distinct literal is one
        # discriminator, so a handful of them leave a handful of classes and a test suite can
        # cover every one. This is the control for the two shapes above: it holds the
        # container constant and varies only the key, so a suite that passed it while failing
        # them is measuring the key and not the container.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.cache = {}\n"
                "    def put(self, v):\n"
                "        self.cache['seven'] = v\n"
                "    def get(self):\n"
                "        return self.cache['seven']\n"),
            "typescript": (
                "class S {\n"
                "  cache: Record<string, number> = {};\n"
                "  put(v: number) { this.cache['seven'] = v; }\n"
                "  get() { return this.cache['seven']; }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  cache = {};\n"
                "  put(v) { this.cache['seven'] = v; }\n"
                "  get() { return this.cache['seven']; }\n"
                "}\n"),
            "java": (
                "import java.util.*;\n"
                "class S {\n"
                "  Map<String,Integer> cache = new HashMap<>();\n"
                "  void put(int v) { cache.put(\"seven\", v); }\n"
                "  Integer get() { return cache.get(\"seven\"); }\n"
                "}\n"),
            "csharp": (
                "using System.Collections.Generic;\n"
                "class S {\n"
                "  Dictionary<string,int> cache = new Dictionary<string,int>();\n"
                "  void Put(int v) { cache[\"seven\"] = v; }\n"
                "  int Get() { return cache[\"seven\"]; }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @cache = {}; end\n"
                "  def put(v); @cache['seven'] = v; end\n"
                "  def get; @cache['seven']; end\n"
                "end\n"),
            "rust": (
                "use std::collections::HashMap;\n"
                "struct S { cache: HashMap<String, i32> }\n"
                "impl S {\n"
                "  fn put(&mut self, v: i32) { self.cache.insert(\"seven\".to_string(), v); }\n"
                "  fn get(&self) -> i32 { self.cache[\"seven\"] }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { cache map[string]int }\n"
                "func (s *S) Put(v int) { s.cache[\"seven\"] = v }\n"
                "func (s *S) Get() int { return s.cache[\"seven\"] }\n"),
            "c": (
                "static int cache[256];\n"
                "void put(int v) { cache[7] = v; }\n"
                "int get(void) { return cache[7]; }\n"),
        },
    },
    {
        "id": "write-only-accumulator",
        "attr": "total",
        "verdict": "neutral",
        # A running total that nothing ever reads. Its value cannot change any observable
        # outcome, so it partitions nothing and no test needs to reach it. The interesting
        # half of this shape is that it must stay neutral however large its domain is:
        # cardinality is not the question the indicator asks.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.total = 0\n"
                "    def record(self, amount):\n"
                "        self.total += amount\n"),
            "typescript": (
                "class S {\n"
                "  total = 0;\n"
                "  record(amount: number) { this.total += amount; }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  total = 0;\n"
                "  record(amount) { this.total += amount; }\n"
                "}\n"),
            "java": (
                "class S {\n"
                "  int total = 0;\n"
                "  void record(int amount) { total += amount; }\n"
                "}\n"),
            "csharp": (
                "class S {\n"
                "  int total = 0;\n"
                "  void Record(int amount) { total += amount; }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @total = 0; end\n"
                "  def record(amount); @total += amount; end\n"
                "end\n"),
            "rust": (
                "struct S { total: i32 }\n"
                "impl S {\n"
                "  fn record(&mut self, amount: i32) { self.total += amount; }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { total int }\n"
                "func (s *S) Record(amount int) { s.total += amount }\n"),
            "c": (
                "static int total = 0;\n"
                "void record(int amount) { total += amount; }\n"),
        },
    },
    {
        "id": "presence-test-branches-converge",
        "attr": "hits",
        "verdict": "neutral",
        # A per-key tally. The presence test has two arms and they fall through to the same
        # statement, so no test can tell the arms apart and none needs to; nothing reads the
        # tally back out, so the count reaches no decision either. The container is keyed by
        # an open key throughout, which is what makes this shape the hard case: the key is
        # unbounded and the shape is still neutral, because every reference to it is a WRITE.
        #
        # C is absent. It has no membership test and no growing container: a fixed array
        # answers for every index whether or not anything was stored there, so the presence
        # question this shape turns on cannot be asked. That is a real absence in the
        # language, not a gap in the fixture.
        "src": {
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
            "c": None,
        },
    },
    {
        "id": "bounded-scalar-vs-constants",
        "attr": "count",
        "verdict": "neutral",
        # A counter that only ever meets comparisons against literals. Two cuts leave three
        # intervals and boundary values reach all of them, so the partition is finite however
        # wide the integer type is. This is the shape the whole indicator turns on: it says
        # the meter counts partitions and not values.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.count = 0\n"
                "    def incr(self):\n"
                "        if self.count < 3:\n"
                "            self.count += 1\n"
                "    def reset(self):\n"
                "        self.count = 0\n"
                "    def allowed(self):\n"
                "        return self.count < 3\n"),
            "typescript": (
                "class S {\n"
                "  count = 0;\n"
                "  incr() { if (this.count < 3) { this.count += 1; } }\n"
                "  reset() { this.count = 0; }\n"
                "  allowed() { return this.count < 3; }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  count = 0;\n"
                "  incr() { if (this.count < 3) { this.count += 1; } }\n"
                "  reset() { this.count = 0; }\n"
                "  allowed() { return this.count < 3; }\n"
                "}\n"),
            "java": (
                "class S {\n"
                "  int count = 0;\n"
                "  void incr() { if (count < 3) { count += 1; } }\n"
                "  void reset() { count = 0; }\n"
                "  boolean allowed() { return count < 3; }\n"
                "}\n"),
            "csharp": (
                "class S {\n"
                "  int count = 0;\n"
                "  void Incr() { if (count < 3) { count += 1; } }\n"
                "  void Reset() { count = 0; }\n"
                "  bool Allowed() { return count < 3; }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @count = 0; end\n"
                "  def incr; @count += 1 if @count < 3; end\n"
                "  def reset; @count = 0; end\n"
                "  def allowed; @count < 3; end\n"
                "end\n"),
            "rust": (
                "struct S { count: i32 }\n"
                "impl S {\n"
                "  fn incr(&mut self) { if self.count < 3 { self.count += 1; } }\n"
                "  fn reset(&mut self) { self.count = 0; }\n"
                "  fn allowed(&self) -> bool { self.count < 3 }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { count int }\n"
                "func (s *S) Incr() {\n"
                "  if s.count < 3 {\n"
                "    s.count += 1\n"
                "  }\n"
                "}\n"
                "func (s *S) Reset() { s.count = 0 }\n"
                "func (s *S) Allowed() bool { return s.count < 3 }\n"),
            "c": (
                "static int count = 0;\n"
                "void incr(void) { if (count < 3) { count += 1; } }\n"
                "void reset(void) { count = 0; }\n"
                "int allowed(void) { return count < 3; }\n"),
        },
    },
    {
        "id": "state-handed-to-an-unreadable-call",
        "attr": "config",
        "verdict": "unresolved",
        # The value is passed to a function this analyser cannot read. What that function does
        # with it may partition it finitely or not at all, and the honest answer is that the
        # meter does not know. UNRESOLVED is the fail-closed verdict and it is disclosed
        # rather than rounded to either of the other two, so this shape is also the check that
        # the third verdict is reachable in every language.
        "src": {
            "python": (
                "class S:\n"
                "    def __init__(self):\n"
                "        self.config = 0\n"
                "    def set(self, v):\n"
                "        self.config = v\n"
                "    def route(self, r):\n"
                "        return dispatch(self.config, r)\n"),
            "typescript": (
                "class S {\n"
                "  config = 0;\n"
                "  set(v: number) { this.config = v; }\n"
                "  route(r: string) { return dispatch(this.config, r); }\n"
                "}\n"),
            "javascript": (
                "class S {\n"
                "  config = 0;\n"
                "  set(v) { this.config = v; }\n"
                "  route(r) { return dispatch(this.config, r); }\n"
                "}\n"),
            "java": (
                "class S {\n"
                "  Config config = new Config();\n"
                "  void set(Config c) { config = c; }\n"
                "  String route(String r) { return dispatch(config, r); }\n"
                "}\n"),
            "csharp": (
                "class S {\n"
                "  Config config = new Config();\n"
                "  void Set(Config c) { config = c; }\n"
                "  string Route(string r) { return Dispatch(config, r); }\n"
                "}\n"),
            "ruby": (
                "class S\n"
                "  def initialize; @config = 0; end\n"
                "  def set(v); @config = v; end\n"
                "  def route(r); dispatch(@config, r); end\n"
                "end\n"),
            "rust": (
                "struct S { config: Config }\n"
                "impl S {\n"
                "  fn set(&mut self, c: Config) { self.config = c; }\n"
                "  fn route(&self, r: &str) -> String { dispatch(&self.config, r) }\n"
                "}\n"),
            "go": (
                "package main\n"
                "type S struct { config int }\n"
                "func (s *S) Set(v int) { s.config = v }\n"
                "func (s *S) Route(r int) int { return dispatch(s.config, r) }\n"),
            "c": (
                "static int config = 0;\n"
                "void set(int v) { config = v; }\n"
                "int route(int r) { return dispatch(config, r); }\n"),
        },
    },
]


# --- measurement ---------------------------------------------------------------------


def _expressed_in(shape: dict) -> tuple[str, ...]:
    """The languages that can express this shape. A None source is a declared absence,
    argued in the shape's prose; a missing key is a fixture the author forgot, and the
    completeness test below refuses it."""
    return tuple(lang for lang in LANGUAGES if shape["src"].get(lang) is not None)


def _verdict_of(tmp_path, lang: str, shape: dict) -> str:
    """Classify one shape in one language. `absent` is not a verdict - it means the
    enumerator never surfaced the state - and it is reported as itself rather than folded
    into neutral, because a state nobody read and a state read and cleared are different
    facts and only one of them is a measurement."""
    work = tmp_path / lang
    work.mkdir()
    (work / _FILENAME[lang]).write_text(shape["src"][lang])
    result = state_bounds.classify(work, lang)
    key = _KEY[lang].format(shape["attr"])
    return next((f["verdict"] for f in result["findings"] if f["state"] == key), "absent")


def _verdicts(tmp_path, shape: dict) -> dict[str, str]:
    return {lang: _verdict_of(tmp_path, lang, shape) for lang in _expressed_in(shape)}


def _by_verdict(verdicts: dict[str, str]) -> str:
    """Every distinct verdict and the languages that returned it, so a failure names both
    sides of a split instead of one expected value and one actual."""
    groups: dict[str, list[str]] = {}
    for lang, verdict in sorted(verdicts.items()):
        groups.setdefault(verdict, []).append(lang)
    return "; ".join(f"{v}: {', '.join(langs)}" for v, langs in sorted(groups.items()))


_IDS = [s["id"] for s in SHAPES]


# --- the two assertions ---------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES, ids=_IDS)
def test_every_language_agrees_on_the_shape(tmp_path, shape):
    """The regression guard. One runtime behaviour, one verdict, whatever the surface
    language. A split here is a defect in at least one language's reading and the message
    names every language on both sides so the argument can start from the evidence."""
    verdicts = _verdicts(tmp_path, shape)
    assert len(set(verdicts.values())) == 1, (
        f"{shape['id']}: languages disagree about one runtime shape -> {_by_verdict(verdicts)}")


@pytest.mark.parametrize("shape", SHAPES, ids=_IDS)
def test_the_agreed_verdict_is_the_one_the_behaviour_entails(tmp_path, shape):
    """The correctness guard. Unanimity is not proof: nine languages can agree on a wrong
    answer, and only this assertion can say so. The expected value is declared once per
    shape, never per language."""
    verdicts = _verdicts(tmp_path, shape)
    wrong = {lang: v for lang, v in verdicts.items() if v != shape["verdict"]}
    assert not wrong, (
        f"{shape['id']}: behaviour entails {shape['verdict']}, got {_by_verdict(wrong)}")


def test_every_shape_states_a_source_or_a_declared_absence_for_all_nine():
    """A fixture missing by oversight is invisible: the shape just measures fewer languages
    and the suite stays green. So every shape must carry all nine keys, and a language that
    cannot express the shape must say None on purpose."""
    for shape in SHAPES:
        assert set(shape["src"]) == set(LANGUAGES), (
            f"{shape['id']}: covers {sorted(shape['src'])}, needs all of {sorted(LANGUAGES)}")
