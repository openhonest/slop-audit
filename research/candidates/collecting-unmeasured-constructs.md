# Collecting what we could not read, without collecting the code

**Status: proposal, not approved. Written 2026-08-15.** It sends data off an adopter's machine, so it is a product decision before it is a code change.

## The recommendation

When the analyzer meets a construct it has no rule for, offer to send us the **shape of the parse tree** and nothing else: node types and how they nest, with every leaf value stripped. Opt in per run, with the entire payload printed first. Collect only the cases that are our backlog, never the ones that are the adopter's architecture.

## Why we need it, and why the current ask fails

UNMEASURED is our gap. The card says so on every report that carries one: *"That is our gap to close, not yours. Send us the repository and we will teach our reader the construct."*

Nobody will ever do that. We are asking for the maximum possible payload, from a stranger, about proprietary code, to fix a problem that is ours. The ask is honest and useless, so we learn nothing and the same construct stays unreadable for the next adopter.

The three kinds we know we cannot read were found by running the analyzer over repositories we already had. Every one was a Python class-body binding, a C struct field or a C# auto-property, and it took two days of hand-reading to find them. There is no reason to think we have found the last three, and no mechanism that would tell us.

## What gets sent

The construct, as a path through the grammar:

    csharp / property_declaration
      -> modifiers, predefined_type, identifier, accessor_list
         -> accessor_declaration(get), accessor_declaration(set)

Plus the language, the analyzer version, and the reason code that classified it as unread.

**No identifiers. No literals. No file names. No line numbers. No source.**

## Why the promise is structural rather than contractual

A payload of node types has nowhere for a secret to live. There is no string field, so a key cannot be in it. There is no identifier, so a business term cannot be in it. There is no path, so the repository cannot be identified from it.

This matters because it changes what the consent screen can say. Most consent asks a reader to trust a policy about data they cannot see. This one can print the payload in full, and the reader can confirm by looking that it contains no identifiers. That is verification rather than trust, and it is the same standard the rest of this instrument is held to: **make the wrong thing impossible rather than promising not to do it.**

The strip must be done by construction, not by filtering. A redaction pass over a payload that could have carried identifiers is a rule that can miss one. Building the payload from node types only means there is no step at which an identifier could enter.

## What is not collected

**Only `unmodeled_callee` and its equivalents, never `external_boundary`.** The silence reasons already draw this line. An unmodeled callee is a name we have not taught the analyzer, which is our backlog. An external boundary is a place the adopter's own architecture hands data to code we cannot read, which is theirs to fix with a contract. Collecting the second means asking someone to send us evidence about their design, and that is not our business.

**Nothing that a verdict was reached on.** If the analyzer read it and decided, there is nothing to learn.

## The consent rules

**Opt in per run.** Not a configuration flag set once and forgotten. The reader sees the payload each time and decides each time.

**Print the whole payload, not a summary.** A truncated preview reintroduces the trust problem the design exists to remove.

**No automatic sending from an agent loop.** An MCP server running inside an agent's edit loop, posting shapes upstream between keystrokes, is a different product with a different consent story. It must not arrive by inheritance from this one. If it is ever wanted, it is a separate decision with its own screen.

**Default off, and silent when off.** A tool that nags is a tool people disable entirely, and then we lose the reports we would otherwise have had.

## What it would buy

A list, ordered by frequency, of the constructs our reader cannot see. That is the backlog we currently discover by hand, two days at a time, and it is the only mechanism that would tell us about a construct in a language we do not write.

It also closes a gap in the standard's own claim. We say the instrument discloses what it could not read. Today that disclosure reaches a reader who can do nothing with it and does not reach us, who can.

## What must be decided

**Where it goes and who holds it.** A shape corpus is not sensitive, but it is still someone's data, and the Foundation has no collection infrastructure today.

**Whether the analyzer version is enough provenance.** A shape that was unreadable at one version may be readable at the next, so a report needs to expire or be re-checked, or the backlog fills with things already fixed.

**Whether to do it at all before the reader is better.** We currently cannot read three constructs we know about. There is an argument for closing those first and only then asking adopters to tell us about ones we do not know about.
