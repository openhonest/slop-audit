Feature: scope — deciding which files are the code under audit and which are set aside, and disclosing why
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today _bucket_reason returns nothing both for a file it examined and kept
  # and for a directory whose test convention no marker names, so a JavaScript __tests__ tree or
  # a Ruby spec tree is measured as production code and the disclosure records no judgment at all.
  @undecidable @not-implemented
  Scenario: under_symlinked_dir decides symlinked trees rather than leaving it to the interpreter
    Given a path below the repository root
    When under_symlinked_dir walks up looking for a symlinked directory
    Then it answers yes for anything inside one, so a tree that is not in this commit is not measured
    And the answer is the same on every Python, because pathlib stopped following them in 3.13 and the Rust port's walkdir never did, and agreeing by version is not agreeing
    But a symlinked FILE is unaffected, since is_file follows symlinks on purpose and one file is not a tree

  Scenario: undecidable a test-directory convention no marker in the scope names
    Given a repository whose tests sit in a directory named by a convention outside the two markers, such as a JavaScript __tests__ tree, a Ruby spec tree, or a Cucumber features tree
    When _bucket_reason tests that path against the vendored list, the scope's markers, the docs directory, the tooling names and the loose-root-script rule
    Then it is recorded as unread rather than as the same nothing a file that was examined and kept receives, so a scope disclosure means read-and-kept and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: excluded_dirs gives a named scope the directory names it removes from a measurement
    Given the name of a scope
    When excluded_dirs looks that name up in the scope table
    Then it returns the directory names that scope removes: the two test-directory names for the production scope, those plus the conformance directory for the scope the god-file and state meters use, and none at all for the whole-repository scope
    And routing every reader through it is what stops an indicator measuring under a scope nobody wrote down
    But a name that is not in the table raises rather than falling back to a default, so an unrecorded scope cannot be measured quietly

  Scenario: _test_dir_corroborated checks that a directory named like a test directory really holds tests
    Given a directory
    When _test_dir_corroborated walks everything under it looking for a file whose name follows a test convention, or a test-framework marker in the first four kilobytes of any file
    Then it answers yes on the first such file it finds, and the answer is cached per directory because it is a pure question about the tree
    And it judges a file by its name alone, never by a path component, so a renamed directory cannot corroborate itself
    But it answers no when the directory cannot be listed, and a no keeps the directory in the audit, since the rule is one-directional and a failure to corroborate can only add code to the measurement

  Scenario: _test_file_by_name decides from the file name alone whether a file is a test
    Given a path
    When _test_file_by_name examines the name, the stem and the suffix
    Then it answers yes for a name beginning with the test prefix in its underscore, hyphen or dot spelling, a stem ending in a test or spec suffix in any of those spellings, a doubled test or spec extension, or the .NET and JVM capitalised stem endings
    And the hyphen spelling matters because a genuine C test tree can carry no framework import at all and would otherwise be measured as production
    But it deliberately ignores the path, which is the arm that would let the directory under examination vouch for itself

  Scenario: _claiming_dir finds which ancestor directory is the one making the test claim
    Given a path and the name of one of its components
    When _claiming_dir walks up the path's ancestors looking for the directory whose own name is that component
    Then it returns that directory, so corroboration is asked of the directory that actually carries the name
    But it returns nothing when no ancestor bears the name

  Scenario: _component_scoped_out decides whether one path component is removed by one marker
    Given a path component and a marker
    When _component_scoped_out compares them
    Then an exact match removes the component under any marker
    And a test marker also matches case-insensitively and as a dotted suffix, so a project directory named for its parent with a test suffix is caught where an exact match never would be
    But a marker that is not a test marker matches on the nose only, so a directory merely resembling the conformance name stays in the audit

  Scenario: _extra_reason names the first scope marker that removes any component of a path
    Given a path's components, the markers a scope removes, and optionally the path itself
    When _extra_reason takes each marker in turn and looks for a component it removes
    Then it returns that marker as the reason
    And when the marker is a test marker and the path is supplied, the claiming directory must also corroborate the claim, or the match is passed over and the file stays in the audit
    But the conformance marker and any other non-test marker still match on the name alone, with no corroboration asked

  Scenario: _in_ignored_dir answers whether a path sits in a vendored, tooling, or scoped-out directory
    Given a path and a scope's extra markers
    When _in_ignored_dir checks the path's components against the fixed ignore list and then against the extra markers
    Then it answers yes when any component is version-control metadata, an installed-dependency tree, a virtual environment, a cache, a build or distribution output, or a vendored tree, or when any extra marker removes a component
    And the fixed ignore list applies under every scope, including the whole-repository scope, so vendored code is never the subject of any measurement

  Scenario: _rglob_files yields every real file under a repository, and nothing that only looks like one
    Given a repository root and a name pattern
    When _rglob_files walks the tree for that pattern
    Then it yields only entries that are files, so a directory whose name ends in a source extension is neither measured nor counted as unreadable
    And it skips anything under a nested checkout, meaning any directory below the root that carries its own version-control marker, because a submodule, a vendored clone or a worktree is a different repository with its own history
    But it follows symbolic links, so a symlinked source file is still read, and a file the process may not open still reaches its reader and is still disclosed as unreadable

  Scenario: _is_generated decides whether a file's own header marks it as machine-generated
    Given a path
    When _is_generated reads the first two kilobytes and looks for the machine-readable generated marker, the Go generated banner, or the protocol-buffer banner
    Then it answers yes when one of them appears in that header
    And only the header is read, so a hand-written file mentioning the same phrase further down is unaffected
    But an unreadable file answers no and falls through to ordinary scope, rather than being excluded on a guess

  Scenario: _repo_has_packages asks whether the repository is organised into importable packages
    Given a repository
    When _repo_has_packages looks for any package marker file outside a vendored directory
    Then it answers yes when one exists, which is what tells a loose entry-point script apart from a flat script-only repository
    But it takes no scope and removes no test tree, because the question is about the repository's layout rather than about its production code, and scoping the test tree out here would misclassify a repository whose only packages are its tests

  Scenario: _bucket_reason gives the one reason a source file is set aside, or keeps it
    Given a path, the repository, whether the repository has packages, and a scope name
    When _bucket_reason tests the path in order against the vendored list, the scope's markers, a docs directory, the conventional tooling file names, and the loose-root-script rule
    Then it returns the first reason that applies, and nothing when the file stays in the audit
    And the loose-root-script reason fires only for a file directly at the root of a repository that has packages and is not itself a package, so a flat script-only repository keeps its root scripts because they are the code
    But it names no project and encodes no specific repository, and every reason it returns is disclosed rather than applied silently

  Scenario: _read_source_bytes reads the audited source files as bytes under a named scope
    Given a repository, a set of file extensions, and a scope name
    When _read_source_bytes walks the tree for each extension and keeps every file that _bucket_reason does not set aside
    Then it returns the files it read with their bytes, and a count of the files it could not read
    And it takes a scope by name rather than a bare list of directories, so the table records which measurement each reader belongs to
    But an unreadable file is counted and disclosed, never dropped in silence

  Scenario: bucketed_paths discloses what the audit did not look at, and why
    Given a repository, a set of file extensions, and a scope name
    When bucketed_paths asks _bucket_reason about every file with those extensions and groups the answers
    Then it returns a count for every reason, and a sorted list naming each file set aside as documentation, as tooling, or as a loose root script
    And those three are the judgment calls a reader most needs to challenge, since over-bucketing a real entry point would otherwise hide behind a silent skip
    But vendored dependencies are counted only and not listed, because naming every vendored file would bury the judgment calls

  # The docstring says this reads files "under the named scope", and it does apply that scope's
  # directory markers — but it applies only those, not the docs, tooling and loose-root-script
  # reasons that _read_source_bytes applies through _bucket_reason. Two readers of the same
  # named scope therefore see different file sets. Recorded, not fixed.
  Scenario: _read_text_files reads files of the given extensions as text under a named scope
    Given a repository, a set of file suffixes, and a scope name
    When _read_text_files walks the whole tree, keeps the files whose suffix is in the set, and drops the ones in a vendored or scoped-out directory
    Then it returns the files it read with their text, decoded so an undecodable byte is replaced rather than raising, and a count of the files it could not read
    But it applies only the scope's directory markers, so a documentation file, a conventional tooling file or a loose root script that the source reader would have set aside is read here
