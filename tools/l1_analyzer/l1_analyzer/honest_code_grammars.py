"""The grammars the clause reader parses an embedded block with.

Three callers now: the clause that reads a script element, the reader that finds source of
another language held whole inside a string, and the assessment that runs one over the
other. A copy in each is the two-owners defect this package keeps finding elsewhere, so the
table sits where none of them owns it.
"""

from __future__ import annotations

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_rust
from tree_sitter import Language

_MARKUP = "html"
_STYLESHEET = "css"


def _grammars() -> dict[str, Language]:
    """The grammars this reader can accept a block with, built once at import.

    Not every language the tool knows. A grammar is here when accepting a whole string with
    it says something: markup and a stylesheet are what a page embeds, and the three
    languages beside them are what a string in this package's own corpus turned out to hold.
    """
    import tree_sitter_css
    import tree_sitter_html

    return {
        "javascript": Language(tree_sitter_javascript.language()),
        "python": Language(tree_sitter_python.language()),
        "rust": Language(tree_sitter_rust.language()),
        _MARKUP: Language(tree_sitter_html.language()),
        _STYLESHEET: Language(tree_sitter_css.language()),
    }


GRAMMARS = _grammars()
