"""
Tests for the sampling processor.

Tests tail-based sampling with rate filtering and always-keep rules.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agenttrace.core.models import AgentRun, Step, StepType
from agenttrace.processors.sampling import (
    SamplingDecision,
    SamplingProcessor,
    SamplingRule,
)


@pytest.fixture
def fast_run() -> AgentRun:
    """Create a fast run (100ms)."""
    start = datetime.now(UTC)
    return AgentRun(
        name="fast_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=100),
        duration_ms=100.0,
    )


@pytest.fixture
def slow_run() -> AgentRun:
    """Create a slow run (6000ms)."""
    start = datetime.now(UTC)
    return AgentRun(
        name="slow_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=6000),
        duration_ms=6000.0,
    )


@pytest.fixture
def error_run() -> AgentRun:
    """Create a run with errors."""
    start = datetime.now(UTC)
    run = AgentRun(
        name="error_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=100),
        duration_ms=100.0,
    )
    error_step = Step(
        trace_id=run.id,
        type=StepType.TOOL,
        name="failing_tool",
        start_time=start,
        error="Connection failed",
        error_type="ConnectionError",
    )
    run.steps.append(error_step)
    run.error_count = 1
    return run


@pytest.fixture
def normal_run() -> AgentRun:
    """Create a normal run without errors."""
    start = datetime.now(UTC)
    run = AgentRun(
        name="normal_agent",
        start_time=start,
        end_time=start + timedelta(milliseconds=500),
        duration_ms=500.0,
    )
    step = Step(
        trace_id=run.id,
        type=StepType.TOOL,
        name="working_tool",
        start_time=start,
    )
    run.steps.append(step)
    return run


class TestSamplingDecision:
    """Tests for SamplingDecision."""

    def test_decision_keep(self) -> None:
        """KEEP decision should exist."""
        assert SamplingDecision.KEEP.value == "keep"

    def test_decision_drop(self) -> None:
        """DROP decision should exist."""
        assert SamplingDecision.DROP.value == "drop"


class TestSamplingRule:
    """Tests for SamplingRule."""

    def test_rule_with_rate(self) -> None:
        """Rule with sampling rate."""
        rule = SamplingRule(name="default", rate=0.1)
        assert rule.name == "default"
        assert rule.rate == 0.1

    def test_rule_with_conditions(self) -> None:
        """Rule with match conditions."""
        rule = SamplingRule(
            name="errors",
            rate=1.0,
            match_error=True,
        )
        assert rule.match_error is True

    def test_rule_with_duration_threshold(self) -> None:
        """Rule with duration threshold."""
        rule = SamplingRule(
            name="slow",
            rate=1.0,
            min_duration_ms=5000.0,
        )
        assert rule.min_duration_ms == 5000.0


class TestSamplingProcessorBasics:
    """Tests for basic sampling functionality."""

    def test_sample_rate_filters_deterministically(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Sampling should be deterministic based on trace ID."""
        processor = SamplingProcessor(default_rate=0.5)
        decisions = [processor.should_sample(normal_run) for _ in range(10)]
        # All decisions should be the same for the same run
        assert len({d[0] for d in decisions}) == 1

    def test_sample_rate_zero_drops_all(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Rate 0.0 should drop all traces."""
        processor = SamplingProcessor(default_rate=0.0)
        should_keep, reason = processor.should_sample(normal_run)
        assert should_keep is False
        assert "rate" in reason.lower()

    def test_sample_rate_one_keeps_all(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Rate 1.0 should keep all traces."""
        processor = SamplingProcessor(default_rate=1.0)
        should_keep, reason = processor.should_sample(normal_run)
        assert should_keep is True

    def test_sample_returns_decision_tuple(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Should return (bool, str) tuple."""
        processor = SamplingProcessor(default_rate=0.5)
        result = processor.should_sample(normal_run)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)


class TestSamplingProcessorErrorHandling:
    """Tests for error trace handling."""

    def test_always_keep_errors(
        self,
        error_run: AgentRun,
    ) -> None:
        """Error traces should always be kept."""
        processor = SamplingProcessor(
            default_rate=0.0,  # Would normally drop everything
            always_keep_errors=True,
        )
        should_keep, reason = processor.should_sample(error_run)
        assert should_keep is True
        assert "error" in reason.lower()

    def test_keep_errors_disabled(
        self,
        error_run: AgentRun,
    ) -> None:
        """Error traces can be dropped if keep_errors is disabled."""
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_errors=False,
        )
        should_keep, reason = processor.should_sample(error_run)
        assert should_keep is False

    def test_error_detection_via_error_count(
        self,
        error_run: AgentRun,
    ) -> None:
        """Should detect errors via error_count field."""
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_errors=True,
        )
        assert error_run.error_count > 0
        should_keep, _ = processor.should_sample(error_run)
        assert should_keep is True


class TestSamplingProcessorSlowTraces:
    """Tests for slow trace handling."""

    def test_always_keep_slow(
        self,
        slow_run: AgentRun,
    ) -> None:
        """Slow traces should always be kept."""
        processor = SamplingProcessor(
            default_rate=0.0,  # Would normally drop everything
            always_keep_slow=True,
            slow_threshold_ms=5000.0,
        )
        should_keep, reason = processor.should_sample(slow_run)
        assert should_keep is True
        assert "slow" in reason.lower()

    def test_keep_slow_disabled(
        self,
        slow_run: AgentRun,
    ) -> None:
        """Slow traces can be dropped if keep_slow is disabled."""
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_slow=False,
        )
        should_keep, reason = processor.should_sample(slow_run)
        assert should_keep is False

    def test_slow_threshold_customizable(
        self,
        fast_run: AgentRun,
    ) -> None:
        """Slow threshold should be customizable."""
        # With a very low threshold, fast_run becomes "slow"
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_slow=True,
            slow_threshold_ms=50.0,  # 50ms threshold
        )
        should_keep, reason = processor.should_sample(fast_run)
        assert should_keep is True
        assert "slow" in reason.lower()

    def test_not_slow_with_high_threshold(
        self,
        slow_run: AgentRun,
    ) -> None:
        """Run should not be considered slow if under threshold."""
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_slow=True,
            slow_threshold_ms=10000.0,  # 10s threshold
        )
        should_keep, reason = processor.should_sample(slow_run)
        assert should_keep is False


class TestSamplingProcessorCustomRules:
    """Tests for custom sampling rules."""

    def test_custom_rule_by_name(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Custom rule can match by agent name."""
        rule = SamplingRule(
            name="important_agents",
            rate=1.0,
            match_names=["normal_agent"],
        )
        processor = SamplingProcessor(
            default_rate=0.0,
            rules=[rule],
        )
        should_keep, reason = processor.should_sample(normal_run)
        assert should_keep is True
        assert "important_agents" in reason

    def test_custom_rule_by_tag(self) -> None:
        """Custom rule can match by tag."""
        run = AgentRun(
            name="agent",
            start_time=datetime.now(UTC),
            tags=["production", "critical"],
        )
        rule = SamplingRule(
            name="critical_traces",
            rate=1.0,
            match_tags=["critical"],
        )
        processor = SamplingProcessor(
            default_rate=0.0,
            rules=[rule],
        )
        should_keep, reason = processor.should_sample(run)
        assert should_keep is True

    def test_rules_checked_in_order(self) -> None:
        """Rules should be checked in order, first match wins."""
        run = AgentRun(
            name="test_agent",
            start_time=datetime.now(UTC),
        )
        rule1 = SamplingRule(
            name="first",
            rate=1.0,
            match_names=["test_agent"],
        )
        rule2 = SamplingRule(
            name="second",
            rate=0.0,
            match_names=["test_agent"],
        )
        processor = SamplingProcessor(
            default_rate=0.5,
            rules=[rule1, rule2],
        )
        should_keep, reason = processor.should_sample(run)
        assert should_keep is True
        assert "first" in reason


class TestSamplingProcessorPriority:
    """Tests for sampling priority (error > slow > rules > default)."""

    def test_error_takes_priority_over_slow(
        self,
    ) -> None:
        """Error handling should take priority over slow handling."""
        start = datetime.now(UTC)
        run = AgentRun(
            name="agent",
            start_time=start,
            end_time=start + timedelta(milliseconds=6000),
            duration_ms=6000.0,
            error_count=1,
        )
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_errors=True,
            always_keep_slow=True,
        )
        should_keep, reason = processor.should_sample(run)
        assert should_keep is True
        assert "error" in reason.lower()  # Error reason, not slow

    def test_slow_takes_priority_over_rules(
        self,
        slow_run: AgentRun,
    ) -> None:
        """Slow handling should take priority over custom rules."""
        rule = SamplingRule(
            name="drop_all",
            rate=0.0,
            match_names=["slow_agent"],
        )
        processor = SamplingProcessor(
            default_rate=0.0,
            always_keep_slow=True,
            slow_threshold_ms=5000.0,
            rules=[rule],
        )
        should_keep, reason = processor.should_sample(slow_run)
        assert should_keep is True
        assert "slow" in reason.lower()


class TestSamplingProcessorEdgeCases:
    """Tests for edge cases."""

    def test_run_without_duration(self) -> None:
        """Handle runs without duration_ms set."""
        run = AgentRun(
            name="agent",
            start_time=datetime.now(UTC),
            duration_ms=None,
        )
        processor = SamplingProcessor(
            default_rate=1.0,
            always_keep_slow=True,
        )
        should_keep, reason = processor.should_sample(run)
        assert should_keep is True

    def test_run_without_error_count(self) -> None:
        """Handle runs with error_count=0 (default)."""
        run = AgentRun(
            name="agent",
            start_time=datetime.now(UTC),
            # error_count defaults to 0
        )
        processor = SamplingProcessor(
            default_rate=1.0,
            always_keep_errors=True,
        )
        should_keep, reason = processor.should_sample(run)
        assert should_keep is True

    def test_empty_rules_list(
        self,
        normal_run: AgentRun,
    ) -> None:
        """Handle empty rules list."""
        processor = SamplingProcessor(
            default_rate=1.0,
            rules=[],
        )
        should_keep, reason = processor.should_sample(normal_run)
        assert should_keep is True
