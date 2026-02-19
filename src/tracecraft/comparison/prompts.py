"""
Prompt management for trace comparison.

Handles builtin and user-defined comparison prompts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

from tracecraft.comparison.models import ComparisonPrompt

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages comparison prompts - builtin and user-defined.

    Prompts are stored in ~/.config/tracecraft/comparison_prompts.json.
    Builtin prompts are always available and cannot be deleted.

    Example:
        manager = PromptManager()

        # List all prompts
        prompts = manager.list_prompts()

        # Get a specific prompt
        prompt = manager.get_prompt("diff-summary")

        # Add a custom prompt
        manager.add_prompt(
            name="My Prompt",
            template="Compare {trace_a} with {trace_b}",
            description="My custom comparison"
        )
    """

    CONFIG_DIR: ClassVar[Path] = Path.home() / ".config" / "tracecraft"
    PROMPTS_FILE: ClassVar[Path] = CONFIG_DIR / "comparison_prompts.json"

    BUILTIN_PROMPTS: ClassVar[list[ComparisonPrompt]] = [
        ComparisonPrompt(
            id="diff-summary",
            name="Difference Summary",
            template=(
                "Compare these two agent traces and summarize the key differences:\n\n"
                "## Trace A:\n{trace_a}\n\n"
                "## Trace B:\n{trace_b}\n\n"
                "Provide a concise summary of:\n"
                "1. Key differences in execution flow\n"
                "2. Differences in outputs or results\n"
                "3. Notable variations in tool usage or LLM calls"
            ),
            description="Summarize key differences between traces",
            is_builtin=True,
        ),
        ComparisonPrompt(
            id="performance-analysis",
            name="Performance Analysis",
            template=(
                "Analyze the performance characteristics of these two traces:\n\n"
                "## Trace A:\n{trace_a}\n\n"
                "## Trace B:\n{trace_b}\n\n"
                "Focus on:\n"
                "- Execution time comparison\n"
                "- Token usage and efficiency\n"
                "- Cost comparison\n"
                "- Number of steps/operations\n"
                "- Potential optimizations"
            ),
            description="Compare performance metrics and efficiency",
            is_builtin=True,
        ),
        ComparisonPrompt(
            id="error-analysis",
            name="Error Analysis",
            template=(
                "Compare error handling between these traces:\n\n"
                "## Trace A:\n{trace_a}\n\n"
                "## Trace B:\n{trace_b}\n\n"
                "Analyze:\n"
                "- Errors encountered in each trace\n"
                "- Error recovery strategies\n"
                "- Differences in failure handling\n"
                "- Recommendations for improving error handling"
            ),
            description="Analyze error patterns and handling",
            is_builtin=True,
        ),
        ComparisonPrompt(
            id="tool-usage",
            name="Tool Usage Comparison",
            template=(
                "Compare tool usage patterns between these traces:\n\n"
                "## Trace A:\n{trace_a}\n\n"
                "## Trace B:\n{trace_b}\n\n"
                "Analyze:\n"
                "- Which tools were used in each trace\n"
                "- Order and frequency of tool calls\n"
                "- Tool input/output differences\n"
                "- Effectiveness of tool usage"
            ),
            description="Compare tool usage patterns",
            is_builtin=True,
        ),
    ]

    def __init__(self) -> None:
        """Initialize prompt manager."""
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def list_prompts(self) -> list[ComparisonPrompt]:
        """List all available prompts (builtin + user-defined).

        Returns:
            List of all comparison prompts, builtins first.
        """
        return list(self.BUILTIN_PROMPTS) + self._load_user_prompts()

    def get_prompt(self, prompt_id: str) -> ComparisonPrompt | None:
        """Get a prompt by ID.

        Args:
            prompt_id: The prompt identifier.

        Returns:
            The prompt if found, None otherwise.
        """
        # Check builtins first
        for prompt in self.BUILTIN_PROMPTS:
            if prompt.id == prompt_id:
                return prompt

        # Check user prompts
        for prompt in self._load_user_prompts():
            if prompt.id == prompt_id:
                return prompt

        return None

    def add_prompt(self, name: str, template: str, description: str = "") -> ComparisonPrompt:
        """Add a custom comparison prompt.

        Args:
            name: Human-readable name for the prompt.
            template: Prompt template with {trace_a} and {trace_b} placeholders.
            description: Optional description.

        Returns:
            The created prompt.
        """
        # Generate unique ID from name
        prompt_id = name.lower().replace(" ", "-")
        # Ensure uniqueness
        existing_ids = {p.id for p in self.list_prompts()}
        if prompt_id in existing_ids:
            prompt_id = f"{prompt_id}-{uuid4().hex[:6]}"

        prompt = ComparisonPrompt(
            id=prompt_id,
            name=name,
            template=template,
            description=description,
            is_builtin=False,
        )

        user_prompts = self._load_user_prompts()
        user_prompts.append(prompt)
        self._save_user_prompts(user_prompts)

        logger.info(f"Added custom prompt: {prompt_id}")
        return prompt

    def remove_prompt(self, prompt_id: str) -> bool:
        """Remove a custom prompt.

        Builtin prompts cannot be removed.

        Args:
            prompt_id: The prompt ID to remove.

        Returns:
            True if removed, False if not found or is builtin.
        """
        # Check if it's a builtin
        for prompt in self.BUILTIN_PROMPTS:
            if prompt.id == prompt_id:
                logger.warning(f"Cannot remove builtin prompt: {prompt_id}")
                return False

        user_prompts = self._load_user_prompts()
        original_count = len(user_prompts)
        user_prompts = [p for p in user_prompts if p.id != prompt_id]

        if len(user_prompts) < original_count:
            self._save_user_prompts(user_prompts)
            logger.info(f"Removed custom prompt: {prompt_id}")
            return True

        return False

    def _load_user_prompts(self) -> list[ComparisonPrompt]:
        """Load user-defined prompts from config file.

        Returns:
            List of user-defined prompts.
        """
        if not self.PROMPTS_FILE.exists():
            return []

        try:
            with open(self.PROMPTS_FILE, encoding="utf-8") as f:
                data = json.load(f)

            return [
                ComparisonPrompt(
                    id=p["id"],
                    name=p["name"],
                    template=p["template"],
                    description=p.get("description", ""),
                    is_builtin=False,
                )
                for p in data.get("prompts", [])
            ]
        except Exception as e:
            logger.warning(f"Failed to load user prompts: {e}")
            return []

    def _save_user_prompts(self, prompts: list[ComparisonPrompt]) -> None:
        """Save user-defined prompts to config file.

        Args:
            prompts: List of user prompts to save.
        """
        data = {
            "prompts": [
                {
                    "id": p.id,
                    "name": p.name,
                    "template": p.template,
                    "description": p.description,
                }
                for p in prompts
            ]
        }

        try:
            with open(self.PROMPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user prompts: {e}")
            raise
