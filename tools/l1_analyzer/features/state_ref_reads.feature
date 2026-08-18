Feature: state_ref_reads — how one reference to a piece of state reads, in nine grammars
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Every predicate here answers false for a construct it has no row for, and a
  # false cannot say whether the language spells the shape some other way or whether nobody has
  # written the row yet. A presence test spelled with a method this table does not carry reads
  # exactly like a language that asks no presence question at all.
  @undecidable @not-implemented
  Scenario: undecidable a reference in a position no row in this module names
    Given a reference whose host construct matches no declared node type, such as a presence test written with a method the spec does not carry
    When every predicate reads its own table, finds no row and answers false
    Then it is recorded as unread rather than answered false as though the language had been asked and had said no, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: named_as_member recognises state reached through a receiver
    Given a node and the attribute name, in a language whose state is reached through a receiver
    When named_as_member checks the node is a member access whose attribute part carries that name
    Then it is true for Python, Rust, JavaScript, TypeScript and Go spellings of the same attribute
    But a member access naming a different attribute is declined, so a neighbouring slot is never read as this one

  Scenario: named_as_identifier recognises a field named bare inside its own scope
    Given a node and the attribute name, in a language that names its fields without a receiver
    When named_as_identifier checks the node is an identifier carrying that name
    Then it is true for the Java, C# and C spelling
    But any other node type is declined, so a method name that happens to match is not read as the field

  Scenario: named_as_ivar recognises Ruby's sigil-carrying instance variable
    Given a node and the attribute name
    When named_as_ivar checks the node is an instance variable whose own text is that name
    Then it is true for the Ruby spelling, sigil included, because the sigil is part of the name the grammar records
    But a local variable of the same letters is a different node type and is declined

  Scenario: names_the_attribute picks the spelling this language uses for its own state
    Given a node, the attribute name and the language spec
    When names_the_attribute reads the spec's two enumeration keys and dispatches to the matching spelling
    Then it answers with the same notion of a reference the enumerator used to find the references in the first place
    And a spec declaring a style nobody wrote raises rather than falling through to one of the three
    But an absent node is false, so a caller that reached the end of a chain needs no guard of its own

  Scenario: receiver_call finds the call whose receiver this reference is
    Given a reference and the language spec
    When receiver_call reads the reference's own parent in a flat-call grammar, or the member access and the call above it elsewhere
    Then it returns the call node in both shapes, so no predicate above has to know which kind of grammar it is reading
    But a reference that is not a receiver returns nothing, which is the ordinary case and not an error

  Scenario: call_receiver finds the receiver of a call
    Given a call node and the language spec
    When call_receiver reads the receiver field directly in a flat-call grammar, or through the member access elsewhere
    Then it returns the receiver, which is the inverse of the walk above and is what a walk arriving at the call first needs
    But a plain function call has no receiver and returns nothing

  Scenario: method_name reads the bare method name of a call on a receiver
    Given a call node and the language spec
    When method_name reads the name field in a flat-call grammar, or the attribute part of the member access elsewhere
    Then it returns the method name alone
    And the receiver text a flat grammar would otherwise fold into it is left out, so a name set can be matched against

  Scenario: result_discarded decides whether a call's answer is thrown away
    Given a call node and the language spec
    When result_discarded checks whether the call sits directly under one of the language's discard forms
    Then it is true for a bare statement, which is what makes a write that also returns the previous value carry nothing
    But Ruby declares no discard form at all, so the question can never be answered there and the caller declines rather than assuming

  Scenario: test_slot_field reads a construct that holds its test in a named condition field
    Given a construct, one of its children and the language spec
    When test_slot_field compares the child against the declared condition field
    Then it is true when the child is that condition
    But a construct whose condition field is absent yields false rather than a match against nothing

  Scenario: test_slot_first reads a construct whose test is its first named child
    Given a construct and one of its children
    When test_slot_first compares the child against the first named child
    Then it is true for an assertion, whose test is everything it has
    But a construct with no named children is declined

  Scenario: test_slot_second reads a construct whose test is its second named child
    Given a construct and one of its children
    When test_slot_second compares the child against the second named child
    Then it is true for Python's ternary, which carries no condition field at all and puts the test between its two arms
    But a construct with fewer than two named children is declined

  Scenario: test_slot_all reads a construct that is nothing but a test
    Given a construct and one of its children
    When test_slot_all answers without looking
    Then it is true for a comprehension guard, where every part of the construct is the test
    But the answer is unconditional, so only a node type declared to hold this slot may be handed to it

  Scenario: test_slot_bare reads a test that no field names
    Given a branch node, one of its children, and the language spec
    When test_slot_bare asks the spec for the branch's positional condition and compares it against the child
    Then it is true when the child is that condition, which is the only way a loop holding its test positionally can be read
    But a branch whose spec leaves nothing after its exclusions has no condition, so an endless loop's body is not a test

  Scenario: test_slot_of says how a construct holds its test
    Given a construct and the language spec
    When test_slot_of reads the extra positions the language declares, then falls to the branch and elif types
    Then it returns the slot rule for a construct the language declared, and the condition field for a plain branch
    But a construct nobody wrote a rule for returns the absent case, which is a value no written rule holds

  Scenario: is_condition_position decides whether a child is the test part of its parent
    Given a construct, one of its children and the language spec
    When is_condition_position finds the slot rule for the construct and applies it
    Then it is true for the condition of an if, a while or an elif, the test of a ternary, an assertion and a comprehension guard
    But a construct with no slot rule is false, and that false is a decline rather than an answer about the child

  Scenario: in_test decides whether a reference sits inside a real test expression
    Given a reference and the language spec
    When in_test walks up from the reference looking for a condition position, carrying the child with it
    Then it is true when the reference is anywhere inside a test, however deeply nested
    And a parenthesis or a negation between the reference and the condition costs nothing, because the walk compares the child it carried and not the reference itself
    But the walk stops at the enclosing function, so a test in the caller does not count as this one

  Scenario: container_of_comparison_in recognises Python's membership operator
    Given a reference and the comparison node above it
    When container_of_comparison_in looks for an in or not-in token and compares the reference against the last named operand
    Then it is true when the reference is the container being asked
    And the negated form is recognised, because the grammar makes not-in a single token and matching only in would miss it
    But the reference on the left of the operator is the key and not the container, and is declined

  Scenario: container_of_binary_in recognises the JavaScript and TypeScript membership operator
    Given a reference and the binary node above it
    When container_of_binary_in checks the operator is in and the reference is the right operand
    Then it is true when the reference is the object being asked
    But any other operator is declined, since a binary node carries every operator the language has

  Scenario: container_of_no_operator declines for the six languages that have no membership operator
    Given a reference and a comparison node, in Java, C#, Ruby, Rust, Go or C
    When container_of_no_operator answers without looking
    Then it is false, and the decline is explicit rather than accidental
    But those six are not left unread: they ask presence with a method or a binding, which the two predicates below answer

  Scenario: is_membership_container decides whether a reference is the container of an operator membership test
    Given a reference and the language spec
    When is_membership_container checks the parent is a comparison node and dispatches on the declared membership style
    Then it is true for the operator form in whichever language spells one
    And a spec declaring a style nobody wrote raises rather than defaulting to no membership at all

  Scenario: is_presence_method_call decides whether a reference is asked for a key by a method
    Given a reference and the language spec
    When is_presence_method_call finds the call the reference receives and checks the method against the declared presence set
    Then it is true for containsKey, ContainsKey, key? and contains_key, which answer about the key and hand no stored value back
    But a keyed read that yields the value is not on the presence set and is declined, which is what keeps a gate apart from an inspection

  Scenario: presence_binding finds the binding a keyed read feeds
    Given a subscript node and the language spec
    When presence_binding steps out through the language's target wrapper, checks the read is on the value side and looks for a declared presence binding
    Then it returns Go's short variable declaration, which is not one of Go's assignment types and which no other reader in the tree recognises
    But the other eight declare no presence binding and get nothing, which is the honest answer for a language that asks presence another way

  Scenario: binding_targets lists the names a binding writes
    Given a binding node and the language spec
    When binding_targets reads the target side and unwraps the language's target wrapper
    Then it returns one node per name bound
    But a binding with no target side returns an empty list rather than failing

  Scenario: is_comma_ok_presence recognises Go's two-name presence test
    Given a reference and the language spec
    When is_comma_ok_presence checks the reference is the collection of a keyed read feeding a presence binding with two targets, the first of them the blank identifier
    Then it is true for the comma-ok form, where the stored value is discarded and only the presence flag is kept
    But a binding that keeps the value under a real name is declined, because then the value has been read out after all

  Scenario: is_presence_test decides whether a reference is asked whether it holds a key
    Given a reference and the language spec
    When is_presence_test tries the operator form, the method form and the binding form in turn
    Then it is true for whichever of the three this language spells, so one question asked three ways answers as one
    But a language that spells none of them declines on all three, and C is the language that does

  Scenario: is_deleted decides whether a node is the target of a key removal statement
    Given a node and the language spec
    When is_deleted checks whether the node sits directly under a declared delete statement
    Then it is true for Python, which is the only one of the nine with a statement form
    But the other eight declare none, because a removal there is a call that hands the removed value back, or a unary operator already declared transparent

  Scenario: is_keyed_read_of decides whether an expression addresses the attribute by key
    Given an expression, the attribute name and the language spec
    When is_keyed_read_of checks the expression is a subscript whose collection names the attribute
    Then it is true for the stored value addressed by key
    But a subscript of something else, and a node that is no subscript at all, are both declined

  Scenario: keyed_value_read finds the node that yields a value stored under a key
    Given a reference and the language spec
    When keyed_value_read checks the subscript and method forms of a keyed read, leaving out the store targets and the presence tests
    Then it returns the reading node, so the caller can ask where that value goes
    And a store target yields nothing, because putting a value in is not taking one out
    But a presence test yields nothing either, since it answers about the key and never about what is stored under it
