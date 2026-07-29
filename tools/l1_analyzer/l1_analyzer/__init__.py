"""slop-audit-l1: Python implementation of Slop Audit Layer 1 indicators runnable against any language."""

from .indicators import (
    analyze_mutable_state,
    compute_config_indicators,
    compute_git_indicators,
    compute_source_indicators,
    detect_primary_language,
)

__all__ = [
    "analyze_mutable_state",
    "compute_config_indicators",
    "compute_git_indicators",
    "compute_source_indicators",
    "detect_primary_language",
]
