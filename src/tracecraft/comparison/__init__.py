"""
Trace comparison module.

Compare traces using LLM-powered analysis.
"""

from tracecraft.comparison.models import (
    ComparisonPrompt,
    ComparisonRequest,
    ComparisonResult,
)
from tracecraft.comparison.prompts import PromptManager
from tracecraft.comparison.runner import ComparisonRunner

__all__ = [
    "ComparisonPrompt",
    "ComparisonRequest",
    "ComparisonResult",
    "ComparisonRunner",
    "PromptManager",
]
