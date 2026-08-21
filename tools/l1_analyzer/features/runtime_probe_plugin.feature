Feature: runtime_probe_plugin — watching the audited module while its suite runs
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  A real module rather than a string the probe writes to a temp file. It began as source
  inside a string literal, which put a module's worth of logic where the linter, the type
  checker, the coverage run and this project's own facet reader could all see nothing.

  Every collaborator the wrapper uses is a parameter bound at definition time. A wrapper
  that reaches for one through the module namespace it has just replaced calls itself
  without bound, and that recursion came back three times, one link further down each time.

  Scenario: safe_repr reads a value without breaking or swamping the suite
    Given any value the audited code was passed or returned
    When safe_repr reads it
    Then a value whose own repr raises is unreadable rather than a test failure in the audited code
    But a value over the read limit is unreadable rather than truncated, because a truncated repr compares two different values as equal

  Scenario: opaque says whether any value in a call defeated the reader
    Given the reprs of one call's values
    When opaque reads them
    Then one unreadable value makes the whole call evidence for nothing
    But an empty call is readable, because a no-argument call is a real call

  Scenario: describe reads one call's arguments and keywords
    Given the positional arguments and the keywords of a call
    When describe reads them with the reader it was given
    Then both come back as reprs
    But the reader is bound at definition time, because reaching for it through the namespace being replaced described the describing of a call

  Scenario: observe wraps one function so every call to it is recorded
    Given a function, the list to record into, and the collaborators the bookkeeping uses
    When observe wraps it
    Then the arguments are read on both sides of the call, which is what makes a change in place visible
    And it returns exactly what the function returned, because an observer that changed the answer would be measuring itself
    But the exception belongs to the suite and is re-raised, because swallowing it would turn a failing test green

  Scenario: wrap_module replaces every function the module defines
    Given the name of the module to watch and the list to record into
    When wrap_module walks the module's attributes
    Then only the functions the module DEFINES are wrapped, since a function it merely imported belongs elsewhere
    But a second pass wraps nothing, because a wrapper belongs to this module and double wrapping would record every call twice

  Scenario: pytest_configure wraps the module before collection begins
    Given the pytest config object and the module the probe named
    When pytest_configure runs
    Then the wrappers are in place before a test says "from m import band" and binds the name
    But the observations ride on the config object rather than a module level list, because that list was unbounded shared state in the tool that measures unbounded shared state

  Scenario: pytest_unconfigure hands back what the run saw
    Given the pytest config object at the end of the run
    When pytest_unconfigure reads the observations off it
    Then they are written where the probe asked
    But a run killed before this point loses them, and the probe reports that as a run it could not watch rather than as a module with no runtime properties

  Scenario: write_observations records the run where the probe asked
    Given the observations and the destination the probe named
    When write_observations is called
    Then it says whether it wrote
    But no destination means nobody asked to watch this run, and writing to a path from a previous one would overwrite one audit with another

  Scenario: module_state reads the module's own data, which purity is about
    Given the module being watched
    When module_state reads its namespace
    Then functions, classes and dunders are left out, since what a call can change and the return value does not mention is the data
    But an unreadable namespace comes back empty, and empty is not the same as a module holding nothing

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A default repr carries an address, so two distinct values never compare equal and a change
  # in place leaves no trace the observer can read. Answering either way would report evidence
  # nobody produced.
  @undecidable @not-implemented
  Scenario: undecidable whether an unreadable value was changed in place
    Given a call whose argument carries the default repr, which holds an address
    When someone asks whether the function mutated it
    Then the call is marked unreadable and counts toward nothing
    But the question itself cannot be answered from a repr that compares equal to nothing, and answering it either way would be reporting evidence nobody produced
