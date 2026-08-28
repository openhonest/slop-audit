"""Declaring where this package meets the world.

The audit's I/O-at-the-boundary rule puts input and output at the edges and pure logic in
the middle. Its checker infers the boundary from the call graph, because most projects say
nothing, and that inference cannot tell a function that is ONLY I/O from a piece of logic
that has swallowed a read.

This is how a function says which it is. It is the same declaration the analyzer package
carries, written here because a small tool should not import a large one to say one word.

IT IS NOT A SUPPRESSION, and the difference is the whole of it. A suppression silences a
rule over code that still breaks it. This is honest only after the decision has been lifted
out, so that what remains under the decorator obtains data and decides nothing. Applying it
to a function that still decides things is a suppression wearing a declaration's name, and
nothing here can tell the two apart.
"""

from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable)


def boundary(fn: F) -> F:
    """Mark a function as one of this package's edges.

    Returned unchanged. A declaration that altered behaviour would be a wrapper rather than
    a statement, and it would put a frame between a reader and the thing they came to
    read."""
    return fn
