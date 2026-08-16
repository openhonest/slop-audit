Feature: state_bounds — the finite-testability classifier that grades every piece of state neutral, promiscuous or unresolved
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today this module already states the case: _flow's total row returns
  # unmeasured carrying the two node types, so the verdict is withheld and named, and the only
  # missing half here is the offer to collect the shape.
  @undecidable @not-implemented
  Scenario: undecidable a value carried through a construct no dispatch row covers
    Given a value derived from the state standing on the right of an assignment, inside a binary operator, or as a decorator, none of which _flow has a row for
    When _flow works down its rows and every one of them declines
    Then it is recorded as unread rather than handed to output, which would call it compositional and cost no tests, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _sub_named lists the named parts of an indexing expression
    Given a subscript node
    When _sub_named keeps only its named children
    Then it returns them in source order, which is what the positional grammars index into
    But the bracket tokens are dropped, since they carry no part of the collection or the key

  Scenario: _sub_collection finds the collection being indexed
    Given a subscript node and the language spec
    When _sub_collection takes the first named child in a positional grammar, or the named field elsewhere
    Then it returns the collection
    But a positional subscript with no named children yields nothing, so the caller gets an absence rather than a wrong node

  Scenario: _sub_key finds the key or index of an indexing expression
    Given a subscript node and the language spec
    When _sub_key takes the second named child in a positional grammar, unwraps a bracketed argument list, or reads the named field
    Then it returns the key, which is what decides whether the read is bounded
    But a positional subscript with fewer than two named children yields nothing

  Scenario: _first_arg reads the value of the first argument at a call site
    Given a call node and the language spec
    When _first_arg finds the argument list, takes its first named entry and unwraps a named-argument wrapper
    Then it returns the value passed
    But a missing call, a missing argument list or an empty one all yield nothing, since every step passes an absence straight through

  Scenario: _callee_name reads the name of what is being called
    Given a call node and the language spec
    When _callee_name reads the receiver-and-name field in a flat-call grammar, or the function field elsewhere
    Then it returns the callee's text, which the bounded and effect lists are matched against
    But a missing node, or a node that is not a call at all, yields the empty string, which matches no list

  Scenario: _is_immutable_collection recognises a fixed collection on the right of an assignment
    Given the right-hand side of an assignment
    When _is_immutable_collection checks for a tuple, or for a frozen-set construction
    Then it is true for those two shapes and nothing else
    But a plain set or list is not accepted here, because either can still be mutated after it is built

  Scenario: _collect_closed_sets builds the file's table of statically fixed collections
    Given the parse tree of one file
    When _collect_closed_sets walks every assignment whose right-hand side is a fixed collection
    Then it returns a table from the bound name, or the bound attribute's name, to that collection's member count
    And a collection whose size cannot be recovered is recorded with no count, which is not the same as a count of zero
    But the same name bound twice keeps the last binding read, since the walk simply overwrites

  Scenario: _is_closed_set decides whether a container is statically fixed
    Given a container node and the file's table of fixed collections
    When _is_closed_set accepts a collection written out in place, a set construction, or a name recorded in the table
    Then it is true for a container whose membership cannot change while the program runs
    But a name the table does not carry is not accepted, so a collection built elsewhere stays unproven

  Scenario: _unwrap_unary peels unary operators off a value
    Given a value node and the language spec
    When _unwrap_unary steps down to the operand through each unary operator in turn
    Then it returns the value underneath, so a negated literal is still one compile-time value
    But a negated variable peels to a name, which is no literal, and stays unbounded

  Scenario: _is_unbounded_value decides whether a value ranges over a domain nobody can enumerate
    Given a value node and the language spec
    When _is_unbounded_value unwraps it and tests it against the grammar's literal types
    Then it is true for a parameter or a variable, and false for a literal
    But a missing node counts as bounded, so an absent key never makes a read unbounded on its own

  Scenario: _membership_operands splits a membership test into the value and the container
    Given a node and the language spec
    When _membership_operands matches the grammar's spelling of a membership test
    Then it returns the value tested and the container tested against, in that order
    And the negated form is matched too, because it is one token in this grammar rather than a negation wrapping the positive form
    But any other node yields nothing, and the caller then falls on to the comparison rule

  Scenario: _is_comparison decides whether a construct compares its operands
    Given a node and the language spec
    When _is_comparison accepts any comparison node in Python, and elsewhere reads the operator
    Then it is true when the operator is one of the ordering or equality operators
    But it reads the node without checking that one was supplied, so an absent node is a caller error rather than a false answer

  Scenario: _is_lvalue decides whether a node is the target of an assignment
    Given a node and the language spec
    When _is_lvalue steps out through an optional target wrapper and compares the node against the assignment's target
    Then it is true when the node is what the assignment writes to
    And the wrapper step is what lets a grammar that puts targets in a list still be read

  Scenario: _is_binding_site decides whether a reference is the declared name of a declaration
    Given a reference, the construct above it and the language spec
    When _is_binding_site looks the construct up in the spec's table of declarations and compares the named field
    Then it is true for a field or property declaration naming the state, which binds it rather than consuming it
    And the field is checked, not just the construct type, so a name read inside a declaration's value is not mistaken for the name being bound
    But Python declares no such sites, so this rule never fires there

  Scenario: _is_write_target decides whether a reference is written to rather than read
    Given a reference, the construct above it and the language spec
    When _is_write_target accepts an assignment target, a declared name, or the collection of an indexed store
    Then it is true for all three ways the code puts a value in
    And a keyed store counts, because the collection is being written through even though the reference is not itself the target

  Scenario: _keyed_read grades a read of the collection at a key
    Given the key node and the language spec
    When _keyed_read tests whether the key is bounded
    Then an unbounded key yields an unbounded partition, and a literal key yields a two-class split keyed on the literal's text
    And the split is ordered only when the literal is numeric, because a numbered position has a neighbour and a named one does not

  Scenario: _categorize decides how one reference to a piece of state is consumed
    Given a reference, the language spec and the file's fixed collections
    When _categorize works down its rows: written to, invoked, indexed, reached through, or passed as an argument
    Then it returns the category for the first row that matches, and a reference at the top of the tree is output
    And a reference supplying what runs is followed through the call result rather than fail-closed, since no arm selector reads its value
    But when no row consumes the value the reference is the value itself, and the question moves to where that value goes

  # This is where five currently-red tests part company with the code, and the disagreement is
  # one missing row rather than five. tests/test_state_bounds_filters.py loses four cases and
  # tests/test_reference_honest_framework.py one, all with the same reason recorded: no rule
  # covered the construct. Three shapes reach the total row today — a value assigned to
  # something else, a value inside an arithmetic operator, and a call standing as a decorator.
  # The tests assert the old answer, which was output, meaning compositional and costing no
  # tests. The code's answer is the honest one and the tests encode a verdict the reader never
  # earned; the fix owed is the three missing rows, not a return to the silent clearing.
  Scenario: _flow follows a value derived from the state until it reaches a decision, or admits it cannot
    Given a node holding a value derived from the state, the language spec and the file's fixed collections
    When _flow works down its rows: returned, discarded, invoked, passed through, compared, branched on, passed as an argument, or indexed
    Then it returns the category for the first row that matches, recursing through every construct that merely carries the value onward
    And a truthiness test anywhere in the file shares one discriminator, so the same two-class split written fifty times is counted once
    But when every row declines it returns unmeasured rather than output, because output is a verdict and the reader has not earned one

  Scenario: _is_call_target decides whether a reference supplies what runs at a call site
    Given a reference and the language spec
    When _is_call_target checks that the reference is the callee of the call above it
    Then it is true for state invoked directly, which is the injected-slot shape
    But a flat-call grammar never matches, since it spells the receiver and the method name as one node

  Scenario: _written_through decides whether the host reaches into the value's own shape
    Given a reference and the language spec
    When _written_through checks for a write to a member of the state, or a mutating method called on it
    Then it is true when the host depends on a collaborator's internals, which it cannot enumerate
    But a plain read of a member is not enough, because reading a contract is not reaching behind it

  Scenario: _injected_slot_premise_fails decides whether the compositional rule for an invoked slot loses its premise
    Given every reference to one piece of state, the language spec, and whether the state belongs to an instance
    When _injected_slot_premise_fails tests the three constructs that defeat the proof
    Then it is true for a module-level slot, for a slot bound more than once, and for a slot the host writes through
    And a state that is never invoked at all fails no premise, so the rule declines before any of the three is tested
    But none of the three can be seen one reference at a time, which is why this runs over the whole attribute

  Scenario: _verdict combines one state's reaches into a single verdict
    Given every reach collected for one piece of state
    When _verdict takes undecided first, then unbounded, then finite
    Then it returns the verdict, whether the state drives a decision, the silence reason, the construct and the partition
    And the reason reported is the first undecided reference in source order, because the reader's next move is to open the site and any ranking would be invented here
    But a state with no decision-reaching reference at all is neutral and observe-only, with an empty reaching set of one class

  Scenario: _under_import_path recognises an identifier that names a package rather than a value
    Given an identifier node
    When _under_import_path walks up looking for an import or package construct
    Then it is true when the name binds nothing here, so an import of a package is not read as a reference to same-named state
    But the match is on the construct type containing the marker word, not on an exact type, so it catches each grammar's spelling

  Scenario: _shadowing_scope finds the nearer function that binds the same name
    Given a reference, the state key and the language spec
    When _shadowing_scope walks up looking for a function whose parameters declare that name
    Then it returns that function, and the reference is then known to belong to the parameter rather than the state
    And only the parameter list is consulted, because a local assignment shadows by rules that diverge per language while a parameter is unambiguous everywhere

  Scenario: _bound_to keeps only the references that really denote the state
    Given a list of name matches, the state key and the language spec
    When _bound_to drops the ones under an import path and the ones a nearer parameter binds
    Then it returns the references that actually denote the state
    And both collection routes go through it, because a filter applied to one used to miss the other silently

  Scenario: _state_refs collects every reference to one piece of state inside its own scope
    Given the scope to search, the state key and the language spec
    When _state_refs matches the spelling the language uses for that kind of state
    Then it returns every reference within the scope, stopping at a nested class so an inner class's state is not swept in
    And only the plain-name spelling is filtered for imports and shadowing, since the other spellings cannot be shadowed by a parameter

  Scenario: _rhs_is_immutable decides whether an assigned value can never change after it is built
    Given the right-hand side of an assignment and the names of the repository's immutable constructors
    When _rhs_is_immutable accepts a literal, a tuple, a known immutable wrapper, or a call to one of those constructors
    Then it is true for a value no callee can mutate
    But a missing right-hand side, and anything else at all, is not accepted

  Scenario: _returns_immutable decides whether a function only ever hands back immutable values
    Given a function's parse tree
    When _returns_immutable requires every return in it to carry an immutable value
    Then it is true only when the function is a constructor of constants, which lets a declared table resolve on the evidence
    And a function with no return at all is not accepted, so the absence of returns is never read as a promise
    But a bare return with no value also fails, since there is no value to prove immutable

  Scenario: _collect_immutable_ctors names the repository's constructors of immutable values
    Given the parse tree of one file
    When _collect_immutable_ctors keeps every function whose returns are all immutable
    Then it returns their names, which a one-level follow then uses to resolve a constant built by one of them
    But it matches Python's spelling of a function definition only, so no other language contributes names

  Scenario: _reaches_decision decides whether any reference to the state is consumed at all
    Given every reference to one piece of state and the language spec
    When _reaches_decision skips the references that are returned and the ones that are written to
    Then it is true as soon as one reference is left, meaning the state is read somewhere that could turn on it
    But a state that is only bound and only returned reaches no decision, and an empty reference list reaches none either

  Scenario: _immutable_const_verdict clears a state that is a constant with a one-value domain
    Given every reference, the repository's immutable constructors and the language spec
    When _immutable_const_verdict requires exactly one plain assignment from an immutable construction, with no rebinding, no keyed store, no call and no mutating method
    Then it returns neutral together with whether the constant reaches a decision
    But any one of the four disqualifiers, or a count of assignments other than one, returns nothing and the ordinary classification runs instead

  Scenario: _binding_line reports the line where the state is bound, not where its name first appears
    Given every reference to one piece of state and the language spec
    When _binding_line takes the earliest reference that is an assignment target
    Then it returns that line, so the reader is sent to the definition rather than to an import that binds nothing
    And a state never assigned in this file falls back to its earliest reference, which is right for an injected or inherited name
    But this changes no verdict and no count, only where the reader is sent

  Scenario: _finding assembles the verdict for one piece of state
    Given the state key, its references, the file path, the language spec, the fixed collections, the immutable constructors and whether the state belongs to an instance
    When _finding takes the constant shortcut if it applies, otherwise categorises every reference and combines them
    Then it returns the state, the verdict, whether it drives a decision, the file and binding line, the silence reason, the construct and the partition
    And a neutral verdict earned by the compositional rule for an invoked slot is demoted to unresolved when that rule's premises fail
    But the attribute-level false-positive filter runs last, for Python only, and can clear a non-neutral verdict back to neutral and observe-only

  Scenario: _analyze_file classifies every piece of state in one file and records what was looked at
    Given a parsed file, its path, the language spec, the language config and the immutable constructors
    When _analyze_file runs the module, receiver-grouped, class and record enumerators in turn
    Then it returns the findings together with the declarations it visited and the subset it judged
    And the two sets are kept apart because a declaration reached and declined is not the same as one nothing looked at, which is the only real gap in the reading
    But the table of fixed collections is built for Python alone, so a membership test in any other language never resolves by that route

  Scenario: _na returns the whole panel entry for a language the classifier has no spec for
    Given the language name
    When _na builds the entry without reading any source at all
    Then it returns every field the real result carries, with the verdict, value and band all marked not applicable
    And the census is reported as uncounted rather than zero, because a confident zero would claim there is no state in a repository nobody read

  Scenario: classify produces the finite-testability verdict distribution for a whole repository
    Given a repository path and a language name
    When classify parses the production source, collects the immutable constructors in a first pass, then classifies every file
    Then it returns the counts by verdict, the coverage matrix, the resolvable fraction, the silence index, the partition summary, the census comparison and the sorted findings
    And the repository verdict is promiscuous if any state is, otherwise unresolved if any state is, so the worst answer is the one reported
    But the census is counted by a separate route, because no measure over the state this module recognised can see the state it never enumerated
