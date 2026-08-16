Feature: interleaving_robustness — which of the flagged concurrency surface no model checker exercises
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today classify has no third answer: one word search files the file under
  # modeled-elsewhere when the stem hits and under unmodeled when it misses, and both go out
  # as a verdict.
  @undecidable @not-implemented
  Scenario: undecidable exposed surface whose module name the word search can neither confirm nor deny
    Given an exposed-surface file whose module stem is an ordinary Rust word such as state or mod, so a mention of it in the modelled text says nothing about whether a model drives that file
    When analyze compares the surface against the modelled text
    Then it is recorded as unread rather than filed under modeled-elsewhere or unmodeled, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _module_stem gives the module name a Rust file defines
    Given a path relative to the repository, such as storage/shared_wal_coordination.rs
    When _module_stem strips the directories and the extension
    Then it returns shared_wal_coordination, which is the word a mod or use line in a model test would name

  Scenario: classify splits the flagged surface by whether a model touches it
    Given the flagged surface files, the set of files that carry a model marker, and the concatenated text of every modelled file
    When classify sorts the surface and places each file in exactly one of three lists
    Then a file that carries a marker itself is modeled-in-file, a file whose module name appears anywhere in the modelled text is modeled-elsewhere, and everything left is unmodeled
    And the modeled-elsewhere test is a whole-word search over that one blob of text, so a common module name can match a mention that has nothing to do with the surface, which is why the class is called a weak signal rather than proof
    But nothing here reads a file, so the answer is fixed entirely by the three arguments

  Scenario: _na builds the refusal this meter hands back when it will not measure
    Given the reason it is declining
    When _na assembles the result
    Then every list comes back empty, the verdict, the value and the band all read n/a, and the reason is carried in the details

  Scenario: analyze reports how much exposed concurrency surface no loom or shuttle model touches
    Given a repository and a language name
    When analyze asks the thread-surface meter for the surface and then reads every Rust file for a loom or shuttle marker
    Then it returns the unmodeled files as the finding, with the modelled-elsewhere and modelled-in-file lists beside them and a verdict of unmodeled when any file is unmodeled
    And it refuses for any language but Rust, and refuses again when the surface meter itself read no source, passing that refusal through rather than inventing a reading of its own
    But a repository with no exposed surface returns clean, and the band is n/a on every path, so this meter never grades anything
