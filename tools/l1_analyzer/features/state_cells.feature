Feature: state_cells — how wide a keyed access is, and how many cells the writes into it can create
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the guard rule reads one shape only, an inline membership test, and
  # returns nothing for every other way a key can be confined. Nothing separates that from a key
  # nobody guarded at all, so the state is reported unbounded and the guard that was not read is
  # never named.
  @undecidable @not-implemented
  Scenario: undecidable a key confined by a guard this module has no rule for
    Given a subscript store whose key is bounded by a helper call rather than by an inline membership test, as in a branch on valid(k) wrapping CACHE[k] = v
    When guarded_by_closed_set walks up to the enclosing function, matches no membership test on that name and returns nothing, and write_key_bound declines with it
    Then it is recorded as unread rather than reported unbounded as though the key had been guarded by nothing, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: is_unbounded_value decides whether a value ranges over a domain nobody can enumerate
    Given a value node and the language spec
    When is_unbounded_value unwraps it and tests it against the grammar's literal types
    Then it is true for a parameter or a variable, and false for a literal
    But a missing node counts as bounded, so an absent key never makes a read unbounded on its own

  Scenario: keyed_read grades a read of the collection at a key
    Given the key node, the language spec and the number of cells the writes can create, which may be unknown
    When keyed_read tests whether the key is bounded
    Then an unbounded key yields an unbounded partition, and a literal key yields a two-class split keyed on the literal's text
    And the split is ordered only when the literal is numeric, because a numbered position has a neighbour and a named one does not
    But an unbounded key over a known cell set reaches the cells and absent instead, and every such read shares that one discriminator, since a read cannot observe a cell no write created

  Scenario: guarded_by_closed_set bounds a name that an enclosing membership test confines
    Given a key node and the closed sets the file declares
    When guarded_by_closed_set walks up to the enclosing function looking for a branch on that name's membership
    Then it returns the cardinality of the declared set the name is tested against
    And it reads only the consequence side, so a name bounded on the taken branch is not bounded on the other one
    But it returns nothing when the container is not a declared closed set, because a mutable list bounds no key

  Scenario: contains answers whether one node sits inside another
    Given a scope node and a candidate node from the same tree
    When contains compares their byte spans
    Then it returns true only when the candidate lies wholly within the scope
    But it compares spans rather than walking parents, so it says nothing about which node owns the other

  Scenario: write_key_bound counts the cells a subscripted state's writes can create
    Given every reference to one state and the closed sets the file declares
    When write_key_bound reads the key of each subscript store
    Then it returns how many distinct cells those writes can reach, a literal key counting one and a guarded key counting its set's size
    And a state with no subscript store at all returns nothing, because the rule has nothing to say about it
    But one store with an open key returns nothing however narrow every other store is, since a single unguarded write reopens the whole cell set

  Scenario: membership_operands splits a membership test into the value and the container
    Given a node and the language spec
    When membership_operands matches the grammar's spelling of a membership test
    Then it returns the value tested and the container tested against, in that order
    And the negated form is matched too, because it is one token in this grammar rather than a negation wrapping the positive form
    But any other node yields nothing, and the caller then falls on to the comparison rule

  Scenario: is_closed_set decides whether a container is statically fixed
    Given a container node and the file's table of fixed collections
    When is_closed_set accepts a collection written out in place, a set construction, or a name recorded in the table
    Then it is true for a container whose membership cannot change while the program runs
    But a name the table does not carry is not accepted, so a collection built elsewhere stays unproven

  Scenario: collect_closed_sets builds the file's table of statically fixed collections
    Given the parse tree of one file
    When collect_closed_sets walks every assignment whose right-hand side is a fixed collection
    Then it returns a table from the bound name, or the bound attribute's name, to that collection's member count
    And a collection whose size cannot be recovered is recorded with no count, which is not the same as a count of zero
    But the same name bound twice keeps the last binding read, since the walk simply overwrites

  Scenario: is_immutable_collection recognises a fixed collection on the right of an assignment
    Given the right-hand side of an assignment
    When is_immutable_collection checks for a tuple, or for a frozen-set construction
    Then it is true for those two shapes and nothing else
    But a plain set or list is not accepted here, because either can still be mutated after it is built
