"""Within-repository against between-repository variance, for a windowed L1 indicator.

Written for the threshold-calibration question: does a single measurement characterise a
repository? If within-repository variation over time is comparable to between-repository
variation, then one value per repository is substantially a sample of WHEN it was taken,
and a study that clusters one value per repository is clustering sampling dates.

Three estimators and two interval methods, because at small k they disagree and the
disagreement is the result rather than a nuisance:

  moment ICC    between-variance over total, from group means and pooled within-SD
  ANOVA ICC     the one-way random-effects form, which subtracts within-group mean square
                and is bounded below at zero
  cluster bootstrap   resamples repositories with replacement
  exact F interval    from the one-way ANOVA, no resampling

The cluster bootstrap is BIASED DOWNWARD at small k and must not be used for a threshold
claim. Drawing k repositories with replacement yields about 0.63k distinct ones, and a
duplicated repository contributes a second group with the same mean, which shrinks the
observed spread of group means. Between-cluster variance is underestimated in most
resamples, and since ICC is between over total, the whole distribution shifts down. The
diagnostic is included: the observed point estimate's percentile within its own bootstrap
distribution. Near 50 is fine. Consistently above it is the signature of that bias, and on
the data this was written for it ran 56 to 69.

    uv run --no-project --with scipy python decompose.py panel.tsv

Panel format, tab-separated, one row per repository-window:

    repository <TAB> window <TAB> value [<TAB> value ...]

Build one with build_panel.sh, which is the measurement half and is kept separate so the
statistics can be rerun without remeasuring.
"""

from __future__ import annotations

import collections
import math
import random
import statistics as st
import sys

# The interval both estimators report, named once. It was two facts in two spellings:
# `alpha=0.05` as a default on the exact interval, and 0.025/0.975 written into the
# bootstrap's cut points. Nothing checked they agreed, and a default meant a caller who
# omitted alpha could not be told from one who chose it.
ALPHA = 0.05

BOOTSTRAP_DRAWS = 4000
SEED = 20260814


def moment_icc(groups: list[list[float]]) -> float:
    """Between-variance over total, from group means and the pooled within-group SD."""
    withins = [st.pstdev(v) for v in groups if len(v) > 1]
    means = [st.mean(v) for v in groups]
    within = st.mean(withins)
    between = st.pstdev(means)
    total = between ** 2 + within ** 2
    return between ** 2 / total if total else float("nan")


def anova_icc(groups: list[list[float]]) -> tuple[float, float, float]:
    """The one-way random-effects ICC and its mean squares.

    Differs from the moment form by subtracting the within-group mean square, so it is
    bounded below at zero and can report 0.00 where the moment form reports 0.27. At small
    k the CHOICE OF ESTIMATOR moves the answer as much as the choice of interval does."""
    k = len(groups)
    n = min(len(g) for g in groups)
    total_n = sum(len(g) for g in groups)
    grand = st.mean([x for g in groups for x in g])
    msb = sum(len(g) * (st.mean(g) - grand) ** 2 for g in groups) / (k - 1)
    msw = sum((x - st.mean(g)) ** 2 for g in groups for x in g) / (total_n - k)
    return (msb - msw) / (msb + (n - 1) * msw), msb, msw


def exact_interval(groups: list[list[float]], alpha: float) -> tuple[float, float]:
    """The F-based interval for the one-way ANOVA ICC. No cluster resampling, so it does
    not carry the duplicate-cluster bias. It assumes normality within groups, which is why
    the rank transform matters and why this should be run on more than raw values."""
    from scipy.stats import f as fdist
    k = len(groups)
    n = min(len(g) for g in groups)
    total_n = sum(len(g) for g in groups)
    _, msb, msw = anova_icc(groups)
    ratio = msb / msw
    lower_f = ratio / fdist.ppf(1 - alpha / 2, k - 1, total_n - k)
    upper_f = ratio * fdist.ppf(1 - alpha / 2, total_n - k, k - 1)
    return (lower_f - 1) / (lower_f + n - 1), (upper_f - 1) / (upper_f + n - 1)


def bootstrap(groups: list[list[float]], draws: int, alpha: float) -> tuple[float, float, float]:
    """Percentile interval from a cluster bootstrap, plus the bias diagnostic.

    Returns (low, high, percentile_of_point_estimate). Read the percentile first: if it is
    well above 50 the interval is shifted low and must not carry a threshold claim."""
    random.seed(SEED)
    point = moment_icc(groups)
    draws_out = []
    for _ in range(draws):
        picked = [random.choice(groups) for _ in groups]
        value = moment_icc(picked)
        if not math.isnan(value):
            draws_out.append(value)
    draws_out.sort()
    percentile = 100 * sum(1 for d in draws_out if d < point) / len(draws_out)
    return (draws_out[int(alpha / 2 * len(draws_out))],
            draws_out[int((1 - alpha / 2) * len(draws_out))], percentile)


TRANSFORMS = {
    "raw": lambda values: list(values),
    # +1 because an indicator may legitimately read zero in a window.
    "log10": lambda values: [math.log10(v + 1) for v in values],
    "rank": lambda values: [sorted(values).index(v) for v in values],
}


def decompose(panel: dict[str, list[float]]) -> None:
    """Print every estimator and both intervals for one indicator's panel."""
    flat = [v for group in panel.values() for v in group]
    print(f"{'transform':<8}{'moment':>8}{'anova':>8}   {'bootstrap 95%':>20}  {'pctile':>7}   {'exact F 95%':>18}")
    for label, fn in TRANSFORMS.items():
        mapped = fn(flat)
        lookup = dict(zip(flat, mapped))
        groups = [[lookup[v] for v in group] for group in panel.values()]
        point = moment_icc(groups)
        a_icc, _, _ = anova_icc(groups)
        lo, hi, pct = bootstrap(groups, BOOTSTRAP_DRAWS, ALPHA)
        try:
            exact_lo, exact_hi = exact_interval(groups, ALPHA)
            exact = f"[{exact_lo:5.2f}, {exact_hi:5.2f}]"
        except ImportError:
            exact = "scipy not installed"
        print(f"{label:<8}{point:8.2f}{a_icc:8.2f}   [{lo:5.2f}, {hi:5.2f}]{'':6}{pct:6.0f}%   {exact}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    columns: dict[int, dict[str, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    header: list[str] = []
    for line in open(sys.argv[1]):
        parts = line.rstrip("\n").split("\t")
        if not parts or not parts[0] or parts[0].startswith("#"):
            continue
        if parts[0] == "repository":
            header = parts[2:]
            continue
        for i, value in enumerate(parts[2:]):
            try:
                columns[i][parts[0]].append(float(value))
            except ValueError:
                continue
    for i, panel in sorted(columns.items()):
        name = header[i] if i < len(header) else f"column {i}"
        print(f"\n=== {name}   {len(panel)} repositories, {sum(len(v) for v in panel.values())} observations")
        decompose(dict(panel))
    return 0


if __name__ == "__main__":
    sys.exit(main())
