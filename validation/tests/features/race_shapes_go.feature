Feature: Goroutine captured-write races in Go
  Go has no borrow checker and its maps are not concurrent-safe, so a `go func(){...}()`
  that writes to a variable captured from the enclosing scope with no synchronization is
  a genuine data race - what `go test -race` catches. A write to a name not declared
  inside the closure is a captured write; a lock or a channel send in the body downgrades
  it to a candidate (the guard is unproven).

  Scenario: A goroutine writing a captured variable and map is flagged
    Given a Go function that spawns a goroutine writing captured `total` and `m`
    When I scan the Go file for race shapes
    Then a goroutine shared write is reported on "total"
    And a goroutine shared write is reported on "m"

  Scenario: A goroutine writing only its own locals is not flagged
    Given a Go function whose goroutine writes only variables it declares
    When I scan the Go file for race shapes
    Then no goroutine shared write is reported

  Scenario: A goroutine that holds a lock is a candidate, not review
    Given a Go function whose goroutine locks a mutex before writing captured state
    When I scan the Go file for race shapes
    Then the goroutine shared write is a candidate
