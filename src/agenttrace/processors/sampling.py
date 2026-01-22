"""
Tail sampling processor.

Provides intelligent sampling decisions based on trace characteristics
like errors, duration, and custom rules.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun


class SamplingDecision(Enum):
    """Sampling decision result."""

    KEEP = "keep"
    DROP = "drop"


@dataclass
class SamplingRule:
    """A rule for deciding whether to sample a trace."""

    name: str
    rate: float = 1.0
    match_error: bool = False
    match_names: list[str] = field(default_factory=list)
    match_tags: list[str] = field(default_factory=list)
    min_duration_ms: float | None = None


class SamplingProcessor:
    """
    Processor for making intelligent sampling decisions.

    Implements tail-based sampling with support for:
    - Rate-based sampling
    - Always keeping error traces
    - Always keeping slow traces
    - Custom rule matching
    """

    def __init__(
        self,
        default_rate: float = 1.0,
        always_keep_errors: bool = True,
        always_keep_slow: bool = False,
        slow_threshold_ms: float = 5000.0,
        rules: list[SamplingRule] | None = None,
    ) -> None:
        """
        Initialize the sampling processor.

        Args:
            default_rate: Default sampling rate (0.0 to 1.0).
            always_keep_errors: Always keep traces with errors.
            always_keep_slow: Always keep slow traces.
            slow_threshold_ms: Duration threshold for "slow" traces.
            rules: Custom sampling rules to apply.
        """
        self.default_rate = default_rate
        self.always_keep_errors = always_keep_errors
        self.always_keep_slow = always_keep_slow
        self.slow_threshold_ms = slow_threshold_ms
        self.rules = rules or []

    def should_sample(self, run: AgentRun) -> tuple[bool, str]:
        """
        Decide whether to sample (keep) a trace.

        Priority order:
        1. Error traces (if always_keep_errors)
        2. Slow traces (if always_keep_slow)
        3. Custom rules (first match wins)
        4. Default rate

        Args:
            run: The AgentRun to evaluate.

        Returns:
            Tuple of (should_keep, reason).
        """
        # 1. Check for errors first
        if self.always_keep_errors and self._has_errors(run):
            return True, "Kept: error trace (always_keep_errors=True)"

        # 2. Check for slow traces
        if self.always_keep_slow and self._is_slow(run):
            return True, f"Kept: slow trace (>{self.slow_threshold_ms}ms)"

        # 3. Check custom rules
        for rule in self.rules:
            if self._matches_rule(run, rule):
                should_keep = self._should_keep_by_rate(run, rule.rate)
                if should_keep:
                    return True, f"Kept: matched rule '{rule.name}'"
                return False, f"Dropped: matched rule '{rule.name}' (rate={rule.rate})"

        # 4. Apply default rate
        should_keep = self._should_keep_by_rate(run, self.default_rate)
        if should_keep:
            return True, f"Kept: default rate ({self.default_rate})"
        return False, f"Dropped: default rate ({self.default_rate})"

    def _has_errors(self, run: AgentRun) -> bool:
        """Check if run has any errors."""
        if run.error_count is not None and run.error_count > 0:
            return True
        # Also check steps for errors
        return any(self._step_has_error(step) for step in run.steps)

    def _step_has_error(self, step: object) -> bool:
        """Check if a step has an error."""
        return getattr(step, "error", None) is not None

    def _is_slow(self, run: AgentRun) -> bool:
        """Check if run is considered slow."""
        if run.duration_ms is None:
            return False
        return run.duration_ms >= self.slow_threshold_ms

    def _matches_rule(self, run: AgentRun, rule: SamplingRule) -> bool:
        """Check if a run matches a rule's conditions."""
        # Check error condition
        if rule.match_error and not self._has_errors(run):
            return False

        # Check name match
        if rule.match_names and run.name not in rule.match_names:
            return False

        # Check tag match
        if rule.match_tags:
            run_tags = set(run.tags or [])
            if not any(tag in run_tags for tag in rule.match_tags):
                return False

        # Check duration threshold
        return not (
            rule.min_duration_ms is not None
            and (run.duration_ms is None or run.duration_ms < rule.min_duration_ms)
        )

    def _should_keep_by_rate(self, run: AgentRun, rate: float) -> bool:
        """
        Decide whether to keep a trace based on rate.

        Uses deterministic hashing based on trace ID to ensure
        consistent decisions for the same trace.
        """
        if rate <= 0.0:
            return False
        if rate >= 1.0:
            return True

        # Use trace ID hash for deterministic sampling (not for security)
        hash_value = hashlib.md5(str(run.id).encode(), usedforsecurity=False).hexdigest()
        # Convert first 8 hex chars to a float between 0 and 1
        hash_float = int(hash_value[:8], 16) / 0xFFFFFFFF
        return hash_float < rate
