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
from typing import TypedDict

from tree_sitter import Node, Parser

from l1_analyzer import (
    c_trace,
    csharp_trace,
    go_trace,
    java_trace,
    js_trace,
    pytest_trace,
    ruby_trace,
    rust_trace,
)
from l1_analyzer.disclosure import (
    with_skipped as _with_skipped,
)
from l1_analyzer.incomplete import IncompleteCode, ratio
from l1_analyzer.lang_spec import DECISION_NODE_TYPES
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
    _is_generated,
    _read_source_bytes,
    _read_text_files,
    _repo_has_packages,
    _rglob_files,
    _test_dir_corroborated,
    _test_file_by_name,
    bucketed_paths,
)

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


def _classify_file(path: str) -> str:
    p = path.lower()
    if any(p.endswith(ext) for ext in (".md", ".rst", ".adoc", ".txt", ".feature")):
        return "doc"
    if any(p.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".h", ".cpp", ".cs", ".kt", ".swift", ".php", "dockerfile", ".yml", ".yaml", ".json", ".toml")):
        return "code"
    return "other"

def _doc_line_share(doc_added: int, total_added: int) -> L1Result:
    """L1.4: the share of added lines that are documentation.

    Raises rather than substituting 0.0, which is what stood here. A share of no added lines
    is absent, and 0.0 with higher_is_better lands below the Slop threshold, so the
    substitution did not merely publish a wrong number, it published a BAD one over a range
    that had added nothing. Found by vacuity.check.
    """
    pct = ratio(doc_added, total_added, "L1.4 documentation line share",
                "no line was added in the measured range, so the share of them that is "
                "documentation is absent and not zero")
    return {"value": round(pct, 1), "band": band(pct, 25, 5, higher_is_better=True),
            "details": f"{doc_added} doc / {total_added} total lines added"}


def _delete_to_add_ratio(code_deleted: int, code_added: int) -> L1Result:
    """L1.5: deleted lines as a share of added ones, the refactoring signal.

    Same substitution, same direction, and this one is load-bearing: L1.5 is one of the four
    indicators that separated the controls in the 2026-08-17 validation run.
    """
    pct = ratio(code_deleted, code_added, "L1.5 delete-to-add ratio",
                "no CODE line was added in the measured range, so a ratio against them is "
                "absent and not zero")
    return {"value": round(pct, 1), "band": band(pct, 60, 30, higher_is_better=True),
            "details": f"{code_deleted} deleted / {code_added} added code lines"}


def compute_git_indicators(repo: Path, since: str | None, until: str | None) -> dict[str, L1Result]:
    """L1.1-L1.8 from `git log --numstat`. `since`/`until` are the explicit
    Optional date bounds (None = unbounded); resolved here at the boundary.

    `--numstat` alone carries added/deleted counts AND the path (enough to both
    classify each commit's files and sum line changes). Combining it with
    `--name-status` makes git drop the numeric counts, so we use numstat only.
    """
    cmd = ["git", "-C", str(repo), "log", "--numstat", "--pretty=format:COMMIT %H"]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]

    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        # "n/a", not 0. The band said nothing was measured and the value said zero, and the
        # card renders the value, so a directory that is not a git working copy produced
        # eight rows reading 0%. Zero is not neutral on this panel: L1.5 is deleted over
        # added lines, so 0% is the Slop end of its own scale, and the shares of commits
        # read the same way. A reader taking in the number before the band - the order the
        # card puts them in - read a repository nobody could measure as one that measured
        # terribly. The half-repair this package's own vacuity checker exists to convict,
        # sitting inside an exception handler where nothing looked until the handlers were
        # swept on 2026-08-19.
        return {f"L1.{i}": {"value": "n/a", "band": "n/a", "details": f"git log failed: {error}"}
                for i in range(1, 9)}

    total_commits = 0
    doc_only = code_only = mixed = 0
    total_added = total_deleted = 0
    doc_added = code_added = code_deleted = 0
    net_negative_commits = high_delete_commits = 0

    current_commit_files: set[str] = set()
    current_add = current_del = 0

    def close_commit() -> None:
        nonlocal total_commits, doc_only, code_only, mixed
        nonlocal total_added, total_deleted, net_negative_commits, high_delete_commits
        if not current_commit_files:
            return
        total_commits += 1
        kinds = {_classify_file(f) for f in current_commit_files}
        if "doc" in kinds and "code" not in kinds:
            doc_only += 1
        elif "code" in kinds and "doc" not in kinds:
            code_only += 1
        elif "doc" in kinds and "code" in kinds:
            mixed += 1
        if current_add or current_del:
            total_added += current_add
            total_deleted += current_del
            if current_del > current_add:
                net_negative_commits += 1
            if current_add > 0 and (current_del / current_add) > 0.4:
                high_delete_commits += 1

    for line in out.splitlines():
        if line.startswith("COMMIT "):
            close_commit()
            current_commit_files = set()
            current_add = current_del = 0
            continue
        if "\t" not in line:
            continue
        # numstat line: "added<TAB>deleted<TAB>path" (added/deleted are "-" for binary)
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s, path = parts[0], parts[1], parts[-1]
        current_commit_files.add(path)  # every touched file counts toward commit classification
        if added_s.isdigit() and deleted_s.isdigit():
            a, d = int(added_s), int(deleted_s)
            current_add += a
            current_del += d
            kind = _classify_file(path)
            if kind == "doc":
                doc_added += a
            elif kind == "code":
                code_added += a
                # Deletions of CODE, which L1.5 divides by and which nobody tracked. The
                # additions were tracked all along and never read: L1.5 used the whole-tree
                # totals while the canon says "across code files".
                code_deleted += d
    close_commit()

    if total_commits == 0:
        # The same refusal as the unreadable-git one above, and for the same reason: a range
        # that holds no commit measured nothing, and 0% is the Slop end of L1.5's scale.
        # `--since` narrower than the history is an ordinary way to reach here.
        return {f"L1.{i}": {"value": "n/a", "band": "n/a", "details": "no commits in range"}
                for i in range(1, 9)}

    results: dict[str, L1Result] = {}

    l1 = doc_only / total_commits * 100
    # Every one of these carries the counts behind it. Six published a bare percentage
    # until 2026-08-18, and answering "why is this repository Slop on L1.5" meant
    # re-deriving from git log what the analyzer had already counted and discarded.
    results["L1.1"] = {"value": round(l1, 1), "band": band(l1, 10, 1, higher_is_better=True),
                       "details": f"{doc_only} doc-only / {total_commits} commits"}

    l2 = code_only / total_commits * 100
    results["L1.2"] = {"value": round(l2, 1), "band": band(l2, 70, 85, higher_is_better=False),
                       "details": f"{code_only} code-only / {total_commits} commits"}

    l3 = mixed / total_commits * 100
    results["L1.3"] = {"value": round(l3, 1), "band": band(l3, 12, 3, higher_is_better=True),
                       "details": f"{mixed} mixed doc-and-code / {total_commits} commits"}

    # Through the one boundary, like every other measure. Both divide by added lines, so both
    # can meet a range that added none, and _measure is what turns the refusal into an n/a
    # carrying its reason instead of a fabricated Slop.
    results["L1.4"] = _measure(_doc_line_share, doc_added, total_added)
    results["L1.5"] = _measure(_delete_to_add_ratio, code_deleted, code_added)

    l6 = net_negative_commits / total_commits * 100
    results["L1.6"] = {"value": round(l6, 1), "band": band(l6, 15, 5, higher_is_better=True),
                       "details": f"{net_negative_commits} net-negative / {total_commits} commits"}

    l7 = high_delete_commits / total_commits * 100
    results["L1.7"] = {"value": round(l7, 1), "band": band(l7, 20, 5, higher_is_better=True),
                       "details": f"{high_delete_commits} delete-heavy / {total_commits} commits"}

    results["L1.8"] = _test_to_prod_ratio(repo)

    return results

# Files whose path marks them as test code (used by L1.8).
_TEST_PATH_MARKERS = frozenset({"test", "tests", "spec", "specs", "__tests__"})
# A .NET test project is a sibling directory named <Project>.Tests, never a plain
# `tests/` parent. The production scope learned this in the same pass; L1.8 needs it too.
_TEST_DOTTED_MARKERS = ("test", "tests", "spec", "specs")
# The .NET and JVM file convention, in its original casing. Capitalised on purpose: see
# _is_test_file.
_SRC_EXTS = frozenset({".py", ".rs", ".c", ".h", ".cpp", ".js", ".jsx", ".mjs", ".cjs",
                       ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".kt", ".swift", ".php"})

def _is_test_file(path: Path) -> bool:
    """True when a path is test code, for the L1.8 test-to-production split.

    Two arms beyond the original ones carry the .NET and JVM conventions, which the
    Python, Go and JavaScript arms could not see. Without them L1.8 reported
    Newtonsoft.Json as "0 test / 193720 production LOC", band Slop, for a repository
    with 704 test files: the exact inverse of the truth, on a scored indicator.

    A dotted project directory (Newtonsoft.Json.Tests) is a test directory, matching the
    same rule the production scope uses. A stem ending in a CAPITALISED Test, Tests, Spec
    or Specs (JsonSerializerTests.cs) is a test file. The capital is what makes that arm
    safe: `Latest.java` ends with "test" when lowercased and would otherwise be counted
    as test code, while `SmokeTests.cs` reads as one only in its original casing.
    """
    lowered = {p.lower() for p in path.parts}
    if lowered & _TEST_PATH_MARKERS:
        return True
    if any(p.endswith("." + m) for p in lowered for m in _TEST_DOTTED_MARKERS):
        return True
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.startswith("test_") or name.endswith(("_test" + suffix, ".test" + suffix, ".spec" + suffix)):
        return True
    return path.stem.endswith(_TEST_STEM_SUFFIXES)

def _test_to_prod_ratio(repo: Path) -> L1Result:
    """L1.8: lines of test code / lines of production code."""
    files, skipped = _read_text_files(repo, _SRC_EXTS, scope=WHOLE_REPO)
    test_loc = prod_loc = 0
    for path, text in files:
        n = len(text.splitlines())
        if _is_test_file(path):
            test_loc += n
        else:
            prod_loc += n
    if prod_loc == 0:
        return {"value": "n/a", "band": "n/a", "details": _with_skipped("no production source files found", skipped)}
    ratio = test_loc / prod_loc
    return {"value": round(ratio, 2), "band": band(ratio, 0.4, 0.1, higher_is_better=True), "details": _with_skipped(f"{test_loc} test / {prod_loc} production LOC", skipped)}

# ---------------------------------------------------------------------------
# Config (L1.9-11)
# ---------------------------------------------------------------------------

def compute_config_indicators(repo: Path) -> dict[str, L1Result]:
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
) -> dict[str, L1Result]:
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

    results: dict[str, L1Result] = {"lang": lang}
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
    results.update(_compute_external_indicators(repo, lang))
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
# span at least _MIN_TABLE_LINES to read as a table (small inline literals stay code).
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
_MIN_TABLE_LINES = 12


def _data_literal_lines(node: Node, literal_types: frozenset[str]) -> int:
    """Lines spanned by large container literals under `node`. A counted literal is
    not recursed into, so nested literals are counted once, not compounded."""
    span = node.end_point[0] - node.start_point[0] + 1
    if node.type in literal_types and span >= _MIN_TABLE_LINES:
        return span
    return sum(_data_literal_lines(c, literal_types) for c in node.children)


def _code_line_count(src: bytes, ext: str) -> int:
    """Lines of a file that are code, not a large data literal. Unknown languages (or
    a parse failure) get no discount and fall back to the raw line count."""
    total = len(src.splitlines())
    literal_types = _LITERAL_NODES.get(_GOD_FILE_LANG.get(ext, ""))
    if not literal_types:
        return total
    try:
        root = _get_parser(_GOD_FILE_LANG[ext]).parse(src).root_node
    except Exception:  # noqa: BLE001
        return total
    return total - _data_literal_lines(root, literal_types)


def _god_file_reason(f: Path, repo: Path, has_packages: bool) -> str | None:
    """Why a candidate file is not a production god-file, or None to count it. The
    shared production scoping (tests, conformance, docs, tooling, vendored, loose
    scripts) plus generated code, which is L1.17-specific: a machine-generated or
    minified file carries no merge-conflict surface and nobody hand-piles into it.

    The scope is the finite-testability meter's, so L1.17 is declared under it in
    scope.SCOPES and a change to that scope names L1.17 among the numbers it moves.

    Generated-exclusion lives here, NOT in the shared _bucket_reason, so it never
    changes the mutable-state (L1.18) or finite-testability measurements that flow
    through that function; only the god-file indicator is refined."""
    reason = _bucket_reason(f, repo, has_packages, PRODUCTION_WITHOUT_CONFORMANCE)
    if reason is not None:
        return reason
    if f.name.endswith((".min.js", ".min.css")) or _is_generated(f):
        return "generated"
    return None


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

    def walk(n: Node):
        nonlocal count
        if not n.children:  # leaf token
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if text in escape_tokens and not in_string(n) and not _in_non_type_position(n, nonpositions):
                count += 1
        if "comment" in n.type:
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if any(text.lstrip().startswith(pat) for pat in _COMMENT_TYPE_ESCAPES):
                count += 1
        if n.type in annotation_nodes and _annotation_name(n) in annotation_names:
            count += 1
        for c in n.children:
            walk(c)

    walk(root)
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
    found: list[Node] = []

    def walk(n: Node) -> None:
        if n.type == node_type:
            found.append(n)
        for c in n.children:
            walk(c)

    walk(root)
    return found


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
        def walk(n: Node):
            nonlocal decision_points
            if n.type in decision_types:
                decision_points += 1
            for c in n.named_children:
                walk(c)
        walk(root)

    detail = f"{decision_points} finite decision points enumerated across {len(files)} files; exercised-coverage fraction requires a test-execution trace (not run by this reference implementation)"
    return {"value": decision_points, "band": "n/a", "details": _with_skipped(detail, skipped)}

def _compute_external_indicators(repo: Path, lang: str) -> dict[str, L1Result]:
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
