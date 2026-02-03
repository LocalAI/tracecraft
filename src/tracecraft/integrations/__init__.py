"""
Ecosystem integrations for TraceCraft.

Provides bridges to evaluation frameworks (DeepEval, RAGAS, MLflow)
and prompt management tools (Langfuse).
"""

from __future__ import annotations

# Re-export key functions for convenient access
# Note: These imports are lazy to avoid requiring optional dependencies
# Users should import from submodules if they need specific functionality

__all__ = [
    # Submodules
    "deepeval",
    "ragas",
    "mlflow_eval",
    "langfuse_prompts",
]


def __getattr__(name: str):
    """Lazy import support for integration modules."""
    if name == "deepeval":
        from tracecraft.integrations import deepeval

        return deepeval
    elif name == "ragas":
        from tracecraft.integrations import ragas

        return ragas
    elif name == "mlflow_eval":
        from tracecraft.integrations import mlflow_eval

        return mlflow_eval
    elif name == "langfuse_prompts":
        from tracecraft.integrations import langfuse_prompts

        return langfuse_prompts
    raise AttributeError(f"module 'tracecraft.integrations' has no attribute {name!r}")
