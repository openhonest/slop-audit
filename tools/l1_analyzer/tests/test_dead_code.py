"""L1.12, native: the unreachable-code ratio, to the canon's definition.

Canon (03-layer1-indicators.md, L1.12 row): "Lines of code flagged as unreachable or
unreferenced by a language-appropriate dead-code analyzer ... divided by total
production lines of code", banded <1% / 1-5% / >5%.

The tests that matter most here are the ones that must NOT fire. A dead-code detector
that cannot see a framework entry point and reports it as dead is reporting its own
blind spot as a defect in someone's code. Every such case below asserts `undecidable`,
never `dead`.

Pure assertions against temp repos, no mocks.
"""

import pathlib
import tempfile

from l1_analyzer import dead_code


def _analyze(files: dict[str, str], lang: str) -> dict:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        return dead_code.analyze(root, lang)


def _names(entries: list[dict]) -> set[str]:
    return {e["name"] for e in entries}


def _reasons(entries: list[dict]) -> dict[str, str]:
    return {e["name"]: e["reason"] for e in entries}


# --- the ratio itself, which the canon defines and the old implementation did not ----

def test_value_is_a_percentage_of_production_loc_not_a_raw_count():
    # 10 production lines; `dead` spans lines 5-6, so 2 flagged lines -> 20%.
    src = (
        "def used():\n"          # 1
        "    return 1\n"         # 2
        "\n"                     # 3
        "\n"                     # 4
        "def dead():\n"          # 5
        "    return 2\n"         # 6
        "\n"                     # 7
        "\n"                     # 8
        "print(used())\n"        # 9
        "\n"                     # 10
    )
    r = _analyze({"app.py": src}, "python")
    assert r["production_loc"] == 10
    assert r["flagged_lines"] == 2
    assert r["value"] == 20.0
    assert r["band"] == "Slop"


def test_bands_follow_the_canon_thresholds():
    assert dead_code._band_for(0.9) == "Healthy"
    assert dead_code._band_for(1.0) == "Not Healthy"
    assert dead_code._band_for(4.9) == "Not Healthy"
    assert dead_code._band_for(5.0) == "Slop"


def test_clean_repo_is_healthy_at_zero():
    r = _analyze({"app.py": "def used():\n    return 1\n\n\nprint(used())\n"}, "python")
    assert r["value"] == 0.0 and r["band"] == "Healthy"


# --- category one: unreachable statements after a terminator ------------------------

def test_flags_a_statement_after_return():
    r = _analyze({"app.py": "def f():\n    return 1\n    print('never')\n\n\nprint(f())\n"}, "python")
    assert [e["category"] for e in r["findings"]] == ["unreachable"]
    assert r["findings"][0]["line"] == 3


def test_flags_every_statement_after_a_raise():
    src = "def f():\n    raise ValueError('x')\n    a = 1\n    b = 2\n\n\nprint(f)\n"
    r = _analyze({"app.py": src}, "python")
    unreachable = [e for e in r["findings"] if e["category"] == "unreachable"]
    assert len(unreachable) == 2 and r["flagged_lines"] == 2


def test_does_not_flag_code_after_a_conditional_return():
    src = "def f(x):\n    if x:\n        return 1\n    return 2\n\n\nprint(f)\n"
    r = _analyze({"app.py": src}, "python")
    assert r["findings"] == []


# --- category two: unreferenced module-level definitions ----------------------------

def test_flags_an_unreferenced_module_level_function():
    r = _analyze({"app.py": "def orphan():\n    return 1\n"}, "python")
    assert _names(r["findings"]) == {"orphan"}
    assert r["findings"][0]["category"] == "unreferenced"


def test_a_definition_referenced_from_another_file_is_alive():
    r = _analyze({"a.py": "def used():\n    return 1\n",
                  "b.py": "from a import used\n\n\nprint(used())\n"}, "python")
    assert r["findings"] == []


# --- the cases a naive detector gets wrong: these must NOT be flagged as dead -------

def test_a_public_api_consumed_only_by_tests_is_not_dead():
    r = _analyze({"a.py": "def public_api():\n    return 1\n",
                  "tests/test_a.py": "from a import public_api\n\n\ndef test_it():\n    assert public_api() == 1\n"},
                 "python")
    assert _names(r["findings"]) == set()
    assert "public_api" in _names(r["test_only"])


def test_an_entry_point_named_in_a_config_file_is_not_dead():
    r = _analyze({"pkg/cli.py": "def main():\n    return 0\n",
                  "pyproject.toml": '[project.scripts]\nmytool = "pkg.cli:main"\n'},
                 "python")
    assert _names(r["findings"]) == set()
    assert _reasons(r["undecidable"])["main"].startswith("named in")


def test_a_framework_hook_is_undecidable_not_dead():
    src = ("import flask\n"
           "app = flask.Flask(__name__)\n"
           "\n"
           "\n"
           "@app.route('/health')\n"
           "def healthz():\n"
           "    return 'ok'\n")
    r = _analyze({"srv.py": src}, "python")
    assert "healthz" not in _names(r["findings"])
    assert "decorated" in _reasons(r["undecidable"])["healthz"]


def test_an_all_export_is_undecidable_not_dead():
    r = _analyze({"pkg/api.py": '__all__ = ["exported"]\n\n\ndef exported():\n    return 1\n'}, "python")
    assert "exported" not in _names(r["findings"])
    assert "__all__" in _reasons(r["undecidable"])["exported"]


def test_a_name_used_only_inside_a_string_is_undecidable_not_dead():
    # getattr(mod, "handler") is dynamic dispatch. The detector cannot resolve it,
    # so it says so instead of calling the target dead.
    r = _analyze({"a.py": "def handler():\n    return 1\n",
                  "b.py": "import a\n\n\nfn = getattr(a, 'handler')\n"}, "python")
    assert "handler" not in _names(r["findings"])
    assert "string" in _reasons(r["undecidable"])["handler"]


def test_a_pytest_plugin_hook_and_a_test_function_are_never_flagged():
    # Found on a real repository: umbra ships `pytest_configure` and
    # `pytest_sessionfinish` as production code. pytest calls them by name, nothing
    # imports them, and this pass called both dead.
    src = ("def pytest_configure(config):\n"
           "    return None\n"
           "\n"
           "\n"
           "def pytest_sessionfinish(session, exitstatus):\n"
           "    return None\n")
    r = _analyze({"plugin.py": src,
                  "examples/test_cart.py": "def test_total():\n    assert True\n"}, "python")
    assert _names(r["findings"]) == set()
    assert r["counts"]["entry_points"] == 3


def test_dunder_and_main_are_never_flagged():
    src = ("__version__ = '1.0'\n"
           "\n"
           "\n"
           "def main():\n"
           "    return 0\n"
           "\n"
           "\n"
           "if __name__ == '__main__':\n"
           "    main()\n")
    r = _analyze({"app.py": src}, "python")
    assert _names(r["findings"]) == set()


# --- honest disclosure --------------------------------------------------------------

def test_details_disclose_the_undecidable_share_so_the_ratio_reads_as_a_lower_bound():
    r = _analyze({"pkg/api.py": '__all__ = ["exported"]\n\n\ndef exported():\n    return 1\n'}, "python")
    assert "undecidable" in r["details"]
    assert r["counts"]["undecidable"] == 1


def test_an_unsupported_language_is_na_with_a_reason_never_guessed():
    r = _analyze({"a.kt": "fun main() {}\n"}, "kotlin")
    assert r["value"] == "n/a" and r["band"] == "n/a"
    assert "kotlin" in r["details"]


def test_a_repo_with_no_production_source_is_na_not_zero():
    r = _analyze({"tests/test_a.py": "def test_x():\n    assert True\n"}, "python")
    assert r["value"] == "n/a" and r["band"] == "n/a"


# --- the other eight languages ------------------------------------------------------

def test_rust_flags_a_private_unreferenced_function_and_spares_pub_api():
    files = {"Cargo.toml": "[package]\nname = \"x\"\n",
             "src/lib.rs": "pub fn api() -> i32 { 1 }\n\nfn orphan() -> i32 { 2 }\n"}
    r = _analyze(files, "rust")
    assert _names(r["findings"]) == {"orphan"}
    assert "public" in _reasons(r["undecidable"])["api"]


def test_rust_derive_attribute_makes_an_item_undecidable():
    files = {"Cargo.toml": "[package]\nname = \"x\"\n",
             "src/main.rs": "#[derive(Debug)]\nstruct Config { a: i32 }\n\nfn main() {}\n"}
    r = _analyze(files, "rust")
    assert "Config" not in _names(r["findings"])


def test_go_spares_main_init_and_exported_package_identifiers():
    files = {"go.mod": "module x\n",
             "lib/lib.go": "package lib\n\nfunc Exported() int { return 1 }\n\nfunc orphan() int { return 2 }\n"}
    r = _analyze(files, "go")
    assert _names(r["findings"]) == {"orphan"}
    assert "exported" in _reasons(r["undecidable"])["Exported"]


def test_go_flags_a_statement_after_return():
    files = {"go.mod": "module x\n",
             "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\treturn\n\tfmt.Println("x")\n}\n'}
    r = _analyze(files, "go")
    assert [e["category"] for e in r["findings"]] == ["unreachable"]


def test_java_flags_an_unreferenced_private_method_and_spares_public_ones():
    src = ("package a;\n"
           "public class Foo {\n"
           "    private int orphan() { return 1; }\n"
           "    public int api() { return 2; }\n"
           "}\n")
    r = _analyze({"src/a/Foo.java": src}, "java")
    assert "orphan" in _names(r["findings"])
    assert "api" not in _names(r["findings"])


def test_java_annotated_member_is_undecidable():
    src = ("package a;\n"
           "public class Foo {\n"
           "    @Override\n"
           "    private int hook() { return 1; }\n"
           "}\n")
    r = _analyze({"src/a/Foo.java": src}, "java")
    assert "hook" not in _names(r["findings"])
    assert "annotated" in _reasons(r["undecidable"])["hook"]


def test_typescript_flags_an_unreferenced_export_the_way_ts_prune_does():
    files = {"package.json": '{"name":"x","main":"src/index.ts"}\n',
             "src/index.ts": "export function entry(): number { return 1; }\n",
             "src/util.ts": "export function orphan(): number { return 2; }\n"}
    r = _analyze(files, "typescript")
    assert _names(r["findings"]) == {"orphan"}
    assert "entry" in _names(r["undecidable"])


def test_tsx_is_parsed_with_the_jsx_grammar_so_a_component_is_not_reported_dead():
    files = {"package.json": '{"name":"x"}\n',
             "src/Button.tsx": "export function Button() { return <b>hi</b>; }\n",
             "src/App.tsx": "import { Button } from './Button';\nexport function App() { return <Button />; }\n"}
    r = _analyze(files, "typescript")
    assert "Button" not in _names(r["findings"])


def test_javascript_flags_an_unreferenced_function():
    r = _analyze({"a.js": "function orphan() { return 1; }\n",
                  "b.js": "console.log('hi');\n"}, "javascript")
    assert _names(r["findings"]) == {"orphan"}


def test_csharp_flags_an_unreferenced_private_method():
    src = ("namespace N {\n"
           "  public class Foo {\n"
           "    private int Orphan() { return 1; }\n"
           "    public int Api() { return 2; }\n"
           "  }\n"
           "}\n")
    r = _analyze({"src/Foo.cs": src}, "csharp")
    assert "Orphan" in _names(r["findings"])
    assert "Api" not in _names(r["findings"])


def test_c_flags_an_unreferenced_static_function_and_spares_an_external_one():
    files = {"src/a.c": "static int orphan(void) { return 1; }\n\nint api(void) { return 2; }\n"}
    r = _analyze(files, "c")
    assert _names(r["findings"]) == {"orphan"}
    assert "external linkage" in _reasons(r["undecidable"])["api"]


# --- the false positives the real-repository run exposed ----------------------------

def test_a_case_label_after_a_break_is_reachable_not_dead():
    """Found on libuv. `uv__close` has a `#if`-guarded `return` followed by `break`, and
    every remaining `case` in that switch read as unreachable code. A `case` is entered
    from the switch, not from the statement above it."""
    src = ("void f(int h) {\n"
           "  switch (h) {\n"
           "  case A:\n"
           "    g();\n"
           "    return;\n"
           "    break;\n"
           "  case B:\n"
           "    q();\n"
           "    break;\n"
           "  default:\n"
           "    r();\n"
           "  }\n"
           "}\n")
    r = _analyze({"src/a.c": src}, "c")
    assert [f["line"] for f in r["findings"] if f["category"] == "unreachable"] == []


def test_a_preprocessor_directive_after_a_return_is_not_unreachable_code():
    """Found on Newtonsoft.Json, 28 times: `return default;` sits between a
    `#pragma warning disable` and its matching `restore`."""
    src = ("class C {\n"
           "  static int F() {\n"
           "#pragma warning disable CS8653\n"
           "    return 0;\n"
           "#pragma warning restore CS8653\n"
           "  }\n"
           "}\n")
    r = _analyze({"src/C.cs": src}, "csharp")
    assert [f for f in r["findings"] if f["category"] == "unreachable"] == []


def test_a_trailing_comment_after_a_return_is_not_unreachable_code():
    """Found on JUnit: `return 0L; // 0 = never failed`. The Java grammar spells a
    comment `line_comment`, so a rule that only knew `comment` charged it."""
    src = ("class C {\n"
           "  private long f() {\n"
           "    return 0L; // never\n"
           "  }\n"
           "}\n")
    r = _analyze({"src/C.java": src}, "java")
    assert [f for f in r["findings"] if f["category"] == "unreachable"] == []


def test_a_goto_does_not_make_the_rest_of_the_function_dead():
    """Found on libuv's `uv_setup_args`: `goto loop;` jumps into the middle of the `for`
    below it. Where a goto lands is not decidable by scanning siblings, so a goto is not
    treated as a terminator at all."""
    src = ("void f(int argc) {\n"
           "  int i = 0;\n"
           "  goto loop;\n"
           "  for (; i < argc; i++) {\n"
           "  loop:\n"
           "    g(i);\n"
           "  }\n"
           "}\n")
    r = _analyze({"src/a.c": src}, "c")
    assert [f for f in r["findings"] if f["category"] == "unreachable"] == []


def test_a_conditionally_compiled_block_is_not_scanned_for_unreachable_code():
    """Found on libuv's `uv__fs_statfs`: a `#endif` sits between an `if` condition and its
    body, which detaches them in the parse and makes every following statement read as
    dead. A sibling scan is unsound there, so the block is skipped rather than guessed at."""
    src = ("int f(void) {\n"
           "#ifdef __sun\n"
           "  if (0 != g())\n"
           "#endif\n"
           "    return -1;\n"
           "  h();\n"
           "  return 0;\n"
           "}\n")
    r = _analyze({"src/a.c": src}, "c")
    assert [f for f in r["findings"] if f["category"] == "unreachable"] == []


def test_a_c_file_that_pastes_identifiers_has_undecidable_definitions():
    """Found on libuv: `#define XX(uc, lc) case UV_FS_##uc: fs__##lc(req); break;` calls
    `fs__rmdir` at a site where that name never appears. Twenty-eight findings were this."""
    src = ("#define XX(uc, lc)  case UV_FS_##uc: fs__##lc(req); break;\n"
           "static void fs__rmdir(uv_fs_t* req) { g(req); }\n")
    r = _analyze({"src/fs.c": src}, "c")
    assert "fs__rmdir" not in _names(r["findings"])
    assert "token pasting" in _reasons(r["undecidable"])["fs__rmdir"]
    assert r["counts"]["files_token_pasting"] == 1


def test_a_file_the_grammar_cannot_parse_produces_no_findings():
    """Found on Newtonsoft.Json: JValue.cs parses with ERROR nodes and the statements
    around them read as unreachable, sixteen of them. A tree the grammar could not parse
    cannot support a claim about what it contains."""
    files = {f"ok{i}.py": f"def used_{i}():\n    return {i}\n\n\nprint(used_{i}())\n" for i in range(9)}
    files["broken.py"] = "def f(:\n    return 1\n    print('x')\n"
    r = _analyze(files, "python")
    assert r["findings"] == []
    assert r["counts"]["files_unparsed"] == 1
    assert "could not parse" in r["details"]


def test_a_language_the_grammar_mostly_fails_to_parse_is_na_not_a_ratio():
    """C parses at 34% on json-c and 59% on libuv: tree-sitter runs no preprocessor, and
    real C hides its declarations behind export macros. A ratio over a third of a
    codebase is not a ratio for that codebase."""
    files = {f"src/f{i}.c": "static int orphan(void) { return 1; }\n" for i in range(4)}
    files["src/broken.c"] = "int f(void) { if (\n"
    files["src/broken2.c"] = "int g(void) { while (\n"
    r = _analyze(files, "c")
    assert r["value"] == "n/a" and r["band"] == "n/a"
    assert "parsed only" in r["details"] and "preprocessor" in r["details"]


def test_a_csharp_extension_member_block_container_is_undecidable_not_dead():
    """RestSharp's newer `extension(Receiver r) { ... }` spelling, which the grammar
    parses as a constructor named `extension`."""
    src = ("static class BodyExtensions {\n"
           "    extension(RestRequest request) {\n"
           "        public bool TryGet(out int x) { x = 1; return true; }\n"
           "    }\n"
           "}\n")
    r = _analyze({"src/BodyExtensions.cs": src}, "csharp")
    assert "BodyExtensions" not in _names(r["findings"])


def test_a_csharp_extension_method_container_is_undecidable_not_dead():
    """Found on RestSharp: all ten `unreferenced type` findings were extension
    containers in daily use. `items.ForEach(...)` never names `CollectionExtensions`."""
    src = ("static class CollectionExtensions {\n"
           "    public static void ForEach<T>(this IEnumerable<T> items, Action<T> a) { }\n"
           "}\n")
    r = _analyze({"src/CollectionExtensions.cs": src}, "csharp")
    assert "CollectionExtensions" not in _names(r["findings"])
    assert "extension-method container" in _reasons(r["undecidable"])["CollectionExtensions"]


def test_a_java_serialization_member_is_never_flagged():
    """Found on JUnit: `Result.serialPersistentFields` is read by the serialization
    runtime through reflection, so no source references it."""
    src = ("import java.io.ObjectStreamField;\n"
           "class Result {\n"
           "    private static final ObjectStreamField[] serialPersistentFields = null;\n"
           "}\n")
    r = _analyze({"src/Result.java": src}, "java")
    assert "serialPersistentFields" not in _names(r["findings"])


def test_ruby_is_na_when_the_repo_uses_runtime_metaprogramming():
    files = {"lib/a.rb": "class Foo\n  define_method(:x) { 1 }\nend\n"}
    r = _analyze(files, "ruby")
    assert r["value"] == "n/a" and "metaprogramming" in r["details"]


def test_ruby_flags_an_unreferenced_method_when_no_metaprogramming_is_present():
    files = {"lib/a.rb": "def orphan\n  1\nend\n"}
    r = _analyze(files, "ruby")
    assert _names(r["findings"]) == {"orphan"}
