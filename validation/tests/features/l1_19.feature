Feature: L1.19 Decision-space coverage
  Of the enumerable decision branches, what percent are exercised by the test
  suite, measured by running the suite under branch tracing. (An earlier draft
  asserted 95/50/30 against fabricated fixtures. These use a real 4-arm classifier
  and the branch counts the tracer actually reports: 4 arms are 6 branches, so
  exercising 4/3/2 arms is 100/83.3/50 percent.)

  Scenario: All decision branches exercised is Healthy
    Given a 4-arm classifier whose tests exercise 4 of 4 arms
    When I compute L1.19
    Then L1.19 is 100.0
    And the band is Healthy

  Scenario: Most but not all branches exercised is Not Healthy
    Given a 4-arm classifier whose tests exercise 3 of 4 arms
    When I compute L1.19
    Then L1.19 is 83.3
    And the band is Not Healthy

  Scenario: Half the branches exercised is Slop
    Given a 4-arm classifier whose tests exercise 2 of 4 arms
    When I compute L1.19
    Then L1.19 is 50.0
    And the band is Slop
