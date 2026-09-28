Feature: test_regions — the parts of a production file that are somebody's tests
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Eight indicators measure production code only, and every rule that decides what is a test
  works on a path: a directory named test or tests, a file whose stem ends in _test or .spec.
  Rust puts its unit tests inside the file they test, so no path names them. Counted on 68
  crates, 2,532 of uuid-rs/uuid's 9,821 lines are inside a test module and 4,300 of the Rust
  port's 21,633 are. Those numbers were not wrong about what they measured; they answered a
  different question for Rust than for the other eight languages, and nothing said so.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a
  # verdict. Here it is a whole file of tests sitting under src, declared `#[cfg(test)] mod
  # tests;` from the parent file, with no marker of any kind in the file itself. Deciding it
  # needs a module declaration followed from one file to another, which no reader in this
  # package does. Rayon, indexmap and winnow all write their tests that way: 851 test
  # functions in 54 files, about a third of the test code inside src.
  @undecidable @not-implemented
  Scenario: undecidable whether a file of tests under src is production code
    Given a crate whose parent module declares "#[cfg(test)] mod tests;" and whose tests live in their own file
    When blanked reads that file
    Then it finds no attribute marking anything, because the marker is in the other file
    And the file's test functions are measured as production code
    But the module says so and counts them, so the gap is a number rather than a silence

  Scenario: marks_a_test reads a cfg predicate instead of looking for the word test
    Given one attribute written above an item
    When marks_a_test decides whether the item exists only for tests
    Then "#[cfg(test)]", "#[cfg(all(test, unix))]" and "#[test]" all say yes, along with the async runtimes' own spellings of a test
    And "#[cfg(any(test, feature = \"std\"))]" says no, because any means the item ships whenever either condition holds
    But the two mistakes are not symmetric, so a predicate this cannot read is left alone: missing a test region keeps the old answer, and excluding a production item deletes somebody's code from the measurement

  Scenario: blanked replaces every test region with spaces and counts the lines it emptied
    Given the bytes of a file and the extension that says which language wrote it
    When blanked empties the test regions
    Then the file comes back the same length with its newlines in place, so a reader that reports line 391 still means the author's line 391
    And the count comes back with the bytes, because an emptied line and a line the author left blank are the same bytes afterwards
    But eight of the nine languages have no row in the table and come back untouched, which is the finding rather than an omission

  Scenario: _regions spans the whole run of attributes and the item they mark
    Given an item carrying several attributes, where the one marking it a test need not be next to it
    When _regions collects the byte spans
    Then the span starts at the run's first attribute and ends at the item, so no attribute is left in front of nothing and no function is left bare
    And a comment written between an attribute and the item it marks stays inside the region, because reading it as the marked item left the function bare
    And it does not read below a region, since a test module's own functions carry their own attributes
    But an attribute run with no item after it is walked into rather than spanned, because there is nothing for it to mark
