"""
Reference implementations of Slop Audit L1.1-L1.20 indicators.

Design goal: runnable against *any* language.
- L1.1-L1.8: pure git log (completely language-agnostic)
- L1.9-L1.11: file presence (agnostic)
- L1.12-L1.17, L1.18-L1.20: where source analysis is needed, use tree-sitter
  with per-language CFG so the *same* semantic metric works for Python, Rust, C,
  and can be extended to Java/TS/C#/etc. exactly as L1.18 does in the research.

This file (and the package) tries to follow Honest Code principles:
pure functions, TypedDict data, dict dispatch for language differences, I/O at edges.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from l1_analyzer import pytest_trace

# ---------------------------------------------------------------------------
# Data shapes (TypedDicts)
# ---------------------------------------------------------------------------

class L1Result(TypedDict, total=False):
    value: float | int | str
    band: str  # Healthy / Not Healthy / Slop / n/a
    details: str

# Vendored / generated / tooling directories that no source metric should scan.
# (Note: ".venv" and "venv" are distinct path parts; both must be listed.)
_IGNORE_DIRS = frozenset({
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs",
    "site-packages", "target", "build", "dist", "vendor",
})

def _in_ignored_dir(path: Path, extra: tuple[str, ...] = ()) -> bool:
    """True if any path component is a vendored/tooling dir (or one of `extra`)."""
    parts = set(path.parts)
    return bool(parts & _IGNORE_DIRS) or any(e in parts for e in extra)

# ---------------------------------------------------------------------------
# Git-based (L1.1-L1.8) - language agnostic
# ---------------------------------------------------------------------------

def _run_git_log(repo: Path, since: str | None = None, until: str | None = None) -> list[str]:
    cmd = ["git", "-C", str(repo), "log", "--pretty=format:%H", "--name-only"]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    return [line for line in out.splitlines() if line.strip()]

def _classify_file(path: str) -> str:
    p = path.lower()
    if any(p.endswith(ext) for ext in (".md", ".rst", ".adoc", ".txt", ".feature")):
        return "doc"
    if any(p.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".h", ".cpp", ".cs", ".kt", ".swift", ".php", "dockerfile", ".yml", ".yaml", ".json", ".toml")):
        return "code"
    return "other"

def compute_git_indicators(repo: Path, since: str | None = None, until: str | None = None) -> dict[str, L1Result]:
    """Robust git log based indicators. Uses --numstat and --name-status for reliable counts."""
    # `--numstat` alone carries added/deleted counts AND the path (enough to both
    # classify each commit's files and sum line changes). Combining it with
    # `--name-status` makes git drop the numeric counts, so we use numstat only.
    cmd = ["git", "-C", str(repo), "log", "--numstat", "--pretty=format:COMMIT %H"]
    if since:
        cmd += ["--since", since]
    if until:
        cmd += ["--until", until]

    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return {f"L1.{i}": {"value": 0, "band": "n/a", "details": "git log failed"} for i in range(1, 9)}

    total_commits = 0
    doc_only = code_only = mixed = 0
    total_added = total_deleted = 0
    doc_added = code_added = 0
    net_negative_commits = high_delete_commits = 0

    current_commit_files: set[str] = set()
    current_add = current_del = 0

    for line in out.splitlines():
        if line.startswith("COMMIT "):
            if current_commit_files:
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

    # last commit
    if current_commit_files:
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

    if total_commits == 0:
        return {f"L1.{i}": {"value": 0, "band": "n/a"} for i in range(1, 9)}

    results: dict[str, L1Result] = {}

    l1 = (doc_only / total_commits) * 100
    results["L1.1"] = {"value": round(l1, 1), "band": "Healthy" if l1 >= 10 else ("Not Healthy" if l1 >= 1 else "Slop")}

    l2 = (code_only / total_commits) * 100
    results["L1.2"] = {"value": round(l2, 1), "band": "Healthy" if l2 < 70 else ("Not Healthy" if l2 <= 85 else "Slop")}

    l3 = (mixed / total_commits) * 100
    results["L1.3"] = {"value": round(l3, 1), "band": "Healthy" if l3 >= 12 else ("Not Healthy" if l3 >= 3 else "Slop")}

    # L1.4 doc lines as % of total lines added
    l4 = (doc_added / total_added * 100) if total_added > 0 else 0.0
    results["L1.4"] = {"value": round(l4, 1), "band": "Healthy" if l4 >= 25 else ("Not Healthy" if l4 >= 5 else "Slop"), "details": f"{doc_added} doc / {total_added} total lines added"}

    l5 = (total_deleted / total_added * 100) if total_added > 0 else 0
    results["L1.5"] = {"value": round(l5, 1), "band": "Healthy" if l5 >= 60 else ("Not Healthy" if l5 >= 30 else "Slop")}

    l6 = (net_negative_commits / total_commits * 100)
    results["L1.6"] = {"value": round(l6, 1), "band": "Healthy" if l6 >= 15 else ("Not Healthy" if l6 >= 5 else "Slop")}

    l7 = (high_delete_commits / total_commits * 100)
    results["L1.7"] = {"value": round(l7, 1), "band": "Healthy" if l7 >= 20 else ("Not Healthy" if l7 >= 5 else "Slop")}

    l8 = _test_to_prod_ratio(repo)
    results["L1.8"] = l8

    return results

# Files whose path marks them as test code (used by L1.8).
_TEST_PATH_MARKERS = ("test", "tests", "spec", "specs", "__tests__")
_SRC_EXTS = frozenset({".py", ".rs", ".c", ".h", ".cpp", ".js", ".jsx", ".mjs", ".cjs",
                       ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".kt", ".swift", ".php"})

def _test_to_prod_ratio(repo: Path) -> L1Result:
    """L1.8: lines of test code / lines of production code, via a filesystem walk."""
    test_loc = prod_loc = 0
    for f in repo.rglob("*"):
        if f.suffix.lower() not in _SRC_EXTS:
            continue
        if _in_ignored_dir(f):
            continue
        try:
            n = len(f.read_text(errors="ignore").splitlines())
        except Exception:
            continue
        lowered = {p.lower() for p in f.parts}
        name = f.name.lower()
        is_test = bool(lowered & set(_TEST_PATH_MARKERS)) or name.startswith("test_") or name.endswith(("_test" + f.suffix.lower(), ".test" + f.suffix.lower(), ".spec" + f.suffix.lower()))
        if is_test:
            test_loc += n
        else:
            prod_loc += n
    if prod_loc == 0:
        return {"value": "n/a", "band": "n/a", "details": "no production source files found"}
    ratio = test_loc / prod_loc
    band = "Healthy" if ratio >= 0.4 else ("Not Healthy" if ratio >= 0.1 else "Slop")
    return {"value": round(ratio, 2), "band": band, "details": f"{test_loc} test / {prod_loc} production LOC"}

# ---------------------------------------------------------------------------
# Config (L1.9-11)
# ---------------------------------------------------------------------------

def compute_config_indicators(repo: Path) -> dict[str, L1Result]:
    has_precommit = (repo / ".pre-commit-config.yaml").exists() or (repo / ".husky").exists()
    ci_files = list((repo / ".github" / "workflows").glob("*.yml")) + list((repo / ".github" / "workflows").glob("*.yaml"))
    ci_count = len(ci_files)
    has_docker = (repo / "Dockerfile").exists() or (repo / "docker-compose.yml").exists()

    return {
        "L1.9": {
            "value": "present" if has_precommit else "absent",
            "band": "Healthy" if has_precommit else "Slop",
        },
        "L1.10": {
            "value": ci_count,
            "band": "Healthy" if ci_count >= 5 else ("Not Healthy" if ci_count >= 1 else "Slop"),
        },
        "L1.11": {
            "value": "present and parameterized" if has_docker else "absent",
            "band": "Healthy" if has_docker else "Slop",
        },
    }

# ---------------------------------------------------------------------------
# Tree-sitter setup for language-agnostic source analysis
# ---------------------------------------------------------------------------

LANG_CFG: dict[str, dict[str, Any]] = {
    "python": {
        "language": Language(tree_sitter_python.language()),
        "extensions": (".py",),
        "function_types": ("function_definition",),
        "class_types": ("class_definition",),
        "member_access": "attribute",
        "this_ident": {"self"},
        "module_level_assign": ("assignment", "augmented_assignment"),
        "type_escape_patterns": ("any",),  # plus comments # type: ignore
    },
    "rust": {
        "language": Language(tree_sitter_rust.language()),
        "extensions": (".rs",),
        "function_types": ("function_item",),
        "class_types": ("struct_item", "enum_item", "trait_item"),
        "member_access": "field_expression",
        "this_ident": set(),
        "module_level_assign": ("let_declaration", "static_item", "const_item"),
        "type_escape_patterns": (),
    },
    "c": {
        "language": Language(tree_sitter_c.language()),
        "extensions": (".c", ".h"),
        "function_types": ("function_definition",),
        "class_types": ("struct_specifier", "union_specifier"),
        "member_access": "field_expression",
        "this_ident": set(),
        "module_level_assign": ("declaration", "init_declarator"),
        "type_escape_patterns": (),
    },
    "java": {
        "language": Language(tree_sitter_java.language()),
        "extensions": (".java",),
        "function_types": ("method_declaration", "constructor_declaration"),
        "class_types": ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration"),
        "member_access": "field_access",
        "this_ident": {"this"},
        "module_level_assign": ("field_declaration", "local_variable_declaration"),
        "type_escape_patterns": ("Object",),  # raw types, etc.
    },
    "typescript": {
        "language": Language(tree_sitter_typescript.language_typescript()),
        "extensions": (".ts", ".tsx"),
        "function_types": ("function_declaration", "method_definition", "arrow_function"),
        "class_types": ("class_declaration", "interface_declaration", "enum_declaration"),
        "member_access": "member_expression",
        "this_ident": {"this"},
        "module_level_assign": ("variable_declaration", "lexical_declaration"),
        "type_escape_patterns": ("any", "unknown"),  # plus // @ts-ignore
    },
    "csharp": {
        "language": Language(tree_sitter_c_sharp.language()),
        "extensions": (".cs",),
        "function_types": ("method_declaration", "constructor_declaration"),
        "class_types": ("class_declaration", "interface_declaration", "struct_declaration", "enum_declaration", "record_declaration"),
        "member_access": "member_access_expression",
        "this_ident": {"this"},
        "module_level_assign": ("field_declaration", "local_declaration_statement"),
        "type_escape_patterns": ("object", "dynamic"),
    },
    "javascript": {
        "language": Language(tree_sitter_javascript.language()),
        "extensions": (".js", ".jsx", ".mjs", ".cjs"),
        "function_types": ("function_declaration", "function_expression", "generator_function_declaration", "method_definition", "arrow_function"),
        "class_types": ("class_declaration", "class"),
        "member_access": "member_expression",
        "this_ident": {"this"},
        "module_level_assign": ("variable_declaration", "lexical_declaration"),
        "type_escape_patterns": (),  # untyped
        # `const` bindings are immutable; `let`/`var` are mutable module state
        "const_keywords": ("const ",),
    },
    "ruby": {
        "language": Language(tree_sitter_ruby.language()),
        "extensions": (".rb",),
        "function_types": ("method", "singleton_method"),
        "class_types": ("class", "module", "singleton_class"),
        "member_access": "call",
        "this_ident": {"self"},
        # Ruby signals external mutable state through @instance and $global variables,
        # not a `self.`-prefixed member access.
        "instance_field_types": ("instance_variable", "global_variable"),
        "module_level_assign": ("assignment", "operator_assignment"),
        "type_escape_patterns": (),  # untyped
    },
    "go": {
        "language": Language(tree_sitter_go.language()),
        "extensions": (".go",),
        "function_types": ("function_declaration", "method_declaration"),
        "class_types": ("type_declaration",),
        "member_access": "selector_expression",
        # Go has no fixed receiver keyword; the receiver name is parsed per method
        # and passed to the detector dynamically.
        "this_ident": set(),
        "module_level_assign": ("var_declaration",),
        "type_escape_patterns": ("any", "interface{}"),
        "const_keywords": ("const ",),
    },
}

# Body node types that hold a function/method's statements, across all grammars.
_BODY_NODE_TYPES = ("block", "compound_statement", "body", "function_body", "body_statement", "statement_block")

def _get_parser(lang: str) -> Parser:
    cfg = LANG_CFG[lang]
    p = Parser(cfg["language"])
    return p

def detect_primary_language(repo: Path) -> str:
    counts: Counter[str] = Counter()
    for lang, cfg in LANG_CFG.items():
        for ext in cfg["extensions"]:
            counts[lang] += len(list(repo.rglob(f"*{ext}")))
    if not counts:
        return "python"
    return counts.most_common(1)[0][0]

# ---------------------------------------------------------------------------
# L1.18 Mutable state ratio (the key "any language" indicator, using tree-sitter)
# Simplified reference implementation. Full production version lives in the
# Paper A replication package with all the bound-literal logic etc.
# ---------------------------------------------------------------------------

def _find_module_mutable_names(root: Node, cfg: dict[str, Any], source: bytes) -> set[str]:
    """Detect top-level names that are likely mutable (assigned and not const/Final/readonly)."""
    mutables: set[str] = set()
    assign_types = cfg.get("module_level_assign", ("assignment",))
    this_idents = cfg.get("this_ident", set())
    const_keywords = cfg.get("const_keywords", ("const ", "final ", "readonly ", "let ", "val "))

    for node in root.children:
        if node.type in assign_types:
            # crude extraction of left-hand side identifiers
            text = node.text.decode("utf8", errors="ignore")
            # very simple: look for NAME = ... at top level
            # In real impl this is a proper tree walk per language (see research l1_18.py)
            for line in text.splitlines():
                if "=" in line and not any(kw in line.lower() for kw in const_keywords):
                    parts = line.split("=")[0].strip().split()
                    if parts:
                        name = parts[-1].strip("()[]:,")
                        if name and name not in this_idents:
                            mutables.add(name)
    return mutables

def _count_mutable_refs(
    body: Node,
    cfg: dict[str, Any],
    source: bytes,
    module_mutables: set[str],
    receiver_names: set[str],
) -> int:
    """Count references inside a function body to external mutable state.

    Handles, per-language via cfg:
    - receiver/member access (self./this./<go-receiver>.<field>) via member_access node
    - Ruby-style @instance / $global variables via instance_field_types nodes
    - module-level mutable globals referenced by bare identifier
    - Rust/C raw patterns (&mut self, static mut)

    Simplified reference implementation; the production version (Paper A replication
    package) adds bound-literal exclusion and full per-language field resolution.
    """
    count = 0
    member_type = cfg.get("member_access", "attribute")
    instance_field_types = cfg.get("instance_field_types", ())

    def walk(n: Node):
        nonlocal count
        # Member/receiver access: self.x, this.x, or <go receiver>.field
        if n.type == member_type and receiver_names:
            text = n.text.decode("utf8", errors="ignore")
            if any(text.startswith(r + ".") for r in receiver_names):
                count += 1
        # Ruby @instance / $global variables are themselves external-state references
        if n.type in instance_field_types:
            count += 1
        # module-level mutable global referenced by bare name
        if n.type == "identifier":
            name = n.text.decode("utf8", errors="ignore")
            if name in module_mutables:
                count += 1
        # Rust/C raw patterns
        txt = n.text.decode("utf8", errors="ignore") if n.text else ""
        if "static mut" in txt or "&mut self" in txt or "mut self" in txt:
            count += 1

        for c in n.children:
            walk(c)
    walk(body)
    return count

def _receiver_names(func_node: Node, cfg: dict[str, Any]) -> set[str]:
    """Names that denote the enclosing instance for this function.

    For self/this languages it is the fixed keyword set. For Go it is the
    method receiver identifier, parsed from the receiver parameter list.
    """
    fixed = set(cfg.get("this_ident", set()))
    if fixed:
        return fixed
    # Go: `func (r *Foo) Bar(...)` -> receiver identifier is `r`
    names: set[str] = set()
    if func_node.type == "method_declaration":
        for child in func_node.children:
            if child.type == "parameter_list":
                for decl in child.children:
                    if decl.type == "parameter_declaration":
                        for part in decl.children:
                            if part.type == "identifier":
                                names.add(part.text.decode("utf8", errors="ignore"))
                break  # first parameter_list is the receiver
    return names

def analyze_mutable_state(repo: Path, lang: str = "python") -> L1Result:
    cfg = LANG_CFG.get(lang, LANG_CFG["python"])
    parser = _get_parser(lang)

    total_funcs = 0
    mutable_funcs = 0

    for ext in cfg["extensions"]:
        for f in list(repo.rglob(f"*{ext}")):
            if _in_ignored_dir(f, extra=("tests", "test")):
                continue
            try:
                src = f.read_bytes()
                tree = parser.parse(src)
                root = tree.root_node

                module_mutables = _find_module_mutable_names(root, cfg, src)

                def find_functions(n: Node):
                    nonlocal total_funcs, mutable_funcs
                    if n.type in cfg["function_types"]:
                        total_funcs += 1
                        body = None
                        for c in n.children:
                            if c.type in _BODY_NODE_TYPES:
                                body = c
                                break
                        if body:
                            receivers = _receiver_names(n, cfg)
                            refs = _count_mutable_refs(body, cfg, src, module_mutables, receivers)
                            if refs > 0:
                                mutable_funcs += 1
                    for c in n.children:
                        find_functions(c)
                find_functions(root)
            except Exception:
                continue

    ratio = (mutable_funcs / total_funcs * 100) if total_funcs > 0 else 0.0
    band = "Healthy" if ratio < 15 else ("Not Healthy" if ratio < 40 else "Slop")
    return {
        "value": round(ratio, 1),
        "band": band,
        "details": f"{mutable_funcs}/{total_funcs} functions reference external mutable state ({lang})",
    }

# ---------------------------------------------------------------------------
# Full source-based indicators with tree-sitter for multi-lang support
# ---------------------------------------------------------------------------

def _run_external(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""

def compute_source_indicators(repo: Path, lang: str = "auto", exec_tests: bool = True, **kwargs) -> dict[str, L1Result]:
    if lang == "auto":
        lang = detect_primary_language(repo)

    results: dict[str, L1Result] = {"lang": lang}

    # L1.16 - trailing whitespace (language agnostic, fast)
    try:
        count = 0
        total = 0
        exts = {".py", ".rs", ".c", ".h", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".cs", ".rb", ".go"}
        for f in repo.rglob("*"):
            if f.suffix.lower() not in exts: continue
            if _in_ignored_dir(f): continue
            try:
                lines = f.read_text(errors="ignore").splitlines()
                total += len(lines)
                count += sum(1 for ln in lines if ln.rstrip() != ln and ln.strip())
            except Exception:
                pass
        ws_pct = (count / total * 100) if total > 0 else 0.0
        band = "Healthy" if ws_pct < 0.5 else ("Not Healthy" if ws_pct < 3 else "Slop")
        results["L1.16"] = {"value": round(ws_pct, 2), "band": band, "details": f"{count} lines with trailing ws"}
    except Exception as e:
        results["L1.16"] = {"value": 0, "band": "n/a", "details": str(e)}

    # L1.17 - god files (language agnostic)
    try:
        prod_files = 0
        god_files = 0
        big_files = 0
        for f in repo.rglob("*"):
            if _in_ignored_dir(f, extra=("tests", "test")): continue
            if f.suffix.lower() in {".py", ".rs", ".c", ".h", ".js", ".ts", ".java", ".cs", ".go", ".rb"}:
                try:
                    lines = len(f.read_text(errors="ignore").splitlines())
                    prod_files += 1
                    if lines > 1000:
                        god_files += 1
                    if lines > 4000:
                        big_files += 1
                except Exception:
                    pass
        god_pct = (god_files / prod_files * 100) if prod_files > 0 else 0.0
        band = "Healthy" if god_pct < 0.5 and big_files == 0 else ("Not Healthy" if god_pct < 2 and big_files == 0 else "Slop")
        results["L1.17"] = {"value": round(god_pct, 2), "band": band, "details": f"{god_files}/{prod_files} files >1k LOC, {big_files} >4k LOC"}
    except Exception:
        results["L1.17"] = {"value": 0, "band": "n/a"}

    # L1.18 - Mutable state (core multi-lang tree-sitter impl)
    results["L1.18"] = analyze_mutable_state(repo, lang)

    # L1.15 - Type escape density (tree-sitter)
    results["L1.15"] = _compute_type_escapes(repo, lang)

    # L1.19 - decision-space coverage. Prefer the real runtime measurement
    # (coverage.py branch tracing); fall back to the honest static enumeration
    # (a decision-point count, coverage explicitly not measured) when the suite
    # cannot be run.
    results["L1.19"] = _decision_space_l19(repo, lang, exec_tests)

    # L1.12,13,14 - External static tools (auto-dispatch)
    results.update(_compute_external_indicators(repo, lang))

    # L1.20 - test determinism (runs the suite; Python-only for now)
    results["L1.20"] = _test_determinism_l20(repo, lang, exec_tests)

    return results

def _decision_space_l19(repo: Path, lang: str, exec_tests: bool) -> L1Result:
    """Real branch coverage when the suite can run; otherwise the static
    decision-point enumeration with coverage clearly marked not-measured."""
    static = _compute_decision_space(repo, lang)
    if not exec_tests:
        static["details"] += "; coverage not measured (test execution disabled)"
        return static
    cov = pytest_trace.decision_space_coverage(repo, lang)
    if cov.get("band") != "n/a":
        return cov
    # Runtime coverage unavailable: keep the static count but stay honest that
    # the exercised-coverage fraction was not measured, and say why.
    static["details"] += f"; coverage not measured: {cov.get('details', 'unavailable')}"
    return static

def _test_determinism_l20(repo: Path, lang: str, exec_tests: bool) -> L1Result:
    if not exec_tests:
        return {"value": "not run", "band": "n/a", "details": "test execution disabled"}
    return pytest_trace.test_determinism(repo, lang)

def _compute_type_escapes(repo: Path, lang: str) -> L1Result:
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a"}
    cfg = LANG_CFG[lang]
    if not cfg.get("type_escape_patterns"):
        # Untyped or no configured escape hatch (Ruby, JavaScript, Rust, C):
        # a type-escape density is not meaningful, so report it honestly.
        return {"value": "n/a", "band": "n/a", "details": f"type-escape density not applicable for {lang}"}
    parser = _get_parser(lang)
    escape_count = 0
    total_loc = 0

    escape_nodes = set(cfg.get("type_escape_patterns", []))
    comment_escape = {"# type: ignore", "// @ts-ignore", "/* @ts-ignore", "@SuppressWarnings"}

    for ext in cfg["extensions"]:
        for f in repo.rglob(f"*{ext}"):
            if _in_ignored_dir(f, extra=("tests", "test")): continue
            try:
                src = f.read_bytes()
                text = src.decode("utf8", errors="ignore")
                total_loc += len(text.splitlines())
                tree = parser.parse(src)
                root = tree.root_node

                def walk(n: Node):
                    nonlocal escape_count
                    t = n.text.decode("utf8", errors="ignore") if n.text else ""
                    if n.type in ("type_identifier", "predefined_type", "any", "object", "dynamic_type"):
                        if t.lower() in ("any", "object", "dynamic", "unknown"):
                            escape_count += 1
                    if any(pat in t for pat in comment_escape):
                        escape_count += 1
                    for c in n.children:
                        walk(c)
                walk(root)
            except Exception:
                pass

    density = (escape_count / (total_loc / 1000)) if total_loc > 1000 else 0.0
    band = "Healthy" if density < 1 else ("Not Healthy" if density < 5 else "Slop")
    return {"value": round(density, 2), "band": band, "details": f"{escape_count} escapes in ~{total_loc//1000}kLOC"}

# Control-flow branch node types across the supported grammars. Exact-type
# matches (not substring) so short Ruby types like "if"/"case"/"when" are safe.
_DECISION_NODE_TYPES = frozenset({
    # if / conditional
    "if_statement", "if_expression", "if", "elif_clause", "else_if_clause",
    "conditional_expression", "ternary_expression",
    # switch / match
    "switch_statement", "switch_expression", "switch_section", "switch_case",
    "expression_switch_statement", "type_switch_statement", "expression_case",
    "type_case", "default_case", "communication_case", "select_statement",
    "match_expression", "match_statement", "match_arm", "case_clause",
    # ruby
    "case", "when", "case_match", "in_clause",
})

def _compute_decision_space(repo: Path, lang: str) -> L1Result:
    """L1.19, static half: enumerate the finite decision points (the size of the
    decision space) via tree-sitter. The *coverage* half of L1.19 (what fraction
    of these a test suite exercises) requires a runtime test-execution trace, which
    this reference implementation does not run, so it is reported as not-run rather
    than fabricated. The production analyzer (Paper A l1_19_decision_coverage.py)
    instruments the suite to compute the exercised fraction.
    """
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    parser = _get_parser(lang)
    decision_points = 0
    files_scanned = 0

    for ext in LANG_CFG[lang]["extensions"]:
        for f in repo.rglob(f"*{ext}"):
            if _in_ignored_dir(f, extra=("tests", "test")): continue
            try:
                root = parser.parse(f.read_bytes()).root_node
                files_scanned += 1

                def walk(n: Node):
                    nonlocal decision_points
                    if n.type in _DECISION_NODE_TYPES:
                        decision_points += 1
                    for c in n.children:
                        walk(c)
                walk(root)
            except Exception:
                pass

    return {
        "value": decision_points,
        "band": "n/a",
        "details": (
            f"{decision_points} finite decision points enumerated across {files_scanned} files; "
            "exercised-coverage fraction requires a test-execution trace (not run by this reference implementation)"
        ),
    }

def _compute_external_indicators(repo: Path, lang: str) -> dict[str, L1Result]:
    """Indicators that delegate to an external tool. Each reports an honest
    `n/a` when the tool it needs is not installed, rather than a fabricated
    number or a misleading "Healthy" that only means "nothing ran".
    """
    res: dict[str, L1Result] = {}

    # L1.14 secrets - prefer gitleaks, then detect-secrets
    if shutil.which("gitleaks"):
        out = _run_external(["gitleaks", "detect", "--no-git", "--source", ".", "--report-format", "json", "--report-path", "/dev/stdout"], repo)
        hits = out.count('"RuleID"')
        res["L1.14"] = {"value": hits, "band": "Healthy" if hits == 0 else ("Not Healthy" if hits <= 2 else "Slop"), "details": "gitleaks findings"}
    elif shutil.which("detect-secrets"):
        out = _run_external(["detect-secrets", "scan", "."], repo)
        hits = out.count('"is_verified"')
        res["L1.14"] = {"value": hits, "band": "Healthy" if hits == 0 else ("Not Healthy" if hits <= 2 else "Slop"), "details": "detect-secrets findings"}
    else:
        res["L1.14"] = {"value": "n/a", "band": "n/a", "details": "install gitleaks or detect-secrets to compute L1.14"}

    # L1.12 dead code - language-specific tool; only Python (vulture) is wired here
    if lang == "python" and shutil.which("vulture"):
        out = _run_external(["vulture", ".", "--min-confidence", "80"], repo)
        unreach = len([l for l in out.splitlines() if l.strip()])
        res["L1.12"] = {"value": unreach, "band": "Healthy" if unreach < 50 else "Slop", "details": "vulture unreachable/unused symbols"}
    elif lang == "python":
        res["L1.12"] = {"value": "n/a", "band": "n/a", "details": "install vulture to compute L1.12 for Python"}
    else:
        res["L1.12"] = {"value": "n/a", "band": "n/a", "details": f"no dead-code tool wired for {lang} (Python uses vulture)"}

    # L1.13 clones - jscpd, parse the reported duplication percentage
    if shutil.which("jscpd"):
        out = _run_external(["jscpd", "--mode", "weak", "--min-tokens", "50", "--reporters", "console", "."], repo)
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", out)
        if m:
            clone_pct = float(m.group(1))
            res["L1.13"] = {"value": clone_pct, "band": "Healthy" if clone_pct < 3 else ("Not Healthy" if clone_pct < 10 else "Slop"), "details": "jscpd duplication percentage"}
        else:
            res["L1.13"] = {"value": "n/a", "band": "n/a", "details": "jscpd produced no parseable duplication percentage"}
    else:
        res["L1.13"] = {"value": "n/a", "band": "n/a", "details": "install jscpd to compute L1.13"}

    return res
