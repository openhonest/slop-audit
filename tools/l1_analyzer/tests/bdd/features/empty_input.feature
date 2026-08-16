Feature: What every measure says when it read nothing
  Each indicator, check and predicate in this analyzer can be handed an input
  it cannot read: an empty repository, a file of zero length, a language with
  no rule, a set with no members. This feature states what each one must answer
  in that case, and the answer is never a verdict.

  The rule these scenarios enforce, in one sentence: a measure that examined
  nothing must not report a property. "Not measured" and "measured and clean"
  are different facts, and every scenario below is a place they were once
  spelled the same way.

  These scenarios are written from the intended behaviour, not from the
  implementation. Where the code disagrees, the code is wrong.

  Background:
    Given the analyzer is available via import

  @l1-12 @dead-code
  Scenario: A repository of empty files is not healthy, it is unmeasured
    Given a repository containing two Python files of zero length
    When I run the dead-code analysis on it
    Then the value is "n/a"
    And the band is "n/a"
    And the details say that no production lines were read
    # Today this reports value 0.0 and band Healthy over production_loc 0.
    # A ratio whose denominator is zero is not a ratio, and Healthy is the
    # field a reader looks at.

  @l1-12 @dead-code
  Scenario: A repository the analysis did read, and found nothing in, is healthy
    Given a repository containing one Python file with a referenced function
    When I run the dead-code analysis on it
    Then the value is a number
    And the band is "Healthy"
    # The control. Without this scenario the one above could be satisfied by
    # refusing everything, which is a different lie.

  @vacuity
  Scenario: The vacuity checker reports the languages it actually read
    Given a repository containing no Python source at all
    When I run the vacuity check on it
    Then the reach reports zero files read
    And the reach reports zero languages read
    # Today languages_read is the constant 1, so the checker reports having
    # read one of nine languages having opened no file. That number lives in
    # the reach, whose whole purpose is to stop a zero being read as a pass,
    # and it is the one number in it that was never measured.

  @vacuity
  Scenario: The vacuity checker has no affirmative field to fabricate into
    Given a repository containing one Python file with no vacuous path
    When I run the vacuity check on it
    Then the result has exactly the keys "findings" and "reach"
    And the rendered report contains none of the words "Healthy", "clean", "pass", "OK"
    And the rendered report states the reach beside the count

  @state-census
  Scenario: A count that cannot be recovered is None, never zero
    Given a repository in a language the census has no spec for
    When I take the census
    Then the declared count is None
    And the visited fraction is None
    # A confident zero would let an unread repository report a full
    # denominator and pass.

  @state-census
  Scenario: A record the reader read in full does not score as unread
    Given a Python file with one TypedDict of five fields and one module-level dict
    When I take the census beside what the classifier admitted
    Then the visited fraction is 1.0
    And the judged fraction is less than 1.0
    # Six declarations, one piece of state, nothing missed. The single ratio
    # that preceded these two reported 0.167 and was read as coverage.

  @state-bounds-filters
  Scenario: A predicate with nothing to examine says so, rather than yes
    Given a Python class whose attribute has no membership test on it
    When I ask whether the result is invariant under presence
    Then the answer is that the question does not apply
    And the answer is not the same value as "invariant"
    # Today this returns True having examined nothing, because the loop over
    # membership-gated methods is empty and the function falls through to a
    # bare return True. Two rules downstream depend on that vacuous answer.

  @state-bounds-filters
  Scenario: A predicate that examined a membership gate answers about it
    Given a Python class whose accessor returns None when the key is absent
    When I ask whether the result is invariant under presence
    Then the answer is that the result varies with presence
    # The control for the scenario above. Presence IS the answer here, so the
    # finding must stand.

  @state-partition
  Scenario: State with no finite reach is one class, not zero
    Given a list of reaches containing no finite reach
    When I roll them up into a partition
    Then the partition has one class
    And the partition is counted
    # An empty reaching set means every value behaves alike, which is one
    # class. Zero classes would be a different and false claim.

  @state-partition
  Scenario: A partition whose size cannot be recovered can never be accused
    Given a partition whose count could not be recovered
    When I ask whether it is coarse
    Then the answer is no
    # An unknown count is a limit of ours, and the coarse verdict is a claim
    # about the audited code.
