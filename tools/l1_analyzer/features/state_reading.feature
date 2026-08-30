Feature: What a reading of a repository's state looks like when it comes back

  Three records, split out of the reader that produces them when that file crossed a
  thousand lines and this tool's own god-file rule failed the commit. They are the shapes a
  caller holds rather than the walk that fills them, and the card reads eight of their
  fields.

  Scenario: undecidable whether a field a caller never reads is still true
    Given a record carrying a field nothing in this repository reads
    When a reader asks whether that field is accurate
    Then nothing here can say, because a shape is checked where it is read and an unread field is never checked
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it
