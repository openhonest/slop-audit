Feature: The three clauses about a program's edges

  I/O, exceptions and logging. Split from the shared rules when that module crossed the
  god-file threshold, at the seam the growth follows: every clause here asks what crosses
  the line between this program and the world, and whether the code says so.

  Scenario: io_below_the_boundary finds I/O a sibling reaches
    Given a function that reads a file and another that reaches it
    When io_below_the_boundary builds the call graph from calls, table entries and names handed on
    Then the reader is reported, because neither it nor its caller can be tested without a mock
    But a function nothing reaches IS the edge, and whether it is truly an entry point is not readable here

  Scenario: swallowed_exceptions finds an error going somewhere to be forgotten
    Given a parsed source
    When swallowed_exceptions reads its handlers
    Then a handler whose body only passes, or returns a stand-in, reports success for work that failed
    But a handler that re-raises, or that maps the error to a response at a boundary, is doing the thing the rule asks for

  Scenario: _throws_it_away says whether a handler discards the failure
    Given one empty handler and one returning the message of the error it caught
    When _throws_it_away reads the body through the language's vocabulary
    Then only the first discards the failure
    But a body mentioning the caught error is disclosing it rather than hiding it

  Scenario: _guarded_body_asserts_a_raise says when the handler is the success condition
    Given a try body ending in a statement that records a failure
    When _guarded_body_asserts_a_raise reads the body the handler guards
    Then reaching the recorder is the defect and the handler beneath is correct
    But whether the recorded failure is the one the author meant is not readable here

  Scenario: _caught_text says what one handler catches
    Given a handler naming one exception type and one naming none
    When _caught_text reads the handler's children other than its body
    Then the first names its type and the second names nothing
    But a handler catching everything is the one this clause is least able to excuse

  Scenario: _caught_variable names what the handler binds the error to
    Given a handler binding the error and one binding nothing
    When _caught_variable takes the last identifier before the body
    Then the bound name comes back for the first and nothing for the second
    But all five grammars put it there whether they field it or not

  Scenario: undeclared_logging finds a function that writes a log line
    Given one function logging a failure and carrying on, and one logging information
    When undeclared_logging reads both through the language's logging vocabulary
    Then the first is reported for losing the failure and the second for opening an edge onto a global nothing declared
    But whether the return value already names the failure is not readable from the callee alone

  Scenario: _log_levels_in names the logging calls one function makes
    Given a call on a logger and a call named info on something that is not one
    When _log_levels_in matches the receiver and the call together
    Then only the logger's call counts
    But both halves are ordinary words alone, so matching either by itself would report a field named info

  Scenario: _silenced_without_a_handler finds an exception discarded by a call
    Given a block wrapped in a suppression naming an exception type
    When _silenced_without_a_handler reads the calls that discard rather than the handlers
    Then the block is reported, because it returns as though it succeeded and there is no handler body to judge
    But a suppression naming only a control-flow signal is not the failure this rule is about

  # The reserved case. These three clauses decide what CROSSES the line, and one thing about
  # a crossing is never in the file: whether the function doing it is where the program is
  # supposed to meet the world.
  @undecidable @not-implemented
  Scenario: undecidable whether an unreached function is truly an entry point
    Given a function no call, no table and no argument reaches
    When someone asks whether it is this program's edge or merely unused
    Then the answer is in how the module is imported from outside, which is not in the module
    But a module read only from elsewhere has every function looking like an entry point

  Scenario: returns_a_declared_absence says whether a handler returns the absence its function declares
    Given a handler node, its language's vocabulary, and the source bytes
    When returns_a_declared_absence reads the enclosing function's declared return type and what the handler returns
    Then it answers yes where the type admits an absence and the handler returns exactly that, because the absent case is then in the contract and every caller has to handle it
    And this package carried twelve comments telling the swallow rule to allow such sites, the largest group of exceptions in it by a factor of two, and reading them together showed one shape rather than twelve judgments
    And a function returning the empty string while typed as a string is not covered, since no caller can tell an absent value from an empty one and that is the shape the rule exists to name
    And a handler returning some other value where an absence was declared is not covered either, because declaring an absence permits returning that and not a value nobody asked for
    But a language declaring no return type is refused before anything is read, so this cannot become a way to go quiet by writing less

  Scenario: self_caught_failures finds a test that catches its own failure, or a handler sorting by words
    Given a parsed source and its language's node vocabulary
    When self_caught_failures reads each try for a declared failure inside it and each handler for what it catches and how it decides
    Then it reports a deliberate failure inside a try whose handler catches everything, because that declaration raises like anything else and both land in the same branch
    And it reports a handler deciding what happened by reading the exception as text, which is the wider rule and holds outside a test entirely
    And an adopter found this in the only test of a constraint surviving a rebuild, where rewording one message would have passed the test while the constraint was broken, and every other exception read as success too
    And a narrow handler that cannot catch the failure is left alone, since the two cannot be confused there
    And a handler sorting by type is left alone, because that is what the rule asks for and reporting it would punish the remedy
    But whether the text being matched is one the same function wrote is not decided, since in general the string can come from anywhere

  Scenario: _declares_failure says whether a node is a test saying it should not have got this far
    Given a node, its language's vocabulary, and the source bytes
    When _declares_failure checks the node against the ways a test declares failure
    Then it answers yes for a call to the framework's fail, a raised assertion error, or a bare false assertion
    But it reads the spellings the table holds, so adding a framework means adding a row and not a branch

  Scenario: _catches_everything says whether a handler catches a deliberate failure along with the rest
    Given a handler node, its language's vocabulary, and the source bytes
    When _catches_everything reads what the handler names
    Then it answers yes for a handler naming nothing and for one naming a root exception type
    But a handler naming a narrower type is answered no, because a test's own failure cannot land there

  Scenario: _sorts_by_text says whether a handler decides what happened by reading the exception as words
    Given a handler node, its language's vocabulary, and the source bytes
    When _sorts_by_text looks for the caught name being rendered as text inside the handler
    Then it answers yes where that rendering sits inside a condition, because rewording a message anywhere then changes which branch runs
    And a handler putting the exception's text into a response is left alone, since it caught by type and is telling the caller what happened rather than deciding by the words
    But this holds outside a test as well, and this package hit it in a different room when a contention check retried an error because one word matched and the cause was ours

  Scenario: _bound_name gives the name a handler binds the caught exception to
    Given a handler node, its language's vocabulary, and the source bytes
    When _bound_name reads the identifiers the catch declares
    Then it returns the last of them in source order, which is the local name rather than the type
    And that is a different question from what type was caught, and the only thing that tells one rendering of the exception from any other call by the same name
    But taking whichever identifier the walk happened to yield last picked the type and matched nothing
