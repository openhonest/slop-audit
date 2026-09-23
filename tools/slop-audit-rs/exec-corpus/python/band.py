"""Two branches, one of them exercised, so coverage is a fraction rather than nought or one."""


def band(n):
    if n < 0:
        return "neg"
    return "pos"


def halve_or_climb(n):
    """Never called by a test, so the run has a branch it did not reach."""
    if n % 2 == 0:
        return n // 2
    return n * 3 + 1
