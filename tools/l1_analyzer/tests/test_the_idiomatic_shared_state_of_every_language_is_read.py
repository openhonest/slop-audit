"""The way each language actually holds shared state, read in every language.

Four readings came back as a clean pass in one day where the honest answer was silence, and
two of the four were the same mistake in two languages: a keyword was allowed to answer a
question about the thing it was attached to.

    export const CACHE = {};                             declined on `const`
    pub static COUNTER: AtomicUsize = AtomicUsize::new(0);   declined for want of `mut`

Both are the shape people write. `const` is the default in JavaScript and TypeScript, and
`static mut` requires unsafe at every access so modern Rust does not use it. Each decline
took nearly all the real shared state out of every reading of that language, and took it out
as a pass rather than as silence.

Finding those one at a time was luck. This file asks the same question of all nine languages
at once: here is how that language's programmers actually hold state something else can
change, and the classifier has to see it. The rows below were run on 2026-09-06 and the seven
other languages were already right, including the two closest analogues, Java's `static
final` and C#'s `static readonly`, which decline nothing.

Kept as one table so the next reader added here is asked the same question. A rule that
declines a keyword is easy to write and reads as thoroughness; what it costs is invisible
until somebody measures a corpus and wonders why one language reports a tenth of the others.
"""

from __future__ import annotations

import subprocess

import pytest

# One row per language: the file it goes in, and the way that language's programmers hold
# state some other function can change. Written the way the language's own documentation
# would, not the way that happens to be easiest to parse.
_IDIOM = {
    "python": ("app.py", "CACHE = {}\n\n\ndef put(k, v):\n    CACHE[k] = v\n"),
    "javascript": ("m.js", "export const CACHE = {};\n\nexport function put(k, v) { CACHE[k] = v; }\n"),
    "typescript": ("m.ts", ("export const CACHE: Record<string, string> = {};\n\n"
                            "export function put(k: string, v: string) { CACHE[k] = v; }\n")),
    "rust": ("lib.rs", ("use std::sync::atomic::{AtomicUsize, Ordering};\n\n"
                        "pub static COUNTER: AtomicUsize = AtomicUsize::new(0);\n\n"
                        "pub fn bump() -> usize { COUNTER.fetch_add(1, Ordering::SeqCst) }\n")),
    "java": ("A.java", ("import java.util.*;\npublic class A {\n"
                        "  private static final Map<String,String> CACHE = new HashMap<>();\n"
                        "  public static void put(String k, String v) { CACHE.put(k, v); }\n}\n")),
    "csharp": ("A.cs", ("using System.Collections.Generic;\npublic class A {\n"
                        "  private static readonly Dictionary<string,string> Cache = new();\n"
                        "  public static void Put(string k, string v) { Cache[k] = v; }\n}\n")),
    "go": ("a.go", ("package a\n\nvar cache = map[string]string{}\n\n"
                    "func Put(k, v string) { cache[k] = v }\n")),
    "c": ("a.c", "static char cache[256];\n\nvoid put(int i, char c) { cache[i] = c; }\n"),
    "ruby": ("a.rb", ("class A\n  def initialize\n    @cache = {}\n  end\n\n"
                      "  def put(k, v)\n    @cache[k] = v\n  end\nend\n")),
}


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _classify(tmp_path, lang: str) -> dict:
    from l1_analyzer import state_bounds

    name, source = _IDIOM[lang]
    (tmp_path / name).write_text(source)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return state_bounds.classify(tmp_path, lang)


@pytest.mark.parametrize("lang", sorted(_IDIOM))
def test_the_shared_state_a_language_actually_writes_is_read_as_state(tmp_path, lang):
    reading = _classify(tmp_path, lang)
    assert sum(reading["counts"].values()) == 1, (
        f"{lang} holds shared state this way and the classifier returned no verdict on it. "
        f"census: {reading['census']}")


@pytest.mark.parametrize("lang", sorted(_IDIOM))
def test_the_two_meters_agree_about_what_was_there(tmp_path, lang):
    """The census counts declarations and the classifier judges them, and the pair is what
    makes a blindness measurable rather than invisible. Every one of these was found by the
    census reporting a declaration the classifier had visited and said nothing about."""
    census = _classify(tmp_path, lang)["census"]
    assert census["declared"] == census["visited"] == 1, census


def test_every_language_the_analyzer_supports_has_a_row_here():
    """A language with no row is a language nobody asked this question of, which is how the
    JavaScript and Rust declines survived as long as they did."""
    from l1_analyzer.lang_cfg import LANG_CFG

    assert sorted(_IDIOM) == sorted(LANG_CFG)
