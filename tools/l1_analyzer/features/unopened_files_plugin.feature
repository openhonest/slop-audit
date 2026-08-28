Feature: The plugin that records every file the suite opens

  Loaded into the repository's own test run. The interpreter reports each open, so the
  answer is watched rather than inferred from the source.

  Scenario: undecidable whether a file opened during collection belongs to a test
    Given a file opened while a test module is being imported
    When the plugin records it
    Then it is recorded, because the hook is installed before collection and cannot tell import from execution
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: watcher gives the hook the interpreter calls on every open
    Given somewhere to record what was opened
    When watcher builds the hook and the interpreter calls it
    Then every open of a named file is recorded
    But it takes its store rather than reaching for one, because a module-level set is shared state and this project's own check reports that

  Scenario: pytest_configure starts watching before the suite collects
    Given the test run is starting
    When pytest_configure installs the hook
    Then a file opened while a test module is imported is counted
    But the store rides on the run's own configuration object rather than on the module, for the same reason the other probe plugin does it that way

  Scenario: pytest_unconfigure hands back what the run opened
    Given the test run is ending
    When pytest_unconfigure writes what was recorded
    Then the caller reads the list of files the suite opened
    But a run killed before this point reports nothing at all, which the caller reads as a run it could not watch rather than a suite that opened no files

  Scenario: write_opened writes what was opened where the caller asked
    Given what was opened and somewhere to put it
    When write_opened writes the list
    Then it says whether it wrote
    But no destination means nobody asked to watch this run, since the plugin is registered by name and also loads in runs that are not audits, where writing would overwrite one answer with another
