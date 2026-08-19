Feature: vacuity_size — is this quantity one an empty input can drive to zero?
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Split out of vacuity when that file crossed the god-file threshold this package gates on.
  It is one question asked several ways, and it is the question the whole check turns on: a
  constant published behind a guard is a finding only when the guard's quantity can
  actually reach zero. The boundary between a size and a flag is where this check goes
  wrong in both directions, too loose convicting every indicator that calls band() and too
  tight letting a real fabrication past, so each rule carries the measurement that put it
  there.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A local bound from a call in another module is the standing one. This module reads one
  # function at a time, so a quantity that arrives from a call it cannot follow is judged by
  # what the body does with it, which is evidence and not proof: a body that indexes and
  # measures a value it received could still have received something no empty input can
  # shrink. Following the call would need the whole package's call graph, which this check
  # does not build.
  @undecidable @not-implemented
  Scenario: undecidable whether a value from an unfollowable call can reach zero
    Given a local bound from a call this module cannot follow
    When the rules judge it by what the body does with it
    Then the answer is evidence about the body rather than proof about the value
    And the call graph that would settle it is not built, so nothing here can say which
    But judging it by its right-hand side alone was measured to be worse: it convicted every constant below every guard whose quantity arrived that way

  Scenario: _assignments gathers every expression bound to one name inside a scope
    Given a function body and the name to look for
    When _assignments walks the whole body
    Then it returns the right-hand side of each plain, augmented and annotated assignment to that name
    But an augmented or annotated assignment with no value on the right is skipped, since there is nothing to read

  Scenario: _bound_names lists the names an assignment binds
    Given an assignment statement
    When _bound_names walks its targets
    Then it returns every name appearing in them, so a tuple unpacking yields all of its names
    But it does not tell a bare name from a subscript target, so the caller has to ask that separately

  Scenario: _is_size decides whether an empty input can drive a quantity to zero
    Given an expression, the function it sits in, and how deep the recursion already is
    When _is_size reads how the quantity is built rather than what it is called
    Then a length, a sum, a comprehension, a container literal, a container constructor and a numeric literal all count as sizes
    And a name is a size when any one of its local bindings is, because a counter starts at zero and is then added to, and a parameter is a size only when the body indexes, iterates over or does arithmetic with it
    But an attribute read with no local definition is not, which is what keeps a comparison of a process exit status against zero out of the finding list, and the recursion gives up past three levels

  Scenario: _is_the_iterable decides whether a loop walks this name
    Given a name and the expression a loop iterates
    When _is_the_iterable reads that expression
    Then the name counts when it is the iterable itself, or the argument of a wrapper that walks what it was handed
    But it does not count when it is merely an argument buried in an opaque call, which walks whatever that call returns and not the argument

  Scenario: _parameters lists the names a function declares as arguments
    Given a scope, which may or may not be a function
    When _parameters reads the argument list
    Then it returns every positional, keyword and star argument name
    And a scope with no argument list at all returns nothing rather than failing

  Scenario: _read_as_a_number decides whether a subscript's result is measured
    Given a subscript of a name, and the function around it
    When _read_as_a_number looks at what the body does with that subscript
    Then a result compared against a number, used in arithmetic, or measured is a tally read
    But a result only tested for truth is a flag read, which no empty input can drive to zero, and the key cannot tell the two apart because both are spelled the same

  Scenario: _referenced_names lists every name mentioned in a node
    Given any node
    When _referenced_names walks it
    Then it returns each name it finds, with no regard for whether the name is read or written

  Scenario: _used_as_quantity looks for the evidence that a parameter is a tally
    Given a parameter name and the function body
    When _used_as_quantity searches for the name in arithmetic, in a subscript, as the thing a loop walks, or as the argument of a sizing or container call
    Then any one of those is enough to call it a quantity
    But a name the body only ever tests for truth is a flag, and reading a flag as a tally once put a finding on every check that asks whether higher is better
