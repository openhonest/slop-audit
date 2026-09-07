Feature: sweep_pool — how a whole-repository sweep runs on more than one core
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  A module is proven by appending a test to that module's own source file, compiling the
  crate, running it, and putting the file back. Two workers in one checkout would restore
  each other's files mid-compile, and cargo locks the target directory besides, so
  parallelism here is a question about directories rather than about threads.

  Nothing here knows what a proof is or how one is judged.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Nothing here can tell whether a copy shares its blocks with the original
  # after the fact: the copy command's exit status is all there is, and a filesystem that
  # accepts the flag and copies anyway would be recorded as copying by reference.
  @undecidable @not-implemented
  Scenario: undecidable whether a copy the filesystem accepted actually shares its blocks
    Given a filesystem that accepts the copy-by-reference flag without honouring it
    When checkouts_for records how the copies were made
    Then it is recorded as unread rather than reported as sharing blocks it may not share, so a reader is not told a cost that was never checked
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: workers_for settles how many workers this sweep will actually run
    Given how many were asked for and how many modules there are to prove
    When workers_for compares the two
    Then it never returns more workers than there is work, because a worker with no module still costs a checkout and asking for eight against three modules would copy a repository five times to do nothing
    And a pool of nothing raises, since zero would run nothing and report it as a sweep that found nothing
    But the ceiling in practice is the core count rather than the disk: a core-only checkout with a warm build directory is about 6 GB, so a 270 GB volume holds more copies than any box has cores

  Scenario: share_out deals the modules out among the workers
    Given the sweep's modules and how many workers there are
    When share_out deals them round robin
    Then every module lands in exactly one share, because a module in two is proven and counted twice and a module in none is a gap nobody attempted while the ceiling counted it as spent
    And round robin rather than contiguous blocks, since the work arrives in roughly source order and neighbouring modules in one crate build in similar times, so dealing them keeps one worker from drawing every slow one
    But a worker with an empty share is dropped rather than started

  Scenario: checkouts_for gives each worker a directory of its own to prove in
    Given the repository, how many workers there are, and where the copies may live
    When checkouts_for makes them
    Then a single worker proves in the repository itself, since copying a checkout to hand it back to itself costs the disk for nothing
    And every worker gets a copy once there is more than one, the first included, so a parallel sweep never edits the repository under audit
    And that is what makes an interrupt harmless: a module is proven by editing its own source file and putting it back, a hard kill skips the putting back, and a copy is disposable by construction while a repository is not
    But how the copies were made is recorded, because eight workers is nearly free on a filesystem that copies by reference and the full size of the checkout on one that does not, and a reader told only the number cannot tell them apart

  Scenario: copy_checkout makes one copy of the repository and says how it was made
    Given the repository and where the copy is to go
    When copy_checkout asks the filesystem to share the blocks, then to copy them
    Then a filesystem that copies by reference says so, and one that does not is copied byte for byte and says that instead
    And the destination is cleared first every time, because a copy that died part way leaves a directory behind and the next thing tried against it fails on the directory existing, which reports the wrong cause
    But a copy that cannot be made at all answers with nothing rather than raising, since by the time the pool is built the sweep has bought every proposal and a traceback would throw that away

  Scenario: _copy_tree is the last resort where no cp on this machine would do it
    Given the repository and a destination no cp could produce
    When _copy_tree copies the tree itself
    Then a copy that succeeds is byte for byte, which is what a fallback with no filesystem help can be
    But a copy that fails leaves nothing behind and answers with nothing, for the reason copy_checkout gives: one directory that will not copy must cost a worker rather than the run

  Scenario: discard_checkouts removes what the sweep copied and never the repository
    Given the checkouts a sweep was given
    When discard_checkouts clears up
    Then every copy is removed, since a worker's copy left behind after a day-long sweep is gigabytes somebody has to find
    But a sweep that copied nothing removes nothing, because its one path is the repository itself

  Scenario: pool_detail says what the pool was and what it cost
    Given the number of workers, the number of copies and how they were made
    When pool_detail writes the sentence the report carries
    Then it is said whether or not the pool was one, so a sweep that wanted eight workers and got one does not read like a sweep that asked for one
    And a parallel sweep says the repository itself was never edited, which is the fact a reader wants after an interrupt
