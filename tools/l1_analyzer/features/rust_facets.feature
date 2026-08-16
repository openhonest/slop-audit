Feature: rust_facets — turning a Rust coverage run into named, provable decision gaps
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today _branches names five constructs, so the early return a question-mark
  # operator carries and the diverging arm of a let-else binding are enumerated nowhere, and an
  # uncovered line belonging to one of them matches no branch and yields no gap to prove.
  @undecidable @not-implemented
  Scenario: undecidable a Rust decision the branch walk names no rule for
    Given a function whose decisions include the early return of a question-mark operator or the diverging arm of a let-else binding
    When module_functions walks the body and _branches records only conditionals, else arms, match arms, while loops and for loops
    Then it is recorded as unread rather than left out of the branch list, where uncovered_gaps returns no gap for it, so an empty gap list means read-and-proved and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _cfg_inner reads the predicate out of a conditional-compilation attribute
    Given the text of one attribute
    When _cfg_inner finds the conditional marker and counts brackets until they balance
    Then it returns the predicate inside, however deeply the predicate nests further brackets of its own
    And an attribute that is not a conditional-compilation one yields nothing
    But the marker is matched anywhere in the text, so an attribute whose name merely ends in the same letters is read as though it were one

  Scenario: _enclosing_cfg gathers every condition that gates a node
    Given the source text and one node in the parse tree
    When _enclosing_cfg climbs from that node through every enclosing item, reading the attributes that precede each one
    Then it returns the single condition when only one gates the node, and otherwise all of them joined as a requirement that every one must hold
    And a node nothing gates yields no condition at all
    But this is what lets a branch that the host platform never compiles be spotted before any effort is spent proving it

  Scenario: _text reads the source text a node spans
    Given the source bytes and a node, or nothing
    When _text slices the bytes the node covers and decodes them
    Then it returns that text
    And bytes that will not decode are dropped rather than raising, so a file with stray encoding never stops the walk
    But being handed nothing yields nothing, which is how every caller here distinguishes an absent part of the tree from an empty one

  Scenario: _is_test_scoped decides whether a function is test code rather than a subject
    Given the source bytes and a function node
    When _is_test_scoped climbs from the function through its enclosing items, reading the attributes before each
    Then it reports test code when any of those attributes marks a test
    But the match is on the bare letters of the attribute text, so an attribute that merely contains those letters somewhere, in a feature name or a documentation string, also counts as a test marker and quietly removes a real function from the subjects

  Scenario: _first_executable_line finds the line a branch's execution is attributed to
    Given the body of one branch, or nothing
    When _first_executable_line looks for the first real statement in it
    Then it returns the one-based line of that statement, skipping comments, because that is the line the coverage tool attributes the branch's execution to
    And a body that is not a block is reported at its own first line
    But an empty body, or no body at all, yields nothing, and a branch with no body line can never be matched against a coverage gap

  Scenario: _branches enumerates the decision branches inside one function body
    Given the source bytes and a function body
    When _branches walks the body and records every conditional, else arm, match arm, while loop and for loop
    Then it returns each branch with its kind, the line of the construct, the line its body starts executing on, and the condition gating it
    And a conditional with an alternative yields two branches, one for the taken side and one for the untaken, since a run must reach each separately
    But a function nested inside this one is skipped, because its branches belong to it rather than to the enclosing function

  Scenario: _parameters reads a function's parameter names and declared types
    Given the source bytes and a parameter list, or nothing
    When _parameters reads each parameter in the list
    Then it returns each parameter's name together with its declared type
    And a parameter whose pattern cannot be read is named with a placeholder rather than dropped
    But a parameter with no readable type carries no type at all, which is what later disqualifies its function from being proof-ready

  # The docstring says free functions. The walk records every function in the file, so a
  # method declared inside an implementation block, and a function nested inside another
  # function body, are both collected too.
  Scenario: module_functions lists the module's non-test functions with everything a proof needs
    Given the source text of one module
    When module_functions parses it and walks the tree for function declarations that are not test-scoped
    Then it returns each function's name, its full source text, its parameters, its return type and its decision branches
    And a function whose name or body cannot be read is skipped rather than half-reported
    But it needs the Rust grammar rather than a Rust toolchain, so it reads a module on a machine with no Rust installed at all, and every function it finds is collected, methods and nested functions included

  Scenario: uncovered_gaps matches enumerated branches against the lines coverage never reached
    Given the module's functions and the set of lines a coverage run marked never-executed
    When uncovered_gaps checks each branch's body-entry line against that set
    Then it returns one gap per uncovered branch, carrying the function name, the branch kind, its line, its gating condition, the function's source, its parameters and its return type
    And a function with no declared return type, or with any untyped parameter, is skipped entirely, because a test that calls it cannot be built without the types
    But it is handed the uncovered line set rather than measuring it, and an empty set yields no gaps whether the branches were all covered or the coverage toolchain was never there, so it relies on its callers refusing to call it until the coverage harness has said the measurement was taken

