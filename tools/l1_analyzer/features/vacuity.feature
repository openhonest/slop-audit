Feature: vacuity — paths where a check publishes a property it never measured, stated only in the negative
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today empty_branch returns nothing decided, the walk enters both arms
  # carrying whatever selection it already had, and the field under that guard is still counted
  # as one of the emission points the reach publishes.
  @undecidable @not-implemented
  Scenario: undecidable a guard whose emptiness no rule can evaluate
    Given a function that publishes a constant behind a guard the rule cannot settle, such as a chained comparison or a call to an emptiness predicate of the module's own
    When check reads the file
    Then it is recorded as unread rather than counted as one more emission point the search covered, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  # The docstring says "plain and augmented". The body collects a third form as well:
  # an annotated assignment, which is how `findings: list[Finding] = []` is picked up.
  Scenario: _assignments gathers every expression bound to one name inside a scope
    Given a function body and the name to look for
    When _assignments walks the whole body
    Then it returns the right-hand side of each plain, augmented and annotated assignment to that name
    But an augmented or annotated assignment with no value on the right is skipped, since there is nothing to read

  Scenario: _is_size decides whether an empty input can drive a quantity to zero
    Given an expression, the function it sits in, and how deep the recursion already is
    When _is_size reads how the quantity is built rather than what it is called
    Then a length, a sum, a comprehension, a container literal, a container constructor and a numeric literal all count as sizes
    And a name is a size when any one of its local bindings is, because a counter starts at zero and is then added to, and a parameter is a size only when the body indexes, iterates over or does arithmetic with it
    But an attribute read with no local definition is not, which is what keeps a comparison of a process exit status against zero out of the finding list, and the recursion gives up past three levels

  Scenario: _used_as_quantity looks for the evidence that a parameter is a tally
    Given a parameter name and the function body
    When _used_as_quantity searches for the name in arithmetic, in a subscript, as the thing a loop walks, or as the argument of a sizing or container call
    Then any one of those is enough to call it a quantity
    But a name the body only ever tests for truth is a flag, and reading a flag as a tally once put a finding on every check that asks whether higher is better

  Scenario: _parameters lists the names a function declares as arguments
    Given a scope, which may or may not be a function
    When _parameters reads the argument list
    Then it returns every positional, keyword and star argument name
    And a scope with no argument list at all returns nothing rather than failing

  Scenario: _threshold_branch settles which arm a size takes against a numeric literal
    Given a comparison and the function it sits in
    When _threshold_branch substitutes zero for the size and evaluates the comparison
    Then it names the body or the else arm in one arithmetic step, whichever way round the size and the literal were written
    And a floor above zero needs no second rule, because a count over a thousand sends zero to the same arm a count over zero does
    But a chained comparison, an operator it has no evaluator for, or a quantity that is not a size, all return nothing decided

  Scenario: refusal_branch names the arm taken when the upstream refused
    Given a test expression
    When refusal_branch checks for an equality against a refusal constant
    Then equality selects the body and inequality selects the else arm
    And this decides a cut and never a value, because a repository can be empty on either side of it, so a check that passes an upstream refusal through is not reported as a fabrication
    But anything that is not a single equality or inequality against a refusal returns nothing decided

  Scenario: empty_branch names the arm an empty input takes
    Given a test expression and the function it sits in
    When empty_branch reads the test as a threshold, a negation, a compound, or a bare truthiness test on a size
    Then it returns the body or the else arm, flipping for a negation and combining the arms of an and or an or the way that operator does
    But an undecided test is neither a finding nor a clearance, and the caller then walks both arms and lets an inner guard settle it

  Scenario: _is_refusal_constant decides whether a value declines to assert anything
    Given a constant, a name or an attribute
    When _is_refusal_constant compares it against the refusal vocabulary
    Then none and false both count, since a nullable field and a did-not-measure flag are two spellings of the same refusal, and a name or attribute spelled like one of the refusal constants counts too
    And the error family is recognized by its ending rather than by listing the words, so a module that invents its own error token is still read as refusing
    But true does not count, because true asserts

  Scenario: _is_prose declines to judge a sentence
    Given a value
    When _is_prose checks whether it is a formatted string or a string containing a space
    Then either one is prose and the check refuses to judge it
    And the reason is that a refusal and a fabricated clean are both written in English, and telling them apart would need the word list this whole check exists to avoid

  Scenario: _is_property_constant decides whether a value reads as a measurement
    Given a value and the module's own scalar constants
    When _is_property_constant checks it
    Then a number or a string is a property, and so is a name bound to one of the module's scalar constants, because that is a verdict word a reader will act on
    And a negated number is read through to the number underneath
    But a constant bound to a table of specifications is not on that list, since choosing a layout asserts nothing about the code

  Scenario: _verdict_tokens collects the module constants a reader would take as a verdict
    Given a parsed module
    When _verdict_tokens reads the top-level assignments
    Then it keeps the upper-case names of more than one letter that are bound to a plain string or number
    But a boolean is excluded, and so is a constant bound to a list or a dict, because that is a table and not a verdict

  Scenario: _bound_names lists the names an assignment binds
    Given an assignment statement
    When _bound_names walks its targets
    Then it returns every name appearing in them, so a tuple unpacking yields all of its names
    But it does not tell a bare name from a subscript target, so the caller has to ask that separately

  Scenario: _writes_a_container tells filling a tally apart from binding a name
    Given an assignment statement
    When _writes_a_container looks at what is on the left
    Then a subscript or an attribute target means the statement fills a container rather than binding a constant to it
    And the distinction matters because reading the two as the same thing convicted an empty tally, which asserts nothing

  Scenario: _guard_rule names which spelling of the one predicate decided a branch
    Given the test that selected the branch
    When _guard_rule reads the shape of the test
    Then a boolean operator is a compound, a negation is a negation, a comparison is a threshold, and anything else is a truthiness test
    And the label is published with the finding so a reader can see which form fired

  Scenario: derivation_map traces every local name back to the names it came from
    Given a function body
    When derivation_map records the sources of each binding in one pass and then closes the relation transitively
    Then it returns each locally bound name mapped to every name it is derived from
    And a name bound by a loop is derived from what the loop walked, and so is a tally filled inside that loop, whether by assignment or by one of the filling methods
    But the closure is capped at three rounds, so a chain of derivations longer than that is not followed to the end

  Scenario: _roots names the quantity a guard is actually about
    Given an expression and the derivation map for the function
    When _roots collects the names in the expression and follows each through the map
    Then it returns the whole set of names the quantity is built from
    And this is what keys the cut, so that two guards close each other only when they are about the same quantity, since a check that refuses because the language has no scanner has not repaired a later division by a finding count

  # A directly-guarded constant is always labelled "threshold", whatever guard actually
  # selected it. `_guard_rule` steers only the conditional-expression path, so a finding
  # under a truthiness or a compound guard is published under the wrong rule name.
  Scenario: _vacuous_constant finds the constant an empty input publishes through an expression
    Given an expression, whether an emptiness guard already selected this path, the function, and the running state of the walk
    When _vacuous_constant reads the expression, descending into a conditional expression to try the arm an empty input reaches
    Then it returns the constant with the rule that decided it, or nothing
    And it descends through a conditional whose test it cannot decide, because an outer test it cannot read can hide an inner one it can
    But a refusal is never returned, and prose is counted as declined rather than convicted or cleared

  Scenario: _is_refusal_dict decides whether a published dictionary declines to assert anything
    Given a dictionary expression and the function it sits in
    When _is_refusal_dict reads its values
    Then an explicit false or none among them settles it, because the sentinels beside such a flag are the shape of the refusal rather than separate claims
    And otherwise every single field has to be a refusal, prose, or the reason for the refusal, since a refusal dictionary measures nothing at all
    But a dictionary that publishes a measured-looking zero beside a band of n/a is not a refusal, and that half-repair is exactly what this check has to keep convicting

  Scenario: _is_reason recognizes the explanatory payload sitting beside a refusal
    Given a value and the function it sits in
    When _is_reason checks it
    Then a parameter handed in, an empty container, a call, and the sentinels zero, empty string and minus one all count as the reason rather than as a claim
    And this is the one place the check knowingly trades a miss for a false positive: a half-repair publishing zero beside a refusal reads as a refusal here and is not reported
    But false equals zero in Python, so a false value reaches this answer as well as the earlier one

  Scenario: _refuses decides whether a branch declines to publish and returns
    Given the statements of a branch, the helpers known to refuse, and the function
    When _refuses looks at the last statement
    Then a return of nothing, of a refusal constant, of a call to a known refusing helper, or of a refusal dictionary all count as a refusal
    And a path ending in a refusal is not a vacuous path, and nothing below it is reachable on an empty input, which is the repair this check must not convict
    But a branch whose last statement is not a return does not count, however it refuses in the middle

  Scenario: _terminates decides whether a block leaves rather than falling through
    Given the statements of a block
    When _terminates looks at the last one
    Then a return, a raise, a continue or a break means control leaves the block, and an empty block does not

  Scenario: _record writes one finding, with the source line that proves it
    Given the surroundings of the walk, the running state, the field name, the node, the rule, and the constant
    When _record appends the finding
    Then it carries the file, the function, the field, the line and the guard's own source text, so a reader can check the claim in one look
    And the guard text is stripped and cut at 140 characters, and a line number outside the source gives an empty guard rather than failing

  # The docstring names a flag `cut`. There is no such parameter: the flag is `refused`.
  Scenario: _emit reads one published dictionary field by field
    Given the dictionary, whether an emptiness guard selected this path, the quantities already refused about, the surroundings, and the running state
    When _emit counts each string-keyed field as an emission point and asks what an empty input would find there
    Then it records a field carrying a name already known to be vacuous, a field calling a helper already known to be vacuous, and a field holding a vacuous constant inline
    And a dictionary carrying its own did-not-measure flag is a refusal whole and none of its fields are judged, because judging them one at a time convicted the sentinels that are the refusal
    But a field whose quantity an earlier guard already refused about is not recorded, since an empty input never reaches it

  Scenario: _published_dict finds the dictionary a statement publishes
    Given a statement and the surroundings of the walk
    When _published_dict checks what it does
    Then a returned dictionary literal is published, and so is one assigned into a container or bound to a name the function later returns
    And a panel entry written into a results table is published exactly as a returned literal is

  Scenario: _walk_body collects the vacuous names and the published fields an empty input reaches
    Given the statements, whether an emptiness guard selected this path, the quantities already refused about, the surroundings, and the running state
    When _walk_body reads each statement and descends into every branch, handler, loop and context block
    Then it records the findings and hands back the set of quantities the path has refused about
    And an exception handler is walked as a selected path outright, since the handler is the did-not-measure branch, and falling past a not-empty guard that returns selects the rest of the function, which is the guard-chain form with no else in sight
    But entering the arm an empty input does not take clears the selection rather than inheriting it, because that arm has proved the quantity is not zero

  Scenario: _called_names lists the plain function names called anywhere in a node
    Given any node
    When _called_names walks it
    Then it returns the name of each call made through a bare name
    But a call through an attribute is not a bare name and does not appear

  Scenario: _referenced_names lists every name mentioned in a node
    Given any node
    When _referenced_names walks it
    Then it returns each name it finds, with no regard for whether the name is read or written

  Scenario: _returned_names lists the names a function hands straight back
    Given a function
    When _returned_names looks at each return statement
    Then it returns the names returned bare, which is how a dictionary built up under a name is recognized as published
    But a return of anything more complicated than a bare name is not counted

  Scenario: _functions lists every function defined anywhere in a module
    Given a parsed module
    When _functions walks the whole tree
    Then it returns every function and every asynchronous function, nested ones included, each analysed in its own right

  Scenario: _blank_path starts the running state for one function
    Given the module's verdict tokens and the function
    When _blank_path builds the state
    Then it builds the derivation map here, once per function, and hands it back inside that state
    And it lives here and not in a module-level cache because a cache is hidden state, which this package's own state indicator counts against it, and did the first time this module joined the tree

  Scenario: _context packages the read-only surroundings of one walk
    Given the function, its file, its source lines, the helpers known to be vacuous, and the helpers known to refuse
    When _context assembles them
    Then it also works out the names the function returns bare, and calls a scope with no name of its own the module
    And nothing in it changes during the walk

  Scenario: _classify_helpers reads what each helper in a file hands back
    Given every function in the file, the file, its source lines, and the module's verdict tokens
    When _classify_helpers walks each helper and looks at what its returns produce
    Then it returns the helpers that hand a vacuous constant back, each carrying the rule that fired inside it, and separately the helpers that refuse
    And both answers are read from the body, so a refusal helper earns its meaning by returning refusals and not by what it was named
    But a helper that returns from an exception handler is filed under the handler rule whatever else its returns were decided by

  Scenario: _returns_from_a_handler asks whether a function returns from inside an except block
    Given a function
    When _returns_from_a_handler looks inside every exception handler in it
    Then it is true when any of them contains a return
    And that is enough to file the helper under the handler rule, so a finding at the call site still names the handler that produced the value

  Scenario: _refuses_outright asks whether a function ever returns a refusal
    Given a function
    When _refuses_outright looks at each of its returns
    Then it is true as soon as one returns a refusal constant or a refusal dictionary
    But one refusing return is enough, so a helper that refuses on one path and publishes a measurement on another is still counted as a refusing helper everywhere it is called

  Scenario: scan_function reports the vacuous paths one function publishes
    Given the function, its file, its source lines, the vacuous helpers, the refusing helpers, the verdict tokens, and the running counters
    When scan_function walks the body from an unselected start
    Then it returns the findings against named fields and adds this function's emission points and declined prose fields to the counters
    But a finding against the function's own return value is dropped here, because that answer belongs to the caller's classification of helpers and not to the file's finding list

  Scenario: scan_module reports the vacuous paths in one parsed module
    Given a parsed module, a file path, and the source lines
    When scan_module runs the whole analysis over it
    Then it returns the findings
    And it does no input or output at all, so a caller can hand it a snippet and read the answer without putting a file on disk
    But the reach it counted along the way is discarded, so only the whole-tree entry point can say what the search was worth

  Scenario: _scan_counting runs the analysis over one module and accumulates the reach
    Given a parsed module, its path, its source lines, the running counters, and the refusing helpers found elsewhere in the tree
    When _scan_counting classifies the file's helpers, adds the imported refusals to them, and scans each function
    Then it returns the findings with duplicates on the same function, line and field removed
    And a refusal helper defined in one module and imported into another is the same helper, which reading each module alone got wrong on eight coverage harnesses whose refusal lives next door

  Scenario: _python_files lists the Python sources under a root
    Given a directory
    When _python_files searches it recursively
    Then it returns the paths in sorted order
    But anything under a virtual environment, a cache, a build directory or the version-control directory is left out

  # The reach publishes eight rule names. Two of them, "fall-through" and "call-hop",
  # never label a finding: the fall-through path records whatever rule the constant was
  # decided by, and a call hop carries the callee's own rule. So the denominator counts
  # two rules a reader will never see in the output.
  Scenario: check reports every vacuous path under a root, with the reach that says what the answer is worth
    Given a directory
    When check parses each Python file, collects every refusing helper in the tree first, and then scans each file
    Then it returns the findings and the reach: the rule count, the emission points, the files read and unparsed, the prose fields declined, and one language out of nine
    And a file it cannot read or parse is counted as unparsed rather than dropped silently
    But there is no band, no verdict and no value in what it returns, and that is deliberate: an affirmative field is a field that can hold a fabricated affirmative value, and this check would then be its own first finding

  Scenario: render writes the report, and can say nothing good
    Given a result
    When render formats it
    Then zero findings renders as a negation carrying its own reach, saying how many rules, emission points, files and languages were looked at, and stating outright that this is the reach of the search rather than a statement about the code
    And a finding renders as a withdrawal, naming the output that cannot be relied on when the input is empty and printing the guard line beneath it, never as a fault
    But the declined prose fields and the unparsed files are printed either way, because they are what a silence is worth
