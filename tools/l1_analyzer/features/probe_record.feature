Feature: probe_record — how a plugin watching a suite from inside it hands its record back
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: hand_back writes what the run recorded, or nothing when nothing was watched
    Given pytest's config, the name the record hangs off it under, where to write, and how this record wants preparing
    When hand_back reads the record off the config
    Then a run whose configure never installed its hook writes no file at all, because the reader treats a missing file as a run it could not watch and an empty list as a run that watched and saw nothing
    And a run nobody asked to watch writes nothing either, since both plugins load in runs that are not audits and a leftover path would overwrite one answer with another
    But a run that watched and saw nothing does write its empty list, because that is a measured answer and it has to reach the reader as one

  Scenario: write_record writes a prepared record where the caller asked
    Given a record already in the shape its own probe wants and the path to write it to
    When write_record is called
    Then it writes and says it wrote, and it says so for an empty record too
    But no destination means nobody asked to watch this run, and it writes nothing and says so

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built.
  @undecidable @not-implemented
  Scenario: undecidable a record holding a value no JSON encoder can write
    Given a record carrying a value the encoder cannot serialise, which a probe watching arbitrary code can collect
    When write_record hands it to the encoder and the encoder refuses
    Then the run says the record could not be written rather than leaving a partial file that reads as a complete answer
    And the type it could not write is offered for collection: the type name alone, with no value and no path
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
