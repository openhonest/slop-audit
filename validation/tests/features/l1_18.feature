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

  # WITHDRAWN 2026-08-15. L1.18 has no I/O boundary exclusion. The canon described
  # one, but what was implemented was a `honest: boundary` comment a function had to
  # carry, which fired on no repository that had not adopted this project's private
  # marker. Recognising a route handler, a database adapter or a CLI entry point by
  # analysis needs a per-framework enumeration and was measured to be undoable
  # credibly, so the claim was dropped and the marker deleted with it: an exclusion a
  # subject opts into is a lever a subject controls. This scenario now asserts the
  # withdrawal, which is what stops the marker returning by the door it left by.
  # See tools/l1_analyzer/docs/amendment-2026-08-15-l1-18-corrected-ratio.md.
  @multi-lang
  Scenario Outline: IO boundary functions are NOT excluded from the L1.18 count
    Given a <lang> source file containing an IO boundary function that also touches global state
    When I run L1.18 analysis on it
    Then the IO boundary function is counted like any other function

    Examples:
      | lang   |
      | python |
      | rust   |
      | c      |

  Scenario: Analyzer is self-consistent on its own source (bootstrap)
    Given the L1.18 analyzer source itself
    When I run L1.18 analysis in amended mode on it
    Then the mutable state ratio is 0.0
    # The stateful CFG builder in path_cover.py was refactored to pure functions
    # that thread the accumulator explicitly, so the analyzer now passes its own
    # L1.18 (0/N). See docs/amendment-2026-08-02-self-clean-path-cover.md.

  # More scenarios would cover: file discovery, decision coverage interaction (L1.19),
  # different syntaxes for methods, closures, etc. See full suite in paper replication package.
