Feature: callmap — the four-column call-stack map, emitted as a .hd file
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  `.hd` is the Honest Framework's own plain-text architecture spec, and the grammar here
  is that one rather than a private dialect. Roles are function prefixes: boundary_in
  reads a source, orchestrator composes, a bare fn is pure, boundary_out writes a target.

  The violation the map exists to show is a write sitting in the pure lane. It is emitted
  that way on purpose rather than quietly moved to column four, because the point is to
  show the write where nothing should write.

  The charge rests on the watched run rather than on a guess, so a function nobody watched
  is not accused at all.

  Scenario: _open_writes says whether an open was opened for writing
    Given a call to open with or without a mode
    When _open_writes reads the mode
    Then w, a, x and + are writes
    But a call with no mode is a read, as it is in Python, rather than an unknown

  Scenario: _made_here names what the function itself created
    Given a function definition
    When _made_here walks its locals and its nested definitions
    Then every name the function bound comes back
    But writing to something you made is not outbound I/O, and a wrapper setting an attribute on the closure it had just built was filed in column four on that basis

  Scenario: effects names the sources a function reads and the targets it writes
    Given a function definition
    When effects walks its calls, its globals and its attribute reads
    Then each source and target is named once, because side_effect reads "filesystem" tells a reader what the boundary is and a count would only say how often
    But a setattr on a local names nothing, since the object does not outlive the call

  Scenario: invocations names the sibling functions this one calls
    Given a function definition and the names its module defines
    When invocations walks its calls
    Then only functions of this same module are listed, since a call to a library is a fact about the library
    But its own name is left out, because recursion is a fact about the function rather than about what it composes

  Scenario: role_of places a function in one of the four columns
    Given what a function reads, what it writes and what it invokes
    When role_of reads them
    Then a write outranks a read, since the map's whole point is where the writes are
    But a function that neither reads, writes nor composes is pure, which is the column with no prefix

  Scenario: _first_mutable names the argument an observed mutation is about
    Given a function definition whose watched run showed it changing an argument
    When _first_mutable reads the signature
    Then the argument is named from the declaration rather than from the observation
    But a function with no arguments names none, and the write is then attributed to the module instead

  Scenario: classify places every function and marks the demonstrated violations
    Given the module tree and what the watched run showed
    When classify reads them together
    Then an observed mutation names the argument written and an observed impurity names the module
    But a function nobody watched is not accused, since silence about a property is not evidence of a violation

  Scenario: _stanza writes one function as one line of .hd
    Given one classified function
    When _stanza renders it
    Then the prefix, the signature, the side effects and the invocations come back as one line
    But a violation keeps the bare fn prefix with the write still attached, because moving it to boundary_out would make the file describe an honest module

  Scenario: render writes the module as a .hd file in column order
    Given every classified function, the module name and the layer
    When render writes the file
    Then the four columns appear in order with their headings
    But a layer nobody declared is named as undeclared, since a layer is an architectural intent and no reading of the source decides it

  Scenario: read_roles reads the columns back out of a rendered file
    Given a rendered .hd file
    When read_roles parses its function lines
    Then each function comes back with the column it was placed in
    But a format nobody can read back is a report rather than a spec, which is what this direction exists to show

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A layer is an architectural intent. Nothing in the source distinguishes a foundation module
  # from a domain one, and emitting a guess would put an invented fact in a file whose whole job
  # is to state facts.
  @undecidable @not-implemented
  Scenario: undecidable which layer a module belongs to
    Given a module whose functions have all been placed in their columns
    When someone asks which of foundation, data, domain, ui or tooling it is
    Then the file records that nobody declared one
    But nothing here can decide it, because a layer is a statement of intent and the source carries no trace of intent
