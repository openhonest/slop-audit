Feature: Structural race-condition shapes in Python (free-threading)
  Python has no borrow checker, so shared mutable state under threads is exposed the
  moment the GIL is gone. Beyond the unguarded-shared-state surface, the meter locates
  the check-then-act (TOCTOU) shape on a shared module-level container: a membership
  check followed by a mutation of the same container. Only surfaced when the file
  actually uses threads, and restricted to module-level shared containers.

  Scenario: A check-then-act on a shared dict under threads is flagged
    Given a threaded module that checks then writes a shared dict
    When I scan the Python file for race shapes
    Then a check-then-act is reported on "CACHE"

  Scenario: The same check-then-act without any threading is not flagged
    Given a single-threaded module that checks then writes a shared dict
    When I scan the Python file for race shapes
    Then no check-then-act is reported

  Scenario: A check-then-act on a purely local dict is not flagged
    Given a threaded module that checks then writes a local dict
    When I scan the Python file for race shapes
    Then no check-then-act is reported

  Scenario: A non-atomic compound update on a shared global is flagged
    Given a threaded module that does COUNTER += 1 on a global
    When I scan the Python file for race shapes
    Then a non-atomic read-modify-write is reported on "COUNTER"

  Scenario: A local counter increment is not flagged
    Given a threaded module that increments a local counter
    When I scan the Python file for race shapes
    Then no non-atomic read-modify-write is reported
