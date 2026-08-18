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

  Scenario: _is_comparison decides whether a construct compares its operands
    Given a node and the language spec
    When _is_comparison accepts any comparison node in Python, and elsewhere reads the operator
    Then it is true when the operator is one of the ordering or equality operators
    But it reads the node without checking that one was supplied, so an absent node is a caller error rather than a false answer

  Scenario: _reads_its_own_target says whether an assignment reads what it writes
    Given a reference standing as an assignment target, through a subscript or a member access
    When _reads_its_own_target reads the assignment's operator
    Then a conditional operator the language declares, such as Ruby's ||= or C#'s ??=, counts as a read
    And a plain store does not, and neither does a language that declares no such operator
    But a reference that is not a target at all is declined before the operator is consulted

  Scenario: _categorize_read decides how the read half of a conditional assignment lands
    Given a target that its own assignment reads before writing
    When _categorize_read looks at what the target is
    Then a keyed target is a keyed read, so an open key is unbounded exactly as on the right-hand side
    But a bare name is the value meeting a presence test, which is the two-class split any truthiness test makes

  Scenario: _local_binding_name finds the local a reference is being bound into
    Given a reference and the language's local-binding vocabulary
    When _local_binding_name checks whether the reference fills the binding's value slot
    Then it returns the name being bound, so the caller can look for what the function does with it
    And a language whose grammar leaves the initialiser unnamed declares no value field, and the last named child is read instead, which is C# alone among the nine
    But a destructuring pattern returns nothing, because it binds several names and none of them is this value on its own

  Scenario: _follow_local reports what the state reaches through a local it was copied into
    Given the reference, the local's name, and a remaining depth
    When _follow_local finds every use of that local inside the enclosing function and categorises each
    Then it returns the widest finite reach among them, or the first undecided one, so the state is read through the copy instead of stopping at it
    And a local bound at module level is not followed, because there the binding is its own state and is enumerated as such
    And a local nobody reads returns output, since the value came to rest
    But several uses collapse into one reach and the narrower ones are lost, and the depth bound stops a pair of locals bound from each other walking forever

  Scenario: _switch_partition counts the classes a switch cuts in its subject
    Given the subject reference, the switch node and the language's name for an arm
    When _switch_partition counts the arms
    Then it returns one class per arm, plus one more when no default arm exists, because a subject matching no case is an outcome too
    And the partition is unordered, since there is no value just above a case label, which is the distinction the D tier rests on
    But the discriminator is keyed on the switch's own position, so one switch read twice is one cut and two switches on one state are two

  Scenario: _categorize decides how one reference to a piece of state is consumed
    Given a reference, the language spec and the file's fixed collections
    When _categorize works down its rows: written to, named as a member of another receiver, invoked, indexed, reached through, or passed as an argument
    Then it returns the category for the first row that matches, and a reference at the top of the tree is output
    And a reference supplying what runs is followed through the call result rather than fail-closed, since no arm selector reads its value
    And a reference sitting in the name half of a member access re-enters the same dispatch one node up, so a field read off another receiver is judged exactly as a bare read of it would be, in the three languages that key class state by a bare identifier
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

  Scenario: _state_refs collects every reference to one piece of state inside its own scope
    Given the scope to search, the state key and the language spec
    When _state_refs matches the spelling the language uses for that kind of state
    Then it returns every reference within the scope, stopping at a nested class so an inner class's state is not swept in
    And only the plain-name spelling is filtered for imports and shadowing, since the other spellings cannot be shadowed by a parameter

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
