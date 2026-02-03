"""Tests for quality score monitoring functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from tracecraft.alerting.quality import (
    QualityAlert,
    QualityMetric,
    QualityScoreAggregator,
    QualityScoreProcessor,
    QualityThreshold,
)
from tracecraft.core.models import AgentRun, Step, StepType


@pytest.fixture
def sample_run() -> AgentRun:
    """Create a sample run for testing."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name="test-run",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_ms=1500,
        total_tokens=500,
        total_cost_usd=0.05,
        error=None,
        error_count=0,
        attributes={
            "quality_faithfulness": 0.85,
            "quality_relevancy": 0.90,
        },
        steps=[
            Step(
                id=uuid4(),
                trace_id=trace_id,
                name="llm-step",
                type=StepType.LLM,
                start_time=datetime.now(UTC),
            )
        ],
    )


@pytest.fixture
def low_quality_run() -> AgentRun:
    """Create a run with low quality scores."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name="low-quality-run",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_ms=500,
        total_tokens=100,
        total_cost_usd=0.01,
        error=None,
        error_count=0,
        attributes={
            "quality_faithfulness": 0.50,
            "quality_relevancy": 0.60,
        },
        steps=[],
    )


class TestQualityMetric:
    """Tests for QualityMetric enum."""

    def test_metric_values(self):
        """Test metric enum values."""
        assert QualityMetric.FAITHFULNESS.value == "faithfulness"
        assert QualityMetric.ANSWER_RELEVANCY.value == "answer_relevancy"
        assert QualityMetric.LATENCY.value == "latency"
        assert QualityMetric.ERROR_RATE.value == "error_rate"


class TestQualityThreshold:
    """Tests for QualityThreshold class."""

    def test_creates_threshold_with_min_value(self):
        """Test creating threshold with min value."""
        threshold = QualityThreshold(
            metric=QualityMetric.FAITHFULNESS,
            min_value=0.8,
        )
        assert threshold.min_value == 0.8
        assert threshold.max_value is None

    def test_creates_threshold_with_max_value(self):
        """Test creating threshold with max value."""
        threshold = QualityThreshold(
            metric=QualityMetric.LATENCY,
            max_value=5000,
        )
        assert threshold.min_value is None
        assert threshold.max_value == 5000

    def test_creates_threshold_with_both_values(self):
        """Test creating threshold with both min and max."""
        threshold = QualityThreshold(
            metric=QualityMetric.COST,
            min_value=0.01,
            max_value=1.0,
        )
        assert threshold.min_value == 0.01
        assert threshold.max_value == 1.0

    def test_raises_without_threshold_values(self):
        """Test raises error if no threshold values set."""
        with pytest.raises(ValueError, match="At least one of"):
            QualityThreshold(metric=QualityMetric.FAITHFULNESS)

    def test_custom_window_size(self):
        """Test custom window size."""
        threshold = QualityThreshold(
            metric=QualityMetric.FAITHFULNESS,
            min_value=0.8,
            window_size=50,
        )
        assert threshold.window_size == 50

    def test_custom_aggregation(self):
        """Test custom aggregation method."""
        threshold = QualityThreshold(
            metric=QualityMetric.LATENCY,
            max_value=5000,
            aggregation="max",
        )
        assert threshold.aggregation == "max"


class TestQualityScoreProcessor:
    """Tests for QualityScoreProcessor."""

    def test_creates_processor(self):
        """Test creating processor with thresholds."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=5000),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        assert processor.name == "quality_score"
        assert len(processor.thresholds) == 2

    def test_process_returns_run(self, sample_run):
        """Test process always returns the run."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        result = processor.process(sample_run)

        assert result is sample_run

    def test_extracts_scores_from_attributes(self, sample_run):
        """Test score extraction from run attributes."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        scores = processor.extract_scores(sample_run)

        assert "faithfulness" in scores
        assert scores["faithfulness"] == 0.85

    def test_extracts_built_in_metrics(self, sample_run):
        """Test extraction of built-in metrics."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=5000),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        processor.process(sample_run)

        scores = processor.get_current_scores()
        assert "latency" in scores
        assert scores["latency"] == 1500

    def test_tracks_error_rate(self, sample_run):
        """Test error rate tracking."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.ERROR_RATE, max_value=0.1),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        # Process multiple runs
        for _ in range(5):
            processor.process(sample_run)

        scores = processor.get_current_scores()
        assert "error_rate" in scores
        assert scores["error_rate"] == 0.0  # No errors

    def test_triggers_alert_on_threshold_violation(self, low_quality_run):
        """Test alert triggered when threshold violated."""
        on_alert = MagicMock()

        thresholds = [
            QualityThreshold(
                metric=QualityMetric.FAITHFULNESS,
                min_value=0.8,
                window_size=1,
            ),
        ]
        processor = QualityScoreProcessor(
            thresholds=thresholds,
            on_alert=on_alert,
        )

        processor.process(low_quality_run)

        on_alert.assert_called_once()
        alert = on_alert.call_args[0][0]
        assert isinstance(alert, QualityAlert)
        assert alert.current_value == 0.50
        assert "below minimum" in alert.message

    def test_does_not_alert_when_passing(self, sample_run):
        """Test no alert when scores pass threshold."""
        on_alert = MagicMock()

        thresholds = [
            QualityThreshold(
                metric=QualityMetric.FAITHFULNESS,
                min_value=0.8,
                window_size=1,
            ),
        ]
        processor = QualityScoreProcessor(
            thresholds=thresholds,
            on_alert=on_alert,
        )

        processor.process(sample_run)

        on_alert.assert_not_called()

    def test_uses_windowed_aggregation(self):
        """Test windowed aggregation for threshold checking."""
        thresholds = [
            QualityThreshold(
                metric="custom",
                min_value=0.7,
                window_size=3,
                aggregation="mean",
            ),
        ]
        processor = QualityScoreProcessor(
            thresholds=thresholds,
            extract_scores=lambda run: {"custom": run.attributes.get("score", 0)},
        )

        # Create runs with different scores
        scores = [0.8, 0.6, 0.9]  # Mean = 0.77 > 0.7
        for score in scores:
            run = AgentRun(
                id=uuid4(),
                name="test",
                start_time=datetime.now(UTC),
                steps=[],
                attributes={"score": score},
            )
            processor.process(run)

        current = processor.get_current_scores()
        assert abs(current["custom"] - 0.77) < 0.01

    def test_get_window_data(self, sample_run):
        """Test getting window data."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=5000),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        for _ in range(3):
            processor.process(sample_run)

        data = processor.get_window_data(QualityMetric.LATENCY)
        assert len(data) == 3
        assert all(v == 1500 for v in data)

    def test_reset_clears_windows(self, sample_run):
        """Test reset clears all windows."""
        thresholds = [
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=5000),
        ]
        processor = QualityScoreProcessor(thresholds=thresholds)

        processor.process(sample_run)
        assert len(processor.get_window_data(QualityMetric.LATENCY)) > 0

        processor.reset()
        assert len(processor.get_window_data(QualityMetric.LATENCY)) == 0

    def test_alert_cooldown(self, low_quality_run):
        """Test alert cooldown prevents repeated alerts."""
        on_alert = MagicMock()

        thresholds = [
            QualityThreshold(
                metric=QualityMetric.FAITHFULNESS,
                min_value=0.8,
                window_size=1,
            ),
        ]
        processor = QualityScoreProcessor(
            thresholds=thresholds,
            on_alert=on_alert,
        )
        processor._alert_cooldown_seconds = 300  # 5 minute cooldown

        # First violation triggers alert
        processor.process(low_quality_run)
        assert on_alert.call_count == 1

        # Second violation within cooldown doesn't trigger
        processor.process(low_quality_run)
        assert on_alert.call_count == 1


class TestQualityScoreAggregator:
    """Tests for QualityScoreAggregator."""

    def test_adds_single_score(self):
        """Test adding a single score."""
        aggregator = QualityScoreAggregator()
        aggregator.add_score("faithfulness", 0.85)

        summary = aggregator.get_summary()
        assert "faithfulness" in summary
        assert summary["faithfulness"]["mean"] == 0.85
        assert summary["faithfulness"]["count"] == 1

    def test_adds_multiple_scores(self):
        """Test adding multiple scores."""
        aggregator = QualityScoreAggregator()
        aggregator.add_scores(
            {
                "faithfulness": 0.85,
                "relevancy": 0.90,
            }
        )

        summary = aggregator.get_summary()
        assert "faithfulness" in summary
        assert "relevancy" in summary

    def test_calculates_statistics(self):
        """Test statistical calculations."""
        aggregator = QualityScoreAggregator()

        for score in [0.8, 0.85, 0.9, 0.95]:
            aggregator.add_score("faithfulness", score)

        summary = aggregator.get_summary()
        assert abs(summary["faithfulness"]["mean"] - 0.875) < 0.001
        assert summary["faithfulness"]["min"] == 0.8
        assert summary["faithfulness"]["max"] == 0.95
        assert summary["faithfulness"]["count"] == 4

    def test_passes_thresholds(self):
        """Test passes_thresholds check."""
        aggregator = QualityScoreAggregator()
        aggregator.add_score("faithfulness", 0.85)
        aggregator.add_score("latency", 1000)

        thresholds = [
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=2000),
        ]

        assert aggregator.passes_thresholds(thresholds) is True

    def test_fails_thresholds(self):
        """Test fails_thresholds check."""
        aggregator = QualityScoreAggregator()
        aggregator.add_score("faithfulness", 0.50)

        thresholds = [
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
        ]

        assert aggregator.passes_thresholds(thresholds) is False

    def test_reset_clears_scores(self):
        """Test reset clears all scores."""
        aggregator = QualityScoreAggregator()
        aggregator.add_score("faithfulness", 0.85)

        aggregator.reset()

        summary = aggregator.get_summary()
        assert len(summary) == 0


class TestQualityAlert:
    """Tests for QualityAlert dataclass."""

    def test_creates_alert(self):
        """Test creating an alert."""
        threshold = QualityThreshold(
            metric=QualityMetric.FAITHFULNESS,
            min_value=0.8,
        )
        alert = QualityAlert(
            threshold=threshold,
            current_value=0.5,
            timestamp=datetime.now(UTC),
            trace_id="abc123",
            trace_name="test-run",
            message="faithfulness below minimum",
        )

        assert alert.current_value == 0.5
        assert alert.trace_id == "abc123"
        assert "below minimum" in alert.message
