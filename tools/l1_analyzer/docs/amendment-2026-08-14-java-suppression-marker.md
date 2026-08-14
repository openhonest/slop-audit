# Amendment 2026-08-14: Java's suppression marker is an annotation, not a comment

## What was wrong

L1.15 counted `@SuppressWarnings` only through the comment arm, because `_COMMENT_TYPE_ESCAPES` listed it beside `# type: ignore` and `// @ts-ignore`. Java does not write it as a comment. A real parse settles it: `@SuppressWarnings("unchecked")` is an `annotation` node whose `name` field holds the identifier, and an argument-free annotation is a `marker_annotation`. The comment arm therefore never fired on Java's only real suppression marker, and Java's escape count was made up entirely of `Object` tokens.

The arm was not merely weak, it was dead. Across the two Java corpus repositories, production scope, no comment begins with `@SuppressWarnings`: 0 in gson, 0 in junit4. Nothing was ever counted through it.

This is the defect the previous amendment recorded under "Not fixed here" and left open. It widens the measure rather than narrowing a false positive, which is why it was separated from that change.

## The counting rule

**One annotation is one escape, however many warnings it names.** `@SuppressWarnings({"unchecked", "rawtypes"})` counts once, not twice.

The rule is the one the comment arm already applies: `# type: ignore[attr-defined, arg-type]` counts once. What L1.15 measures is the decision to opt out of the type system, and the author makes that decision once per site. Counting the names inside would weight one site by how thorough its author was in listing what he silenced, which rewards the vaguer suppression.

The name is read from the grammar's `name` field, followed down as far as the field goes, so `@java.lang.SuppressWarnings` resolves to `SuppressWarnings`. Reading the field rather than splitting the node's text is the lesson of `amendment-2026-08-02-rust-receiver-and-static.md`.

`@Override`, `@Deprecated` and `@SafeVarargs` are annotations and are not counted. Only the names in the language's `annotation_escape_names` count, which for Java is `SuppressWarnings` alone.

`@SuppressWarnings` was removed from `_COMMENT_TYPE_ESCAPES` in the same change. It now lives in the annotation table, where the grammar puts it. A comment that begins with the marker is a commented-out annotation, which is disabled code, not an active suppression.

## The architectural cause, removed

The vocabulary was unpacked at the call site, not carried in the config. `_count_type_escapes_in_tree` took the escape tokens as an argument, and two callers assembled them independently: L1.15 in `indicators.py` and the pre-commit ratchet in `cli.py`. Adding a vocabulary therefore had to be remembered twice, and the gate would have gone on counting by the old rule while the indicator counted by the new one. Nothing would have failed; the two numbers would just have drifted apart. Python's own gate caught it here only because the new parameters were positional and required.

The counting function now takes the `LangCfg` and reads the whole vocabulary itself, so a vocabulary added to the table reaches every caller by construction. `type_escapes.rs` takes `&lang::LangCfg` for the same reason, and `test_l1_15_the_ratchet_counts_what_the_indicator_counts` holds the gate and the indicator to one answer.

## What the numbers did

Both repositories at their pinned corpus commits, Python reference, `--no-exec`, production scope:

| Repo | Escapes before | Escapes after | L1.15 before | L1.15 after | Band |
|---|---|---|---|---|---|
| google/gson | 161 | 292 | 6.91/kLOC | 12.54/kLOC | Slop, unchanged |
| junit-team/junit4 | 277 | 294 | 13.87/kLOC | 14.72/kLOC | Slop, unchanged |

The deltas are +131 and +17, which match the `@SuppressWarnings` annotations in production scope exactly: 131 in gson, 17 in junit4. Nothing else moved, and no repository's band changed.

The gson number is the point of the fix. Almost half of that repository's real type escapes were invisible, and the visible half were all `Object` tokens.

## Regression cover

`tests/test_basic.py`:

- `test_l1_15_counts_java_suppresswarnings_annotation`: `@SuppressWarnings("unchecked")` on a method counts 1, with `@Override` beside it uncounted.
- `test_l1_15_java_suppression_counts_once_however_many_warnings`: a two-name suppression and a fully-qualified one count 2 in total, not 3.
- `test_l1_15_java_comment_mentioning_suppresswarnings_is_documentation`: a comment about the marker and a string holding it count 0. This is the self-reference rule of `amendment-2026-08-14-self-reference-in-the-meter.md`, held in place while the marker moved.
- `test_l1_15_the_ratchet_counts_what_the_indicator_counts`: the pre-commit gate and L1.15 return the same count for the same file.

`src/indicators/type_escapes.rs` carries the same four cases as Rust unit tests, including a fourth that re-asserts the comment and string rules on the Python grammar so the two walkers cannot drift on the rules the annotation arm sits beside.

## The port

`tools/slop-audit-rs` landed the change in the same commit: `lang.rs` gains `annotation_escape_nodes` and `annotation_escape_names` on every row, and `type_escapes.rs` gains the annotation arm. Parity was re-run: 16/16 indicators equal on this repository, and 16/16 on each of gson and junit4.

## C#, reported and not fixed

C# has the same *shape* and not the same defect. `[SuppressMessage]` parses as an `attribute` node carrying a `name` field, so this change's machinery would count it with one row of vocabulary. But nothing in the C# configuration ever named it, so nothing is currently dead or mis-bucketed. Adding it is a new measurement decision, not a repair, and the decision is about meaning:

- `@SuppressWarnings("unchecked")` silences the Java compiler's own type diagnostics. It is a type escape by construction.
- `[SuppressMessage]` silences a static-analyzer rule (naming, design, usage), which is usually not a type judgment at all.
- `[Obsolete]` is a deprecation marker. It suppresses nothing and should not be counted under any reading.

The corpus says the stakes are small either way: in production scope, Newtonsoft.Json carries 1 `[SuppressMessage]` and 41 `[Obsolete]`, and RestSharp carries 0 and 10. Whoever decides should decide on the meaning, not on the size of the move.

## Note for Paper A

Java L1.15 numbers rise under this fix, from an under-count toward the true value. It is a defect correction, not a definitional change, and belongs in the v1-vs-v2 side-by-side re-run per the finite-testability supersession rule.
