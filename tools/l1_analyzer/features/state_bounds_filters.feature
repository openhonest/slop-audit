Feature: state_bounds_filters — attribute-level false-positive filters for the finite-testability classifier
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today this module is in the opposite position from state_bounds: it answers
  # a bare false, and a false cannot say whether the four rules ran and declined or whether three
  # of them were withheld because the verdict arrived unresolved, so the disclosure is missing too.
  @undecidable @not-implemented
  Scenario: undecidable an attribute whose finding arrived unresolved, where three of the four rules may not run
    Given an attribute the classifier could not decide, so the verdict handed to the filters is unresolved and only the write-once rule is allowed to fire
    When is_false_positive runs the two guards and then the one rule that verdict admits
    Then it is recorded as unread rather than answered false as though all four rules had been tried and declined, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _text reads the source text of a node without ever failing on a missing one
    Given a node, or nothing
    When _text decodes the node's own bytes
    Then it returns the text the node covers in the file
    But a missing node and a node with no bytes both return the empty string, so no caller has to guard the call

  Scenario: _attr reduces a state key to the bare attribute name
    Given a state key such as a receiver followed by an attribute
    When _attr takes the part after the last dot
    Then it returns the attribute name alone, which is what every rule below matches on
    But a key with no dot comes back unchanged

  Scenario: _enclosing_class finds the class whose body a reference sits in
    Given a reference node
    When _enclosing_class walks up the tree looking for a class definition or declaration
    Then it returns the nearest one
    But a reference at module level has none, and every rule in this module declines when that happens

  Scenario: _is_condition_position decides whether a child is the test part of its parent
    Given a construct and one of its children
    When _is_condition_position checks the child against the condition slot of that construct
    Then it is true for the condition of an if, a while or an elif, the test of a ternary, and the first part of an assertion
    But under a comprehension guard it is true for any child, because that construct is nothing but a test

  Scenario: _in_test decides whether a reference sits inside a real test expression
    Given a reference node
    When _in_test walks up from the reference looking for a condition position
    Then it is true when the reference is anywhere inside a test, however deeply nested
    But the walk stops at the enclosing function, so a test in the caller does not count as this one

  Scenario: _drives_no_decision recognises the carried value, which appears in no test at all
    Given every reference to one attribute
    When _drives_no_decision checks that none of them sits in a test expression
    Then it is true when the attribute decides nothing, so unbounded data that never reaches a branch does not bound testability
    But an attribute with no references at all also passes, since nothing was found to contradict it

  Scenario: _member_writes collects every assignment to the attribute anywhere in the class
    Given the class body and the attribute name
    When _member_writes walks the whole class for assignments whose target is that attribute
    Then it returns one entry per assignment, through any receiver at all
    And a builder that writes the attribute on a second instance is counted, because a receiver-blind scan over-approximates writes, which is the safe direction

  Scenario: _mutated_in_place recognises a mutation route beyond the single assignment
    Given every reference to one attribute and the attribute name
    When _mutated_in_place looks at what sits immediately above each reference
    Then it is true for a keyed store or delete, for an in-place method call, and for an augmented assignment to the attribute itself
    But it decides on position alone and never reads the attribute name it is handed, so the name is dead weight in this rule

  Scenario: _returned_whole recognises the attribute being handed out entire
    Given every reference to one attribute
    When _returned_whole checks whether any reference is returned directly
    Then it is true when the caller receives the object itself and can then mutate it
    But a slice or a copy is a different node above the reference, so returning one of those does not count

  Scenario: _argument_list_above finds the argument list a reference is an argument of
    Given a reference whose parent may be an argument list or a wrapper around one
    When _argument_list_above reads it
    Then it returns the argument list, through a splat or a keyword argument
    And it returns None when the reference is not an argument at all, which is the ordinary case
    But a fourth wrapper spelling is a missing row in the table rather than a silent escape

  Scenario: _attribute_targets lists every attribute an assignment target binds
    Given an assignment target that is a plain attribute or a destructuring pattern
    When _attribute_targets reads it
    Then a plain target yields itself and a pattern yields one node per element
    But it yields nothing for a target that binds no attribute, so a local name is not a member write

  Scenario: _escapes recognises the attribute reaching somewhere that could act on it
    Given every reference to one attribute
    When _escapes checks whether any reference is invoked, or passed bare into a call
    Then it is true when the attribute is called as a value, since the target is chosen while the program runs
    And it is true for an argument to any callee outside the short list of read-only builtins
    But being handed to one of those builtins is safe, because they read or copy without retaining

  Scenario: _is_write_once recognises the attribute assigned once and never disturbed after
    Given the class body, the attribute name and every reference
    When _is_write_once requires exactly one assignment and no mutation, no whole return and no escape
    Then it is true only when all four hold, which is the one shape allowed to clear a fail-closed finding
    But two assignments end it immediately, whichever receivers they went through

  Scenario: _is_membership_container recognises the attribute standing as the container of a membership test
    Given a reference node
    When _is_membership_container checks that its parent is a comparison carrying a membership token and that the reference is the right-hand side
    Then it is true for the attribute being asked whether it holds a key
    But the negated form is one token in this grammar, not a negation wrapping the positive form, and both are matched

  Scenario: _has_presence_gate decides whether the attribute is ever asked whether it holds a key
    Given every reference to one attribute
    When _has_presence_gate looks for any reference standing as a membership container
    Then it is true when at least one presence test exists, which is the first half of both the cache and the accumulator shapes

  Scenario: _value_reaches_condition recognises a stored value being inspected in a branch
    Given every reference to one attribute
    When _value_reaches_condition looks for a keyed read of the attribute sitting inside a test
    Then it is true when presence or magnitude is the answer the code turns on
    And a keyed position that is the target of a store is skipped, because putting a value in is not reading one out
    But this is the guard that keeps a stored timestamp compared against an interval flagged, so it runs before every rule

  Scenario: _writes_are_plain_stores decides whether every write is one a cache could make
    Given the class body, the attribute name and every reference
    When _writes_are_plain_stores rejects an augmented store through the attribute and any in-place method that is not a cache read
    Then it is true when the writes are only keyed stores, deletes, cache methods, and rebinds to an empty collection
    And an augmented store fails, because inspecting and rewriting a stored value is what a counter does, not what a cache does
    But an attribute with no references and no rebinds passes, having offered nothing to reject

  Scenario: _descendants yields every named node beneath a node
    Given any node
    When _descendants walks its named children and their children in turn
    Then it yields each one, parents before their own children
    But unnamed nodes such as operator and keyword tokens are never yielded

  Scenario: _enclosing_function finds the function or lambda a reference sits in
    Given a reference node
    When _enclosing_function walks up looking for a function definition or a lambda
    Then it returns the nearest one, which scopes the result-invariance check to the accessor
    But a reference at class or module level has none

  Scenario: _is_keyed_read_of recognises the cached value being read out by key
    Given an expression and the attribute name
    When _is_keyed_read_of checks that the expression indexes an attribute of that name
    Then it is true for the attribute read at a key, whatever the receiver
    But the key itself is not examined, so any key at all satisfies this rule

  Scenario: _result_invariant decides whether the presence of a key changes the answer
    Given the attribute name and every reference
    When _result_invariant checks every return in each method that contains a presence test on the attribute
    Then it is true only when each of those returns hands back the keyed value, or hands back nothing
    And a method that returns a different value on a miss is result-variant, so the presence is the answer and the finding stays
    But methods with no presence test are out of scope, so a setter that returns the value it stored is irrelevant

  Scenario: _is_memoization recognises a presence-gated cache written only by plain stores
    Given the class body, the attribute name and every reference
    When _is_memoization requires both a presence gate and plain stores
    Then it is true for the shape the entry point is allowed to clear past the open-key guard
    But it does not check result invariance despite the module header naming that as part of the shape; the entry point checks that separately, before any rule runs

  Scenario: _unwrap_unary peels unary operators off a key
    Given a key node
    When _unwrap_unary steps down through each unary operator to the operand
    Then it returns the value underneath, so a negated literal is still recognised as one compile-time value
    But an operator with no operand under it unwraps to nothing

  Scenario: _is_state_of_this_class recognises a key that is itself state of the class under analysis
    Given a key node
    When _is_state_of_this_class checks that it is an attribute of the instance or the class
    Then it is true for a key the enumerator already reports separately, with its own verdict
    And that is why such a key is excluded below: charging the container for it as well counts one decision twice

  Scenario: _is_open_key recognises a single key the class does not bound
    Given a key node, or nothing
    When _is_open_key rules out a slice, a missing key, a literal and the class's own state
    Then it is true for anything left, which is a key the caller chooses, such as a parameter
    But a slice never reaches this rule, because selecting a contiguous run at a caller's width does not pick one stored value out of unboundedly many

  Scenario: _selects_on_an_open_key decides whether the container answers one way per key
    Given every reference to one attribute
    When _selects_on_an_open_key looks for a keyed read, outside any store position, at an open key
    Then it is true when the caller chooses which stored value comes back, so the classes cannot be enumerated
    And this is what a keyed cache read trips, which is the guard that stopped one shape reading clean in one language and flagged in another
    But a store target does not select, since it puts a value in rather than taking one out

  Scenario: _is_whole_rebind recognises the attribute itself standing as an assignment target
    Given a reference and the assignment above it
    When _is_whole_rebind checks that the reference is the left-hand side
    Then it is true for the attribute being rebound whole, which reads no stored value
    But the construct type is not checked here, because the whitelist that calls this rule already supplied it

  Scenario: _is_presence_gate admits a membership test as a confined role
    Given a reference and the construct above it
    When _is_presence_gate defers entirely to the membership-container rule
    Then it is true for the attribute being asked whether it holds a key, which yields no stored value
    But the construct it is handed is ignored, because every role in the whitelist is called with the same two arguments

  Scenario: _is_confined_subscript admits a keyed position only when it is a store target
    Given a reference and the subscript above it
    When _is_confined_subscript checks that the subscript is the target of an assignment, an augmented assignment, or a delete
    Then it is true for a value being put in or removed
    But a keyed read anywhere else carries the stored value somewhere this rule cannot follow, so it declines

  Scenario: _is_pure_write_call admits an in-place method that returns no stored value
    Given a reference and the member access above it
    When _is_pure_write_call checks that an in-place method is being called on the attribute
    Then it is true for the methods that only write
    But the three methods that also hand the stored value back to the caller are excluded from that list, so they read as well as write and fail here

  Scenario: _is_confined_reference decides whether one reference occupies a role that yields nothing
    Given a reference node
    When _is_confined_reference looks up the rule for the construct above it and applies it
    Then it is true only for the four whitelisted roles, each of which is a write or a presence test
    But a reference under any other construct is not on the list and the rule declines, which is how the whitelist enforces that nothing hands the value out

  Scenario: _is_attr_write_target recognises the left-hand side of a write to the attribute
    Given a node and the attribute name
    When _is_attr_write_target accepts either the attribute itself or the attribute read at a key
    Then it is true for both spellings of a write target
    But the receiver is not checked, so a write through any object with an attribute of that name counts

  Scenario: _stmt_is_attr_assignment decides whether an assignment writes only the attribute
    Given an assignment or augmented assignment and the attribute name
    When _stmt_is_attr_assignment checks the left-hand side
    Then it is true when the target is the attribute or a key inside it
    And the right-hand side is not examined, because the rule asks what the statement writes, not what it computes

  Scenario: _stmt_is_attr_delete decides whether a delete removes only the attribute
    Given a delete statement and the attribute name
    When _stmt_is_attr_delete requires every target to be a write target for that attribute
    Then it is true when the statement touches nothing else
    But a delete with no targets at all passes, having offered nothing to reject

  Scenario: _stmt_is_attr_write_call decides whether a call does nothing but write the attribute
    Given a call statement and the attribute name
    When _stmt_is_attr_write_call requires the receiver to be the attribute and the method to be one that only writes
    Then it is true for an in-place write and nothing else
    But a call on anything other than a member access fails immediately, since there is no receiver to check

  Scenario: _writes_only_the_attribute decides whether a whole statement is observable only as a write to the attribute
    Given a statement and the attribute name
    When _writes_only_the_attribute unwraps a bare expression statement and dispatches on what is inside
    Then it is true for an assignment, an augmented assignment, a delete or a write call that touches only the attribute
    But a statement of any other kind, such as a return or a nested branch, has no rule and fails, which is the conservative answer

  Scenario: _gate_branch finds the branch a membership test is the condition of
    Given a reference standing as a membership test
    When _gate_branch walks up to the if or elif whose condition it is
    Then it returns that branch, whose blocks the convergence rule then reads
    But it returns nothing when the test sits in a ternary, an assertion or a comprehension guard, because there is no block to read, and nothing at the function boundary

  Scenario: _gated_branches_converge requires every presence gate to guard writes to the attribute alone
    Given the attribute name and every reference
    When _gated_branches_converge reads every block under every gate the membership tests control
    Then it is true only when each statement in each of those blocks writes nothing but the attribute
    And this is what stops a presence test clearing when the answer lands in a neighbouring counter, which the return-based invariance check cannot see
    But a gate with no branch to read fails outright, and an attribute with no membership test at all passes vacuously

  Scenario: _is_write_only_accumulator recognises a counter nothing ever reads back out
    Given the attribute name and every reference
    When _is_write_only_accumulator requires every reference to be confined and every gate to converge
    Then it is true for a per-key tally whose value cannot change an observable outcome
    And the gated form is the case only this rule reaches, since the ungated one already clears as a carried value

  # The four failures in tests/test_state_bounds_filters.py land here, and none of them is a
  # disagreement about a filter. The classifier now hands this entry point the verdict
  # unresolved, not promiscuous, for all four sources, because a value flows through an
  # assignment right-hand side or an arithmetic operator and the reader has no rule for
  # either. Under an unresolved verdict only the write-once rule may fire, exactly as this
  # docstring says, so the carried-value, open-key and value-in-a-branch cases never reach
  # the rule each test was written to exercise. The filters behave as described; the input
  # they are given has changed.
  Scenario: is_false_positive decides whether one attribute's finding is a provable false positive
    Given the state key, every reference to it, and the verdict the classifier reached
    When is_false_positive runs the two guards and then the rules the verdict allows
    Then it is true only when a shape is provably testable, and any doubt at all leaves the finding standing
    And a value inspected in a branch, or a presence test that is itself the answer, ends it before any rule runs
    But an unresolved verdict admits only the write-once rule, because a fail-closed finding is not about decision space and the carried-value rule must never clear it
