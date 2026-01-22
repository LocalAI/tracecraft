"""Tests for webhook alerting functionality."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from agenttrace.alerting.webhooks import (
    AlertingProcessor,
    AlertRule,
    GenericAlertFormatter,
    PagerDutyAlertFormatter,
    SlackAlertFormatter,
    create_error_alert,
    create_high_cost_alert,
    create_high_token_alert,
    create_slow_trace_alert,
)
from agenttrace.core.models import AgentRun, Step, StepType


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
def error_run() -> AgentRun:
    """Create a run with an error."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name="error-run",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_ms=500,
        total_tokens=100,
        total_cost_usd=0.01,
        error="Something went wrong",
        error_count=1,
        steps=[],
    )


@pytest.fixture
def high_cost_run() -> AgentRun:
    """Create a run with high cost."""
    trace_id = uuid4()
    return AgentRun(
        id=trace_id,
        name="high-cost-run",
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        duration_ms=5000,
        total_tokens=10000,
        total_cost_usd=2.50,
        error=None,
        error_count=0,
        steps=[],
    )


class TestAlertRule:
    """Tests for AlertRule class."""

    def test_creates_rule_with_required_fields(self):
        """Test creating a rule with required fields."""
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://example.com/hook",
        )
        assert rule.name == "test"
        assert rule.webhook_url == "https://example.com/hook"
        assert rule.cooldown_seconds == 60

    def test_creates_rule_with_custom_cooldown(self):
        """Test creating a rule with custom cooldown."""
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://example.com/hook",
            cooldown_seconds=300,
        )
        assert rule.cooldown_seconds == 300

    def test_creates_rule_with_metadata(self):
        """Test creating a rule with metadata."""
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://example.com/hook",
            metadata={"env": "production"},
        )
        assert rule.metadata == {"env": "production"}


class TestGenericAlertFormatter:
    """Tests for GenericAlertFormatter."""

    def test_formats_basic_alert(self, sample_run):
        """Test basic alert formatting."""
        formatter = GenericAlertFormatter()
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://example.com/hook",
        )

        payload = formatter.format(rule, sample_run)

        assert "text" in payload
        assert "alert_rule" in payload
        assert payload["alert_rule"] == "test"
        assert "trace_id" in payload
        assert "timestamp" in payload
        assert "metadata" in payload

    def test_formats_with_custom_template(self, sample_run):
        """Test formatting with custom message template."""
        formatter = GenericAlertFormatter(message_template="Alert: {name} cost ${cost:.2f}")
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://example.com/hook",
        )

        payload = formatter.format(rule, sample_run)

        assert "Alert: test-run cost $0.05" in payload["text"]


class TestSlackAlertFormatter:
    """Tests for SlackAlertFormatter."""

    def test_formats_slack_alert(self, sample_run):
        """Test Slack alert formatting."""
        formatter = SlackAlertFormatter()
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://hooks.slack.com/...",
        )

        payload = formatter.format(rule, sample_run)

        assert "username" in payload
        assert payload["username"] == "AgentTrace"
        assert "icon_emoji" in payload
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        assert "blocks" in payload["attachments"][0]

    def test_formats_error_alert_as_danger(self, error_run):
        """Test error alerts have danger color."""
        formatter = SlackAlertFormatter()
        rule = AlertRule(
            name="error",
            condition=lambda run: True,
            webhook_url="https://hooks.slack.com/...",
        )

        payload = formatter.format(rule, error_run)

        assert payload["attachments"][0]["color"] == "danger"

    def test_includes_channel_override(self, sample_run):
        """Test channel override is included."""
        formatter = SlackAlertFormatter(channel="#alerts")
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://hooks.slack.com/...",
        )

        payload = formatter.format(rule, sample_run)

        assert payload["channel"] == "#alerts"


class TestPagerDutyAlertFormatter:
    """Tests for PagerDutyAlertFormatter."""

    def test_formats_pagerduty_alert(self, sample_run):
        """Test PagerDuty alert formatting."""
        formatter = PagerDutyAlertFormatter(
            routing_key="test-routing-key",
            source="test-app",
        )
        rule = AlertRule(
            name="test",
            condition=lambda run: True,
            webhook_url="https://events.pagerduty.com/v2/enqueue",
        )

        payload = formatter.format(rule, sample_run)

        assert payload["routing_key"] == "test-routing-key"
        assert payload["event_action"] == "trigger"
        assert "dedup_key" in payload
        assert payload["payload"]["source"] == "test-app"
        assert payload["payload"]["severity"] == "warning"

    def test_sets_error_severity(self, error_run):
        """Test error severity for error runs."""
        formatter = PagerDutyAlertFormatter(routing_key="test")
        rule = AlertRule(
            name="error",
            condition=lambda run: True,
            webhook_url="https://events.pagerduty.com/v2/enqueue",
        )

        payload = formatter.format(rule, error_run)

        assert payload["payload"]["severity"] == "error"


class TestAlertingProcessor:
    """Tests for AlertingProcessor."""

    def test_creates_processor(self):
        """Test creating a processor with rules."""
        rules = [
            AlertRule(
                name="test",
                condition=lambda run: True,
                webhook_url="https://example.com/hook",
            )
        ]
        processor = AlertingProcessor(rules=rules)

        assert processor.name == "alerting"
        assert len(processor.rules) == 1

    def test_process_returns_run(self, sample_run):
        """Test process always returns the run."""
        rules = [
            AlertRule(
                name="test",
                condition=lambda run: False,
                webhook_url="https://example.com/hook",
            )
        ]
        processor = AlertingProcessor(rules=rules, async_send=False)

        result = processor.process(sample_run)

        assert result is sample_run

    def test_does_not_alert_when_condition_false(self, sample_run):
        """Test no alert when condition is false."""
        rules = [
            AlertRule(
                name="test",
                condition=lambda run: False,
                webhook_url="https://example.com/hook",
            )
        ]
        processor = AlertingProcessor(rules=rules, async_send=False)

        with patch.object(processor, "_send_alert") as mock_send:
            processor.process(sample_run)
            mock_send.assert_not_called()

    def test_alerts_when_condition_true(self, sample_run):
        """Test alert sent when condition is true."""
        rules = [
            AlertRule(
                name="test",
                condition=lambda run: True,
                webhook_url="https://example.com/hook",
            )
        ]
        processor = AlertingProcessor(rules=rules, async_send=False)

        with patch.object(processor, "_send_alert_sync") as mock_send:
            processor.process(sample_run)
            mock_send.assert_called_once()

    def test_respects_cooldown(self, sample_run):
        """Test cooldown prevents repeated alerts."""
        rules = [
            AlertRule(
                name="test",
                condition=lambda run: True,
                webhook_url="https://example.com/hook",
                cooldown_seconds=60,
            )
        ]
        processor = AlertingProcessor(rules=rules, async_send=False)

        # First alert should go through
        with patch.object(processor, "_send_alert_sync") as mock_send:
            processor.process(sample_run)
            assert mock_send.call_count == 1

            # Second alert should be blocked by cooldown
            processor.process(sample_run)
            assert mock_send.call_count == 1

    @patch("httpx.post")
    def test_sends_webhook_request(self, mock_post, sample_run):
        """Test actual webhook request is sent."""
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()

        rules = [
            AlertRule(
                name="test",
                condition=lambda run: True,
                webhook_url="https://example.com/hook",
            )
        ]
        processor = AlertingProcessor(rules=rules, async_send=False)

        processor.process(sample_run)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://example.com/hook"
        assert "json" in call_args[1]


class TestConvenienceFactories:
    """Tests for convenience factory functions."""

    def test_create_error_alert(self, error_run, sample_run):
        """Test create_error_alert factory."""
        rule = create_error_alert("https://example.com/hook")

        assert rule.name == "error"
        assert rule.condition(error_run) is True
        assert rule.condition(sample_run) is False

    def test_create_high_cost_alert(self, high_cost_run, sample_run):
        """Test create_high_cost_alert factory."""
        rule = create_high_cost_alert("https://example.com/hook", threshold_usd=1.0)

        assert rule.name == "high_cost"
        assert rule.condition(high_cost_run) is True
        assert rule.condition(sample_run) is False
        assert rule.metadata["threshold_usd"] == 1.0

    def test_create_slow_trace_alert(self, sample_run):
        """Test create_slow_trace_alert factory."""
        rule = create_slow_trace_alert("https://example.com/hook", threshold_ms=1000)

        assert rule.name == "slow_trace"
        # sample_run has 1500ms duration
        assert rule.condition(sample_run) is True

        rule2 = create_slow_trace_alert("https://example.com/hook", threshold_ms=2000)
        assert rule2.condition(sample_run) is False

    def test_create_high_token_alert(self, high_cost_run, sample_run):
        """Test create_high_token_alert factory."""
        rule = create_high_token_alert("https://example.com/hook", threshold_tokens=5000)

        assert rule.name == "high_tokens"
        assert rule.condition(high_cost_run) is True  # 10000 tokens
        assert rule.condition(sample_run) is False  # 500 tokens
