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
