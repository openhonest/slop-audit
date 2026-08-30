"""Fail a commit that adds a type error, and say how many there are.

Nothing type-checked this repository until 2026-08-29, and the checker was not installed. An
adopter reported the same about their own tree: it found 35 errors on the first run, four
written that same day, including a record missing two keys that three routes index by name.
Every annotation they had added that day was a comment that looked like a guarantee.

Ours was worse, because we had spent two days writing shapes down. The first run found 276,
among them two records missing a key the code both writes and reads, and eight rows of one
table holding a mutable set where the row declared a frozen one.

A ratchet rather than a bright line, for the same reason as the type-escape one beside it:
this package is not at zero, so a bright line would block every commit. A NEW error fails.
Lower the number as they are fixed; raising it is a deliberate, reviewable edit here.

Slack is a defect too. A baseline above the real count lets the next regression in for free,
so this refuses in that direction as well and says which way it went.
"""

import re
import subprocess
import sys
from pathlib import Path

# What the checker reports today. Lower it as errors are fixed.
#
# It went 283 to 284 on a round that fixed five real defects, and that is not a regression.
# Writing down a shape lets the checker see disagreements it could not see before: a mapping
# of anything to anything has no keys to be wrong about, so every read of it was an
# assumption nothing could check. Naming the two records the coverage sweeps pass around
# turned a dozen silent assumptions into visible mismatches, and two of those were real.
#
# The same thing happened to the type-escape count the day it learned to see a bare generic:
# 0 became 157 without a line of behaviour changing. A number that rises when a measurement
# gets sharper is the measurement working.
CEILING = 241

_COUNT = re.compile(r"Found (\d+) error")


def counted(output: str) -> int | None:
    """How many errors the checker reported, or None if it did not say.

    None rather than zero, because a run that produced no summary is a run that did not
    finish, and reading that as a clean tree is the failure this repository exists to name."""
    found = _COUNT.search(output)
    if found:
        return int(found.group(1))
    return 0 if "no issues found" in output else None


def main() -> int:
    package = Path(__file__).resolve().parent.parent / "tools" / "l1_analyzer"
    run = subprocess.run(
        ["uv", "run", "mypy", "l1_analyzer", "--ignore-missing-imports"],
        cwd=package, capture_output=True, text=True, check=False)
    output = run.stdout + run.stderr
    errors = counted(output)
    if errors is None:
        print("the type checker did not report a count, so nothing was measured:")
        print("\n".join(output.strip().split("\n")[-5:]))
        return 1
    if errors > CEILING:
        print(f"the type checker found {errors} errors, over the ratchet of {CEILING}.")
        print("Fix it, or raise the baseline in scripts/type_check_ratchet.py as a "
              "deliberate, reviewable change.")
        print("\n".join(output.strip().split("\n")[-6:]))
        return 1
    if errors < CEILING:
        print(f"the type checker found {errors} errors and the ratchet allows {CEILING}. "
              f"Lower it to {errors}: a baseline looser than reality lets the next one in "
              "for free.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
