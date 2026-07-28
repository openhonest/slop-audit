Feature: L1.18 Mutable state ratio analyzer
  The L1.18 indicator measures the percentage of functions that reference
  mutable state outside their parameter list. It must be language-agnostic
  (Python, Rust, C, etc.) using the same semantic definition, implemented
  via tree-sitter with LANG_CFG dispatch (see L1.18 paper and bound literals amendment).
  The analyzer must correctly exclude bound literals (module-level constants,
  frozen dispatch tables, etc.) per the v1 amendment.
  Scenarios are behavioural and cover the long tail, including adversarial cases.

  Background:
    Given the L1.18 analyzer is available via import or CLI

  @python
  Scenario: Pure function with only parameters scores 0% mutable state
    Given a Python source file with:
      """
      def add(a: int, b: int) -> int:
          return a + b
      """
    When I run L1.18 analysis on it
    Then the mutable state ratio is 0.0
    And no functions are flagged as mutable

  @python
  Scenario: Function reading module-level mutable list is flagged
    Given a Python source file with:
      """
      CACHE = []
      def get(key):
          return key in CACHE
      """
    When I run L1.18 analysis on it
    Then the mutable state ratio is 1.0
    And the function "get" is flagged

  @python
  Scenario: Bound literal (frozenset dispatch table) is NOT counted as mutable (amendment)
    Given a Python source file with:
      """
      DISPATCH = frozenset({"a", "b"})
      def handle(x):
          return x in DISPATCH
      """
    When I run L1.18 analysis in amended mode
    Then the mutable state ratio is 0.0
    And the binding "DISPATCH" is recognized as a bound literal

  @rust
  Scenario: Rust function with &mut self references mutable state
    Given a Rust source file with:
      """
      struct Counter { count: i32 }
      impl Counter {
          fn increment(&mut self) { self.count += 1; }
      }
      """
    When I run L1.18 analysis on it
    Then the mutable state ratio is 1.0
    And the method "increment" is flagged

  @c
  Scenario: C function reading global mutable is flagged
    Given a C source file with:
      """
      int global_state = 0;
      int get_state() { return global_state; }
      """
    When I run L1.18 analysis on it
    Then the mutable state ratio is 1.0

  @multi-lang
  Scenario Outline: IO boundary functions are excluded from L1.18 count
    Given a <lang> source file containing an IO boundary function that also touches global state
    When I run L1.18 analysis on it
    Then the IO boundary function is excluded from the mutable state ratio

    Examples:
      | lang   |
      | python |
      | rust   |
      | c      |

  Scenario: Analyzer is self-consistent on its own source (bootstrap)
    Given the L1.18 analyzer source itself
    When I run L1.18 analysis in amended mode on it
    Then the mutable state ratio is 0.0
    # because all top-level bindings used internally are bound literals or pure

  # More scenarios would cover: file discovery, decision coverage interaction (L1.19),
  # different syntaxes for methods, closures, etc. See full suite in paper replication package.
