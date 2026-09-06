"""
Reference implementations of Slop Audit L1.1-L1.20 indicators.

Design goal: runnable against *any* language.
- L1.1-L1.8: pure git log (language-agnostic)
- L1.9-L1.11: file presence (language-agnostic)
- L1.12-L1.20: where source analysis is needed, use tree-sitter with a
  per-language CFG (LANG_CFG) so the *same* semantic metric works across
  Python, Java, JavaScript, TypeScript, C#, Ruby, Go, Rust, and C.

Honest Code shape (enforced, not aspirational):
- Data is TypedDict, never a class.
- Scoring is a pure function of counts (see `band` and the `_score_*` helpers);
  file reading is done by boundary readers (`_read_*`) that return the raw data
  plus a count of files they could not read. No metric silently scans a subset:
  an unreadable file is counted and surfaced in `details`, never swallowed.
- An unknown language returns n/a; it is never silently analyzed as something
  else.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from tree_sitter import Node, Parser

from l1_analyzer import (
    c_trace,
    csharp_trace,
    data_tables,
    go_trace,
    java_trace,
    js_trace,
    pytest_trace,
    ruby_trace,
    rust_trace,
)
from l1_analyzer.boundary import boundary
from l1_analyzer.disclosure import (
    with_skipped as _with_skipped,
)
from l1_analyzer.incomplete import IncompleteCode, ratio
from l1_analyzer.lang_spec import DECISION_NODE_TYPES

if TYPE_CHECKING:
    # Only ever an annotation here, and `from __future__ import annotations` keeps it a
    # string at run time. A plain import would close a cycle: the panel names the shapes
    # the provers return, and a prover reads this module's parser.
    from l1_analyzer.panel import Panel
from l1_analyzer.pytest_trace import L1Result
from l1_analyzer.scope import (  # noqa: F401
    _IGNORE_DIRS,
    _TEST_DIR_MARKERS,
    _TEST_STEM_SUFFIXES,
    _TOOLING_FILES,
    PRODUCTION,
    PRODUCTION_WITHOUT_CONFORMANCE,
    WHOLE_REPO,
    BucketedPath,
    BucketedPaths,
    _bucket_reason,
    _component_scoped_out,
    _extra_reason,
    _in_ignored_dir,
    _read_source_bytes,
    _read_text_files,
    _repo_has_packages,
    _rglob_files,
    _test_dir_corroborated,
    _test_file_by_name,
    bucketed_paths,
)
from l1_analyzer.ts_nodes import descendants

# ---------------------------------------------------------------------------
# Data shape + pure scoring
# ---------------------------------------------------------------------------

# Imported, not redeclared. Two definitions of the published result type stood in this
# package and disagreed: pytest_trace's and this one, both named L1Result, both describing
# the same dict, and only one of them was ever made total. A reader typed against this copy
# was allowed to omit the details line that the other copy required.
def band(value: float, healthy: float, slop: float, *, higher_is_better: bool) -> str:
    """Pure map from a numeric value to a threshold band.

    higher_is_better=True: larger is healthier (e.g. doc-line ratio) - Healthy at
    value >= healthy, Not Healthy at value >= slop, else Slop.
    higher_is_better=False: smaller is healthier (e.g. mutable-state ratio) -
    Healthy at value < healthy, Not Healthy at value < slop, else Slop.
    """
    if higher_is_better:
        return "Healthy" if value >= healthy else ("Not Healthy" if value >= slop else "Slop")
    return "Healthy" if value < healthy else ("Not Healthy" if value < slop else "Slop")

# Both disclosure notes live in one module now. This one was here and `listed_note` was in
# absolute_paths, which is a module about hardcoded paths and no home for a reporting rule.

# ---------------------------------------------------------------------------
# Boundary readers (I/O). Each returns (data, skipped_count) so callers can
# surface partial scans instead of silently dropping unreadable files.
# ---------------------------------------------------------------------------


def compute_config_indicators(repo: Path) -> Panel:
    has_precommit = (repo / ".pre-commit-config.yaml").exists() or (repo / ".husky").exists()
    ci_files = list((repo / ".github" / "workflows").glob("*.yml")) + list((repo / ".github" / "workflows").glob("*.yaml"))
    ci_count = len(ci_files)
    has_docker = (repo / "Dockerfile").exists() or (repo / "docker-compose.yml").exists()

    # Each carries a details line naming what was looked for and where. These three shipped
    # a band and a value with no sentence, so a reader got Slop for the pre-commit indicator
    # with nothing saying what was searched. Every other indicator in the panel says it, and
    # the sentence is the difference between a grade and a measurement.
    return {
        "L1.9": {
            "value": "present" if has_precommit else "absent",
            "band": "Healthy" if has_precommit else "Slop",
            "details": ("a pre-commit hook config is present" if has_precommit else
                        "no .pre-commit-config.yaml and no .husky directory at the repository root"),
        },
        "L1.10": {
            "value": ci_count,
            "band": band(ci_count, 5, 1, higher_is_better=True),
            "details": (f"{ci_count} workflow file(s) in .github/workflows" if ci_count else
                        "no .yml or .yaml workflow files in .github/workflows"),
        },
        "L1.11": {
            "value": "present and parameterized" if has_docker else "absent",
            "band": "Healthy" if has_docker else "Slop",
            "details": ("a Dockerfile or docker-compose.yml is present at the repository root"
                        if has_docker else
                        "no Dockerfile and no docker-compose.yml at the repository root"),
        },
    }
from l1_analyzer.lang_cfg import (  # noqa: F401 - re-exported: every reader imports these from here
    LANG_CFG,
    TYPESCRIPT_CFG_OVERRIDES,
    LangCfg,
)

# Body node types that hold a function/method's statements, across all grammars.
_BODY_NODE_TYPES = ("block", "compound_statement", "body", "function_body", "body_statement", "statement_block")

# Every LANG_CFG entry must define these keys; access them directly (a missing
# key is a config bug that should raise, not silently default). Genuinely
# optional keys (instance_field_types, raw_mut_patterns) still use .get().
# `const_keywords` is NO LONGER optional for a text-scanned language: a shared
# default is what let TypeScript inherit `let ` as an immutability keyword, so the
# key is now read by direct subscript and a language that omits it raises.
_LANGUAGE_UNKNOWN = "unknown"

def _get_parser(lang: str) -> Parser:
    return Parser(LANG_CFG[lang]["language"])

def detect_primary_language(repo: Path) -> str:
    """Return the LANG_CFG key with the most files, or "unknown" when the repo
    contains no recognized source (callers report n/a rather than guess)."""
    # THROUGH THE SAME SCOPE POLICY EVERY OTHER READER USES. This counted the whole tree
    # with no build-artifact exclusion while the scopes in scope.py declare them, so a
    # directory nobody would call source decided which grammar the whole audit ran.
    #
    # Reproduced on this repository's own Rust crate: thirteen .rs files outside target/,
    # zero .c or .h outside it, and twenty-three vendored .c and .h inside it from the
    # linked tree-sitter grammars. The crate detected as C, every source indicator then ran
    # the C grammar over Rust, and the Rust-only interleaving meter returned n/a saying
    # "c not supported yet". `--lang rust` gave the right answer throughout, so the
    # measurement was right and only the detection was wrong.
    counts: Counter[str] = Counter()
    for lang, cfg in LANG_CFG.items():
        for ext in cfg["extensions"]:
            counts[lang] += sum(1 for f in _rglob_files(repo, f"*{ext}")
                                if not _in_ignored_dir(f, ()))
    if not counts or counts.most_common(1)[0][1] == 0:
        return _LANGUAGE_UNKNOWN
    return counts.most_common(1)[0][0]



# ---------------------------------------------------------------------------
# Full source-based indicators with tree-sitter for multi-lang support
# ---------------------------------------------------------------------------

class ExternalRun(TypedDict):
    """The result of shelling out: whether the tool ran, what it exited with, and what
    it printed. All three, because for a scanner a NON-ZERO EXIT IS THE FINDING.

    This replaces a `check_output` wrapped in `except CalledProcessError: return ""`,
    which collapsed "tool absent" and "tool ran and found something" into the same empty
    string. gitleaks exits 1 when it finds leaks and vulture exits 3 when it finds dead
    code, so under that helper L1.14 and L1.12 reported 0 findings and a Healthy band on
    exactly the repositories that had findings. The bug survived because the tests
    stubbed both tools with shell scripts that exit 0, so only the clean path was ever
    executed. A helper that cannot tell silence from a scream must not be the thing a
    security indicator reads.
    """
    ran: bool
    status: int
    output: str


def _run_external(cmd: list[str], cwd: Path) -> ExternalRun:
    try:
        done = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)
    except (FileNotFoundError, OSError):
        return {"ran": False, "status": -1, "output": ""}
    return {"ran": True, "status": done.returncode, "output": done.stdout}

def _measure(fn: Callable[..., L1Result], *args: object) -> L1Result:
    """Run one measure, and turn its refusal to answer into an n/a naming the reason.

    THE ONLY handler for IncompleteCode in the package. A measure raises rather than deciding
    what to do about its own ignorance, and this is the single place that decides. What it
    decides is n/a with the basis printed, never a band and never a number: the whole point of
    the exception is that unmeasured must not be spellable as clean.

    Do not add a second handler. Two handlers mean two policies, and the reason this exception
    exists is that four measures each invented their own and all four chose to publish zero.

    The first version of this took a `key: str` it never read, which is the defect this
    package spent 2026-08-16 cataloguing thirty-seven times elsewhere. The refusal already
    carries the measure's name, put there by `incomplete.refuse` at the site that knows it, so
    a second name passed in here could only ever disagree with the first.
    """
    try:
        return fn(*args)
    except IncompleteCode as refusal:
        return {"value": "n/a", "band": "n/a", "details": str(refusal)}


def compute_source_indicators(
    repo: Path,
    lang: str,
    exec_tests: bool,
    timeout_seconds: float,
    classify_state_bounds: bool,
    python_executable: str | None,
) -> Panel:
    """L1.12-L1.20. `lang` may be "auto" (resolved here) or a concrete key.
    `exec_tests` gates the two runtime indicators (L1.19 coverage, L1.20);
    `timeout_seconds` bounds each test-suite execution.

    `python_executable` is the interpreter the L1.19/L1.20 harness runs the target suite
    under. `None` (the named Nothing) means the analyzer's own interpreter; pass the target
    repo's venv python when it needs a Python the analyzer cannot run under (e.g. a 3.11
    target audited from a 3.12+ analyzer). If the target package is not importable there, the
    harness reports n/a with the reason rather than a misleading 0/5 or empty coverage.

    `classify_state_bounds` gates the additive L1.18b state-bounds refinement. It
    is ON by default for real users (CLI, web). The pre-registered experiments
    pass False, which leaves the registered output byte-for-byte unchanged: this
    is the ONLY line the flag touches, so off-mode cannot alter any L1.18 number."""
    if lang == "auto":
        lang = detect_primary_language(repo)

    # The panel, as its own declaration. It said `dict[str, L1Result]` while the language,
    # the path cover, the thread surface, the state reading and two indicators carrying
    # findings all went into it, so six of its rows disagreed with the line above them.
    results: Panel = {"lang": lang}
    results["L1.16"] = _measure(_trailing_whitespace, repo)
    results["L1.17"] = _measure(_god_files, repo)
    results["L1.18"] = _measure(analyze_mutable_state, repo, lang)
    results["L1.15"] = _compute_type_escapes(repo, lang)
    results["L1.19"] = _decision_space_l19(repo, lang, exec_tests, timeout_seconds, python_executable)
    # L1.12 and L1.14, native on tree-sitter. Both were external-tool delegations that
    # reported n/a on any machine without vulture or gitleaks, and reported a fabricated
    # zero on any machine that had gitleaks and a real leak (see ExternalRun).
    from l1_analyzer import dead_code, secret_scan
    # Both return dict[str, object], the same shape state_bounds.classify returns for
    # L1.18b: value/band/details plus the finding lists that make the number readable.
    results["L1.12"] = dead_code.analyze(repo, lang)
    results["L1.14"] = secret_scan.analyze(repo, lang)
    # One row, written by name. `update` from another panel would let this builder be
    # handed any row the panel knows and pass it through without saying which.
    results["L1.13"] = _compute_external_indicators(repo, lang)["L1.13"]
    results["L1.20"] = _test_determinism_l20(repo, lang, exec_tests, timeout_seconds, python_executable)
    if classify_state_bounds:
        from l1_analyzer import state_bounds
        results["L1.18b"] = state_bounds.classify(repo, lang)
        from l1_analyzer import path_cover
        results["path_cover"] = path_cover.cover_paths(repo, lang)
        # Additive, gated with the other refinements so frozen/pre-registered runs
        # (classify_state_bounds=False) keep exactly the L1.18 set. Measures the
        # concurrency audit surface, never a race verdict.
        from l1_analyzer import thread_surface
        results["thread_surface"] = thread_surface.scan(repo, lang)
        from l1_analyzer import absolute_paths
        # The scan's own shape, not the shared refusal type. `_measure` is the package's
        # single handler for a measure that declines, and it hands back a value, a band and
        # a reason; this scan hands back those and its findings. The row is declared with
        # the findings absent on the refusal rather than empty, so the two paths are told
        # apart by a reader, and the annotation says which one the call site can produce.
        # The refusal type widened to the scan's, which is what `_measure` hands back here:
        # the scan's own shape on the measured path, and the shared refusal on the other.
        # `Scan` carries its two extra fields as absent rather than empty for exactly that,
        # so both paths are one type and a reader can tell them apart.
        results["absolute_paths"] = _measure(absolute_paths.scan, repo, lang)
    return results

_WHITESPACE_EXTS = frozenset({".py", ".rs", ".c", ".h", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".cs", ".rb", ".go"})
_GOD_FILE_EXTS = frozenset({".py", ".rs", ".c", ".h", ".js", ".ts", ".java", ".cs", ".go", ".rb"})

def _trailing_whitespace(repo: Path) -> L1Result:
    """L1.16: percentage of non-blank lines with trailing whitespace."""
    files, skipped = _read_text_files(repo, _WHITESPACE_EXTS, scope=WHOLE_REPO)
    count = total = 0
    for _path, text in files:
        lines = text.splitlines()
        total += len(lines)
        count += sum(1 for ln in lines if ln.rstrip() != ln and ln.strip())
    ws_pct = ratio(count, total, "L1.16 trailing whitespace",
                   "no lines were read, so a rate over them is not zero, it is absent")
    return {"value": round(ws_pct, 2), "band": band(ws_pct, 0.5, 3, higher_is_better=False), "details": _with_skipped(f"{count} lines with trailing ws", skipped)}

# A file that is large because it holds a big data table is not the god-file smell:
# nobody hand-piles logic into a lookup table, and it has no merge-conflict surface a
# reviewer would split. So god-file size is measured in CODE lines, subtracting large
# container literals. Per language, the container-literal node types; a literal must
# read as a table by `data_tables`, which is the rule L1.13 asks too.
_GOD_FILE_LANG = {".py": "python", ".rs": "rust", ".c": "c", ".h": "c", ".js": "javascript",
                  ".ts": "typescript", ".java": "java", ".cs": "csharp", ".go": "go", ".rb": "ruby"}
_LITERAL_NODES = {
    "python": frozenset({"dictionary", "list", "set", "tuple"}),
    "javascript": frozenset({"object", "array"}),
    "typescript": frozenset({"object", "array"}),
    "java": frozenset({"array_initializer"}),
    "csharp": frozenset({"initializer_expression", "collection_expression"}),
    "go": frozenset({"literal_value", "composite_literal"}),
    "ruby": frozenset({"hash", "array"}),
    "rust": frozenset({"array_expression"}),
    "c": frozenset({"initializer_list"}),
}

def _data_literal_lines(node: Node, containers: frozenset[str], literals: frozenset[str]) -> int:
    """Lines spanned by data tables under `node`. A counted table is not recursed into, so
    nested tables are counted once rather than compounded.

    What counts as a table is `data_tables`, shared with L1.13. It was spelled here too,
    as "a container spanning twelve lines or more", and on 2026-09-01 I widened the copy in
    L1.13 and left this one. For half a day the same file was data to one indicator and code
    to the other, which is the one-fact-two-owners shape this package reports in other
    people's code."""
    from l1_analyzer import data_tables

    # An explicit stack, because this one stops at a table rather than reading every node,
    # which is the one thing `ts_nodes.descendants` cannot be asked for. It recursed until
    # 2026-09-05: a two-thousand-deep expression in Rust, Go, Java, C# or C took the
    # interpreter's stack, and the panel died rather than reporting a file it could not
    # read. Order does not matter to a sum, so the children go on as they come.
    total = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if data_tables.is_table(current, containers, literals):
            total += current.end_point[0] - current.start_point[0] + 1
            continue
        stack.extend(current.children)
    return total


def god_file_language(ext: str) -> str | None:
    """The grammar for one file extension, or None when this table has no row for it.

    None rather than the empty string, because the empty string was standing in for both
    "this extension has no grammar" and a grammar key, and the literal-node table was then
    asked about it as though it were a language.

    A one-argument `.get` is what Dispatch Tables Close Open Input asks for and a two-argument one is what it
    forbids. The rule's objection is to filing an unknown key under an answer written for a
    different key; `None` is not such an answer, it is the absence of one, and the caller
    below reads it as absence."""
    return _GOD_FILE_LANG.get(ext)


def _code_line_count(src: bytes, ext: str) -> int:
    """Lines of a file that are code, not a large data literal. Unknown languages (or
    a parse failure) get no discount and fall back to the raw line count."""
    total = len(src.splitlines())
    # The empty string used to stand in for both "this extension has no grammar" and a
    # grammar key, and `_LITERAL_NODES` was then asked about it.
    lang = god_file_language(ext)
    # The absence is read before the table, not through it. `None` reached `.get` and then
    # reached the parser, so a file whose extension this reader has no grammar for was asked
    # about as though `None` were a language.
    if lang is None:
        return total
    literal_types = _LITERAL_NODES.get(lang)
    if not literal_types:
        return total
    try:
        root = _get_parser(lang).parse(src).root_node
    except Exception:  # noqa: BLE001
        return total
    return total - _data_literal_lines(root, literal_types, data_tables.literal_types(lang))


def _god_file_reason(f: Path, repo: Path, has_packages: bool) -> str | None:
    """Why a candidate file is not a production god-file, or None to count it. The
    shared production scoping (tests, conformance, docs, tooling, vendored, loose
    scripts, generated code).

    The scope is the finite-testability meter's, so L1.17 is declared under it in
    scope.SCOPES and a change to that scope names L1.17 among the numbers it moves.

    This function used to read the generated-file marker itself, on the stated
    grounds that excluding machine output here alone left the other indicators'
    published numbers undisturbed. It left them wrong instead: every other measure
    read a parser table or a build stamp as code somebody wrote. _bucket_reason now
    reads the marker for all of them, and this function asks it rather than the file."""
    return _bucket_reason(f, repo, has_packages, PRODUCTION_WITHOUT_CONFORMANCE)


@boundary
def _god_files(repo: Path) -> L1Result:
    """L1.17: concentration of production files over 1k LOC (any file over 4k forces
    Slop). Discloses which large files were scoped out and why, so the drop is
    auditable rather than a silent skip."""
    has_packages = _repo_has_packages(repo)
    prod_files = god_files = big_files = skipped = 0
    scoped_by_reason: dict[str, int] = {}   # >1k-LOC files excluded from the count, by reason
    for ext in _GOD_FILE_EXTS:
        for f in _rglob_files(repo, f"*{ext}"):
            reason = _god_file_reason(f, repo, has_packages)
            try:
                src = f.read_bytes()
            except OSError:
                skipped += 1
                continue
            if reason is not None:
                if len(src.splitlines()) > 1000:   # raw size: disclose that a large file was scoped out
                    scoped_by_reason[reason] = scoped_by_reason.get(reason, 0) + 1
                continue
            code = _code_line_count(src, ext)      # data tables discounted: god-file is a logic pile
            prod_files += 1
            if code > 1000:
                god_files += 1
            if code > 4000:
                big_files += 1
    god_pct = ratio(god_files, prod_files, "L1.17 god-file concentration",
                    f"no production file carried a known extension ({sorted(_GOD_FILE_EXTS)})")
    band_value = "Slop" if big_files > 0 else band(god_pct, 0.5, 2, higher_is_better=False)
    note = f"{god_files}/{prod_files} files >1k LOC, {big_files} >4k LOC"
    if scoped_by_reason:
        note += "; " + ", ".join(f"{n} >1k LOC scoped out ({r})" for r, n in sorted(scoped_by_reason.items()))
    return {"value": round(god_pct, 2), "band": band_value, "details": _with_skipped(note, skipped)}

# The runtime-harness seam. Each entry runs the target repo's OWN suite and returns an
# L1Result; a language with no entry reports n/a with its reason. To add a language, write a
# module exposing `decision_space_coverage(repo, timeout, runtime_override)` and
# `test_determinism(repo, runs, timeout, runtime_override)` that detects the target's own
# runtime (directory-insensitive) and returns n/a with a reason when it cannot measure, then
# register it below. `runtime_override` is the optional runtime hint (the Python interpreter
# for pytest; self-detecting harnesses ignore it).
_COVERAGE_HARNESS = {
    # The hint reaches each harness under the name that harness gave it. Python's is an
    # interpreter, the rest take a runtime hint, and Rust reads its toolchain from the crate
    # so it takes neither. Forwarding it positionally would break the moment one of them
    # grows a parameter, which is what happened here.
    "python": lambda repo, timeout, override: pytest_trace.decision_space_coverage(
        repo, "python", timeout, python_executable=override),
    "rust": lambda repo, timeout, override: rust_trace.decision_space_coverage(repo, timeout),
    "go": lambda repo, timeout, override: go_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "ruby": lambda repo, timeout, override: ruby_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "javascript": lambda repo, timeout, override: js_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "typescript": lambda repo, timeout, override: js_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "java": lambda repo, timeout, override: java_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "csharp": lambda repo, timeout, override: csharp_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
    "c": lambda repo, timeout, override: c_trace.decision_space_coverage(
        repo, timeout, runtime_override=override),
}
_DETERMINISM_HARNESS = {
    "python": lambda repo, timeout, override: pytest_trace.test_determinism(
        repo, "python", 5, timeout, python_executable=override),
    "rust": lambda repo, timeout, override: rust_trace.test_determinism(repo, 5, timeout),
    "go": lambda repo, timeout, override: go_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "ruby": lambda repo, timeout, override: ruby_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "javascript": lambda repo, timeout, override: js_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "typescript": lambda repo, timeout, override: js_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "java": lambda repo, timeout, override: java_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "csharp": lambda repo, timeout, override: csharp_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
    "c": lambda repo, timeout, override: c_trace.test_determinism(
        repo, 5, timeout, runtime_override=override),
}


# honest-code-allow: L1.21.1 - _runtime_coverage and _runtime_determinism each look up a different harness table and refuse differently when the language has none. Two tables, two refusals, and the shape they share is the lookup rather than the work
def _runtime_coverage(repo: Path, lang: str, timeout_seconds: float, python_executable: str | None) -> L1Result:
    """Dispatch to the language's runtime coverage harness (the seam above), or n/a."""
    harness = _COVERAGE_HARNESS.get(lang)
    if harness is None:
        return {"value": "n/a", "band": "n/a", "details": f"runtime decision-coverage harness not implemented for {lang}"}
    # Routed through _measure, like every other measure. These two were the only ones that
    # were not, so a raise from a runtime harness escaped compute_source_indicators entirely
    # and aborted the audit. Three separate extractions of the seven harnesses each wanted to
    # refuse here and each had to return _na instead, which is how the gap was found.
    return _measure(harness, repo, timeout_seconds, python_executable)

def _runtime_determinism(repo: Path, lang: str, timeout_seconds: float, python_executable: str | None) -> L1Result:
    """Dispatch to the language's runtime determinism harness (the seam above), or n/a."""
    harness = _DETERMINISM_HARNESS.get(lang)
    if harness is None:
        return {"value": "n/a", "band": "n/a", "details": f"runtime determinism harness not implemented for {lang}"}
    # Routed through _measure, like every other measure. These two were the only ones that
    # were not, so a raise from a runtime harness escaped compute_source_indicators entirely
    # and aborted the audit. Three separate extractions of the seven harnesses each wanted to
    # refuse here and each had to return _na instead, which is how the gap was found.
    return _measure(harness, repo, timeout_seconds, python_executable)

def _decision_space_l19(repo: Path, lang: str, exec_tests: bool, timeout_seconds: float,
                        python_executable: str | None) -> L1Result:
    """Real coverage when the suite can run; otherwise the static decision-point
    enumeration with coverage clearly marked not-measured."""
    static = _compute_decision_space(repo, lang)
    if not exec_tests:
        static["details"] += "; coverage not measured (test execution disabled)"
        return static
    cov = _runtime_coverage(repo, lang, timeout_seconds, python_executable)
    if cov.get("band") != "n/a":
        return cov
    static["details"] += f"; coverage not measured: {cov.get('details', 'unavailable')}"
    return static

def _test_determinism_l20(repo: Path, lang: str, exec_tests: bool, timeout_seconds: float,
                          python_executable: str | None) -> L1Result:
    if not exec_tests:
        return {"value": "not run", "band": "n/a", "details": "test execution disabled"}
    return _runtime_determinism(repo, lang, timeout_seconds, python_executable)

_COMMENT_TYPE_ESCAPES = ("# type: ignore", "// @ts-ignore", "/* @ts-ignore")

def _annotation_name(node: Node) -> str:
    """The name an annotation declares, read from the grammar's `name` field.

    The field is followed down as far as it goes, so a scoped annotation
    (`@java.lang.SuppressWarnings`) reads as `SuppressWarnings`: a scoped_identifier
    carries its own `name` field holding the final segment. Reading the field beats
    splitting the node's text, which is the mistake ../../../research/amendments/amendment-2026-08-02-rust-
    receiver-and-static.md records.
    """
    name = node.child_by_field_name("name")
    while name is not None:
        node = name
        name = node.child_by_field_name("name")
    return node.text.decode("utf8", errors="ignore") if node.text else ""

def _is_a_bare_generic(node: Node, cfg: LangCfg, text: str) -> bool:
    """Whether this node names a container without saying what it holds.

    `dict` means dict[Any, Any], the least precise mapping Python has. It carries no escape
    token, so a counter reading tokens scored it clean, while scoring the better
    `dict[str, Any]` as an escape. An adopter found that by writing out six annotations they
    already meant and watching our number get worse. An author who watches the number learns
    to write `dict`, which is worse and which we could not see at all.

    Told apart from `dict[str, str]` by where it sits rather than by reading its text: a
    parameterised generic hangs under a generic type node and a bare one hangs directly in
    the type. A `dict()` call and an `isinstance(x, dict)` sit somewhere else again and are
    not annotations at all."""
    if text not in cfg["bare_generics"] or node.named_children:
        return False
    parent = node.parent
    return parent is not None and parent.type in cfg["type_position_types"]


def _count_type_escapes_in_tree(root: Node, cfg: LangCfg) -> int:
    """Count type-escape hatches in one parsed tree.

    The whole vocabulary is read from `cfg` here rather than unpacked by each caller.
    Two callers unpacked it (L1.15 and the pre-commit ratchet in cli.py), so adding a
    vocabulary was a silent measurement split waiting to happen: the gate would keep
    counting the old way while the indicator counted the new way.

    A type token (Any, object, dynamic, ...) is matched only on a leaf node whose
    exact text is one of `escape_tokens`, so it catches real annotations without
    matching parent nodes (which would double count) or the builtin `any()` call.

    Two refinements keep the count on annotations and suppressions rather than on
    prose and data, both of which the meter used to charge against itself:

    A leaf inside a string is data, not an annotation. `("Any",)` in a pattern table,
    an "object" key in a C# message, a "dynamic" label: none of them opt out of a type
    checker. In a language whose escape token is `object` or `Object`, charging every
    string that says "object" would swamp the measure.

    That exclusion used to be the whole string rule, and it called its own cost, a
    stringified forward reference, rare. It is not rare. `cast("dict[str, Any]", ctx)`
    is the ordinary way to write the one acknowledged escape at a framework seam whose
    signature forces `dict[str, Any]`, and the exclusion dropped it. So the same code
    scored 2 unquoted and 1 quoted, and a reader could move the number by adding
    quotation marks. `type_cast_calls` names, per language, the calls whose first
    argument IS a type, and a string there is counted like the annotation it is.

    A token in a NON-type position is not an escape however exactly it matches.
    `from typing import Any` makes a symbol available and types nothing; it was charged
    one escape, so every statically-typed Python file carried a floor of one and a file
    that imported the name without using it was charged for the import alone. The same
    held for `import java.lang.Object`, `import {any}`, and TypeScript's `{any: 1}`,
    where the token is a field name. `type_escape_nonpositions` names those positions
    per language.

    The rule is stated as a refusal rather than an allow-list on purpose. Go and C#
    leave a bare type sitting directly in a declaration with no node to key on, so an
    allow-list of type positions would silently stop counting them. Naming the places a
    match is NOT a type keeps the default counted, which is the direction that fails
    toward reporting an escape rather than hiding one.

    A comment counts only when it BEGINS with a marker, which is what a real suppression
    looks like. A comment that mentions `# type: ignore` while explaining the rule is
    documentation. This module's own pattern list is the proof: it described the marker
    three times and was charged three escapes for saying so.

    A suppression written as an annotation is counted where the grammar puts it. Java's
    `@SuppressWarnings` is an `annotation` node, so the comment path never saw it and
    Java's real suppression marker went uncounted. One annotation is one escape however
    many warnings it names, the same rule `# type: ignore[a, b]` already gets.
    """
    escape_tokens = frozenset(cfg["type_escape_patterns"])
    nonpositions = frozenset(cfg["type_escape_nonpositions"])
    cast_calls = frozenset(cfg["type_cast_calls"])
    annotation_nodes = frozenset(cfg["annotation_escape_nodes"])
    annotation_names = frozenset(cfg["annotation_escape_names"])
    count = 0

    def in_string(n: Node) -> bool:
        parent = n.parent
        while parent is not None:
            if "string" in parent.type:
                return True
            parent = parent.parent
        return False

    for n in descendants(root, "all"):
        if not n.children:  # leaf token
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if text in escape_tokens and not in_string(n) and not _in_non_type_position(n, nonpositions) or _is_a_bare_generic(n, cfg, text) and not in_string(n):
                count += 1
        if "comment" in n.type:
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if any(text.lstrip().startswith(pat) for pat in _COMMENT_TYPE_ESCAPES):
                count += 1
        if n.type in annotation_nodes and _annotation_name(n) in annotation_names:
            count += 1

    for named in _cast_type_strings(root, cast_calls):
        count += sum(1 for tok in escape_tokens if re.search(rf"\b{re.escape(tok)}\b", named))
    return count


def _in_non_type_position(leaf: Node, nonpositions: frozenset[str]) -> bool:
    """True when a matching token sits somewhere its language says is not a type: an
    import or using declaration that names the symbol, or an object key spelled like it.

    Stated as a refusal rather than an allow-list of type positions, because Go and C#
    put a bare type straight into a declaration with no node to key on. An empty
    vocabulary refuses nothing, which is the counted direction."""
    parent = leaf.parent
    while parent is not None:
        if parent.type in nonpositions:
            return True
        parent = parent.parent
    return False


def _cast_type_strings(root: Node, cast_calls: frozenset[str]) -> list[str]:
    """The type names written as strings in a cast, which the leaf walk cannot see
    because it drops everything inside a string.

    `cast("dict[str, Any]", ctx)` names a type. `("Any",)` in a pattern table does not.
    The call name is what separates them, and each language declares its own in
    `type_cast_calls`. A language declaring none gets no walk."""
    if not cast_calls:
        return []
    out: list[str] = []
    for call in _refs_of_type(root, "call"):
        fn = call.child_by_field_name("function")
        if fn is None or _node_text(fn) not in cast_calls:
            continue
        args = call.child_by_field_name("arguments")
        first = next((c for c in args.named_children), None) if args is not None else None
        if first is not None and "string" in first.type:
            out.append(_node_text(first))
    return out


def _refs_of_type(root: Node, node_type: str) -> list[Node]:
    """Every node of one type in a tree, in document order."""
    return [n for n in descendants(root, "all") if n.type == node_type]


def _node_text(n: Node) -> str:
    return n.text.decode("utf8", errors="ignore") if n.text else ""


def _compute_type_escapes(repo: Path, lang: str) -> L1Result:
    """L1.15: density of type-escape hatches (Any/object/dynamic and ignore comments).

    There is no minimum denominator, and the absence of one is the rule.

    This read `if total_loc > 1000 else 0.0` until 2026-08-15. Below a thousand
    production lines it published 0.0 escapes per kLOC and band Healthy however many
    escape hatches the input actually held: a twenty-line file of nothing but `Any`
    scored the same clean as a file with none. That is not an empty-set claim, which
    would be honest; it is a fabricated number over a non-empty input, written into
    the one field a reader looks at, and it is the worse of the two failures because
    the input was there to be measured and was measured correctly right up to the
    last line of arithmetic. `vacuity.py` names this function among the paths it
    finds, and the shape it finds is a threshold guard feeding a constant.

    The threshold had no derivation. Not in 03-layer1-indicators.md, whose bands are
    `<1 / 1-5 / >5` per kLOC with no floor under them; not in the calibration note;
    not in any amendment. Where the canon and the implementation disagree the canon
    wins, so the floor goes rather than acquiring a justification after the fact.

    What the floor was reaching for is real and is a different thing: a rate over a
    small denominator is jumpy. One escape in a 200-line file reads 5.03/kLOC and
    bands Slop, and the next edit can move it by the width of the whole scale. That
    is a property of the ratio, disclosed by the count and the line total printed
    beside it, and not a licence to substitute a number nobody measured. An
    instrument that hides its own variance by asserting the healthy end of the scale
    is worse than one that reports a jumpy figure, because a reader can see variance
    and cannot see a substitution.

    Zero lines is the one case with no density to report, and it refuses. Zero
    escapes over zero lines is the same 0.0 as zero escapes over a thousand, and
    band cannot tell them apart, which is the L1.8 precedent four hundred lines up.

    The denominator is now printed exactly rather than as `~{n}kLOC`. Rounded to
    whole thousands it read "~0kLOC" for every input the floor used to swallow, so
    the disclosure that exists to let a reader recompute the ratio hid the only term
    that moved. A count and its exact denominator are recomputable at any size.
    """
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    cfg = LANG_CFG[lang]
    if not cfg["type_escape_patterns"]:
        # Untyped or no configured escape hatch (Ruby, JavaScript, Rust, C).
        return {"value": "n/a", "band": "n/a", "details": f"type-escape density not applicable for {lang}"}
    parser = _get_parser(lang)
    files, skipped = _read_source_bytes(repo, cfg["extensions"], scope=PRODUCTION)

    escape_count = 0
    total_loc = 0
    for _path, src in files:
        total_loc += len(src.decode("utf8", errors="ignore").splitlines())
        escape_count += _count_type_escapes_in_tree(parser.parse(src).root_node, cfg)

    if total_loc == 0:
        return {"value": "n/a", "band": "n/a", "details": _with_skipped("no production source lines found", skipped)}
    density = escape_count / (total_loc / 1000)
    return {"value": round(density, 2), "band": band(density, 1, 5, higher_is_better=False), "details": _with_skipped(f"{escape_count} escapes in {total_loc} production LOC", skipped)}

def _compute_decision_space(repo: Path, lang: str) -> L1Result:
    """L1.19, static half: enumerate the finite decision points via tree-sitter.
    A decision point is a construct at which control can take more than one path; the
    full rule, and the node types each grammar spells it with, live beside the
    DECISION_NODE_TYPES table in lang_spec.py, because the number is published and a
    reader is owed the definition. The exercised-coverage fraction requires a runtime
    trace (see pytest_trace.decision_space_coverage); when the suite cannot be run this
    is reported as not-measured rather than fabricated."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    parser = _get_parser(lang)
    # Subscript, not .get(): a supported language that declares no decision vocabulary
    # is a gap in the table, and a gap must raise rather than enumerate zero.
    decision_types = DECISION_NODE_TYPES[lang]
    files, skipped = _read_source_bytes(repo, LANG_CFG[lang]["extensions"], scope=PRODUCTION)

    decision_points = 0
    for _path, src in files:
        root = parser.parse(src).root_node

        # named_children, never children. An unnamed keyword token (`if`, `case`,
        # `switch`) sits inside the very node that already matched, and in Ruby it
        # carries the SAME type string as the node, so walking every child counted
        # every `if` twice in all nine languages. Anonymous tokens are leaves, so
        # skipping them loses no descendant.
        decision_points += sum(1 for n in descendants(root, "named")
                               if n.type in decision_types)

    # What it counted, and the bound on that count. NOT whether a trace ran: this function
    # serves the website, which runs nothing, and the CLI, which runs the suite, and it used
    # to end "(not run by this reference implementation)" for both. On a Java repository the
    # reader got that sentence beside the harness's own account of running Maven. It is the
    # larger version of the claim already removed from the footer, that the runtime harness
    # is Python-only. There are harnesses for eight languages and they work.
    detail = (f"{decision_points} finite decision points enumerated across {len(files)} "
              "files; the share a test exercises is a different number and needs a "
              "test-execution trace")
    return {"value": decision_points, "band": "n/a", "details": _with_skipped(detail, skipped)}

def _compute_external_indicators(repo: Path, lang: str) -> Panel:
    """L1.13 near-duplicate code, measured here since 2026-08-19 rather than shelled out.

    It was delegated to jscpd, which was installed on no machine that ever ran this panel,
    so L1.13 reported n/a on every repository this instrument has measured, both validation
    controls included. An indicator that has never produced a number is not a lenient
    indicator: it is a column in a published panel nobody has read, and since n/a is
    excluded from both halves of the slop fraction, the panel measured nineteen things
    while saying twenty.

    L1.12 and L1.14 left the same way, for the same reason: six ecosystems' toolchains
    cannot be asked of an auditor at a client site, and while a tool is absent its
    indicator says nothing. The function keeps its name because the panel's shape is what
    callers depend on; nothing external is left in it.
    """
    from l1_analyzer import clone_detect

    return {"L1.13": clone_detect.analyze(repo, lang)}


# L1.18 mutable-state analysis lives in mutable_state.py; re-exported here so the
# public indicators API is unchanged. Imported at the bottom, after the primitives it
# depends on (LANG_CFG, _get_parser, _read_source_bytes, band) are defined, to avoid a
# circular import between the two modules.
from l1_analyzer.mutable_state import (  # noqa: F401
    _file_mutable_names,
    _find_module_mutable_names,
    analyze_mutable_state,
    module_mutable_names,
    mutable_function_names,
)
