Feature: data_tables — what a container has to be for its contents to be data rather than logic
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: is_table says whether this container carries any logic
    Given a node, the container types this grammar spells a table with, and the types it spells a literal with
    When is_table reads it
    Then a container spanning twelve lines or more is a table whatever it holds, which is the arm the rule started as
    And a container whose every element is a literal is data at any size, which is the premise the size test was standing in for
    But a container holding anything else is logic however short, or a copied block could hide behind brackets

  Scenario: declares_a_table says whether this statement only binds a name to a table
    Given a statement node and the two vocabularies
    When declares_a_table reads what the statement binds
    Then a declaration of data is data, because discounting a table's contents leaves a name, an equals sign and an empty pair of brackets, and nine of those in a row match nine anywhere else
    But one that runs something to build its value is a statement like any other

  Scenario: literal_types names the node types one language spells a literal with
    Given a language name
    When literal_types reads the shared grammar vocabulary
    Then both indicators that ask what a table is get the same answer for that language
    But it is subscripted rather than defaulted, since a language whose literals nobody declared would read every table as logic

  Scenario: _builds_a_table recognises a call that wraps one table and nothing else
    Given a call node
    When _builds_a_table reads its arguments
    Then one argument that is itself a table means a data constructor, which is what frozenset of a set is
    But two arguments, or one that is not a table, is a call doing work

  Scenario: _all_data reads a container's elements down to the bottom
    Given a container and the two vocabularies
    When _all_data walks its elements
    Then a literal, a pair of literals, or another container of the same all count, at any depth
    But an element that is none of those makes the whole container logic

  Scenario: _pair_of_data reads one entry of a mapping
    Given a pair node
    When _pair_of_data reads its two halves
    Then a name bound to a name carries no logic, any more than either half does alone
    But a half that is neither a literal nor a table makes the pair logic

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a table built by a comprehension rather than written out
    Given a container whose contents are produced by a comprehension over another table, which is data written as a loop
    When the rule reads the comprehension and finds a construct it has no arm for
    Then the container is read as logic and the reading says so, rather than a guess in either direction going unrecorded
    And the shape of the unmatched construct is offered for collection: its node type and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
