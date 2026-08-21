Feature: card — the Slop Audit scorecard a reader actually sees, built once for both the CLI and the website
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _honest_code shows L1.21 with the count of clauses it decided
    Given a panel that carries an Honest Code conformity entry
    When _honest_code reads it
    Then the share, the band and the clauses with findings reach the card
    But the count of DECIDED clauses goes with them, since a reader would otherwise take a hundred percent to mean nineteen held when it can mean sixteen held and three were never looked at

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. This module is the counter-example in the set. It is already honest about
  # an absent measurement: _value_str and _metric print n/a and No data rather than a bare zero,
  # _detail reads the basis rather than re-deriving it from the counts, precisely because
  # zero-zero-zero is what an unread repository and a clean one have in common, and build_card
  # withholds the path-cover figure from an ungraded card. Its one silent case is its own copy.
  # Today _t returns the key for a key CARD_COPY does not hold, so a sentence nobody wrote prints
  # to the reader as a raw dotted key instead of raising.
  @undecidable @not-implemented
  Scenario: undecidable a copy key the card's own table does not hold
    Given a section asking for a sentence under a key absent from CARD_COPY, such as a verdict or band spelling added after the copy table was written
    When build_card renders that section and _t looks the key up
    Then it is recorded as unread rather than returned as the key itself, so a card that prints a sentence means the sentence was written and never that the lookup missed
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _t looks up one piece of card copy and fills its fields in
    Given a copy key and any values the sentence needs
    When _t finds the key in the card's copy table and formats the values in as text
    Then it returns the sentence the reader sees
    But a key that is not in the table comes back as the key itself, so a missing string prints as a bare key on the card instead of raising

  Scenario: _value_str prints one indicator's value with its unit
    Given one indicator result and the unit for that row
    When _value_str reads the value
    Then a measured value prints with its unit appended
    But a missing value, and the value n/a, both print as n/a with no unit, so a row that was never measured never shows a bare zero

  Scenario: _metric builds one row of the scorecard table
    Given one metric specification and the result for it
    When _metric assembles the row
    Then it returns the reader's label, the technical name, the value, the band, the plain band word, the meaning and the framework mapping
    But a result carrying no band reads n/a and the band word No data, never Clean

  Scenario: _metrics builds the rows for one group of the table
    Given a group's metric specifications and the whole results set
    When _metrics builds a row for each specification
    Then only the specifications the results actually carry become rows
    And a specification with no result is left out of the table rather than shown as an empty row

  Scenario: _culprits lists what limits the grade, by a different rule for each verdict
    Given the state findings, the verdict status and the coarse list
    When _culprits picks the list that matches the status
    Then a cannot card lists the provably unbounded findings, decision-drivers first
    And a coarse card lists the finite-but-unordered ones, capped at twenty-five with a count of the rest
    But every other status, including both na and can, returns an empty list and no overflow: with no verdict there is nothing to blame

  Scenario: _scoped_out reports what was set aside and never scored
    Given the bucketed set-aside paths and their reasons
    When _scoped_out totals the reason counts
    Then it returns the total, the reasons in one phrase, and the first twelve paths with a count of the rest
    But a zero total returns nothing at all, so the card shows no scoped-out section rather than an empty one

  Scenario: _interleaving_robustness gives the check a section a reader can see
    Given a panel that may carry the interleaving-robustness result
    When _interleaving_robustness reads its verdict and the files no model checker touches
    Then it returns the section's verdict, blurb and file list, so the finding reaches the card rather than only the JSON
    And a check that did not run, or returned n/a, gives nothing, because a heading over no reading is worse than no heading
    But the file list is capped like the thread sites, and the count it dropped is published beside it

  Scenario: _thread_surface builds the thread-safety section from the measured verdict
    Given the language and the analyzer results
    When _thread_surface reads the thread-surface verdict, its counts and its findings
    Then it returns the verdict, the exposed and review counts, the blurb, and the first twelve sites
    And every blurb is handed every field it might name, so a verdict added later cannot crash the card a reader is looking at
    But results with no thread-surface entry return nothing, and a verdict of n/a says the language was not analyzed rather than that it is clean

  Scenario: _detail chooses the paragraph under the headline, and splits the ungraded case three ways
    Given the status, the basis for it, the unbounded count, the path-cover figure, the counts and the census
    When _detail picks the paragraph
    Then an ungraded card says which of three things happened: no readable code, most of the state unfollowed, or none of the state read at all
    And the basis is read rather than re-derived from the counts, because zero-zero-zero is what an unread repository and a clean one have in common
    But a can card with no path-cover figure asks the reader to run the CLI instead of printing a number it does not have

  Scenario: _census_note discloses, on a card that DID grade, what the reader never reached
    Given the census of declared and visited state on a graded card
    When _census_note compares declared against visited
    Then it names how many declared places went unread and in which spellings, in the card's own voice but from the measurement's numbers
    But it returns nothing when the two counts are equal or either is missing, so the note appears only where something really was unread

  Scenario: _int passes an integer through and refuses everything else
    Given any value pulled out of the results
    When _int checks its type
    Then an integer comes back and every other type becomes nothing, so a string never reaches a formatted count
    But a boolean passes the check, because Python counts a boolean as an integer

  Scenario: _proofs collects the adoptable proofs from both prove loops onto one surface
    Given the analyzer results, which may carry concurrency outcomes, coverage proofs, both or neither
    When _proofs takes the demonstrated concurrency outcomes and the retained coverage proofs
    Then each entry carries the layer, the target, the location, the blurb, the detail and the runnable test source
    And only an entry that actually carries test source is listed, capped at twenty
    But a gap that was located and never proven appears here not at all, because this surface is for what execution settled

  Scenario: build_card assembles the whole scorecard model, and withholds the figures an ungraded card has not earned
    Given a slug, a language, the analyzer results and whether the test suite was run
    When build_card grades the state and assembles every section
    Then it returns the headline, the detail, the three counts, the culprits, the silence, both metric groups, the thread surface and the proofs
    And on an ungraded card the path-cover figure is withheld, because a precise run count over state nobody read is a coverage claim about nothing
    But running the tests and measuring them are kept apart: one says the CLI executed the suite, the other says a number came back

  Scenario: _copy_for_html turns the markdown links in the copy into anchors
    Given the whole card copy table
    When _copy_for_html rewrites each markdown link
    Then every link becomes an anchor that opens in a new tab
    And every other string passes through untouched

  Scenario: card_html renders the card as one standalone page
    Given a built card model
    When card_html renders the site's own template and inlines the stylesheet
    Then it returns a complete page titled with the repository slug, so the CLI and the website show the same card from one template
    And autoescaping is on for HTML, so only the copy fields the template marks safe carry markup

  Scenario: _silence_sites lists every place the analyzer stopped, with the reason in the reader's words
    Given the state findings
    When _silence_sites reads the recorded silence
    Then every site comes back with its file, line, state and a reason that says whose move is next
    But no silence record returns an empty list, and an empty list is what published a grade beside no named stopping point before this existed

  Scenario: _silence_lines writes the silence section of the Markdown card
    Given a built card
    When _silence_lines writes each site as one line under its heading
    Then a card refused a grade for silence prints the sites, which on that card are the whole report
    But a card with no silence record, or one whose record names no site, contributes no heading at all

  # The docstring says these lines are "empty on an ungraded card". The function itself always
  # emits the headline, the detail and the three counts; card_markdown is what withholds them,
  # by not calling this at all when the status is na.
  Scenario: _verdict_lines writes the state verdict and what limits it
    Given a built card and the pattern that strips markup out of the copy
    When _verdict_lines writes the grade sentence, the headline, the detail, the three counts and the culprits
    Then a graded card leads with its grade and the share of state that is finitely testable
    And the census note sits directly under the counts, because it qualifies them and a reader who meets it later has already read the counts as the whole story
    But an ungraded card still gets its counts written here; the decision not to print them belongs to the caller

  Scenario: card_markdown writes the whole card as Markdown for the CLI
    Given a built card
    When card_markdown writes the verdict, the silence, both tables, the thread surface and the proofs
    Then an ungraded card keeps every check that WAS measured and prints only the detail paragraph in place of the state verdict, rather than throwing eight measured results away
    And the footer names which run produced the card: the website that never executes code, the CLI that measured the suite, or the CLI whose runtime harness does not reach this language yet
