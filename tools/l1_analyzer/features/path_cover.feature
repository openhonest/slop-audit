Feature: path_cover — the fewest end-to-end runs that walk every branch of a repository's code
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # The collection half is specified in research/candidates/collecting-unmeasured-constructs.md
  # and is NOT built. Today the statement dispatch collapses anything it does not name into the
  # current control point, and models a try as its body alone, so every except handler and every
  # finally is dropped and the cover comes back smaller than the code it was computed over.
  @undecidable @not-implemented
  Scenario: undecidable a control-flow construct the statement dispatch has no rule for
    Given a function whose branching is carried by an except handler, a finally, or another construct _build_stmt does not name
    When _build_stmt reads the statement kind, finds no rule, and returns the current control point unchanged
    Then it is recorded as unread rather than collapsed into straight-line code, where the cover then reads as the smaller number genuinely simpler code earns, so a zero means read-and-clean and never not-looked-at
    And the parse-tree shape around it is offered for collection: node types and nesting, every leaf value stripped
    And the operator opts in for that run only, after the whole payload is printed rather than summarised
    But nothing leaves the machine when the operator declines, and the run says nothing further about it

  Scenario: _add records one directed edge and the reverse edge that can undo it
    Given the flow graph being built, a from-node, a to-node and a capacity
    When _add appends the edge
    Then the graph gains a forward edge with that capacity and a matching reverse edge with none
    And each half records where the other sits, so flow pushed one way can be pushed back the other way
    But it changes the graph it was handed rather than returning a new one, so the caller's graph is the result

  Scenario: _max_flow pushes as much flow as the graph will carry between two nodes
    Given a flow graph, a source and a sink
    When _max_flow repeatedly searches breadth-first for a route with capacity left, then pushes the most that route can carry
    Then it returns the total pushed once no route remains
    And it leaves the graph in its used-up state, which the caller reads afterwards to learn how much sits on a particular edge
    But a sink the search cannot reach ends it immediately with nothing pushed

  Scenario: min_path_cover finds the fewest walks that cover every edge at least once
    Given a list of edges, a source and a sink
    When min_path_cover turns each edge's walk-me-once requirement into node demand, satisfies that demand, then pushes flow backwards to squeeze the total down
    Then it returns the number of source-to-sink walks needed to traverse every edge at least once
    And an empty edge list needs no walks at all
    But walks may reuse an edge, so this is a far smaller number than the count of distinct paths through the same graph

  Scenario: _cfg_edge adds a control-flow edge only when both ends exist
    Given the edge list, a point control comes from and a point it goes to
    When _cfg_edge is asked to join them
    Then it appends the pair to the edge list
    But an absent end means control does not fall through there, and nothing is recorded, which is how a return, a break or a continue ends a path without inventing an edge to nowhere

  Scenario: _build_block threads one control point through the statements of a block
    Given the edge list, the fresh-identifier source, a block, and the current control, break and continue points
    When _build_block hands each statement in turn to the statement builder, carrying the point the last one left behind
    Then it returns the control point that survives the block, or nothing when the block cannot fall through
    And comments, blank lines, colons and pass statements are skipped, because none of them decides anything
    But a missing block is treated as an empty one rather than as an error

  Scenario: _build_stmt routes one statement to the rule that models its control flow
    Given the edge list, the identifier source, a single statement and the current control, break and continue points
    When _build_stmt reads what kind of statement it is
    Then a return draws an edge to the exit, a break draws one to the loop's after-point, a continue draws one to the loop header, and each reports that control stops there
    And a conditional, a loop or a match is handed to its own builder, while a try or a with is modelled as its body alone
    But anything else is straight-line code that decides nothing, so it is collapsed into the current point unchanged

  Scenario: _cfg_if models a conditional as one arm per branch, meeting at a merge point
    Given the edge list, the identifier source, a conditional statement and the current control, break and continue points
    When _cfg_if builds each arm from a fresh start node and joins every arm that reaches its end to a shared merge point
    Then it returns the merge point when at least one arm falls through, and nothing when every arm returns or jumps away
    And a conditional written with no else branch still gets the branch-not-taken edge straight to the merge, because that untaken branch is a real edge a run must cover
    But the arm builder is a closure that reads the current point and writes into the edge list it captured, rather than being handed them

  Scenario: _cfg_loop models a loop as a header with an entry edge, a skip edge and a back edge
    Given the edge list, the identifier source, a loop statement and the current control, break and continue points
    When _cfg_loop makes a header node, an after node and a body-start node, and wires the body between them
    Then it returns the after node, which is where control continues once the loop is done
    And the header gets both the edge into the body and the edge that skips it, so a run that never enters the loop and a run that does are different edges to cover
    But the body is built with its own break and continue targets, so a break inside it lands on the after node and a continue lands back on the header

  Scenario: _cfg_match models a match as one arm per case, plus the edge where no case matched
    Given the edge list, the identifier source, a match statement and the current control, break and continue points
    When _cfg_match builds each case clause from its own start node and joins them all to a shared merge point
    Then it returns the merge point, with an added edge from the current point to the merge standing for no case matching
    But a match statement carrying no case clauses is not a decision at all, so control passes through unchanged and no nodes are made

  Scenario: function_cover counts the runs needed to cover one function body
    Given the body of a single function
    When function_cover builds the control-flow graph for that body and asks for its minimum edge cover
    Then it returns the fewest entry-to-exit runs that walk every branch in the function
    And a body with no branches at all is one run
    But the answer is never allowed below one, because even straight-line code takes a run to execute

  # The module comment above the builders states that the analyzer stays clean under its own
  # mutable-state rule because every builder threads its accumulators explicitly and binds no
  # state. That holds for the branch builders; it does not hold here. The tree walk below is a
  # closure that reassigns two captured counters, and the refactor that removed the stateful
  # builder class left it in place.
  Scenario: cover_paths sums the per-function cover across a whole repository
    Given a repository and a language name
    When cover_paths parses every production source file and walks each function body it finds
    Then it returns the total number of end-to-end runs, the number of functions counted, and a detail line saying so
    And it carries both running totals in a closure that reassigns captured names, rather than threading them through as the branch builders do
    But the band is always n/a because no threshold is set for this measure, and any language other than Python returns not-applicable without parsing anything
