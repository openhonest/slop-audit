"""Every indicator's reading, by the code the indicator publishes.

One declaration, shared. The report held `dict[str, object]` and the card held
`dict[str, "L1Result | object"]`, and a union with `object` is `object`, so the second
looked precise and said the same nothing as the first. Two owners of one shape, neither
carrying a field, and thirty-five reads across the two files were indexing an `object` as
far as anything could tell.

The keys were known the whole time: twenty-one indicator codes, plus six rows a caller adds
when it asks for them. Every one is produced by a function that already declares what it
returns, so nothing here is a new claim. It is the claims those functions make, written
where the readers look.

`total=False` because a panel is what a run produced. An indicator that was not asked for,
or refused before it ran, has no row, and a reader that treats a missing row as a zero is
the failure this instrument reports elsewhere.

The functional form is the only one that spells these keys. `L1.1` is not an identifier.
"""

from __future__ import annotations

from typing import TypedDict

from l1_analyzer.absolute_paths import Scan as AbsolutePathScan
from l1_analyzer.coverage_prove import Sweep
from l1_analyzer.dead_code import DeadCodeRow
from l1_analyzer.honest_code import ConformityRow
from l1_analyzer.interleaving_robustness import InterleavingRobustnessResult
from l1_analyzer.path_cover import PathCover
from l1_analyzer.pytest_trace import L1Result
from l1_analyzer.race_harness import RaceResult
from l1_analyzer.secret_scan import SecretScanRow
from l1_analyzer.state_reading import StateReading
from l1_analyzer.thread_surface import SurfaceResult

Panel = TypedDict("Panel", {
    "L1.1": L1Result, "L1.2": L1Result, "L1.3": L1Result, "L1.4": L1Result,
    "L1.5": L1Result, "L1.6": L1Result, "L1.7": L1Result, "L1.8": L1Result,
    "L1.9": L1Result, "L1.10": L1Result, "L1.11": L1Result,
    "L1.13": L1Result, "L1.15": L1Result, "L1.16": L1Result,
    "L1.17": L1Result, "L1.18": L1Result, "L1.19": L1Result, "L1.20": L1Result,
    # L1.18b is the state-bounds refinement and reads nothing like a band and a value: it
    # carries the findings, the counts and the census that make the number readable.
    "L1.18b": StateReading,
    # L1.12 and L1.14 carry findings beside the band, the same shape L1.21's row carries.
    # Each was declared as a mapping of anything to anything while writing ten and seven
    # fields, and the findings are what makes the number readable.
    "L1.12": DeadCodeRow,
    "L1.14": SecretScanRow,
    # Three more the source builder writes beside the indicator codes, gated behind the
    # state-bounds refinement. They were absent from this declaration while the builder
    # wrote them on every default run, which is the drift a declaration exists to catch.
    "path_cover": PathCover,
    "thread_surface": SurfaceResult,
    "absolute_paths": AbsolutePathScan,
    # L1.21 is opt-in. It publishes a band and a value like any other indicator and six
    # readings more, which are what say what the share left out.
    "honest_code": ConformityRow,
    "coverage_proofs": Sweep,
    "race": RaceResult,
    "interleaving_robustness": InterleavingRobustnessResult,
    # What `--prove` retained, one entry per proof, built by the CLI rather than by an
    # indicator. Declared as the list it is; the entries' own shape is the prover's.
    "proofs": list[dict[str, object]],
    # The language the audit ran as, which the card prints and several readers branch on.
    "lang": str,
}, total=False)
