"""Generate src/lang_spec.rs from the Python reference's LANG_SPEC.

Eighty-four keys across nine languages is 756 values. Transcribing them by hand is how a
port drifts: nothing would catch one wrong node-type string, and the classifier would
disagree with the reference on one construct in one language and be equal everywhere else,
which is the hardest kind of difference to find.

So the table is generated from the reference and never edited. The generator is the second
owner of nothing: the reference is the only source, and `--check` proves the committed file
still matches it, which is what a pre-commit hook runs.

    uv run generate_lang_spec.py            # write src/lang_spec.rs
    uv run generate_lang_spec.py --check    # exit 1 if the committed file is stale

The generated file carries an @generated marker, so every scope rule in this instrument
already excludes it: nobody's authored code, and every number an audit puts on it would
describe this script rather than the crate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "l1_analyzer"
TARGET = HERE / "src" / "lang_spec.rs"

# The keys the state analysis reads, measured by walking every `sp["..."]` subscript in the
# modules that take a LangSpec. Listed rather than "every key in the spec" because the spec
# carries rows for indicators this port has not reached, and a field nothing reads is a
# field nobody can check.
NEEDED = """
alias_marker alias_types arglist_types argument_wrapper_types assign_left assign_right
assign_types bare_cond_types binding_condition_types binding_sites blank_idents branch_cond
branch_types cache_reads call_args call_fn call_name call_recv call_types class_types
closed_set_rule comparison_types cond_at_index container_literal_types decorator_types
delete_stmt_types
destructuring_types discard_types dispatch_methods elif_types empty_map_types extra_bounded
extra_test_positions field_decl_types flat_call func_types gate_body_types gate_fields
immutable_ctor_rule immutable_modifiers instance_enum instance_ref_style iterate_types
key_prefix key_removal_types keyed_read literal_types local_binding lvalue_wrapper mem_attr
mem_object member_name_field member_types membership module_enum mutates_in_place mutating
opaque_region_types opaque_unary_ops out_argument_types passthrough_types presence_bind_types
presence_methods read_write_assign_ops reading_macros record_enum resting_types return_types
safe_arg_calls scope_by_receiver sink_types slice_types sub_index sub_positional sub_value
subscript_types switch_types this_idents unary_types unread_operand_types
value_preserving_methods value_wrapper_types write_in_place_ops write_methods
writing_builtins
""".split()


def boundary(fn):
    """Mark a function as one of this script's edges, and change nothing about it.

    The analyzer package declares its edges with a decorator of this name. This script sits
    beside that package rather than inside it, so it says the same thing in its own words
    rather than importing across the boundary between a Rust crate's helper and the Python
    tool it reads."""
    return fn


@boundary
def reference_spec() -> dict[str, dict[str, object]]:
    """LANG_SPEC, read out of the reference's own environment.

    Run as a subprocess rather than imported, because this script lives in the crate and
    the reference is a separate project with its own dependencies. Importing across that
    line would make the crate's tooling depend on the reference being installed here."""
    script = (
        "import json\n"
        "from l1_analyzer.lang_spec import LANG_SPEC\n"
        "def plain(v):\n"
        "    if isinstance(v, frozenset): return sorted(v)\n"
        "    if isinstance(v, tuple): return list(v)\n"
        "    if isinstance(v, dict): return {k: plain(x) for k, x in v.items()}\n"
        "    return v\n"
        "print(json.dumps({l: {k: plain(v) for k, v in row.items()} "
        "for l, row in LANG_SPEC.items()}))\n"
    )
    out = subprocess.run(
        ["uv", "run", "python", "-c", script],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    import json
    return json.loads(out)


@boundary
def reference_census_kinds() -> dict[str, list[str]]:
    """The declaration kinds the census can count, per language, in the capability table's
    own order.

    A second small table out of the same reference, for the same reason as the first: the
    census seeds its per-kind counts from this list so that a kind the language can spell
    but this repository does not appears at zero rather than going missing, and a hand-copied
    list would be a second owner of the capability matrix."""
    script = (
        "import json\n"
        "from l1_analyzer.state_census import CAPABILITY\n"
        "out = {}\n"
        "for lang, kind in CAPABILITY:\n"
        "    out.setdefault(lang, []).append(kind)\n"
        "print(json.dumps(out))\n"
    )
    out = subprocess.run(
        ["uv", "run", "python", "-c", script],
        cwd=REFERENCE, capture_output=True, text=True, check=True,
    ).stdout
    import json
    return json.loads(out)


def rust_str(value: str) -> str:
    """One Python string as a Rust string literal."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def rust_strs(values: list[str]) -> str:
    """A sequence of strings as a Rust slice literal.

    Sorted where the reference held a frozenset, because a set has no order and emitting
    iteration order would make the generated file change without the reference changing.
    Left alone where the reference held a tuple, because there the order is the rule: the
    name fields of a declaration are tried in the order they are written."""
    return "&[" + ", ".join(rust_str(v) for v in values) + "]"


def rust_map(mapping: dict, render_value) -> str:
    """A map as a Rust slice of pairs, with the value rendered by its own shape.

    Three of these, one per value shape, left one function behind once the names and the
    quoted strings were erased. The key half is identical in all three and the value half
    is the only difference, so the value half is the parameter."""
    return "&[" + ", ".join(f"({rust_str(k)}, {render_value(v)})"
                            for k, v in mapping.items()) + "]"


def rust_map_pair(mapping: dict[str, list]) -> str:
    """A map to a two-element tuple, where the second half may be absent.

    `local_binding` is the one that carries an absent half: a language whose local binding
    has no value slot writes None there, and reading that as the empty string would make it
    a field named "" rather than a field that is not there."""
    rows = []
    for key, pair in mapping.items():
        first = rust_str(pair[0])
        second = "None" if len(pair) < 2 or pair[1] is None else f"Some({rust_str(pair[1])})"
        rows.append(f"({rust_str(key)}, {first}, {second})")
    return "&[" + ", ".join(rows) + "]"


def classify(spec: dict[str, dict[str, object]], key: str) -> str:
    """Which shape this key takes, measured over every language rather than read off one.

    A key can be a string in eight rows and absent in the ninth, and picking the type from
    the first row would make that ninth a lie. A shape nothing here covers is a refusal,
    never a guess: a new value shape in the reference must stop the generator rather than
    be rendered as whatever the last branch happened to produce."""
    values = [spec[lang].get(key) for lang in sorted(spec)]
    kinds = {type(v).__name__ for v in values}
    if kinds <= {"bool"}:
        return "bool"
    if kinds <= {"str", "NoneType"}:
        return "opt_str" if "NoneType" in kinds else "str"
    if kinds <= {"list"}:
        inner = {type(x).__name__ for v in values for x in (v or [])}
        if inner <= {"str"}:
            return "strs"
        raise SystemExit(f"{key}: a sequence of {sorted(inner)}, which has no shape here")
    if kinds <= {"dict"}:
        pairs = [(k, v) for lang in spec for k, v in (spec[lang].get(key) or {}).items()]
        value_kinds = {type(v).__name__ for _, v in pairs}
        if value_kinds <= {"str"}:
            return "map_str"
        if value_kinds <= {"int"}:
            return "map_int"
        if value_kinds <= {"list"}:
            lengths = {len(v) for _, v in pairs}
            return "map_pair" if lengths <= {2} else "map_slice"
        if not pairs:
            return "map_str"
        raise SystemExit(f"{key}: a map to {sorted(value_kinds)}, which has no shape here")
    raise SystemExit(f"{key}: {sorted(kinds)}, which has no shape here")


RENDER = {
    "bool": lambda v: "true" if v else "false",
    "str": lambda v: rust_str(v or ""),
    "opt_str": lambda v: "None" if v is None else f"Some({rust_str(v)})",
    "strs": lambda v: rust_strs(v or []),
    "map_str": lambda v: rust_map(v or {}, rust_str),
    "map_int": lambda v: rust_map(v or {}, str),
    "map_pair": lambda v: rust_map_pair(v or {}),
    "map_slice": lambda v: rust_map(v or {}, rust_strs),
}

FIELD_TYPE = {
    "bool": "bool",
    "str": "&'static str",
    "opt_str": "Option<&'static str>",
    "strs": "&'static [&'static str]",
    "map_str": "&'static [(&'static str, &'static str)]",
    "map_int": "&'static [(&'static str, i64)]",
    "map_pair": "&'static [(&'static str, &'static str, Option<&'static str>)]",
    "map_slice": "&'static [(&'static str, &'static [&'static str])]",
}

HEADER = '''//! @generated by generate_lang_spec.py from l1_analyzer.lang_spec. Do not edit.
//!
//! Per-language vocabulary for the state analysis: the node types and field names each
//! grammar spells a construct with. Eighty-four keys across nine languages.
//!
//! GENERATED, NOT TRANSCRIBED. Seven hundred and fifty-six values is past what anybody
//! checks by eye, and one wrong node-type string would make the classifier disagree with
//! the reference on one construct in one language and agree everywhere else, which is the
//! hardest kind of difference to find. The reference is the only source; run
//! `uv run generate_lang_spec.py --check` to prove this file still matches it.
//!
//! A map is a slice of pairs rather than a hash map: these are read a handful of times per
//! file over at most a few dozen entries, and a slice is what a single-file binary should
//! carry.

'''


def render(spec: dict[str, dict[str, object]], census_kinds: dict[str, list[str]]) -> str:
    shapes = {key: classify(spec, key) for key in NEEDED}
    lines = [HEADER, "/// The vocabulary one language spells its constructs with.\n"]
    lines.append("pub struct LangSpec {\n")
    lines.append("    /// The LANG_SPEC key, which is also the name the CLI accepts.\n")
    lines.append("    pub key: &'static str,\n")
    for key in NEEDED:
        lines.append(f"    pub {key}: {FIELD_TYPE[shapes[key]]},\n")
    lines.append("}\n\n")

    lines.append("/// Every language, in the reference's own declaration order.\n")
    lines.append("pub const LANG_SPECS: &[LangSpec] = &[\n")
    for lang in spec:
        if lang not in spec:
            continue
        lines.append("    LangSpec {\n")
        lines.append(f"        key: {rust_str(lang)},\n")
        for key in NEEDED:
            value = RENDER[shapes[key]](spec[lang].get(key))
            lines.append(f"        {key}: {value},\n")
        lines.append("    },\n")
    lines.append("];\n\n")

    lines.append("""/// One language's vocabulary, or nothing for a key no row declares.
///
/// Refused rather than defaulted. A language with no row must be a refusal at the call
/// site, because an empty vocabulary recognises no construct and would report a repository
/// the reader never understood as one holding no state.
pub fn spec_for(key: &str) -> Option<&'static LangSpec> {
    LANG_SPECS.iter().find(|row| row.key == key)
}

/// A map field's value for one node type, or nothing when the table has no row for it.
///
/// Every map in this table is consulted this way and never iterated for a default, which
/// is the reference's own discipline: a node type nobody assigned a rule must come back
/// absent, so the caller decides what that means rather than inheriting somebody's zero.
pub fn lookup<'a, V: Copy>(table: &'a [(&'static str, V)], node_type: &str) -> Option<V> {
    table.iter().find(|(name, _)| *name == node_type).map(|(_, value)| *value)
}
""")

    lines.append("""
/// The declaration kinds the census can count for one language, in the capability table's
/// own order.
///
/// The census seeds its per-kind counts from this list, so a kind a language can spell but
/// this repository does not appears at zero rather than going missing from the denominator.
pub const CENSUS_KINDS: &[(&str, &[&str])] = &[
""")
    for lang, kinds in census_kinds.items():
        lines.append(f"    ({rust_str(lang)}, {rust_strs(kinds)}),\n")
    lines.append("""];

/// The kinds one language can spell, or nothing for a language the census has no row for.
///
/// Refused rather than emptied, for the reason `spec_for` gives: an empty kind list is a
/// full denominator over a repository nobody counted.
pub fn census_kinds_for(lang: &str) -> Option<&'static [&'static str]> {
    CENSUS_KINDS.iter().find(|(name, _)| *name == lang).map(|(_, kinds)| *kinds)
}
""")
    return "".join(lines)


def main(argv: list[str]) -> int:
    spec = reference_spec()
    generated = render(spec, reference_census_kinds())
    if "--check" in argv:
        if not TARGET.exists():
            print(f"{TARGET} does not exist; run without --check")
            return 1
        if TARGET.read_text() != generated:
            print(f"{TARGET} is stale; run `uv run generate_lang_spec.py`")
            return 1
        print(f"{TARGET} matches the reference")
        return 0
    TARGET.write_text(generated)
    keys = len(NEEDED)
    print(f"wrote {TARGET}: {keys} keys over {len(spec)} languages, {keys * len(spec)} values")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
