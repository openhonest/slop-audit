Feature: runtime_probe — runtime properties, watched while the suite executes
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  The fifth facet kind, and the only one that cannot be read from the source. Umbra's
  glossary sets the discipline: a runtime property counts only when the test run clearly
  shows it holding or breaking, and when the tests never make it happen the answer is that
  nobody looked, not that it holds.

  Nothing here re-invokes the audited code to manufacture evidence. A property observed by
  calling the function again is a property of the audit rather than of the suite, and it
  would run the caller's I/O a second time to say so.

  Scenario: is_opaque recognises a repr the observer could not read
    Given the repr of one value
    When is_opaque reads it
    Then a default repr, which carries an address and compares equal to nothing, is unreadable
    But a string that merely contains the marker is not, because the shape has to be the whole repr

  Scenario: invites names which properties are a meaningful question about a function
    Given a function definition with its declared types
    When invites reads them
    Then a mutable parameter invites mutation, a declared return invites determinism, and a single argument of the return's own type invites idempotency
    But a property nobody could ever exercise is never enumerated, because an unclosable facet in the denominator charges a suite for a question that does not arise

  Scenario: verdicts says what the watched run showed about each function it reached
    Given every observation the watched run produced
    When verdicts groups them by function
    Then each property reads holds, breaks, unobserved or unverified
    But a function the suite never called does not appear at all, because absence of a key and a claim about the key are different facts

  Scenario: _readable drops the observations nobody could read
    Given a function's observations
    When _readable filters them
    Then only the calls whose values were readable survive
    But an unreadable call is kept out of every count rather than counted either way

  Scenario: _mutation says whether the function changed what it was handed
    Given a function's observations
    When _mutation compares the arguments on both sides of each call
    Then one observed change outweighs any number of clean calls, because a function that mutates on one path mutates
    But no readable call at all is unverified rather than unobserved, since no test could have shown it

  Scenario: _signature identifies one call by everything the caller passed
    Given one observation
    When _signature reads its positional arguments and its keywords
    Then the keywords are included and sorted, so the same call spelled two ways is one call
    But leaving them out gave every keyword call an empty argument list, so they all grouped together and a pure function read as answering differently to the same question

  Scenario: _determinism says whether the same call gave the same answer twice
    Given a function's observations
    When _determinism groups them by signature
    Then a group with two or more entries is evidence, holding when every answer matches
    But a call that raised carries no result, so it is not one of the two

  Scenario: _idempotency says whether running again on its own output changed anything
    Given a function's observations
    When _idempotency looks for a call whose one argument is a result this function returned earlier
    Then holding means the second pass changed nothing
    But a call with several arguments or with keywords is not evidence, because feeding a result back as the first of three is not the function running again on its own output

  Scenario: runtime_facets builds one facet per property a function invites
    Given a function definition, what the run showed about it, and why the run showed nothing when it did
    When runtime_facets reads them
    Then a property is silent while nobody has watched it and closed once the run showed it holding or breaking
    But a run that could not be watched makes every property unverified rather than silent, because a suite nobody watched has not failed to exercise anything

  Scenario: dotted_name gives the name the tests will import the module by
    Given the module path and the directory the suite runs from
    When dotted_name reads the relative path
    Then the name is the one a test's own import statement uses
    But wrapping a second copy loaded under another name leaves the tests calling the original, and the run reports a suite that exercised nothing

  Scenario: watch runs the suite once with the module's functions wrapped
    Given a module and the test files that exercise it
    When watch runs them under the probe plugin
    Then the observations come back with an empty reason
    But a run that timed out or failed before finishing comes back with the reason instead, because an empty list alone reported every property as unobserved and that reads as a suite that never tried

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # Deciding whether an unobserved property holds would mean calling the function again, and
  # that is a property of the audit rather than of the suite. It would also run the caller's
  # I/O a second time to say so.
  @undecidable @not-implemented
  Scenario: undecidable whether an unobserved property would hold
    Given a function whose determinism the suite never put to the test
    When someone asks whether it is in fact deterministic
    Then the audit reports that nobody looked
    But it cannot answer the question itself, because deciding it would mean running the function again and that is a property of the audit rather than of the suite
