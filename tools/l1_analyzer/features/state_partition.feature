Feature: state_partition — what a finite verdict carries beside the word "finite"
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today this module names the silence one reference at a time and then loses
  # it in the roll-up: a state whose every reach came back undecided returns the empty partition,
  # counted and ordered, so the disclosure that exists per reference is missing per state.
  @undecidable @not-implemented
  Scenario: undecidable a state whose every reach came back undecided
    Given every reach collected for one piece of state, all of them undecided, with no finite reach among them to sum
    When roll_up de-duplicates the finite reaches by discriminator and finds none
    Then it is recorded as unread rather than rolled up to one counted, ordered class, which is the partition a state that was read and found single-valued gets, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: write records that a reference is an assignment target and decides nothing
    Given no input at all
    When write is asked for the category of a reference that is written to
    Then it returns a reach marked write, with no equivalence classes, no discriminator
    And it reports itself as ordered and counted, so a roll-up that ignores it is never told a count is missing

  Scenario: output records that a reference is handed to the caller and reaches no decision here
    Given no input at all
    When output is asked for the category of a returned or discarded reference
    Then it returns a reach marked output, with no equivalence classes and no discriminator
    But the decision may still exist one frame up, which is why every rule that reaches for this one has to earn it

  Scenario: unbounded records that a reference reaches a decision over a domain nobody can enumerate
    Given no input at all
    When unbounded is asked for the category of a lookup on a key the code does not bound
    Then it returns a reach marked unbounded, carrying no class count
    And it reports itself as not ordered, because an unbounded split has no boundary values that cover it

  Scenario: undecided records that a reaching-set could not be decided, and whose problem it is
    Given one of the named silence reasons
    When undecided is asked for the category of a reference the reader could not follow
    Then it returns a reach marked undecided carrying that reason
    But the construct field stays empty, because only an unhandled syntax shape has a shape to name

  # The behaviour under this scenario is what turns five currently-passing expectations red:
  # tests/test_state_bounds_filters.py (four cases) and tests/test_reference_honest_framework.py
  # (the reference server, one state at line 31). Those tests assert neutral or promiscuous;
  # the reader now answers undecided because a syntax shape reached the total row. The tests
  # describe a reader that had a rule; the code describes one that admits it has none.
  Scenario: unmeasured records that no rule in the table covered this construct
    Given the type of a node and the type of the construct holding it
    When unmeasured is reached because every rule above it declined
    Then it returns a reach marked undecided under the analyzer's own missing-rule reason
    And it names the shape as the node type inside the parent type, so the missing rule can be read off the report
    But it is handed two node-type strings and nothing else, so no verdict is reachable from what it holds

  Scenario: finite records a decision that cuts the domain into a countable number of classes
    Given a class count, whether boundary values cover the split, and the identity of the discriminator
    When finite is asked for the category of that reference
    Then it returns a reach marked finite carrying all three
    And it reports itself as counted, because the caller supplied a number

  Scenario: uncounted records a split that is provably finite but whose size cannot be recovered
    Given the identity of the discriminator
    When uncounted is asked for the category of a membership test against a set of unreadable size
    Then it returns a reach marked finite, carrying no class count and marked as not counted
    And it reports itself as not ordered, because order it has not established would be the optimistic direction

  Scenario: roll_up combines one state's references into the partition of its whole domain
    Given every reach collected for one piece of state
    When roll_up de-duplicates the finite ones by discriminator and sums them
    Then it returns one more class than the sum of the cuts, ordered only if every cut is ordered
    And a state with no finite reach at all rolls up to one class, because every value behaves alike
    But one uncounted discriminator makes the whole partition uncounted, since a partial sum is not a size

  Scenario: is_coarse decides whether a partition is the positive finding
    Given a rolled-up partition, whether the state drives a decision, and the bound
    When is_coarse tests all four conditions together
    Then it is true only for a counted, unordered partition above the bound that reaches a decision
    But a partition that reaches no decision is never coarse, however many classes its domain would have had

  Scenario: silence_summary reports the share of state the analyzer could not decide, and every site
    Given every finding for a repository and the number of states read
    When silence_summary collects the findings that carry a silence reason
    Then it returns the count, the fraction, a per-reason tally and the full list of sites
    And every reason key appears in the tally, so a zero means the analyzer looked and found none
    But the sites are listed in full rather than capped, because the reader's next move is to open each one

  Scenario: partition_summary publishes the cardinality distribution of state that decides something
    Given every finding for a repository
    When partition_summary keeps only the neutral findings that drive a decision
    Then it returns the count of those states, how many of them have a size nobody could recover, and the two sorted lists of class counts
    And the ordered and unordered class counts are kept apart, because only the unordered ones resist boundary values
    But it publishes the raw lists rather than an average, since a bound has to be set from a distribution

  Scenario: literal_size counts the members of a fixed collection, or admits it cannot
    Given a node that may be a collection
    When literal_size counts its named elements, following one wrapper call through to its argument
    Then it returns the member count for a set, tuple or list, and for a wrapper around one of those
    And it returns nothing at all for a name, a dictionary, or a wrapper around a call it cannot read
    But an empty wrapper call is also uncountable rather than zero, because the argument it would count is absent

  Scenario: closed_set_size recovers the member count of a container already accepted as closed
    Given a container node and the table of collections collected from the file
    When closed_set_size looks the container up by name, or by its attribute name
    Then it returns the recorded member count, which may itself be absent
    And a container written out as a literal is counted directly instead of looked up

  Scenario: membership_reach grades a test of one value against a fixed set
    Given the container of the membership test and the table of closed collections
    When membership_reach recovers the container's size
    Then it returns a finite split of one class per member plus one for matching none of them
    And nothing orders the classes, since no member sits just above another
    But an unrecoverable size leaves the split finite and only the count silent, so the verdict still stands

  Scenario: silence_kind decides whose problem an undecidable call is
    Given a call node and the language spec
    When silence_kind looks at where the callee name comes from
    Then a bare name is the analyzer's own gap, and a name reached through another object is the adopter's boundary
    And a method reached through the receiver of the class under analysis counts as ours, by the spec's scoping rule
    But a callee that is not a name at all is chosen while the program runs, which nobody can enumerate by reading
