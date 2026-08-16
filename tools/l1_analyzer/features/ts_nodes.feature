Feature: ts_nodes — the shared parse-tree accessors every analysis module reads through
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: refs collects every matching node beneath a scope in source order
    Given a scope node and a test that says whether one node is wanted
    When refs walks the whole subtree, testing each node before its children
    Then it returns every node the test accepted, in the order they appear in the source
    And the scope node itself is tested like any other
    But nothing is excluded, so a match inside a nested declaration is collected too

  Scenario: local_refs collects matching nodes but stops at a nested declaration
    Given a scope node, a test that says whether one node is wanted, and the node types that end the search
    When local_refs walks the subtree and turns back at any node of a stopping type
    Then it returns only the matches that belong to this scope
    And the scope node is searched even when its own type is one of the stopping types, so the caller can pass the record it is analysing
    But a match inside an inner record is left for that record's own pass, which is what stops it being counted twice

  Scenario: text reads the source text a node covers
    Given a node that may be absent
    When text decodes the bytes the node spans
    Then it returns that text, ignoring any byte the decoder cannot read
    But an absent node, or a node carrying no bytes, yields the empty string rather than an error

  Scenario: field follows one named child link out of a node
    Given a node that may be absent and the name of a field that may be absent
    When field asks the node for the child stored under that name
    Then it returns that child, or nothing when the node has no such field
    But an absent node, or an empty field name, yields nothing without asking

  Scenario: same decides whether two node handles point at the same node
    Given two node handles that may be absent
    When same compares the identifiers the parser assigns
    Then it answers yes only when both are present and carry the same identifier
    But it never compares the handles themselves, because a fresh handle comes back from every field lookup and comparing handles gets this wrong

  Scenario: first_named returns a node's first meaningful child
    Given a node that may be absent
    When first_named scans the children in order for the first named one
    Then it returns that child, skipping punctuation and other anonymous children
    But an absent node, or one with no named child, yields nothing

  Scenario: arg_value unwraps a C# argument to the expression inside it
    Given a node that may or may not be an argument wrapper
    When arg_value checks the node's type
    Then an argument wrapper yields its first named child, the expression actually passed
    But any other node, and an absent node, comes back exactly as it went in
