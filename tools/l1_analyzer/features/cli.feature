Feature: cli — the command that runs the audit and the gate that runs it on this repository
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _prove_facet runs one caller-written proposal through the execution gate
    Given a module, its tests, a request index and the three fields of a proposal
    When _prove_facet renders and runs it
    Then the verdict says whether it was retained and what happened when it ran
    But it is a separate command from --facets, because one command would have to write the test itself and a tool that both proposes and accepts its own proposal has no gate

  Scenario: _report_call_map emits one module's four-column map as a .hd file
    Given a module, its test file(s) and the layer the caller declares
    When _report_call_map watches the suite and classifies the functions
    Then the map is printed in the Honest Framework's own grammar
    But a run that could not be watched says so first, because the violation this map shows is a write in the pure lane and reading the source alone can only guess at one

  Scenario: _report_honest_code measures the files it was given against the nineteen clauses
    Given one or more files and the shape the caller asked for
    When _report_honest_code assesses each of them
    Then one file returns exactly what it always returned, and several return one result apiece, since a caller that named ten files and got one back would read it as covering all ten
    And the hook shape writes to stderr, where a hook runner puts what a blocked tool call said
    But it writes nothing when there is nothing to change, because a hook that congratulates the agent on every file teaches it to skip the output

  Scenario: run is the console-script entry point, and the only caller that needs no arguments
    Given the installed script, which setuptools calls with nothing
    When run reads the process arguments and hands them to main
    Then main receives the arguments it requires
    But main used to be that callable itself, and its default meant every other caller could omit the arguments too, so nothing distinguished a caller who meant the process arguments from one who forgot to say

  Scenario: version says which build this is
    Given the installed package metadata
    When version reads it
    Then every panel, every card and every facet report carries the same string, so a measurement can be traced to the instrument that made it
    But a constant in the source would be a second owner of the same fact with nothing checking the two agreed, which is how a release ships while the channel serving it reports current

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the god-file arm appends a problem only above zero, so a repository
  # the L1.17 indicator never parsed prints the same pass line as a repository it read and cleared.
  # The state and thread-safety halves of that line were corrected for exactly this; this half
  # was not.
  @undecidable @not-implemented
  Scenario: undecidable a repository whose production source the god-file indicator never opened
    Given a repository in which the god-file indicator matched no production file, so L1.17 carries no positive value
    When _run_gate reads L1.17 off the panel, finds nothing above zero, and composes the pass line
    Then it is recorded as unread rather than printed as "0 production god-files", so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _hazard_context assembles the only code the generator gets to see
    Given the repository and one located hazard naming a file, a line, a kind and a symbol
    When _hazard_context reads the file and cuts a window of thirty lines either side of the hazard
    Then it returns that window under a heading naming the hazard, and nothing else from the repository
    But a file it cannot read yields the heading alone, so generation is attempted on a weaker context rather than abandoned

  Scenario: _run_prove drives locate, generate, run and retain across the review-tier hazards
    Given the repository, its language, the thread-surface result, a cap on hazards, and a timeout
    When _run_prove takes the review-tier findings up to the cap and proves each one in its own throwaway directory
    Then it returns every outcome with its verdict, its detail, and the generated test kept alongside, so a demonstrated proof can be offered as an adoptable test
    And a language other than Rust, or a missing model key, returns not-applicable with the reason and attempts nothing
    But the summary verdict is only "demonstrated" or "none", so a sweep where nothing was generated and nothing was run reads the same at that line as a sweep that ran and fired no race; the per-hazard verdicts are where the two stay distinguishable

  Scenario: main parses the command line and dispatches the requested audit
    Given the arguments the operator typed
    When main validates the repository path, then either runs the gate or collects the git, config and source indicators plus any opt-in runtime stage
    Then it prints the scorecard, or the JSON envelope recording whether the additive state-bounds classifier was on, and returns zero
    And a path that does not exist, and a path that is a file rather than a repository root, each print a plain message and return two rather than crashing inside the coverage runner
    But the stages that generate and run code — the race run and the two prove modes — happen only when explicitly asked for, never by default

  Scenario: _report_facets prints one module's closeable facets for a reader
    Given a module, the test file that should hold evidence about it, and an output format
    When _report_facets audits the pair
    Then it prints the coverage and the Silence index beside each other, then every silent facet grouped by kind
    But undeclared domains are listed apart from the index, because those are closed by declaring a type rather than by adding a test, so counting them would blame the suite for a gap in the signature

  Scenario: _selected_indicators refuses an indicator no stage can run
    Given a caller who typed L1.17 where the flag takes 17
    When _selected_indicators checks what they asked for against the one table of indicators
    Then it names the value, shows the form that would have worked, and exits 2
    But "all" selects every stage, which is the absence of a filter rather than an empty one

  Scenario: window_around takes the thirty lines either side of one
    Given the lines of a file and the line a hazard sits on
    When window_around clips thirty either side to what the file holds
    Then a hazard near the top does not run off the start, and one near the bottom does not run off the end
    But the window is chosen by index, so a hazard on line 50 is shown lines 21 to 80

  Scenario: build_stamp names the commit a build came from
    Given the directory a build was installed from
    When build_stamp asks git which commit it is at and whether anything is uncommitted
    Then the commit follows the release number, and an edited tree is marked dirty
    But a directory in no repository yields nothing, because inventing a commit is worse than the release number alone
