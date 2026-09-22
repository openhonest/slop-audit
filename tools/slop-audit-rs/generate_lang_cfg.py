"""Generate src/lang_cfg.rs from the Python reference's LANG_CFG.

The second table this port reads, beside LANG_SPEC. It was TRANSCRIBED, seven keys of it, by
hand, and that was survivable while seven keys were all the ported indicators needed. L1.18
reads fifteen more, so the hand-copied table was about to more than triple and the risk with
it: one wrong node-type string would make the ratio disagree with the reference on one
construct in one language and agree everywhere else.

So it is generated now, like its neighbour, and never edited. The reference is the only
source, and `--check` proves the committed file still matches it.

    uv run generate_lang_cfg.py            # write src/lang_cfg.rs
    uv run generate_lang_cfg.py --check    # exit 1 if the committed file is stale

The rendering helpers come from generate_lang_spec, which already had them. A second copy of
"render a Python value as a Rust literal" is the drift this pair of generators exists to
prevent, committed by the generators themselves.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from generate_lang_spec import rust_str, rust_strs

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
TARGET = HERE / "src" / "lang_cfg.rs"

# The keys the port reads, and what each one is FOR. A key with no note here is a key
# nothing in this crate consults, and it stays out of the generated struct: a field nobody
# reads is a field nobody can check.
#
# The notes are the doc comments the hand-written table carried. They are here rather than in
# the generated file because the generated file is rewritten on every run, and a comment
# somebody wrote about a measured defect must not be something a regeneration deletes.
NOTES: dict[str, str] = {
    "extensions": "The source extensions of this language, leading dot, lowercase.",
    "type_escape_patterns":
        "L1.15's escape-hatch tokens. Empty means L1.15 is absent for the language, which is\n"
        "the truth for Ruby, JavaScript, Rust and C: untyped, or no configured escape hatch.",
    "annotation_escape_nodes":
        "The grammar's annotation node types, where a language writes its suppressions as an\n"
        "annotation rather than a comment.",
    "annotation_escape_names":
        "The annotation names that suppress a type diagnostic. Java only for now; see\n"
        "research/amendments/amendment-2026-08-14-java-suppression-marker.md.",
    "type_escape_nonpositions":
        "Node types under which a matching token is NOT a type. `from typing import Any` makes\n"
        "a symbol available and types nothing, so every statically typed Python file carried a\n"
        "floor of one escape without this.\n"
        "\n"
        "Stated as a refusal rather than an allow-list of type positions, because Go and C# put\n"
        "a bare type straight into a declaration with no node to key on. An empty vocabulary\n"
        "refuses nothing, which is the counted direction.",
    "type_cast_calls":
        "Calls whose first argument IS a type, so a STRING there is counted like the annotation\n"
        "it is. `cast(\"dict[str, Any]\", ctx)` is the ordinary way to write the one acknowledged\n"
        "escape at a framework seam, and the leaf walk drops it with every other string: the\n"
        "same code scored 2 unquoted and 1 quoted, so a reader could move the number by adding\n"
        "quotation marks.",
    "type_position_types": "Node types that hold a written type.",
    "bare_generics": "Generic container names that carry no element type.",
    "const_keywords":
        "The words this language writes on a binding it cannot rebind.\n"
        "\n"
        "Per language, never shared. The shared default was a union of five languages' keywords\n"
        "that no single language uses, and only two overrode it, so TypeScript inherited `let `\n"
        "and read every module-level `let` as immutable.",
    "field_decl_types": "The node types that declare a field of a record.",
    "function_types": "The node types L1.18 counts as a function.",
    "immutable_modifiers":
        "The modifier words that make a declared field unrebindable: final, readonly, const.",
    "instance_field_types":
        "Node types that ARE a reach into instance state on their own, with no receiver to\n"
        "read: Ruby's instance variable and global variable.",
    "member_access": "The node type of a receiver-and-member reach.",
    "member_op":
        "The operator joining receiver to member. A hard-coded `.` here is right in eight of\n"
        "the nine and wrong in C, where a caller's record is reached as `s->cache`, and that\n"
        "made L1.18's member arm dead code for C.",
    "module_level_assign": "The node types a top-level binding can be spelled as.",
    "module_scan":
        "Which module-scan rule this language DECLARES. A chain of flag tests used to fall\n"
        "through to the text heuristic, so TypeScript and C reached that path by omission\n"
        "rather than by decision and inherited its shared keyword default with it.",
    "raw_mut_patterns": "Raw text patterns that denote mutable state. Rust only.",
    "receiver_scan":
        "Which receiver rule this language DECLARES. The fall-through here was the empty set,\n"
        "and C took it: no `this` keyword and no method declaration, so a struct field mutated\n"
        "through a pointer counted as no external state on any repository ever audited.",
    "this_ident": "The receiver keywords this language fixes for every method.",
    "type_constructors": "Calls that RETURN a type, so a binding to one declares a type.",
    # Its own table in the reference rather than a key of LANG_CFG, and folded in here so
    # that every field the generated struct carries has exactly one note, read by subscript.
    # It was read through a fallback until 2026-09-21, which answers for a key nobody wrote.
    "literal_nodes":
        "Container-literal node types that read as a data table, discounted from the L1.17\n"
        "code-line count.",
}


def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    The analyzer package declares its edges with a decorator of this name. This script sits
    beside that package rather than inside it, so it says the same thing in its own words
    rather than importing across the boundary between a Rust crate's helper and the Python
    tool it reads."""
    return fn


@boundary
def reference_cfg() -> dict[str, dict[str, object]]:
    """LANG_CFG and the literal-node table, read out of the reference's own environment.

    Run as a subprocess rather than imported, because this script lives in the crate and the
    reference is a separate project with its own dependencies.

    The `language` value is dropped: it is a compiled grammar object, and the port links its
    own. Everything else comes across as a list or a string."""
    script = (
        "import json\n"
        "from l1_analyzer.indicators import LANG_CFG, _LITERAL_NODES\n"
        "def plain(v):\n"
        "    if isinstance(v, frozenset): return sorted(v)\n"
        "    if isinstance(v, (tuple, list)): return list(v)\n"
        "    return v\n"
        "rows = {}\n"
        "for lang, row in LANG_CFG.items():\n"
        "    out = {k: plain(v) for k, v in row.items() if k != 'language'}\n"
        "    out['literal_nodes'] = plain(_LITERAL_NODES.get(lang, ()))\n"
        "    rows[lang] = out\n"
        "print(json.dumps(rows))\n"
    )
    out = subprocess.run(
        ["uv", "run", "python", "-c", script],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    import json
    return json.loads(out)


def shape_of(cfg: dict[str, dict[str, object]], key: str) -> str:
    """Whether this key is a string or a list of them, measured over every language.

    A shape nothing here covers is a refusal, never a guess: a new value shape in the
    reference must stop the generator rather than be rendered as whatever the last branch
    happened to produce."""
    kinds = {type(cfg[lang].get(key)).__name__ for lang in cfg}
    if kinds <= {"str"}:
        return "str"
    if kinds <= {"list"}:
        return "slice"
    raise SystemExit(f"{key} holds {sorted(kinds)}, which this generator has no shape for")


HEADER = '''//! @generated by generate_lang_cfg.py from l1_analyzer.indicators.LANG_CFG. Do not edit.
//!
//! The per-language configuration the indicators read: extensions, the node types each
//! grammar spells a construct with, and which scan rule each language declares.
//!
//! GENERATED, NOT TRANSCRIBED. Seven keys of this were hand-copied while seven keys were all
//! the ported indicators needed. L1.18 reads fifteen more, and a hand-copied table of that
//! size drifts in exactly the way nothing catches: one wrong node-type string makes the
//! ratio disagree with the reference on one construct in one language and agree everywhere
//! else. Run `uv run generate_lang_cfg.py --check` to prove this file still matches.
//!
//! The hand-copied table had already drifted, and in the one field whose value is its
//! ORDER. The reference builds TypeScript from JavaScript's row and appends it, so
//! TypeScript is last; the copy had it fifth. The primary-language detector breaks a
//! count tie by this order, so a repository with as many .ts files as .cs files detected
//! as TypeScript here and C# in the reference, and every indicator below that followed
//! the wrong grammar.

'''


def render(cfg: dict[str, dict[str, object]]) -> str:
    keys = [k for k in NOTES if any(k in row for row in cfg.values())]
    shapes = {key: shape_of(cfg, key) for key in keys}
    lines = [HEADER, "/// The configuration one language declares.\n"]
    lines.append("pub struct LangCfg {\n")
    lines.append("    /// The LANG_CFG key, which is also the name the CLI accepts.\n")
    lines.append("    pub key: &'static str,\n")
    for key in keys:
        note = NOTES[key]
        for line in note.split("\n"):
            lines.append(f"    /// {line}\n".rstrip() + "\n" if line else "    ///\n")
        rust_type = "&'static str" if shapes[key] == "str" else "&'static [&'static str]"
        lines.append(f"    pub {key}: {rust_type},\n")
    lines.append("}\n\n")

    lines.append("""/// Every language, in the reference's own declaration order.
///
/// The order is load-bearing: the primary-language detector breaks a count tie by it,
/// exactly as the reference's counter breaks a tie by insertion order.
pub const LANGS: &[LangCfg] = &[
""")
    for lang, row in cfg.items():
        lines.append("    LangCfg {\n")
        lines.append(f"        key: {rust_str(lang)},\n")
        for key in keys:
            value = row.get(key)
            if shapes[key] == "str":
                rendered = rust_str(value if isinstance(value, str) else "")
            else:
                rendered = rust_strs(list(value) if isinstance(value, list) else [])
            lines.append(f"        {key}: {rendered},\n")
        lines.append("    },\n")
    lines.append("];\n\n")

    lines.append("""/// One language's configuration, or nothing for a key no row declares.
///
/// Refused rather than defaulted, for the reason the sibling table gives: a language with no
/// row recognises no construct, and an empty configuration would report a repository the
/// reader never understood as one holding nothing.
pub fn cfg(key: &str) -> Option<&'static LangCfg> {
    LANGS.iter().find(|row| row.key == key)
}
""")
    return "".join(lines)


def main(argv: list[str]) -> int:
    generated = render(reference_cfg())
    if "--check" in argv:
        if not TARGET.exists():
            print(f"{TARGET} does not exist; run without --check")
            return 1
        if TARGET.read_text() != generated:
            print(f"{TARGET} is stale; run `uv run generate_lang_cfg.py`")
            return 1
        print(f"{TARGET} matches the reference")
        return 0
    TARGET.write_text(generated)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
