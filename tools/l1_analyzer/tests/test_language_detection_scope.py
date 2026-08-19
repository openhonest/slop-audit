"""Language detection goes through the same scope policy every other reader does.

`detect_primary_language` counted every file in the tree with no build-artifact
exclusion, while the indicator scopes in scope.py declare them. So detection sat outside
the policy every other reader goes through, and a directory nobody would call source
decided which grammar the whole audit used.

Reproduced on this repository's own Rust crate: thirteen `.rs` files outside `target/`,
zero `.c` or `.h` outside it, and twenty-three vendored `.c` and `.h` files inside
`target/` from the linked tree-sitter grammars. The crate detected as C.

The consequence is not a wrong label. Every source indicator then runs the C grammar over
Rust, and the interleaving-robustness meter, which is Rust-only, returns n/a with the
reason "c not supported yet". Passing `--lang rust` gives the right answer, so the
measurement was right and only the detection was wrong.
"""

import pathlib
import tempfile

from l1_analyzer.indicators import detect_primary_language


def _detect(files: dict[str, str]) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        for name, body in files.items():
            (p / name).parent.mkdir(parents=True, exist_ok=True)
            (p / name).write_text(body)
        return detect_primary_language(p)


def test_a_built_rust_crate_is_not_detected_as_c():
    """Thirteen Rust files against twenty-three vendored C files under `target/`. The
    shape that reproduced it, in miniature."""
    files = {f"src/m{i}.rs": "fn main() {}\n" for i in range(13)}
    files.update({f"target/debug/build/g{i}/parser.c": "int x;\n" for i in range(23)})
    assert _detect(files) == "rust"


def test_a_repository_that_really_is_c_still_detects_as_c():
    """The guard. Excluding build output must not stop a C repository being read as one."""
    files = {f"src/m{i}.c": "int x;\n" for i in range(5)}
    files["README.md"] = "# c\n"
    assert _detect(files) == "c"


def test_vendored_source_does_not_decide_the_language_either():
    """`node_modules` and `vendor` are the same argument as `target`: code nobody here
    wrote, in a directory the scope policy already names."""
    files = {"src/a.py": "x = 1\n"}
    files.update({f"node_modules/p{i}/index.js": "var x;\n" for i in range(20)})
    assert _detect(files) == "python"
