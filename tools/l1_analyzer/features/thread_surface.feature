Feature: thread_surface — the concurrency audit surface, every site where a language's thread-safety guarantee is overridden by hand or absent
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _text reads the source text a parse node covers
    Given a node, or nothing at all
    When _text is asked for its text
    Then it returns the decoded source, replacing any byte it cannot decode rather than failing
    And nothing at all, and a node carrying no text, both come back as the empty string

  Scenario: _walk lists a node and everything under it
    Given the root of any subtree
    When _walk descends into every child in turn
    Then it returns the node first and then its descendants in source order
    But it rebuilds the whole list on every call, so a scanner that walks a function once per rule pays for the walk once per rule

  Scenario: _mk builds one finding about one site
    Given the kind of site, the symbol, the severity, the file it sits in, and the node
    When _mk assembles the finding
    Then it records the line as the node's start row counted from one, not from zero
    And it collapses every run of whitespace in the symbol to one space, so a field access split across lines reads as a single symbol in the report

  Scenario: _rust_method_receiver splits a Rust method call into the method and what it was called on
    Given any node
    When _rust_method_receiver checks that the node is a call whose function is a field access
    Then it returns the method name and the receiver text, which is the shared-state key the per-function rules match on
    But anything that is not a call on a field access returns nothing, which is how a plain function call is passed over

  Scenario: _rust_receivers_by_method collects the self-rooted receivers a named set of methods is called on
    Given a scope to search and the set of method names that count
    When _rust_receivers_by_method walks the scope and keeps every matching call
    Then it returns the receiver text of each one whose receiver begins with self.
    And an empty scope returns nothing, so a missing if-branch costs the caller no special case
    But a receiver that is a plain local is dropped, because only instance state can be shared between threads

  Scenario: _rust_takes_shared_self decides whether a Rust method can be called by two threads at once
    Given a function node
    When _rust_takes_shared_self looks for a self parameter taken by reference
    Then it is true only for &self, a shared borrow, which permits concurrent calls
    But &mut self and self by value are exclusive under the borrow checker, so they are false, and that exclusion is what keeps the read-modify-write and check-then-act rules off methods no two threads can enter together

  Scenario: _rust_nonatomic_rmw finds an atomic that is loaded and stored in the same function
    Given a function and the file it sits in
    When _rust_nonatomic_rmw records which self-rooted receivers are loaded and which are stored or swapped
    Then it reports each receiver that is both, at the line of its load, as a candidate-severity read-modify-write done in two steps
    But a receiver the same function also drives with compare_exchange or any fetch_ method is excluded, because that is a real atomic protocol and not an unguarded update

  Scenario: _call_uses_relaxed spots a Relaxed memory ordering in a call's arguments
    Given a call node
    When _call_uses_relaxed searches the argument list for a scoped identifier
    Then it is true when one of them ends in Ordering::Relaxed once its spaces are removed
    And a call with no arguments at all is false

  Scenario: _result_feeds_branch decides whether a call's value steers control flow
    Given the call node
    When _result_feeds_branch climbs at most five parents, stepping through parentheses, unary, reference and try wrappers
    Then it is true when the call is itself the condition of an if or a while, or an operand of a comparison
    But a value bound to a local first and tested afterwards is deliberately out of reach, which keeps the rule high-precision at the cost of missing that spelling

  Scenario: _rust_check_then_act finds a check on shared state and a mutation of the same state inside one if
    Given a function and the file it sits in
    When _rust_check_then_act reads each if's condition for checked receivers and both its arms for mutated ones
    Then it reports every self-rooted receiver that appears on both sides as a review-severity check-then-act window
    And the else arm counts as a mutation site too, not only the consequence

  # The test-file skip below can only fire when a caller hands _scan_rust a test file.
  # `scan` never does: it reads under PRODUCTION_WITHOUT_CONFORMANCE, so the tests are
  # already gone. The guard is live only for a direct caller.
  Scenario: _scan_rust runs every Rust rule over one parsed file
    Given the root of a parsed Rust file and its path
    When _scan_rust walks the tree once and tries each rule in turn
    Then a hand-written unsafe impl Send or Sync, and a static mut, are exposed-severity findings
    And a Relaxed load that steers a branch is a review-severity missing acquire while every other Relaxed use is only a candidate, because Relaxed is correct for a counter
    But the read-modify-write and check-then-act rules run only on methods taking &self, and every rule below the hand-overrides is skipped entirely in a test file

  Scenario: _is_test_file decides whether a Rust path is test code
    Given a path relative to the repository
    When _is_test_file lowercases it and checks the ending and the directories
    Then a file ending in test.rs or tests.rs, or sitting under a test or tests directory, is test code
    But the check is on forward slashes only, so a path spelled with Windows separators reads as production

  Scenario: _py_rhs_is_mutable decides whether the right-hand side of a Python binding builds a mutable container
    Given the right-hand-side node, or nothing at all
    When _py_rhs_is_mutable checks its type
    Then a dict, list or set literal, or any of their comprehensions, is mutable, and so is a call to one of the named container constructors
    But nothing at all, and anything else, is not

  Scenario: _py_imported_modules lists the top-level modules a Python file imports
    Given the root of a parsed Python file
    When _py_imported_modules reads the import statements
    Then it returns the first segment of each imported name, so concurrent.futures counts as concurrent
    But it reads only the file's own top-level children, so an import inside a function or a try block is invisible to it

  Scenario: _py_uses_concurrency decides whether a Python file actually runs work concurrently
    Given the root of the file and the full list of its nodes
    When _py_uses_concurrency checks the imports and then the calls
    Then it is true when the file imports threading, multiprocessing or concurrent, or calls Thread, Process or either pool executor by name however it was imported
    And this is the gate on the module-container rules, so a single-threaded file is never charged with shared mutable state

  Scenario: _py_module_containers names the mutable containers bound at module scope
    Given the root of a parsed Python file
    When _py_module_containers reads each top-level statement that is a plain assignment to a bare name
    Then it returns the names whose right-hand side builds a mutable container
    But only module scope is read, because those are the bindings every thread in the process can reach

  Scenario: _py_condition_containers names the shared containers a condition tests membership in
    Given a condition node and the set of shared container names
    When _py_condition_containers looks for an in or not-in comparison
    Then it returns the name on the right of the comparison when that name is one of the shared containers
    And a missing condition returns nothing, so an if with no alternative costs the caller no special case

  Scenario: _py_body_mutated names the shared containers a block writes to
    Given a block node and the set of shared container names
    When _py_body_mutated looks for a subscript assignment and for a call on one of the named mutating methods
    Then it returns the container name behind each write it finds
    And a missing block returns nothing

  Scenario: _py_check_then_act pairs a membership test with a write to the same shared container
    Given the root of the file, the shared container names, and the path
    When _py_check_then_act reads each if's condition and both its arms
    Then it reports every container that is both tested and written as a review-severity check-then-act
    And under free threading two threads can both see a key absent and both write it, which is the window the finding names

  Scenario: _py_global_names lists the module state a Python function declares it will write
    Given a function node
    When _py_global_names collects the identifiers on every global statement inside it
    Then it returns those names, which are the shared bindings the function can rebind

  Scenario: _py_nonatomic_rmw finds an augmented assignment to a global-declared name
    Given the root of the file, the path, and whether any lock exists in the file
    When _py_nonatomic_rmw reads each function that declares a global and looks for an augmented assignment to one of those names
    Then it reports each one, because the load, the add and the store are three steps and two threads lose an update between them
    And the severity drops from review to candidate when a lock exists anywhere in the file, since the guard is then present but unproven

  Scenario: _py_has_lock decides whether any synchronization exists in a Python file
    Given the full list of the file's nodes
    When _py_has_lock looks for a lock type's name and for a call to acquire
    Then it is true when either appears anywhere in the file
    But it never checks that the lock guards the state in question, which is exactly why its effect is to downgrade a finding rather than to remove it

  Scenario: _scan_python runs every Python rule over one parsed file
    Given the root of a parsed Python file and its path
    When _scan_python looks first for mutable default arguments and then, only if the file runs work concurrently, for shared module state
    Then a mutable default argument is always a review-severity finding, concurrency imports or not, because it is shared across calls and decidable on sight
    And a module-level mutable container in a threaded file is exposed when no lock exists in the file and only review when one does
    But a file with no concurrency at all returns after the default-argument pass and is never charged with shared state

  Scenario: _js_method_receiver splits a JavaScript method call into the property and the object
    Given any node
    When _js_method_receiver checks that the node is a call whose function is a member expression
    Then it returns the property name and the object text
    But anything else returns nothing

  Scenario: _js_receivers_by_method collects the this-rooted receivers a named set of methods is called on
    Given a scope to search and the set of method names that count
    When _js_receivers_by_method walks the scope and keeps every matching call
    Then it returns the object text of each one that begins with this.
    But a receiver that is a plain local is dropped, because only instance state outlives the awaited gap

  Scenario: _scan_jsts finds an async check-then-act across an await
    Given the root of a parsed JavaScript or TypeScript file and its path
    When _scan_jsts reads each if whose body contains an await, and compares the state checked in the condition against the state mutated in that body
    Then it reports every this-rooted receiver on both sides as a review-severity async TOCTOU, because the await yields the loop and another task can invalidate the check
    But an if with no await in its body is skipped, so the shape gates itself on the concurrency being present, and this is not a data race: one event loop cannot have two threads in the same code

  Scenario: _go_assign_base names the variable a Go write actually targets
    Given the left-hand side of a write, or nothing at all
    When _go_assign_base peels an index or a selector back to what it sits on
    Then a bare name gives itself, a map write gives the map, and a field write gives the object
    But any other shape, and nothing at all, gives nothing

  Scenario: _go_assign_bases names every variable a Go assignment targets
    Given the left-hand side of an assignment, which may list several targets
    When _go_assign_bases splits an expression list and reduces each named part
    Then it returns the base variable of every target
    And a left-hand side that is missing, or reduces to nothing, gives an empty set

  Scenario: _go_declared_inside names what belongs to a goroutine's own closure
    Given the closure node and its body
    When _go_declared_inside collects the closure's parameters and the names it declares with the short form
    Then it returns those names, and they are what the captured-write rule subtracts, so only writes to names from the enclosing scope survive
    But it takes every identifier under the parameter list, including type names, so a parameter typed by a name that is also a captured variable would hide that capture

  Scenario: _go_has_sync decides whether a goroutine body synchronizes at all
    Given the closure body
    When _go_has_sync looks for a channel send and for a call to one of the named lock or atomic methods
    Then it is true when either appears, and its only effect is to downgrade the write findings from review to candidate

  Scenario: _scan_go finds a goroutine writing to a variable it captured
    Given the root of a parsed Go file and its path
    When _scan_go reads each go statement's closure and every assignment, increment and decrement inside it
    Then it reports each target that was not declared inside the closure as a shared write, once per name and not once per write
    And the severity is review when the body synchronizes nowhere and candidate when it does
    But the blank identifier is discarded rather than reported, since a write to it goes nowhere

  Scenario: _java_base_type reduces a Java type to its bare name
    Given a type node, or nothing at all
    When _java_base_type unwraps a generic type and drops any package qualification
    Then Map<String, Object> and java.util.Map both come back as Map
    But an array type, and nothing at all, give nothing

  Scenario: _scan_java finds a static, non-final field of a mutable collection type
    Given the root of a parsed Java file and its path
    When _scan_java reads each field declaration's modifiers and its type
    Then it reports a field that is static and not final whose type is one of the plain collection types, as review-severity class-level state every thread can reach
    But the concurrent and the synchronized collection types are absent from that list on purpose, so a ConcurrentHashMap is never reported

  Scenario: _ruby_uses_threads decides whether a Ruby file uses threads at all
    Given the root of a parsed Ruby file
    When _ruby_uses_threads looks for the constant Thread and for a call whose receiver is Thread
    Then it is true when either appears anywhere in the file

  Scenario: _scan_ruby finds a compound update to a class variable in a threaded file
    Given the root of a parsed Ruby file and its path
    When _scan_ruby checks that the file uses threads and then reads each operator assignment
    Then it reports a compound assignment whose target is a class variable as a review-severity read-modify-write, because that update is several bytecodes and the interpreter lock does not span them
    But a file that never mentions Thread returns nothing at all, without any of its class variables being read

  Scenario: _na builds the answer for a language this meter has no scanner for
    Given the language name
    When _na assembles the result
    Then the verdict, the value and the band all read n/a, every count is zero, and the details say plainly that no scanner exists for that language yet
    And the wording sends the reader to us rather than to their own source, which is the whole reason this answer is spelled differently from the refusal

  Scenario: _unread builds the refusal for a language whose source could not be read
    Given the language name, how many files were in scope, and the scope buckets
    When _unread assembles the result
    Then the verdict reads unread and the value and the band read n/a as well, because a reader and a report template look at those fields and prose alone is not a disclosure
    And the details distinguish no file being in scope from the parser failing on every file that was, and the scope buckets are kept because on the motivating case they name the rule that set every file aside

  # The module docstring lists the verdicts as exposed, review, clean, unread and n/a.
  # The body publishes a sixth, `candidate`, when only candidate-severity sites are found.
  Scenario: scan reports the concurrency-surface distribution for a repository
    Given a repository and a language name
    When scan parses every production file, runs the language's scanner over each, and counts the sites by severity
    Then it returns the worst severity present as the verdict, the three counts as the value, the findings sorted worst first, and the count of files read beside the count that parsed
    And a file the parser choked on is still scanned, because a hazard recovered from a broken tree is still a hazard, and the parse count is published as a denominator rather than used as a filter
    But it refuses with unread only when nothing parsed and nothing was found, since a finding is itself proof the scanner read something, and a language with no scanner gets n/a instead
