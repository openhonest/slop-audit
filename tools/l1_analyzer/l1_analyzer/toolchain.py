"""What ran the measurement, read from the tool's own version banner.

Every measured result says which runtime produced it, because a coverage number from one
compiler is not the same evidence as the same number from another. Getting that name is
three lines, and those three lines existed in seven language readers: c, csharp, go, java,
javascript, ruby and rust.

What differed was the command, the sentence for an unknown one, and which stream the tool
prints to. Java prints its version to standard error and the other six to standard output.

The refusal is what makes this worth one copy rather than seven. A probe that failed must
not report a name: the name goes into the details line beside the number, and a reader uses
it to decide whether to believe the reading. Seven copies of that rule is seven chances to
put an empty string where the runtime should be.

Nothing here starts a process. The caller runs the probe, because the caller is the one that
knows what to run and where, and this reads what came back.
"""

from __future__ import annotations


def named(printed: str, returncode: int, *, unknown: str) -> str:
    """The toolchain the probe named, or the caller's sentence for an unknown one.

    The first line, because a version banner runs to several and only the first names the
    toolchain. Exit zero with nothing printed is a command that ran and said nothing, and it
    is named unknown too: a blank where a reader looks for the runtime is worse than a
    sentence saying it could not be read.

    The caller hands over the text rather than naming a stream. Java prints its version to
    standard error and the other six to standard output, and my first version took the
    choice as a two-value type and then compared against one of the two values inside. The
    clause check refused it on the commit that introduced it: the declaration already
    carried the bound and the comparison wrote it out again, so the two could drift and only
    one was enforced. Which stream a tool prints to is the caller's fact anyway."""
    if returncode != 0:
        return unknown
    first = next((line.strip() for line in (printed or "").splitlines() if line.strip()), "")
    return first or unknown
