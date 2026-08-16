Feature: Concurrency prove loop (locate then demonstrate)
  The runtime prove stage turns a located hazard into a demonstrated one, on Umbra's
  terms: the model only fills an already-located gap, and every generated test is run
  under a concurrency runner and retained only if it genuinely fires a race. A hazard the
  loop cannot demonstrate is never claimed. Both the model and the execution are injected
  here so the honesty property is tested directly.

  Scenario: A generated test that fires a race is demonstrated and retained
    Given a located hazard and a model that writes a test for it
    And the generated test fires a race when run
    When I run the prove loop
    Then the hazard is demonstrated
    And the proof is retained

  Scenario: A generated test that runs clean is not claimed
    Given a located hazard and a model that writes a test for it
    And the generated test runs clean when run
    When I run the prove loop
    Then the hazard is not demonstrated
    And the proof is not retained

  Scenario: With no model available the hazard is not generated, never falsely claimed
    Given a located hazard and no model available
    And no test is generated, so the runner is never reached
    When I run the prove loop
    Then the hazard is not generated
    And the proof is not retained

  Scenario: When the toolchain cannot run the test the result is not-run, not clean
    Given a located hazard and a model that writes a test for it
    And the generated test cannot be built or run
    When I run the prove loop
    Then the hazard is not run
    And the proof is not retained

  Scenario: The production loop delegates through the honesty gate
    Given a located hazard and a model that writes a test for it
    And the generated test fires a race when run
    When I run the production prove loop with those injected
    Then the hazard is demonstrated
    And the proof is retained
