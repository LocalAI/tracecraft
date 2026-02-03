"""
Dataset conversion utilities for TraceCraft.

Provides utilities to convert between TraceCraft traces and common dataset formats
for evaluation, fine-tuning, and analysis.
"""

from __future__ import annotations

from tracecraft.datasets.converters import (
    create_finetuning_dataset,
    create_golden_dataset,
    traces_to_csv,
    traces_to_huggingface,
    traces_to_jsonl,
)

__all__ = [
    "traces_to_csv",
    "traces_to_huggingface",
    "traces_to_jsonl",
    "create_golden_dataset",
    "create_finetuning_dataset",
]
