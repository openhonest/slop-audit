Feature: coverage_gates — the deterministic retention gates that separate a proven bug from the tool's own noise
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  Scenario: _string_literals lists every string a generated test carries
    Given the body of a generated Rust test
    When _string_literals wraps it in a throwaway function, parses it, and walks the tree
    Then it returns the text inside every string and raw string literal, in the order the parse reaches them
    And each literal is handed back already unwrapped, so the caller compares text and not syntax
    But a body with no string at all returns an empty list

  Scenario: _string_content strips the wrapper off one Rust string literal
    Given one string literal exactly as it was written in the source
    When _string_content removes a leading r and its # fence, then the quotes
    Then it returns the text a reader would see printed
    But a token that is not quoted at both ends comes back unchanged rather than being truncated

  Scenario: assertion_message recovers the message the test's own assert would print
    Given the body of a generated test
    When assertion_message takes the last string literal in the body
    Then it returns that message, because the render contract puts the assert message last
    And that message is the only thing later used to tell the test's panic from anyone else's
    But it returns nothing when the body carries no string, and then no panic can ever be attributed to the assertion

  Scenario: parse_panic pulls one proof's panic out of a whole cargo run
    Given the combined output of a cargo test run and the label of one proof
    When parse_panic isolates that proof's block and matches either the current or the older panic spelling
    Then it returns the panic's location and its message
    But it returns nothing when the block shows no panic, so a pass, a build failure and a silent abort are alike here

  Scenario: _proof_block isolates one proof's failure section so a sibling's panic is not misread
    Given the whole cargo output and the label of one proof
    When _proof_block searches for that proof's stdout section
    Then it returns only that section, which is what keeps a batch of twenty proofs from sharing one panic
    But with no such section it falls back to the whole output, and only when the output mentions a panic at all

  Scenario: attribution decides whether the observed panic is the test's own assert firing
    Given the message the test's assert would print and the panic that was observed
    When attribution compares the two strings
    Then it answers assertion only when one string contains the other
    And a construction panic, an arrange-step expect, or a library assert all answer incidental
    But a missing panic or a missing message also answers incidental: with nothing to compare it never credits the assertion

  Scenario: invalid_fixture_marker finds the fabricated construction that makes a panic the fixture's fault
    Given the body of a generated test
    When invalid_fixture_marker looks for an uninitialised or null construction
    Then it returns the first marker it meets, such as mem::zeroed or a null pointer
    But finding none returns nothing, which is not evidence the fixture was valid

  Scenario: permute_scalar_construction rebuilds the test with a bigger, aligned scalar for the re-run
    Given the body of a test that panicked outside its own assertion
    When permute_scalar_construction multiplies every bare integer literal by 64, counting zero as one
    Then it returns the rewritten body, whose re-run is the permutation check
    But a body with no bare integer, or one the rewrite leaves unchanged, returns nothing and cannot be checked this way

  Scenario: _normalise_atom collapses the spacing in a cfg atom so two spellings compare equal
    Given one cfg atom as it was written, in source or in rustc's output
    When _normalise_atom removes the whitespace around the equals sign
    Then target_os = "linux" and target_os="linux" become the same predicate

  Scenario: host_cfg_atoms reads the host's cfg set out of rustc's own output
    Given the text that rustc --print cfg produced
    When host_cfg_atoms normalises every non-blank line
    Then it returns the set of atoms the host target actually satisfies
    But empty text yields an empty set, which proves nothing about the host and therefore excludes no branch

  Scenario: _atom_truth answers one cfg atom in three-valued logic
    Given one atom and the host's cfg set
    When _atom_truth checks the atom against the set
    Then an atom the host lists is true
    And an atom is false only when it names an exhaustive target key the host has set to a different value, or a bare unix or windows the host does not list
    But anything else, a feature flag most of all, is unknown rather than false, so an unrecognised flag can never hide a real gap

  Scenario: _split_top_level splits a cfg predicate list without breaking its nesting
    Given the text inside a cfg predicate list
    When _split_top_level splits on the commas that sit at nesting depth zero
    Then a nested all(...) or any(...) survives as one piece
    And empty pieces are dropped

  Scenario: _eval_cfg evaluates a whole cfg predicate against the host
    Given a cfg predicate and the host's cfg set
    When _eval_cfg recurses through not, all and any down to the bare atoms
    Then it returns true, false, or unknown for the predicate as a whole
    But one unknown atom propagates upward wherever it changes the answer, so the predicate is never forced to a guess

  Scenario: _not inverts a cfg negation without inventing certainty
    Given the evaluated terms of a not(...) predicate
    When _not inverts the first term
    Then an unknown term stays unknown
    But an empty term list is unknown too, rather than defaulting to true

  Scenario: _all combines the terms of a cfg conjunction
    Given the evaluated terms of an all(...) predicate
    When _all combines them
    Then one term proven false makes the whole predicate false, whatever the others are
    And every term proven true makes it true, which also means a predicate with no terms is true
    But a mixture of true and unknown is unknown

  Scenario: _any combines the terms of a cfg disjunction
    Given the evaluated terms of an any(...) predicate
    When _any combines them
    Then one term proven true makes the whole predicate true
    And every term proven false makes it false, which also means a predicate with no terms is false
    But a mixture of false and unknown is unknown

  Scenario: cfg_excluded says whether the host provably never compiles a branch
    Given a branch's cfg predicate and the host's cfg set
    When cfg_excluded evaluates the predicate
    Then it is true only when the host disproves it, so no test on this machine could ever reach the branch
    But a branch with no cfg at all, and one the host cannot disprove, are both kept in scope rather than quietly dropped

  Scenario: is_deferred_return spots a function that hands back a handle instead of a result
    Given a function's return type as it was written
    When is_deferred_return looks for a completion or future marker anywhere in that text
    Then it is true when one appears, because the real outcome then arrives by callback
    But an absent return type is false, so an unknown signature is never demoted to wrong_channel on a guess

  Scenario: classify_failure turns one failing run into its retention bucket
    Given the test body, the function's return type, and the panic parsed from one failing run
    When classify_failure asks attribution first, then the fixture and channel gates
    Then an attributed panic is a divergence, or wrong_channel when the function returns a deferred handle
    And an unattributed panic is an invalid fixture when the body carries a fabrication marker, and an incidental panic otherwise
    But with no panic at all it still returns incidental_panic, because it is only ever asked about a run that already failed
