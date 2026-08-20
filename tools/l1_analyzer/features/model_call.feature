Feature: model_call — the package's one construction of the generation model client
  One scenario per function. The scenario names the single behaviour the function
  stands on, so the count of scenarios is this module's directly-counted
  function-point size (honest-gherkin section 9).

  This module exists because two callers carried the same preamble: read the key, import
  the SDK, construct a client, swallow every failure so an unusable reply never becomes a
  false claim. Two copies of a refusal is two places for it to drift, and they had already
  drifted on the token limit, 4096 against 2048, with nothing written down saying whether
  that was a decision. What differs between the callers is the tail alone: one wants the
  text with its fences stripped, the other wants it parsed as JSON. So the call is one
  function and the parsing belongs to whoever asked.

  # The undecidable case. Every feature carries exactly one, and the gate requires it, because
  # a measure that meets a construct it has no rule for must say so rather than return a verdict.
  # A reply that arrives but is empty, truncated at the token limit, or a refusal in prose is
  # returned as a string like any other. Nothing here can tell those apart from a real answer;
  # the caller's parse rejects some of them and the execution gate rejects more, but a plausible
  # truncated answer that still parses is indistinguishable to this boundary.
  @undecidable @not-implemented
  Scenario: undecidable a reply that arrives complete-looking but is truncated or refused
    Given the model returns text that parses but was cut off at max_tokens, or declines in prose
    When call hands that text back
    Then it is returned as a reply, because nothing at this boundary can separate a short answer from a stopped one
    And the stop reason the SDK reports is the evidence that would settle it, and it is not read here
    But no verdict is published from this module either way, so the false claim can only be made downstream by a caller that trusts the text

  Scenario: model_available says whether a generation model can be called at all
    Given the process environment
    When model_available reads it
    Then it is true when an Anthropic key is present and false when it is absent
    And it is the only place in the package that reads that variable's name, so a rename cannot leave a second copy checking the old one

  Scenario: call returns the model's reply text, or the named reason there is none
    Given a system instruction, a user payload and a token limit
    When call runs
    Then it returns the reply text when the key is present, the SDK imports and the request succeeds
    But when there is no reply it names which of four things happened, because no key, no SDK, a failed request and a model with nothing to say are four different repairs and one of them is not about the model at all

  Scenario: unavailable_reason says which half of the requirement is missing
    Given the process environment and whatever is installed
    When unavailable_reason is asked why no model can be called
    Then it names the absent key, or the absent SDK, or nothing at all when a model can be called
    But it never reports one as the other, since a machine that has a key and lacks the optional extra was sent to the wrong file by the sentence that stood here

  Scenario: anthropic_sdk hands back the Anthropic constructor, or nothing
    Given an interpreter that may or may not have the optional extra installed
    When anthropic_sdk tries the import
    Then it returns the constructor when anthropic is installed
    But it returns nothing when it is not, so the absence is a value this module can report rather than an exception caught beside every other failure
    And it is passed IN to the boundary rather than reached for, because eight tests had to overwrite that name to exercise a missing SDK, a raised request or a thinking-block reply, which is a test asserting against its own fixture

  Scenario: _first_text finds the reply in the first block that carries text
    Given the content blocks of a model response
    When _first_text walks them in order
    Then it returns the text of the first block that has any
    But it returns nothing when no block does, which the caller reports as the model declining rather than as a failed request, since a reply that arrived and held nothing sayable is a thing the model did and not a thing the network did

