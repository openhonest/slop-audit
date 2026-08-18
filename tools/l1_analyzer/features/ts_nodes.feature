Feature: ts_nodes — the shared parse-tree accessors every analysis module reads through
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today text decodes with errors ignored, so a byte the decoder cannot read
  # is dropped without a trace and the caller receives a shortened name, or the empty string,
  # with nothing to say which of the two it holds.
  @undecidable @not-implemented
  Scenario: undecidable a node whose source bytes are not valid utf-8
    Given a node spanning bytes the utf-8 decoder cannot read, such as an identifier in a file written in another encoding
    When text decodes the span with the undecodable bytes ignored
    Then it is recorded as unread rather than returned as the shortened or empty string every caller reads as the node's whole text, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

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

  Scenario: sub_named lists the named parts of an indexing expression
    Given a subscript node
    When sub_named keeps only its named children
    Then it returns them in source order, which is what the positional grammars index into
    But the bracket tokens are dropped, since they carry no part of the collection or the key

  Scenario: sub_collection finds the collection being indexed
    Given a subscript node and the language spec
    When sub_collection takes the first named child in a positional grammar, or the named field elsewhere
    Then it returns the collection
    But a positional subscript with no named children yields nothing, so the caller gets an absence rather than a wrong node

  Scenario: sub_key finds the key or index of an indexing expression
    Given a subscript node and the language spec
    When sub_key takes the second named child in a positional grammar, unwraps a bracketed argument list, or reads the named field
    Then it returns the key, which is what decides whether the read is bounded
    But a positional subscript with fewer than two named children yields nothing

  Scenario: written_in_place finds the operand a node mutates where it stands
    Given a node and the language spec
    When written_in_place checks the node's type against the language's in-place writers, then checks that the operator it carries is one of the ones declared for that type
    Then it returns the operand written, which is the declared target field where the grammar names one and the first named child where it does not
    And the node still produces a value, so the operand is returned rather than a verdict, and the caller decides what that value goes on to do
    But a node type the language did not declare, and a declared type carrying an operator that writes nothing, both yield nothing, so a shift is never read as an append

  Scenario: is_opaque_unary decides whether a unary operator lets a value pass through
    Given a node and the language spec
    When is_opaque_unary checks that the node is a unary form and reads the operator it carries
    Then it is true for an operator the language declares as consuming, such as a channel receive, which takes an element rather than passing the container on
    But every other unary operator is false, so negation and arithmetic stay transparent and the whole node type does not have to be dropped from the wrapper list

  Scenario: bare_condition finds the condition of a branch that names no condition field
    Given a branch node and the language spec
    When bare_condition takes the first named child that is not one of the types the spec excludes for that node
    Then it returns the condition, which is how a loop that holds its test positionally is read at all
    But a branch with nothing left after the exclusions yields nothing, which is what an endless loop and a loop over a range both come to

  Scenario: mutable_alias_value finds the value a node hands out under another name
    Given a node and the language spec
    When mutable_alias_value checks the node against the language's alias forms and then looks for the child that marks the alias mutable
    Then it returns the value borrowed, which is a write route that none of this state's own references contain
    But an alias with no mutability marker yields nothing, so a shared borrow stays the transparent wrapper it has always been

  Scenario: hidden_names collects the names inside a region the grammar leaves unparsed
    Given a scope node and the language spec
    When hidden_names walks the scope for the language's unparsed region types and collects the text of every leaf inside them
    Then it returns those names, because a reference the parser never built cannot be found by a walk and would otherwise read as an absence
    And matching a bare name over-refuses rather than under-refuses, which is the direction to be wrong in when the alternative is clearing a state on a reading that skipped part of it
    But a language whose grammar parses everything declares no such region and gets the empty set without a walk

  Scenario: is_lvalue decides whether a node is the target of an assignment
    Given a node and the language spec
    When is_lvalue steps out through an optional target wrapper and compares the node against the assignment's target
    Then it is true when the node is what the assignment writes to
    And the wrapper step is what lets a grammar that puts targets in a list still be read
