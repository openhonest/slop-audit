Feature: indicators — the Layer-1 indicator computations, L1.1 through L1.20
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today L1.17 globs ten extensions and no others, so a repository written in a
  # language nobody enumerated leaves the production file count at zero, and the guarded division
  # substitutes 0.0 for the figure it could not compute and bands that as Healthy.
  @undecidable @not-implemented
  Scenario: undecidable a source file in a language the L1.17 extension list does not name
    Given a repository whose production source carries none of the ten extensions the god-file scan globs for
    When _god_files measures the code lines of every candidate file
    Then it is recorded as unread rather than published as zero percent of files over a thousand lines under the healthy band, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: band maps one measured number onto a named threshold band
    Given a measured value, the healthy and slop thresholds for its indicator, and which direction is better
    When band compares the value against those two thresholds
    Then it returns Healthy, Not Healthy or Slop and nothing else
    And when higher is better the tests are inclusive, while when lower is better they are strict, so a value sitting exactly on a lower-is-better healthy threshold lands in the middle band
    But it has no answer for "not measured": every caller needing one writes the n/a band itself

  Scenario: _with_skipped discloses the files a reader could not open
    Given a detail sentence and the number of files that could not be read
    When _with_skipped joins them
    Then it returns the sentence with a note naming that count appended to it
    But at zero it returns the sentence unchanged, so a complete scan carries no note

  Scenario: _classify_file sorts one commit path into doc, code or other
    Given one repository-relative path taken from a commit
    When _classify_file reads the end of the lowercased path
    Then it answers doc, code or other
    And the code list holds configuration and data as well as source, so a change to a workflow file, a lock file or a container file counts as code
    But a path matching neither list, such as a licence or a makefile, is other, and no indicator downstream counts it as either

  # The three commit-mix percentages divide by every commit, including the ones classified as neither doc nor code.
  Scenario: compute_git_indicators reads the commit history into the first eight indicators
    Given a repository and the optional earliest and latest dates
    When compute_git_indicators reads the commit log with per-file line counts and closes each commit as it goes
    Then it returns the eight results L1.1 through L1.8, six of them a value and a band with no detail line at all
    And a commit that touched only files classified as other still raises the commit total while joining none of the three mix counts, so all three percentages are diluted by it
    But a merge commit carries no per-file lines in this log form and is invisible to every count here, and when the log fails or the date range holds no commits all eight come back as zero under the n/a band

  Scenario: _is_test_file decides whether one path is test code
    Given a path from anywhere in the repository
    When _is_test_file tries the directory rule, the dotted-project rule, the filename rule and the capitalised-stem rule in turn
    Then it answers yes as soon as one of them matches
    And the capitalised-stem rule reads the name in its original casing on purpose, so a production file whose name merely ends in the letters of the word test is not swept up with the real ones

  Scenario: _test_to_prod_ratio weighs the test tree against the production tree
    Given every source file in the repository, the test tree included
    When _test_to_prod_ratio splits the files by the test rule and counts lines on each side
    Then it returns the ratio of test lines to production lines, its band, and both line totals
    But with no production lines at all it refuses with n/a rather than divide, and a file it could not open is counted and disclosed

  Scenario: compute_config_indicators checks the repository root for three pieces of tooling
    Given the repository root
    When compute_config_indicators looks for a pre-commit configuration, counts the workflow files and looks for a container file
    Then it returns the three results L1.9, L1.10 and L1.11 from presence alone
    And it looks only at the root and only at those exact names, so the same tooling kept anywhere else reads as absent
    But L1.11 publishes the words "present and parameterized" on nothing more than a file existing, because parameterisation is never examined

  Scenario: _get_parser builds a parser for one configured language
    Given a language name
    When _get_parser builds a parser from that language's configured grammar
    Then it returns a fresh parser on every call, so no caller shares parse state with another
    But a name with no configured grammar raises, rather than falling back to a grammar nobody chose

  Scenario: detect_primary_language picks the language the repository is mostly written in
    Given a repository
    When detect_primary_language counts the files carrying each configured language's extensions
    Then it returns the language with the most files
    And test code, vendored code and generated code all count, because this count takes no scope
    But a repository holding nothing the configuration recognises returns unknown, and a tie is settled by the order the languages happened to be counted in

  Scenario: _run_external runs a tool and keeps all three facts about the run
    Given a command line and the directory to run it in
    When _run_external runs the tool
    Then it returns whether the tool ran at all, the exit status and the standard output, so a scanner exiting non-zero because it found something is never mistaken for a scanner that is not installed
    But standard error is dropped, so a tool that explains its failure only there explains it to nobody

  Scenario: compute_source_indicators drives every source-based indicator over one repository
    Given a repository, a language name or the word auto, whether tests may be executed, a timeout and the optional interpreter
    When compute_source_indicators resolves the language and calls each source indicator in turn
    Then it returns the whole L1.12 through L1.20 set in one map
    And the refinements, which are the state-bounds classification, path cover, thread surface and absolute paths, are added only when the caller asks for them, so a frozen pre-registered run gets exactly the original set
    But the resolved language name is stored in that same map under its own key while being a plain name and not a banded result, so every consumer has to know to step over it

  # The docstring says non-blank lines. The denominator is every line, blank ones included.
  Scenario: _trailing_whitespace measures how much of the source ends in whitespace
    Given every source file in the repository, the test tree included
    When _trailing_whitespace counts the lines that end in whitespace and are not themselves blank
    Then it returns that count as a percentage of all lines read, the blank ones among them, which sits below the rate its own docstring describes
    But a wholly blank line carrying trailing spaces is kept out of the count and left in the denominator

  Scenario: _data_literal_lines measures how much of a file is a large data table
    Given a parsed file and the container-literal node kinds for its language
    When _data_literal_lines walks the tree for literals spanning at least a dozen lines
    Then it returns the total number of lines those literals occupy
    And a literal that qualifies is not walked into, so a table nested inside a table is counted once rather than twice
    But a literal under a dozen lines is left alone and read as ordinary code

  Scenario: _code_line_count discounts data tables from a file's size
    Given the bytes of one file and its extension
    When _code_line_count subtracts the large data literals from the raw line count
    Then it returns the lines of that file which are logic rather than a table
    But an extension with no configured grammar returns the raw count undiscounted, and so does any parse failure whatsoever, because the failure is swallowed rather than reported

  Scenario: _god_file_reason says why a large file does not count against the repository
    Given a candidate file, the repository root and whether the repository is organised into packages
    When _god_file_reason applies the shared production scope and then the generated-code test
    Then it returns the reason the file is out of scope, or nothing at all when the file counts
    And the generated-code test lives here rather than in the shared scope rule, so excluding a machine-written file moves the god-file number and no other

  Scenario: _measure runs one measure and turns its refusal to answer into a named n/a
    Given a measure that may raise IncompleteCode rather than publish a value it has no basis for
    When _measure runs it
    Then the measure's result is returned unchanged when it answers
    And a refusal becomes value n/a, band n/a, and details carrying the INCOMPLETE CODE message
    But it is never a band or a number, because the reason the measure raises is that unmeasured must not be spellable as clean

  Scenario: _god_files measures how concentrated the repository is in oversized files
    Given every file carrying one of the large-file extensions
    When _god_files measures each in-scope file's code lines and counts the ones over a thousand
    Then it returns the share of production files over a thousand code lines, with any file over four thousand forcing the worst band outright
    And it names how many large files were scoped out and for what reason, so the drop is auditable instead of silent
    But a repository with no in-scope production file publishes zero percent and the healthy band, which is an empty denominator reported as cleanliness

  Scenario: _runtime_coverage hands the coverage question to the language's own harness
    Given a repository, a language, the timeout and the optional interpreter
    When _runtime_coverage looks up that language's coverage harness and runs the target repository's own suite
    Then it returns whatever the harness measured, unchanged
    But a language with no harness registered returns n/a naming itself, never a zero

  Scenario: _runtime_determinism hands the repeatability question to the language's own harness
    Given a repository, a language, the timeout and the optional interpreter
    When _runtime_determinism looks up that language's determinism harness and runs the suite repeatedly
    Then it returns the harness's verdict on whether repeated runs agree
    And the number of repeats is fixed in the harness table rather than chosen here, so no caller can ask for more or fewer
    But a language with no harness registered returns n/a naming itself

  Scenario: _decision_space_l19 prefers a measured coverage and never fabricates one
    Given a repository, a language, whether tests may run, the timeout and the optional interpreter
    When _decision_space_l19 enumerates the decision points statically and then tries the runtime harness
    Then it returns the measured coverage when the suite ran, and otherwise the static enumeration with the reason coverage was not measured appended to its detail
    And execution being switched off is stated as such, so a reader can tell a suite that could not run from one nobody asked to run

  Scenario: _test_determinism_l20 refuses rather than guess when tests may not run
    Given a repository, a language, whether tests may run, the timeout and the optional interpreter
    When _test_determinism_l20 is called with test execution switched off
    Then it returns the words "not run" under the n/a band, saying execution was disabled
    But with execution allowed it passes straight through to the language's determinism harness and adds nothing of its own

  Scenario: _annotation_name reads the name an annotation declares
    Given an annotation node from a parsed file
    When _annotation_name follows the grammar's name field as deep as it goes
    Then it returns the final segment of the annotation's name, so a fully qualified annotation reads as the bare word
    And it follows the field rather than splitting the node's text, which is what makes the qualified form come out right

  Scenario: _count_type_escapes_in_tree counts the escape hatches in one parsed file
    Given one parsed file and its language's escape vocabulary
    When _count_type_escapes_in_tree walks every node for escape tokens, suppression comments and suppression annotations
    Then it returns how many escapes that file holds
    And a token counts only on a leaf and only outside a string, and a comment only when it begins with a suppression marker, so prose, data tables and a comment explaining the marker are not charged
    But a suppression written as an annotation counts once however many warnings it names

  Scenario: _compute_type_escapes publishes the escape density with no floor under it
    Given a repository and a language
    When _compute_type_escapes counts the escapes across the production source and divides by thousands of lines
    Then it returns the density, its band, the escape count and the exact line total behind it
    And there is no minimum denominator, so a twenty-line file of nothing but escapes reports the density it earned instead of a fabricated clean zero
    But a language with no configured escape vocabulary returns n/a, and so does a scan that found no production lines at all

  Scenario: _compute_decision_space enumerates the decision points without scoring them
    Given a repository and a language
    When _compute_decision_space walks the production source for control-flow nodes
    Then it returns the count of decision points under the n/a band, because a count is not a score
    And it names how many files it read, so the count can be recomputed
    But its detail line always asserts that no execution trace was run, which is true of this function alone, since the caller replaces the whole result when the suite does run

  # The percentage is the first one appearing anywhere in the tool's console output, not a labelled field.
  Scenario: _compute_external_indicators reads the duplication figure off an external tool
    Given a repository and a language
    When _compute_external_indicators looks for the duplication tool on the path and runs it
    Then it returns L1.13 as the percentage it read and banded, or n/a naming the reason when the tool is absent, could not be executed, or printed nothing it could parse
    And the tool's non-zero exit is read rather than used to throw the output away, because crossing a duplication threshold is exactly what makes it exit non-zero
    But it takes the first percentage anywhere in the output as the duplication figure, and the language it is handed is never used at all
