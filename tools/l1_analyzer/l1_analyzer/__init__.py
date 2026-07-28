"""slop-audit-l1: Python implementation of Slop Audit Layer 1 indicators runnable against any language."""

from .indicators import (
    compute_git_indicators,
    compute_config_indicators,
    compute_source_indicators,
    detect_primary_language,
    analyze_mutable_state,
)

__all__ = [
    "compute_git_indicators",
    "compute_config_indicators",
    "compute_source_indicators",
    "detect_primary_language",
    "analyze_mutable_state",
]
