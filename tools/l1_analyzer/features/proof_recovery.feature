Feature: proof_recovery — putting back a file an interrupted proof run was editing
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it. Here it
  # is the reader who never runs the tool again: their file keeps the proof, nothing here ever
  # runs to put it back, and nothing knows. Git holds the original for them, and this module
  # cannot tell whether they ever look.
  @undecidable @not-implemented
  Scenario: undecidable a checkout whose owner never runs the tool again
    Given a run killed between the write and the restore, on a repository nobody audits a second time
    When restore_interrupted_proof is never called, because nothing calls it but the next run
    Then the customer's file keeps the proof, and no sentence anywhere says so
    And the record sits in the temp directory until the machine clears it
    But git holds the original, so the repair exists even where this module cannot reach it

  Scenario: recovery_record says where one checkout's in-flight edit is written down
    Given the path of the repository being proven
    When recovery_record names a file outside that repository, keyed by its resolved path
    Then a later run of the same checkout finds the record its earlier run left
    And two checkouts proven side by side cannot overwrite each other's record
    But it is outside the tree, because a record inside it is a second thing left behind and a clean would delete the only copy of the original

  Scenario: restore_interrupted_proof puts back a file an earlier run was part way through editing
    Given a checkout whose source file carries a proof and a record holding the original bytes
    When restore_interrupted_proof reads the record and writes the original back
    Then the customer's file is byte for byte what it was, and the sentence names which file was restored
    And the record is removed, because one left lying about would later overwrite whatever the author wrote next
    But a record it cannot read is reported and kept rather than deleted, since the only copy of somebody's file may still be in it
