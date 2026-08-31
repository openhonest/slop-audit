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

  Scenario: _named builds a test for identifiers spelling one name
    Given the name of one piece of module-level state
    When _named binds it into a test the tree walk can run over every node
    Then an identifier spelling that name answers yes and everything else answers no
    But the name is a parameter with a name and a type, not a default value standing in for a capture: the loop rebinds it each turn, and a test reading it from around itself would judge every state against the last

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
