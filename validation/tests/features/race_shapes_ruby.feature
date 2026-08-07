Feature: Non-atomic class-variable update in Ruby
  A class variable is shared across every instance and thread. A compound update on one
  (`@@count += 1`) is several bytecodes, so it loses updates under Thread even with
  CRuby's GVL, and JRuby/TruffleRuby run it in true parallel. Flagged only when the file
  uses Thread, and only for class variables; a local increment is not flagged.

  Scenario: A class-variable compound update under Thread is flagged
    Given a threaded Ruby class that does @@count += 1
    When I scan the Ruby file for race shapes
    Then a non-atomic read-modify-write is reported on "@@count"

  Scenario: The same class-variable update with no Thread in the file is not flagged
    Given a Ruby class that does @@count += 1 with no threads
    When I scan the Ruby file for race shapes
    Then no non-atomic read-modify-write is reported

  Scenario: A local compound update under Thread is not flagged
    Given a threaded Ruby method that increments a local variable
    When I scan the Ruby file for race shapes
    Then no non-atomic read-modify-write is reported
