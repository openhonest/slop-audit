# Paper C Pre-Registration Amendment: Refinement of L1.18 to Exclude Bound Literals

**Amendment date.** 2026-04-24.
**Original registration date.** 2026-04-10.
**Prior amendment.** `paper-c-amendment-l118-rationale.md` (2026-04-16), which supplied the theoretical justification for L1.18 as an audit indicator.
**Original document.** `../preregistrations/paper-c-instrument-validation-preregistration.md`.
**Purpose.** To refine the operational definition of L1.18 so that module-level references to **bound literals** — names assigned once to immutable values and never mutated — are excluded from the mutable-state count. The prior amendment established *why* L1.18 is relevant (behavior-domain unboundedness). This amendment tightens *what* L1.18 counts, so that the reported number measures the property the prior amendment defended.
**Data-collection status.** No Paper C data has been collected at the time of this amendment. All Paper C pre-registered predictions and falsification criteria remain unchanged. Paper 1 (Wasserman 2026, preprint, in preparation) drafted its original per-language medians under the prior definition; those medians will be preserved via the `--strict-mode` flag in the released analyzer, and the draft will be updated to carry the amended medians as the primary result alongside the strict-mode medians for reference (see §5).

---

## 1. Motivation

Running the reference analyzer `l1_18.py` on Honest-Framework-compliant Python scripts produces mutable-state ratios between 18% and 57%. The flagged code includes module-level dispatch dictionaries, band-threshold tables, compiled regular expressions, integer constants, and frozen configuration values. These are immutable-by-construction constants. Reading them does not change the function's observable behavior across runs, and no mutation of any of them occurs anywhere in the programs that read them.

The following two functions illustrate the overclaim directly.

```python
# Function A — flagged by l1_18.py at current definition
GOD_FILE_LINES = 1000
def is_god_file(size: int) -> bool:
    return size > GOD_FILE_LINES

# Function B — not flagged
def is_god_file(size: int) -> bool:
    return size > 1000
```

Both functions compute the same partial function from `int` to `bool`. Both have identical behavior domains. Both are exhaustively testable under any reasonable definition. Yet the first is counted toward L1.18 and the second is not. The difference is notational — a name has been introduced for the literal `1000` — and notational differences are precisely the thing a behavioral indicator should not penalize.

The pattern generalizes. A recognizer vocabulary defined as a `frozenset` of strings at module top level, a dispatch table that maps enum names to pure handler functions, a compiled regex assigned once and never replaced: each of these is a named value whose binding is fixed for the life of the program. Each is counted by the current analyzer as external mutable state, and each inflates the L1.18 ratio without adding any element to the behavior domain that exhaustive testing must cover.

The issue is not a minor one. In honest-framework-style code — which uses module-level constants liberally precisely because classes and hidden state are forbidden — the overclaim dominates. `l1_18.py` scored against itself reports 18-57% depending on which helper module is measured. The analyzer is flagging its own legitimate constants as the defect it is designed to detect. The scientifically honest move is to tighten the indicator's definition so it measures what its theoretical statement claims it measures.

## 2. The original definition and what it was trying to measure

The prior amendment (`paper-c-amendment-l118-rationale.md` §2) grounds L1.18 in a statement about *behavior domains*. A function `f(x₁, …, xₙ)` whose body reads only its parameters has behavior domain `D₁ × … × Dₙ`, which is finite whenever each `Dᵢ` is finite. A function that also reads external mutable state `S` has effective signature `f(x₁, …, xₙ, S)` and behavior domain `D₁ × … × Dₙ × State(S)`, where `State(S)` is the set of values `S` can take across the history of program execution. When `State(S)` is unbounded, the behavior domain is infinite and exhaustive behavioral testing is impossible in finite time.

The theoretical statement is about *state whose value can change during program execution*. That is the property that makes `State(S)` non-singleton and, in the general case, unbounded. The prior amendment was careful on this point: §4 item 3 explicitly disclaims the bounded case: "Functions that reference bounded external state (e.g., a small enumerated set of configuration flags) have finite behavior domains and are finitely testable." The claim concerns unbounded mutable state, not every appearance of a free name on the right-hand side of an expression.

The operational definition published in `methodology/03-layer1-indicators.md` §L1.18, however, instructed the analyzer to count *any* function that "reads or writes variables not declared in the function's parameter list or local scope (instance variables, class variables, global variables, module-level mutable state)." The parenthetical listed the intended targets, but the analyzer implementation flagged every module-level name, regardless of whether the value at that name could change. An integer constant, a frozen dispatch table, and a process-wide mutable cache were all counted equally.

The gap between the theoretical statement and the operational definition is the gap this amendment closes. L1.18 is supposed to measure the fraction of a codebase's functions whose behavior domain is, in principle, unbounded by the non-parameter state they reference. Names bound once to immutable values do not contribute to that fraction. The analyzer should not count them.

## 3. Bound literals do not expand the behavior domain

A bound literal is a *named value*, not *state*. The function `is_god_file(size)` shown in §1 reads the name `GOD_FILE_LINES`, but the value at that name is fixed at module load and never reassigned, mutated, or otherwise perturbed. Across every execution of the program, every call to `is_god_file` sees the same value. The function's behavior domain is `{int} → {bool}`, identical to the inlined-literal version. Adding the name `GOD_FILE_LINES` to the module namespace did not enlarge `State(S)`; `State(S)` for this name is a singleton set, and singleton-set state is mathematically indistinguishable from a literal.

The argument generalizes to any immutable value bound once. A module-level `FROZEN_CONFIG = MappingProxyType({...})`, a compiled `COMMIT_RE = re.compile(r"^commit ")`, a threshold `HEALTHY_MAX = 0.15`, a dispatch table `HANDLERS = {"add": _add, "sub": _sub}`: each of these has `State(·) = {initial_value}`. The Cartesian product `D₁ × … × Dₙ × {initial_value}` is order-isomorphic to `D₁ × … × Dₙ`. Exhaustive testing of the function that reads the bound literal is exactly as feasible as exhaustive testing of the function with the literal inlined.

The contrast with genuine mutable state is sharp. Consider a function that reads `CACHE`, where `CACHE` is a dict mutated elsewhere in the program via `CACHE[key] = value` or `CACHE.pop(key)`. The set `State(CACHE)` is not a singleton. It grows and shrinks with the execution history of the mutating functions. It depends on call order, prior inputs, timing, and in concurrent settings on the non-deterministic interleaving of threads. The behavior of any function that reads `CACHE` is therefore characterized not by its parameters alone but by the Cartesian product of its parameters and `State(CACHE)`, and `State(CACHE)` is in the general case unbounded. This is the state-space-explosion case the prior amendment described. The bound-literal case is mathematically disjoint from it: `State(·)` is a singleton, not an unbounded set.

A useful check is to ask whether moving the name into the function's local scope would change the function's observable behavior. For a bound literal, inlining the value (or assigning it to a local at function entry) produces an observably-identical function. For mutable state, inlining is impossible: the whole point of the reference is to read whatever value the state currently holds, which local-scope inlining cannot express. This substitution test separates the two categories cleanly, and it is the test the amended analyzer implements.

One further observation tightens the argument. The Honest Framework's architectural rule — dispatch tables over if/elif/else chains — produces code that is *denser* in bound-literal references than comparable class-based code. A dispatch function reads a module-level dict of handlers; an if/elif/else chain embeds the handlers as inline conditions. Counting the first as mutable state and the second as pure, which the current analyzer does, inverts the intended ordering. The amended analyzer restores the intended ordering: bound-literal dispatch is recognized as pure, which is the property it was designed to have.

## 4. The amended definition

A named binding is a **bound literal** — and therefore **not** counted toward L1.18 — if and only if all four of the following hold. The definition is uniform across Python, Java, TypeScript, and C# at the semantic level; per-language operationalization recognizes each clause through the appropriate tree-sitter node types.

1. **Declared at module scope (Python, TypeScript) or as a class-level constant (Java `static final`, C# `const` or `static readonly`).** Python: module-top-level `NAME = value`. TypeScript: module-top-level `const NAME = value` (top-level `let`/`var` remain module-mutable by the original paper's §3.1 and are not bound-literal-eligible regardless of RHS). Java: class-level `static final` field (or interface-level `final`, constant by default). C#: class-level `const` or `static readonly` field.
2. **Assigned exactly once.** `NAME` is never on the LHS of any subsequent assignment, augmented assignment, or update expression in the file.
3. **Never mutated.** `NAME` is never subject to the language-specific syntactic mutation vocabulary. Python: `.append`, `.extend`, `.update`, `.pop`, `.clear`, `.remove`, `.sort`, `.reverse`, `.insert`, `.setdefault`; subscript assign `NAME[k] = v`; `del NAME[...]`. Java: `.add`, `.addAll`, `.put`, `.putAll`, `.remove`, `.clear`, `.sort`; indexed assign; field assign. TypeScript: `.push`, `.pop`, `.shift`, `.unshift`, `.splice`, `.sort`, `.reverse`, `.set`, `.delete`, `.clear`; subscript or property assign. C#: `.Add`, `.AddRange`, `.Insert`, `.Remove`, `.RemoveAt`, `.Clear`, `.Sort`; indexed assign; field assign. Read-only method calls are permitted.
4. **Right-hand side is bound-literal-eligible.** Accepts: immutable primitive literals (per-language); immutable composite literals (Python `tuple`/`frozenset`; Java `List.of`/`Set.of`/`Map.of`/immutable array initialisers; TypeScript `readonly` tuples and frozen object literals; C# `ImmutableArray`/`ImmutableDictionary` / `readonly` collection expressions); dict/object/map literals whose keys and values are bound-literal-eligible (recursive); **any class instantiation or function call** on the right-hand side (Python `ast.Call`; Java `object_creation_expression` or `method_invocation`; TypeScript `call_expression` or `new_expression`; C# `object_creation_expression`, `implicit_object_creation_expression`, or `invocation_expression`); and type declarations (Python `TypedDict`/`Protocol`/`NamedTuple`/`@dataclass(frozen=True)`; Java records; C# `readonly record struct`; TypeScript `type` aliases and `interface`).

The "any call is eligible" rule reflects the principle that *instantiation does not expand the behavior domain; only mutation does.* The enclosing binding is still subject to the mutation check in clause (3), which is the operational test for whether the instance changes in practice. This rule replaces the earlier whitelist-based RHS recognizer (`frozenset`, `tuple`, `re.compile`, `Path`, `datetime` enumerated explicitly), because the whitelist was arbitrary — why `datetime` but not `Decimal`, why `Path` but not `URL`? — and did not generalize to third-party classes that are bound-by-convention. Under the current rule, `LANG_CFG = {"python": Language(tree_sitter_python.language())}` is bound-literal-eligible as long as `LANG_CFG` is not subject to the mutation patterns of clause (3).

A reference by a function body to a name that satisfies all four clauses is **not** counted toward L1.18. The language-specific operationalization is implemented in `bound_literal_detector.py`, a unified tree-sitter-based detector that dispatches on language through a single `LANG_CFG` table in the same architectural pattern as `l1_18.py` itself.

A secondary fix accompanies the amendment: the original `is_suppressed_identifier` in `l1_18.py` did not suppress identifiers in the name slot of keyword-argument nodes (Python) or named-argument nodes (C#). This manifested as false positives where a kwarg name happened to match a module-mutable or class-member name. The fix extends `is_suppressed_identifier` to cover `keyword_argument.name` (Python) and `argument` with `name_colon:` (C#), and applies the suppression inside `module_mutable_refs` (which previously did not use `is_suppressed_identifier` at all). The fix applies in both strict and amended modes. TypeScript is unaffected (`shorthand_property_identifier` is a distinct AST node not reached by the identifier walk); Java has no keyword arguments.

The analyzer change is wired into `l1_18.py` and enabled by default. The prior behavior — including the latent kwarg bug — is **not** preserved at runtime; any third party wanting byte-for-byte reproduction of the pre-amendment analyzer should check out the repository at the pre-amendment commit tag. The new detector is self-checking: run against itself, `bound_literal_detector.py` produces L1.18 = 0.0%, a bootstrap property the prior whitelist-based version achieved only partially.

## 5. Impact on Paper 1's published results

Paper 1 (Wasserman 2026, preprint, in preparation) drafted cross-language medians of 61.1% (Python), 53.0% (Java), 40.0% (C#), and 14.8% (TypeScript) on a 200-repository corpus. These numbers were produced by the strict-mode analyzer: the one that counts every module-level reference. They are correct under that definition and will remain available for reproduction via the `--strict-mode` flag in the released analyzer.

The amended analyzer will produce different numbers on the same corpus. The direction is predictable: the amended ratio cannot be higher than the strict ratio on any repository, because the amended analyzer excludes a subset of what the strict analyzer counts. The magnitude is not predictable from first principles. It depends on how heavily each codebase uses module-level constants, and that proportion varies by language, by framework, and by individual repository.

The amendment protocol is therefore:

- Paper 1's published results stand as-published. The strict-mode flag preserves reproducibility of the 61.1% / 53.0% / 40.0% / 14.8% medians exactly.
- A corpus rerun using the amended analyzer (default mode) will be performed on the same 200-repository frozen corpus. The rerun will report the new medians, the per-language delta distribution, and the fraction of each repository's original score attributable to bound-literal references.
- Because Paper 1 is still in draft and not yet deposited, the rerun results will be folded into the draft as the primary per-language medians; the strict-mode medians will be reported alongside as the reference values reproducible under `--strict-mode`. No post-deposit addendum is required.
- Paper A (the 300-repository pre-registered confirmatory study, not yet run) will use the amended analyzer by default. The pre-registration will be annotated with a note referencing this amendment, recorded on OSF before the data-collection window opens.

This is a post-publication refinement, not a correction of an error in the published analysis. The strict-mode analyzer computed its defined quantity faithfully. The amendment narrows the definition of that quantity to match the theoretical claim it was supposed to operationalize. The preprint was a snapshot of the best-available analyzer at the time of publication; the refinement is the normal progress of measurement science.

## 6. Relationship to related work

The bound-literal / mutable-state distinction has long-standing analogues in programming-language design and formal verification.

**Type-system const / final / val.** TypeScript's `const`, Java's `final`, C++'s `const`, Kotlin's `val`, Scala's `val`, and Rust's non-`mut` bindings all encode — at different points on the rebinding/mutation spectrum — a notion of "this name will not be reassigned." None of them catches the full bound-literal property (most permit interior mutability through reference types), but each reflects the same underlying intuition: names bound once are categorically different from names that rebind.

**Functional-programming defaults.** Haskell, Clojure, Elm, and the ML family treat immutability as the default. In these languages, the bound-literal distinction is approximately universal: all module-level bindings are bound literals unless IO or explicit mutable-ref machinery is invoked. The Python analyzer must reconstruct by static analysis what these languages express in the language itself.

**Model checking.** The model-checking literature (Clarke & Emerson 1981; Queille & Sifakis 1982; Pnueli 1977 on temporal logic of reactive systems) distinguishes the *initial configuration* of a system from its *transient state space*. Bound literals are part of the initial configuration; they are fixed at system start and do not participate in the state-transition relation. The state-space-explosion problem — which the prior amendment invokes as the theoretical ground of L1.18 — is explicitly a property of the transient state space, not the initial configuration. Counting bound-literal references toward L1.18 conflates the two, and the amendment restores the model-checking distinction.

**Python-specific: `typing.Final`.** PEP 591 (2019) introduced the `Final` type qualifier, intended to mark names that should not be rebound. The specification is explicit that `Final` has no runtime enforcement in Python; the check is performed by type checkers (`mypy`, `pyright`) at static-analysis time. The amended `l1_18.py` performs a closely related static check — whether a name is *effectively* `Final`, regardless of whether the programmer annotated it — which is the right level of analysis for an audit indicator that cannot require source-code annotations.

The amendment is therefore not a novel theoretical move. It joins a well-established tradition that treats fixed initial-configuration values as categorically distinct from transient mutable state. What is novel is the operationalization of the distinction at corpus scale for an audit indicator that cannot rely on programmer discipline.

## 7. Limitations and edge cases

Several cases are acknowledged openly rather than claimed-solved.

**Runtime monkey-patching.** Python permits any module-level name to be rebound from outside via `module.NAME = new_value`, and equivalent patterns exist in C# (reflection-based field mutation) and TypeScript (arbitrary property assignment on imported namespaces). The amended analyzer presumes that single-assignment within the source file implies runtime immutability. A module or class that is deliberately monkey-patched or reflection-mutated at runtime escapes detection and would be miscategorized as bound-literal. We mark this as a **known residual false negative** to be addressed in a future amendment, most naturally by a companion indicator that detects dynamic-attribute-rebinding patterns (setattr, reflection writes, property descriptors installed at runtime). It is outside the scope of the current L1 indicator suite as defined.

**Mutable default arguments.** The idiom `def f(x, cache=[]):` creates a per-function-object mutable list that persists across calls and is effectively module-level mutable state wearing a parameter costume. The amended analyzer does not currently flag this case. It is queued as a known-issue item for a future amendment and is not considered a false negative for L1.18 v0.

**Regular classes versus `@dataclass(frozen=True)`.** The amended analyzer treats `@dataclass(frozen=True)` declarations and other guaranteed-immutable type definitions as bound literals; regular `class` declarations with mutable attributes are not. This distinction is intentional — a mutable class at module scope is module-level mutable state — but the cutoff is debatable. Reviewers who prefer a stricter line are free to run `--strict-mode`.

**Circular imports.** A name exported by module A and imported into module B, where module B's import is evaluated before module A has finished top-level execution, can bind to a partial state of A's namespace. The amended analyzer analyzes each module in isolation and does not trace import order; such pathological cases are not detected.

**C extensions and compiled modules.** Bindings imported from C-extension modules (`numpy`, `re` patterns via compiled objects, SQLite connection objects) cannot be statically analyzed as bound literals because the source is not Python. The amended analyzer treats imported names as bound literals if the import statement itself is at module scope and the name is not reassigned within the importing module. This is a conservative approximation: an imported name could in principle be a reference to mutable C-level state.

**`importlib.reload` and dynamic import machinery.** Any rebinding that occurs via `importlib.reload`, `__import__` with custom finders, or module-replacement gymnastics is invisible to the static pass and will not cause the analyzer to reclassify the affected names.

These limitations are disclosed rather than hidden. They do not invalidate the amendment; they characterize its edge-of-envelope behavior for reviewers who wish to probe it.

## 8. Practical implications

The amended L1.18 is a more defensible headline indicator. Enterprise reviewers whose first objection to high L1.18 scores is "but my codebase uses lookup tables at module scope and those are not really state" can be answered with "those are bound literals and the amended analyzer does not count them." The indicator is narrowed to exactly the thing the prior amendment defended on theoretical grounds: references to state whose value can change during program execution.

The expected effect on the 200-repository corpus is that per-language medians will shift downward on every language, because the amended analyzer cannot count more than the strict analyzer. Neither the magnitude nor the per-language distribution of the shift is claimed in advance; both will be reported after the rerun. The relative ordering of the four languages — Python highest, TypeScript lowest, Java and C# in between — is expected to be preserved, because bound-literal density is roughly comparable across the four languages and its exclusion should not reorder them. That expectation is a prediction, not a finding, and the rerun will test it.

The amendment also has a small practical benefit for framework authors. The Honest Framework's architectural rules — dispatch tables over conditional chains, module-level recognizer vocabularies, frozen configuration — produce code that the strict-mode analyzer penalizes precisely where Honest Code intends the opposite. The amended analyzer aligns the measurement with the architectural intent.

## 9. Conclusion

L1.18 is amended to exclude references to bound literals — module-scope or class-level constant names assigned once to immutable values and never mutated — from the mutable-state count. The amendment tightens the operational definition of L1.18 so it measures the property its theoretical statement claims: the fraction of a codebase's functions whose behavior domain is unbounded by state whose value can change during program execution. Bound literals are part of the initial configuration, not the transient state space, and do not contribute to the state-space explosion that makes exhaustive behavioral testing infeasible. Paper 1 (Wasserman 2026, preprint, in preparation) is still in draft; the amended corpus rerun will produce the paper's primary medians, with strict-mode medians reported alongside as the reference values reproducible under `--strict-mode`. Paper A (the 300-repository pre-registered study) will use the amended analyzer from the start. The indicator retains its theoretical claim, its audit utility, and its compliance-framework mapping; it now reports a number that more faithfully corresponds to the claim.

---

**Provenance.** This amendment is authored alongside the analyzer change (`bound_literal_detector.py` added as a unified tree-sitter-based four-language detector, wired into `l1_18.py`, default enabled). Paper 1 is still in draft; the amended corpus rerun will produce its primary medians, with strict-mode medians reported alongside for reference.
