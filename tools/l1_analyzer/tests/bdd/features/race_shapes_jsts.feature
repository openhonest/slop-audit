Feature: Async TOCTOU in JavaScript and TypeScript
  One event loop means the race is not a data race but an async time-of-check-to-time-of-use:
  a check on shared instance state, then an `await` that yields the loop to another task,
  then a mutation of the same state. A concurrent invocation can slip through the awaited
  gap between the check and the write. Restricted to this.-rooted state; the `await` in the
  body is the concurrency, so a synchronous check-then-act is not flagged.

  Scenario: A check, an await, then a write of the same shared state is flagged (TypeScript)
    Given a TypeScript method that checks this.store, awaits, then writes this.store
    When I scan for async TOCTOU
    Then an async TOCTOU is reported on "this.store"

  Scenario: The same shape without an await is not flagged (TypeScript)
    Given a TypeScript method that checks this.store then writes it with no await
    When I scan for async TOCTOU
    Then no async TOCTOU is reported

  Scenario: The async TOCTOU shape is caught in JavaScript too
    Given a JavaScript method that checks this.store, awaits, then writes this.store
    When I scan for async TOCTOU
    Then an async TOCTOU is reported on "this.store"
