Feature: Shared mutable static state in Java
  A non-final static field of a mutable, non-thread-safe collection is shared class-level
  state reachable from every thread with no synchronization on the field. Thread-safe
  (ConcurrentHashMap, CopyOnWrite...) and synchronized (Vector, Hashtable) types are safe
  by design and are not flagged; a final field or an instance field is not flagged.

  Scenario: A non-final static HashMap is flagged
    Given a Java class with a non-final static Map field
    When I scan the Java file for race shapes
    Then a static mutable field is reported on "cache"

  Scenario: A final static field is not flagged
    Given a Java class with a static final Map field
    When I scan the Java file for race shapes
    Then no static mutable field is reported

  Scenario: A non-static instance field is not flagged
    Given a Java class with a non-static Map field
    When I scan the Java file for race shapes
    Then no static mutable field is reported

  Scenario: A thread-safe static collection is not flagged
    Given a Java class with a static ConcurrentHashMap field
    When I scan the Java file for race shapes
    Then no static mutable field is reported
