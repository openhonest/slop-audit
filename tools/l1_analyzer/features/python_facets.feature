Feature: python_facets — locating the Python decision branches no test ever reached
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _text reads the module source a node covers
    Given the module source as bytes and a node that may be absent
    When _text slices the source between the node's start and end
    Then it returns that text, ignoring any byte the decoder cannot read
    But an absent node yields nothing at all, which is how the callers tell "no such part" from an empty name

  Scenario: _first_block finds the body a branch construct guards
    Given a branch construct such as an if, an else, a loop or a case
    When _first_block asks for the consequence field, then the body field, then falls back to the first block among the named children
    Then it returns the block whose first statement is the line coverage attributes the branch to
    But a construct with no block at all yields nothing, and the branch is then recorded with no body line

  # The docstring says leading comments and bare docstrings are skipped. The body skips
  # comments only: a docstring is an ordinary expression statement and is taken as the
  # first executable line.
  Scenario: _first_executable_line names the line coverage will attribute the branch to
    Given the body block of one branch, which may be absent
    When _first_executable_line takes the first statement that is not a comment
    Then it returns that statement's 1-based line number
    And a block holding nothing but comments falls back to the line of the block itself
    But an absent block yields nothing, so the branch is never cross-referenced against coverage

  Scenario: _branches enumerates the decisions inside one function body
    Given the body of a function
    When _branches walks the body recording each if, elif, else, for, while and match case with its own line and its body-entry line
    Then it returns every decision that belongs to this function, in source order
    And a decision nested inside another decision is recorded too, because the walk continues through the children
    But it turns back at a nested function definition, whose branches belong to that function's own entry

  Scenario: _parameters lists the arguments a generated test would have to supply
    Given a function's parameter list, which may be absent
    When _parameters reads each parameter for its name and any annotation
    Then it returns the plain, annotated and defaulted parameters, carrying the annotation only where one is written
    And a parameter whose name cannot be read is recorded under a placeholder name rather than dropped
    But a starred or double-starred parameter is not listed at all, so a test built from this list passes no variable arguments

  # The docstring says "module-level or method". The body walks the whole tree, so a
  # function defined inside another function is collected as well.
  Scenario: module_functions parses a module into the functions a proof could target
    Given the text of one Python module
    When module_functions parses it and records each function's name, source, parameters and decision branches
    Then it returns every function it found, marking one as a method when its first parameter is self or cls
    And a nested function appears as its own entry, holding the branches its enclosing function excluded
    But a function whose name starts with "test" is left out, because a test is a subject to skip, not a gap to close

  Scenario: uncovered_gaps crosses the branches against the lines coverage never executed
    Given the module's functions with their branches, and the set of line numbers coverage recorded as never executed
    When uncovered_gaps checks each branch's body-entry line against that set
    Then it returns one gap per uncovered branch, carrying the function name, the branch kind, the branch's own line, and everything a generated test needs to call the function
    But a branch with no body-entry line is skipped entirely, and an empty uncovered set yields no gaps
