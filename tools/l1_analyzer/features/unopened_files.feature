Feature: Files the code reads that the test run never opened

  Two projects reported the same failure a day apart, from repositories with no shared
  code. In both, the tests passed while the code was broken, because the tests were handed
  a stand-in rather than the real thing. Coverage counted the branches as reached, and
  repairing the defects moved that number down.

  Scenario: undecidable whether a file the run opened was opened for the right reason
    Given a file the suite opened once, in a test that did nothing else with it
    When this check reads the list of files the run opened
    Then it records the file as opened, because that is what it watched
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: analyze reports the files the production code names that the run never opened
    Given a repository, its language, the Python that runs its suite, and a time limit named by the caller
    When analyze collects the files the code names, runs the suite with the watcher loaded, and takes the difference
    Then it returns the files that were named and never opened, which is the finding
    And it carries no band, because an empty list does not mean the tests are good and there is nothing here to grade
    And a suite that could not be run returns nothing decided with the reason, never an empty list, since a clean result on a run that never happened is the failure this instrument names
    But a language other than Python is answered with nothing decided, because the watcher is an interpreter hook and every other language needs its own

  Scenario: files_on_disk gives every file in the repository, by path and by bare name
    Given a repository
    When files_on_disk walks it, skipping dependencies and this run's own leavings
    Then it returns each file both by its path from the root and by its bare name
    But it keeps both spellings, because the code that reads a file may name it by path where the test that opens it names it bare, and a reader knowing only one would keep reporting a file after somebody fixed it

  Scenario: names_a_file says which file a string names, or refuses to guess
    Given a string from the source, and the repository's files by path and by name
    When names_a_file looks for a file that string could be
    Then it returns the file where the string is a path from the root, or where exactly one file carries that bare name
    And it returns nothing where no such file exists, which is what drops a bare suffix out of an f-string
    But a bare name several files share is refused with a reason rather than guessed at, since the string cannot tell them apart and neither can this

  Scenario: strings_in gives every string literal in one source file
    Given the text of a source file
    When strings_in parses it and collects the literals
    Then it returns them all, whatever call each one feeds
    And a file that does not parse returns nothing rather than raising
    But it follows no call, because one adopter builds a path from a default argument to an environment lookup sixty lines above the read, and a reader that followed the read found nothing

  Scenario: files_the_code_names gives the files this repository's production source names
    Given a repository
    When files_the_code_names offers every literal in every production file to names_a_file
    Then it returns the files those literals name, and separately the names it refused to decide
    And it returns both every time, since a flag choosing between one list and two had a default, and this package's own check said a default absorbs the caller's omission while a flag that changes the shape of the answer makes every caller read the signature
    But it reads no test source, because a file only the tests name is a fixture and reporting it would ask an author to test their own fixture

  Scenario: opened_during watches what one piece of work opens
    Given something to run and somewhere to record what it opened
    When opened_during installs an interpreter hook and runs it
    Then it returns every file opened while that work ran
    But it is for watching the watcher, since the suite runs in its own process where the plugin installs the same hook

  Scenario: _run_the_suite runs the repository's tests with the watcher loaded
    Given a repository, the Python to run it with, somewhere to record, and a time limit
    When _run_the_suite starts the suite with the watcher plugin
    Then it says whether the run reported what it opened
    But a suite that did not run comes back with the reason, because a suite that did not run is not a suite with nothing to report

  Scenario: _refusal gives an answer with no number and no list
    Given a reason nothing could be looked at
    When _refusal builds the result
    Then it carries the reason and no findings at all, with the list absent rather than empty
    But absent and empty are different facts here, since a caller reading an empty list as nothing to report would be reading a run that never happened

  Scenario: _ours says whether a path is this repository's own code
    Given a path
    When _ours checks each component of it against the directories that hold somebody else's code or this run's leavings
    Then it answers no for a dependency, a cache, or a build directory
    And the answer is the same whether the path was spelled from the repository root or from the filesystem root, since written as text with slashes it was right for one and wrong for the other, and the first run on this package reported five findings that were all binaries in its own virtual environment
    And a directory merely named like one of them, such as a tools directory whose name begins the same way, is this repository's own
    But it names those directories in one place, so the walk and the filter cannot come to disagree about what belongs to this repository
