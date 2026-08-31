"""The grammars this reader parses with, and the extension that picks one.

Local to the dead-code reading and NOT `indicators.LANG_CFG`, because `.tsx` needs the JSX
grammar: parsing a React component with the plain TypeScript grammar loses every element and
the names inside it.

Its own module since 2026-08-31, when the reader split into the corpus half and the
classifying half. Both parse, so the table belongs to neither and a copy in each would be
the two-owners defect this package keeps finding elsewhere.
"""

from __future__ import annotations

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript
from tree_sitter import Language, Parser

_GRAMMARS = {
    "python": lambda: tree_sitter_python.language(),
    "rust": lambda: tree_sitter_rust.language(),
    "c": lambda: tree_sitter_c.language(),
    "java": lambda: tree_sitter_java.language(),
    "typescript": lambda: tree_sitter_typescript.language_typescript(),
    "tsx": lambda: tree_sitter_typescript.language_tsx(),
    "csharp": lambda: tree_sitter_c_sharp.language(),
    "javascript": lambda: tree_sitter_javascript.language(),
    "ruby": lambda: tree_sitter_ruby.language(),
    "go": lambda: tree_sitter_go.language(),
}

# Extension -> (grammar key, language key). The language key is the collector to run;
# the grammar key is the parser to run it on, and the two differ only for .tsx.
_EXT_LANG: dict[str, tuple[str, str]] = {
    ".py": ("python", "python"),
    ".rs": ("rust", "rust"),
    ".c": ("c", "c"), ".h": ("c", "c"),
    ".java": ("java", "java"),
    ".ts": ("typescript", "typescript"), ".tsx": ("tsx", "typescript"),
    ".cs": ("csharp", "csharp"),
    ".js": ("javascript", "javascript"), ".jsx": ("javascript", "javascript"),
    ".mjs": ("javascript", "javascript"), ".cjs": ("javascript", "javascript"),
    ".rb": ("ruby", "ruby"),
    ".go": ("go", "go"),
}

def parser(grammar: str) -> Parser:
    """One parser for a grammar, built on the spot.

    It used to be cached, and the cache is gone because it was measured: a build costs about
    a hundredth of a millisecond and it is called once per file, so the cache saved a few
    milliseconds across an entire audit while carrying an invalidation risk for them.

    The cache was never there for speed. It replaced a module-level dict a function wrote
    into, which this package's own L1.18 counts as external mutable state. A plain call has
    neither the global nor the cache."""
    return Parser(Language(_GRAMMARS[grammar]()))
