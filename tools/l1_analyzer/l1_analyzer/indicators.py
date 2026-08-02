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
# Data shape + pure scoring
# ---------------------------------------------------------------------------

class L1Result(TypedDict, total=False):
    value: float | int | str
    band: str  # Healthy / Not Healthy / Slop / n/a
    details: str

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

def _with_skipped(details: str, skipped: int) -> str:
    """Append an honest note when some files could not be read."""
    return details if skipped == 0 else f"{details}; {skipped} file(s) unreadable and excluded"

# ---------------------------------------------------------------------------
# Boundary readers (I/O). Each returns (data, skipped_count) so callers can
# surface partial scans instead of silently dropping unreadable files.
# ---------------------------------------------------------------------------

_IGNORE_DIRS = frozenset({
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs",
    "site-packages", "target", "build", "dist", "vendor",
})

def _in_ignored_dir(path: Path, extra: tuple[str, ...]) -> bool:
    """True if any path component is a vendored/tooling dir (or one of `extra`)."""
    parts = set(path.parts)
    return bool(parts & _IGNORE_DIRS) or any(e in parts for e in extra)

def _read_source_bytes(repo: Path, extensions: tuple[str, ...], extra_ignore: tuple[str, ...]) -> tuple[list[tuple[Path, bytes]], int]:
    """Read every source file with one of `extensions` as bytes. Returns the
    files read and the number that could not be read."""
    files: list[tuple[Path, bytes]] = []
    skipped = 0
    for ext in extensions:
        for f in repo.rglob(f"*{ext}"):
            if _in_ignored_dir(f, extra_ignore):
                continue
            try:
                files.append((f, f.read_bytes()))
            except OSError:
                skipped += 1
    return files, skipped

def _read_text_files(repo: Path, extensions: frozenset[str], extra_ignore: tuple[str, ...]) -> tuple[list[tuple[Path, str]], int]:
    """Read every file whose suffix is in `extensions` as text. Returns the files
    read and the number that could not be read."""
    files: list[tuple[Path, str]] = []
    skipped = 0
    for f in repo.rglob("*"):
        if f.suffix.lower() not in extensions:
            continue
        if _in_ignored_dir(f, extra_ignore):
            continue
        try:
            files.append((f, f.read_text(errors="ignore")))
        except OSError:
            skipped += 1
    return files, skipped

# ---------------------------------------------------------------------------
# Git-based (L1.1-L1.8) - language agnostic
# ---------------------------------------------------------------------------

def _classify_file(path: str) -> str:
    p = path.lower()
    if any(p.endswith(ext) for ext in (".md", ".rst", ".adoc", ".txt", ".feature")):
        return "doc"
    if any(p.endswith(ext) for ext in (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rb", ".rs", ".c", ".h", ".cpp", ".cs", ".kt", ".swift", ".php", "dockerfile", ".yml", ".yaml", ".json", ".toml")):
        return "code"
    return "other"

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
        return {f"L1.{i}": {"value": 0, "band": "n/a", "details": f"git log failed: {error}"} for i in range(1, 9)}

    total_commits = 0
    doc_only = code_only = mixed = 0
    total_added = total_deleted = 0
    doc_added = code_added = 0
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
    close_commit()

    if total_commits == 0:
        return {f"L1.{i}": {"value": 0, "band": "n/a", "details": "no commits in range"} for i in range(1, 9)}

    results: dict[str, L1Result] = {}

    l1 = doc_only / total_commits * 100
    results["L1.1"] = {"value": round(l1, 1), "band": band(l1, 10, 1, higher_is_better=True)}

    l2 = code_only / total_commits * 100
    results["L1.2"] = {"value": round(l2, 1), "band": band(l2, 70, 85, higher_is_better=False)}

    l3 = mixed / total_commits * 100
    results["L1.3"] = {"value": round(l3, 1), "band": band(l3, 12, 3, higher_is_better=True)}

    l4 = (doc_added / total_added * 100) if total_added > 0 else 0.0
    results["L1.4"] = {"value": round(l4, 1), "band": band(l4, 25, 5, higher_is_better=True), "details": f"{doc_added} doc / {total_added} total lines added"}

    l5 = (total_deleted / total_added * 100) if total_added > 0 else 0.0
    results["L1.5"] = {"value": round(l5, 1), "band": band(l5, 60, 30, higher_is_better=True)}

    l6 = net_negative_commits / total_commits * 100
    results["L1.6"] = {"value": round(l6, 1), "band": band(l6, 15, 5, higher_is_better=True)}

    l7 = high_delete_commits / total_commits * 100
    results["L1.7"] = {"value": round(l7, 1), "band": band(l7, 20, 5, higher_is_better=True)}

    results["L1.8"] = _test_to_prod_ratio(repo)

    return results

# Files whose path marks them as test code (used by L1.8).
_TEST_PATH_MARKERS = frozenset({"test", "tests", "spec", "specs", "__tests__"})
_SRC_EXTS = frozenset({".py", ".rs", ".c", ".h", ".cpp", ".js", ".jsx", ".mjs", ".cjs",
                       ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".kt", ".swift", ".php"})

def _is_test_file(path: Path) -> bool:
    lowered = {p.lower() for p in path.parts}
    name = path.name.lower()
    suffix = path.suffix.lower()
    return bool(lowered & _TEST_PATH_MARKERS) or name.startswith("test_") or name.endswith(("_test" + suffix, ".test" + suffix, ".spec" + suffix))

def _test_to_prod_ratio(repo: Path) -> L1Result:
    """L1.8: lines of test code / lines of production code."""
    files, skipped = _read_text_files(repo, _SRC_EXTS, extra_ignore=())
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

    return {
        "L1.9": {"value": "present" if has_precommit else "absent", "band": "Healthy" if has_precommit else "Slop"},
        "L1.10": {"value": ci_count, "band": band(ci_count, 5, 1, higher_is_better=True)},
        "L1.11": {"value": "present and parameterized" if has_docker else "absent", "band": "Healthy" if has_docker else "Slop"},
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
        "type_escape_patterns": ("Any",),  # typing.Any; plus comments # type: ignore
        # Read the binding name from the assignment's `left` field, not by text-
        # splitting the node. See docs/amendment-2026-08-01-l1-18-module-global.md.
        "field_based_globals": True,
    },
    "rust": {
        "language": Language(tree_sitter_rust.language()),
        "extensions": (".rs",),
        "function_types": ("function_item",),
        "class_types": ("struct_item", "enum_item", "trait_item"),
        "member_access": "field_expression",
        # A Rust method is a `function_item` carrying a `self_parameter`; `self.field`
        # is a `field_expression` reading "self.<field>". Treating `self` as the
        # receiver counts that access exactly as Python's does. Free functions have
        # no `self.` access, so this never over-counts them.
        "this_ident": {"self"},
        "module_level_assign": ("let_declaration", "static_item", "const_item"),
        # A Rust global is mutable state iff its declaration carries `mut`
        # (`static mut NAME: TYPE`). The name is the declaration's identifier child;
        # the legacy text split grabbed the type (`i32`) instead, so no global was
        # ever recognized. See docs/amendment-2026-08-02-rust-receiver-and-static.md.
        "mutable_specifier_globals": True,
        "type_escape_patterns": (),
        # Retained per docs/amendment-2026-07-31-rust-raw-pattern-scope.md; structural
        # detection above now carries the load, and these never fire inside a body.
        "raw_mut_patterns": ("static mut", "&mut self", "mut self"),
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
        # Go has no fixed receiver keyword; the receiver name is parsed per method.
        "this_ident": set(),
        "module_level_assign": ("var_declaration",),
        "type_escape_patterns": ("any",),  # Go's `any` alias for interface{}
        "const_keywords": ("const ",),
    },
}

# Body node types that hold a function/method's statements, across all grammars.
_BODY_NODE_TYPES = ("block", "compound_statement", "body", "function_body", "body_statement", "statement_block")

# Every LANG_CFG entry must define these keys; access them directly (a missing
# key is a config bug that should raise, not silently default). Genuinely
# optional keys (instance_field_types, const_keywords) still use .get().
_LANGUAGE_UNKNOWN = "unknown"

def _get_parser(lang: str) -> Parser:
    return Parser(LANG_CFG[lang]["language"])

def detect_primary_language(repo: Path) -> str:
    """Return the LANG_CFG key with the most files, or "unknown" when the repo
    contains no recognized source (callers report n/a rather than guess)."""
    counts: Counter[str] = Counter()
    for lang, cfg in LANG_CFG.items():
        for ext in cfg["extensions"]:
            counts[lang] += len(list(repo.rglob(f"*{ext}")))
    if not counts or counts.most_common(1)[0][1] == 0:
        return _LANGUAGE_UNKNOWN
    return counts.most_common(1)[0][0]

# ---------------------------------------------------------------------------
# L1.18 Mutable state ratio (the key "any language" indicator, using tree-sitter)
# Simplified reference implementation. Full production version lives in the
# Paper A replication package with all the bound-literal logic etc.
# ---------------------------------------------------------------------------

# Container literals/constructors whose empty form seeds an accumulator.
_PY_CONTAINER_CTORS = frozenset({
    "dict", "list", "set", "frozenset", "defaultdict", "OrderedDict", "deque", "Counter", "bytearray",
})


def _py_is_type_expression(n: Node) -> bool:
    """A pure type expression: a bare name, a dotted name, a subscript
    (Iterable[X]), or a `|` union of those. No call, no container literal."""
    if n.type in ("identifier", "attribute", "subscript"):
        return True
    if n.type == "binary_operator":
        op = n.child_by_field_name("operator")
        left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
        return (op is not None and op.text == b"|" and left is not None and right is not None
                and _py_is_type_expression(left) and _py_is_type_expression(right))
    return False


def _py_is_type_alias(node: Node, rhs: Node | None) -> bool:
    annot = node.child_by_field_name("type")
    if annot is not None and annot.text.decode("utf8", errors="ignore").split("[", 1)[0].strip() == "TypeAlias":
        return True
    return rhs is not None and _py_is_type_expression(rhs)


def _py_is_empty_container(rhs: Node | None) -> bool:
    """An accumulator seed: {}, [], or set()/dict()/list()/... with no elements."""
    if rhs is None:
        return False
    if rhs.type in ("dictionary", "list"):
        return not rhs.named_children
    if rhs.type == "call":
        fn = rhs.child_by_field_name("function")
        args = rhs.child_by_field_name("arguments")
        if fn is not None and fn.type == "identifier" and fn.text.decode("utf8", errors="ignore") in _PY_CONTAINER_CTORS:
            return args is None or not args.named_children
    return False


def _module_mutables_python(candidates: list[Node], this_idents: set[str]) -> set[str]:
    """Field-based module-global detection for Python. The binding name is read
    from the assignment's `left` field, so string literals and annotation tails
    are never scanned as source. Type aliases are skipped. An uppercase name is a
    constant by convention, unless it is seeded with an empty container, which is
    an accumulator (e.g. `CACHE = {}`), the pattern the indicator exists to catch."""
    mutables: set[str] = set()
    for node in candidates:
        left = node.child_by_field_name("left")
        if left is None or left.type != "identifier":  # skip subscripts, tuples, attributes
            continue
        name = left.text.decode("utf8", errors="ignore")
        # Dunders (__all__, __version__, ...) are module metadata, not state.
        if name in this_idents or (name.startswith("__") and name.endswith("__")):
            continue
        rhs = node.child_by_field_name("right")
        if _py_is_type_alias(node, rhs):
            continue
        if name.isupper():
            if _py_is_empty_container(rhs):
                mutables.add(name)
        else:
            mutables.add(name)
    return mutables


def _module_mutables_by_specifier(candidates: list[Node]) -> set[str]:
    """Rust-style: a top-level binding is mutable state iff its declaration carries
    a `mut` specifier (`static mut counter: i32 = 0`). The name is the declaration's
    `identifier` child, read structurally so the type token is never mistaken for
    the name. `const` and plain `static` are immutable and excluded."""
    mutables: set[str] = set()
    for node in candidates:
        if not any(c.type == "mutable_specifier" for c in node.children):
            continue
        name = next((c.text.decode("utf8", errors="ignore") for c in node.children if c.type == "identifier"), None)
        if name:
            mutables.add(name)
    return mutables


def _find_module_mutable_names(root: Node, cfg: dict[str, Any]) -> set[str]:
    """Detect top-level names that are likely mutable module state.

    Candidate assignments are collected structurally; for Python the binding name
    is read from the assignment's fields, never by splitting the node's text
    (which harvested annotation tails and identifiers out of string literals).
    Languages not yet migrated keep the legacy text heuristic."""
    assign_types = cfg["module_level_assign"]
    this_idents = cfg["this_ident"]

    # Top-level assignments, allowing one wrapper: Python nests `x = 0` inside an
    # `expression_statement`, so the `assignment` node is a child of a root child.
    candidates: list[Node] = []
    for node in root.children:
        if node.type in assign_types:
            candidates.append(node)
        else:
            candidates.extend(c for c in node.children if c.type in assign_types)

    if cfg.get("field_based_globals"):
        return _module_mutables_python(candidates, this_idents)

    if cfg.get("mutable_specifier_globals"):
        return _module_mutables_by_specifier(candidates)

    # Legacy text heuristic (unchanged), for languages not yet migrated.
    const_keywords = cfg.get("const_keywords", ("const ", "final ", "readonly ", "let ", "val "))
    mutables: set[str] = set()
    for node in candidates:
        text = node.text.decode("utf8", errors="ignore")
        for line in text.splitlines():
            if "=" in line and not any(kw in line.lower() for kw in const_keywords):
                parts = line.split("=")[0].strip().split()
                if parts:
                    name = parts[-1].strip("()[]:,")
                    if name and name not in this_idents and not name.isupper():
                        mutables.add(name)
    return mutables

def _count_mutable_refs(body: Node, cfg: dict[str, Any], module_mutables: set[str], receiver_names: set[str]) -> int:
    """Count references inside a function body to external mutable state.

    Handles, per-language via cfg: receiver/member access (self./this./<go
    receiver>.field), Ruby @instance / $global variables, module-level mutable
    globals referenced by bare identifier, and Rust/C raw patterns.

    Simplified reference implementation; the production version (Paper A) adds
    bound-literal exclusion and full per-language field resolution.
    """
    count = 0
    member_type = cfg["member_access"]
    instance_field_types = cfg.get("instance_field_types", ())
    raw_mut_patterns = cfg.get("raw_mut_patterns", ())

    def walk(n: Node):
        nonlocal count
        if n.type == member_type and receiver_names:
            text = n.text.decode("utf8", errors="ignore")
            if any(text.startswith(r + ".") for r in receiver_names):
                count += 1
        if n.type in instance_field_types:
            count += 1
        if n.type == "identifier" and n.text.decode("utf8", errors="ignore") in module_mutables:
            count += 1
        # Raw-text mutable patterns are language-scoped (Rust only). Running them
        # for every language flagged any source that merely contained the strings.
        if raw_mut_patterns:
            txt = n.text.decode("utf8", errors="ignore") if n.text else ""
            if any(p in txt for p in raw_mut_patterns):
                count += 1
        for c in n.children:
            walk(c)
    walk(body)
    return count

def _receiver_names(func_node: Node, cfg: dict[str, Any]) -> set[str]:
    """Names that denote the enclosing instance for this function. For self/this
    languages it is the fixed keyword set; for Go it is the method receiver
    identifier, parsed from the receiver parameter list."""
    fixed = set(cfg["this_ident"])
    if fixed:
        return fixed
    names: set[str] = set()
    if func_node.type == "method_declaration":  # Go: `func (r *Foo) Bar(...)`
        for child in func_node.children:
            if child.type == "parameter_list":
                for decl in child.children:
                    if decl.type == "parameter_declaration":
                        for part in decl.children:
                            if part.type == "identifier":
                                names.add(part.text.decode("utf8", errors="ignore"))
                break  # first parameter_list is the receiver
    return names

_BOUNDARY_MARKER = "honest: boundary"


def _is_declared_boundary(func_node: Node) -> bool:
    """True when a function carries an explicit boundary declaration: a comment
    containing `honest: boundary` (`# honest: boundary`, `// honest: boundary`).

    A declared boundary is where I/O legitimately touches external state, so L1.18
    excludes it from the ratio entirely, numerator and denominator. Recognition is
    by DECLARATION, never by guessing at function names or I/O calls: an unmarked
    function is never excluded, so no repository's number moves unless its authors
    opt in with the marker (the meter honoring the gate's declaration, per the
    finite-testability asymmetry)."""
    def find(n: Node) -> bool:
        if "comment" in n.type and n.text and _BOUNDARY_MARKER in n.text.decode("utf8", errors="ignore").lower():
            return True
        return any(find(c) for c in n.children)

    return find(func_node)


def _count_file_functions(root: Node, cfg: dict[str, Any], module_mutables: set[str]) -> tuple[int, int]:
    """Pure per-file walk: return (total functions, functions touching external
    mutable state). Module-level (not a loop closure) so it binds no caller state.
    Functions declared as I/O boundaries are excluded from both counts."""
    totals = [0, 0]  # [total, mutable]

    def find_functions(n: Node):
        if n.type in cfg["function_types"] and not _is_declared_boundary(n):
            totals[0] += 1
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers) > 0:
                    totals[1] += 1
        for c in n.children:
            find_functions(c)

    find_functions(root)
    return totals[0], totals[1]

def analyze_mutable_state(repo: Path, lang: str) -> L1Result:
    """L1.18: percentage of functions that reference external mutable state."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    total_funcs = 0
    mutable_funcs = 0
    for _path, src in files:
        root = parser.parse(src).root_node
        module_mutables = _find_module_mutable_names(root, cfg)
        file_total, file_mutable = _count_file_functions(root, cfg, module_mutables)
        total_funcs += file_total
        mutable_funcs += file_mutable

    ratio = (mutable_funcs / total_funcs * 100) if total_funcs > 0 else 0.0
    return {
        "value": round(ratio, 1),
        "band": band(ratio, 15, 40, higher_is_better=False),
        "details": _with_skipped(f"{mutable_funcs}/{total_funcs} functions reference external mutable state ({lang})", skipped),
    }


def _file_mutable_names(root: Node, cfg: dict[str, Any], module_mutables: set[str]) -> list[str]:
    """Names of the functions in one file that L1.18 counts as touching external
    mutable state. Same predicate as _count_file_functions (module-level so it
    binds no caller state), only it keeps the names instead of a tally."""
    names: list[str] = []

    def find(n: Node) -> None:
        if n.type in cfg["function_types"] and not _is_declared_boundary(n):
            body = next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
            if body is not None:
                receivers = _receiver_names(n, cfg)
                if _count_mutable_refs(body, cfg, module_mutables, receivers) > 0:
                    nm = n.child_by_field_name("name")
                    if nm is not None and nm.text:
                        names.append(nm.text.decode("utf8", errors="ignore"))
        for c in n.children:
            find(c)

    find(root)
    return names


def mutable_function_names(repo: Path, lang: str) -> list[str]:
    """L1.18's culprits by name: functions that reference external mutable state.

    Additive, read-only. A name appears here iff analyze_mutable_state counts that
    function (identical _count_mutable_refs predicate), so this never moves L1.18's
    value/band or the pre-registered number. Exists so the behavioural suite can
    assert *which* function is flagged instead of fabricating the answer."""
    if lang not in LANG_CFG:
        return []
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))
    names: list[str] = []
    for _path, src in files:
        root = parser.parse(src).root_node
        module_mutables = _find_module_mutable_names(root, cfg)
        names.extend(_file_mutable_names(root, cfg, module_mutables))
    return names


def module_mutable_names(repo: Path, lang: str) -> set[str]:
    """The module-level bindings L1.18 treats as mutable state. A binding is a
    *bound literal* (a constant, a frozen dispatch table) exactly when it is
    absent from this set. Additive, read-only; never affects L1.18's number."""
    if lang not in LANG_CFG:
        return set()
    cfg = LANG_CFG[lang]
    parser = _get_parser(lang)
    files, _skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))
    out: set[str] = set()
    for _path, src in files:
        root = parser.parse(src).root_node
        out |= _find_module_mutable_names(root, cfg)
    return out


# ---------------------------------------------------------------------------
# Full source-based indicators with tree-sitter for multi-lang support
# ---------------------------------------------------------------------------

def _run_external(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""

def compute_source_indicators(
    repo: Path,
    lang: str,
    exec_tests: bool,
    timeout_seconds: float,
    classify_state_bounds: bool = True,
) -> dict[str, L1Result]:
    """L1.12-L1.20. `lang` may be "auto" (resolved here) or a concrete key.
    `exec_tests` gates the two runtime indicators (L1.19 coverage, L1.20);
    `timeout_seconds` bounds each test-suite execution.

    `classify_state_bounds` gates the additive L1.18b state-bounds refinement. It
    is ON by default for real users (CLI, web). The pre-registered experiments
    pass False, which leaves the registered output byte-for-byte unchanged: this
    is the ONLY line the flag touches, so off-mode cannot alter any L1.18 number."""
    if lang == "auto":
        lang = detect_primary_language(repo)

    results: dict[str, L1Result] = {"lang": lang}
    results["L1.16"] = _trailing_whitespace(repo)
    results["L1.17"] = _god_files(repo)
    results["L1.18"] = analyze_mutable_state(repo, lang)
    results["L1.15"] = _compute_type_escapes(repo, lang)
    results["L1.19"] = _decision_space_l19(repo, lang, exec_tests, timeout_seconds)
    results.update(_compute_external_indicators(repo, lang))
    results["L1.20"] = _test_determinism_l20(repo, lang, exec_tests, timeout_seconds)
    if classify_state_bounds:
        from l1_analyzer import state_bounds
        results["L1.18b"] = state_bounds.classify(repo, lang)
        from l1_analyzer import path_cover
        results["path_cover"] = path_cover.cover_paths(repo, lang)
    return results

_WHITESPACE_EXTS = frozenset({".py", ".rs", ".c", ".h", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".java", ".cs", ".rb", ".go"})
_GOD_FILE_EXTS = frozenset({".py", ".rs", ".c", ".h", ".js", ".ts", ".java", ".cs", ".go", ".rb"})

def _trailing_whitespace(repo: Path) -> L1Result:
    """L1.16: percentage of non-blank lines with trailing whitespace."""
    files, skipped = _read_text_files(repo, _WHITESPACE_EXTS, extra_ignore=())
    count = total = 0
    for _path, text in files:
        lines = text.splitlines()
        total += len(lines)
        count += sum(1 for ln in lines if ln.rstrip() != ln and ln.strip())
    ws_pct = (count / total * 100) if total > 0 else 0.0
    return {"value": round(ws_pct, 2), "band": band(ws_pct, 0.5, 3, higher_is_better=False), "details": _with_skipped(f"{count} lines with trailing ws", skipped)}

def _god_files(repo: Path) -> L1Result:
    """L1.17: concentration of files over 1k LOC (any file over 4k forces Slop)."""
    files, skipped = _read_text_files(repo, _GOD_FILE_EXTS, extra_ignore=("tests", "test"))
    prod_files = god_files = big_files = 0
    for _path, text in files:
        lines = len(text.splitlines())
        prod_files += 1
        if lines > 1000:
            god_files += 1
        if lines > 4000:
            big_files += 1
    god_pct = (god_files / prod_files * 100) if prod_files > 0 else 0.0
    band_value = "Slop" if big_files > 0 else band(god_pct, 0.5, 2, higher_is_better=False)
    return {"value": round(god_pct, 2), "band": band_value, "details": _with_skipped(f"{god_files}/{prod_files} files >1k LOC, {big_files} >4k LOC", skipped)}

def _decision_space_l19(repo: Path, lang: str, exec_tests: bool, timeout_seconds: float) -> L1Result:
    """Real branch coverage when the suite can run; otherwise the static
    decision-point enumeration with coverage clearly marked not-measured."""
    static = _compute_decision_space(repo, lang)
    if not exec_tests:
        static["details"] += "; coverage not measured (test execution disabled)"
        return static
    cov = pytest_trace.decision_space_coverage(repo, lang, timeout_seconds)
    if cov.get("band") != "n/a":
        return cov
    static["details"] += f"; coverage not measured: {cov.get('details', 'unavailable')}"
    return static

def _test_determinism_l20(repo: Path, lang: str, exec_tests: bool, timeout_seconds: float) -> L1Result:
    if not exec_tests:
        return {"value": "not run", "band": "n/a", "details": "test execution disabled"}
    return pytest_trace.test_determinism(repo, lang, 5, timeout_seconds)

_COMMENT_TYPE_ESCAPES = ("# type: ignore", "// @ts-ignore", "/* @ts-ignore", "@SuppressWarnings")

def _count_type_escapes_in_tree(root: Node, escape_tokens: frozenset[str]) -> int:
    """Count type-escape hatches in one parsed tree.

    A type token (Any, object, dynamic, ...) is matched only on a leaf node whose
    exact text is one of `escape_tokens`, so it catches real annotations without
    matching parent nodes (which would double count) or the builtin `any()` call.
    An ignore-comment is matched only on a comment node, so string literals that
    happen to contain "# type: ignore" (like this module's own pattern list) are
    not counted - the false positive that made L1.15 report escapes it never saw.
    """
    count = 0

    def walk(n: Node):
        nonlocal count
        if not n.children:  # leaf token
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if text in escape_tokens:
                count += 1
        if "comment" in n.type:
            text = n.text.decode("utf8", errors="ignore") if n.text else ""
            if any(pat in text for pat in _COMMENT_TYPE_ESCAPES):
                count += 1
        for c in n.children:
            walk(c)

    walk(root)
    return count

def _compute_type_escapes(repo: Path, lang: str) -> L1Result:
    """L1.15: density of type-escape hatches (Any/object/dynamic and ignore comments)."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    cfg = LANG_CFG[lang]
    if not cfg["type_escape_patterns"]:
        # Untyped or no configured escape hatch (Ruby, JavaScript, Rust, C).
        return {"value": "n/a", "band": "n/a", "details": f"type-escape density not applicable for {lang}"}
    parser = _get_parser(lang)
    escape_tokens = frozenset(cfg["type_escape_patterns"])
    files, skipped = _read_source_bytes(repo, cfg["extensions"], extra_ignore=("tests", "test"))

    escape_count = 0
    total_loc = 0
    for _path, src in files:
        total_loc += len(src.decode("utf8", errors="ignore").splitlines())
        escape_count += _count_type_escapes_in_tree(parser.parse(src).root_node, escape_tokens)

    density = (escape_count / (total_loc / 1000)) if total_loc > 1000 else 0.0
    return {"value": round(density, 2), "band": band(density, 1, 5, higher_is_better=False), "details": _with_skipped(f"{escape_count} escapes in ~{total_loc // 1000}kLOC", skipped)}

# Control-flow branch node types across the supported grammars. Exact-type
# matches (not substring) so short Ruby types like "if"/"case"/"when" are safe.
_DECISION_NODE_TYPES = frozenset({
    "if_statement", "if_expression", "if", "elif_clause", "else_if_clause",
    "conditional_expression", "ternary_expression",
    "switch_statement", "switch_expression", "switch_section", "switch_case",
    "expression_switch_statement", "type_switch_statement", "expression_case",
    "type_case", "default_case", "communication_case", "select_statement",
    "match_expression", "match_statement", "match_arm", "case_clause",
    "case", "when", "case_match", "in_clause",  # ruby
})

def _compute_decision_space(repo: Path, lang: str) -> L1Result:
    """L1.19, static half: enumerate the finite decision points via tree-sitter.
    The exercised-coverage fraction requires a runtime trace (see
    pytest_trace.decision_space_coverage); when the suite cannot be run this is
    reported as not-measured rather than fabricated."""
    if lang not in LANG_CFG:
        return {"value": "n/a", "band": "n/a", "details": f"no tree-sitter config for {lang}"}
    parser = _get_parser(lang)
    files, skipped = _read_source_bytes(repo, LANG_CFG[lang]["extensions"], extra_ignore=("tests", "test"))

    decision_points = 0
    for _path, src in files:
        root = parser.parse(src).root_node

        def walk(n: Node):
            nonlocal decision_points
            if n.type in _DECISION_NODE_TYPES:
                decision_points += 1
            for c in n.children:
                walk(c)
        walk(root)

    detail = f"{decision_points} finite decision points enumerated across {len(files)} files; exercised-coverage fraction requires a test-execution trace (not run by this reference implementation)"
    return {"value": decision_points, "band": "n/a", "details": _with_skipped(detail, skipped)}

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
        res["L1.14"] = {"value": hits, "band": band(hits, 1, 3, higher_is_better=False), "details": "gitleaks findings"}
    elif shutil.which("detect-secrets"):
        out = _run_external(["detect-secrets", "scan", "."], repo)
        hits = out.count('"is_verified"')
        res["L1.14"] = {"value": hits, "band": band(hits, 1, 3, higher_is_better=False), "details": "detect-secrets findings"}
    else:
        res["L1.14"] = {"value": "n/a", "band": "n/a", "details": "install gitleaks or detect-secrets to compute L1.14"}

    # L1.12 dead code - language-specific tool; only Python (vulture) is wired here
    if lang == "python" and shutil.which("vulture"):
        out = _run_external(["vulture", ".", "--min-confidence", "80"], repo)
        unreach = len([line for line in out.splitlines() if line.strip()])
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
            res["L1.13"] = {"value": clone_pct, "band": band(clone_pct, 3, 10, higher_is_better=False), "details": "jscpd duplication percentage"}
        else:
            res["L1.13"] = {"value": "n/a", "band": "n/a", "details": "jscpd produced no parseable duplication percentage"}
    else:
        res["L1.13"] = {"value": "n/a", "band": "n/a", "details": "install jscpd to compute L1.13"}

    return res
