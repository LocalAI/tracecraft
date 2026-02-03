"""
Webhook alerting for TraceCraft.

Send alerts when traces meet certain conditions via webhooks.
Supports Slack, PagerDuty, and generic webhook endpoints.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tracecraft.processors.base import BaseProcessor

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """
    A rule that triggers alerts based on trace conditions.

    Attributes:
        name: Unique name for this rule.
        condition: Function that takes an AgentRun and returns True to trigger.
        webhook_url: URL to send the alert to.
        formatter: Optional formatter for the alert payload.
        cooldown_seconds: Minimum seconds between alerts for same rule.
        metadata: Additional metadata to include in alerts.
    """

    name: str
    condition: Callable[[AgentRun], bool]
    webhook_url: str
    formatter: AlertFormatter | None = None
    cooldown_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)

    # Internal state for cooldown
    _last_alert_time: datetime | None = field(default=None, repr=False)


class AlertFormatter(ABC):
    """Base class for alert formatters."""

    @abstractmethod
    def format(self, rule: AlertRule, run: AgentRun) -> dict[str, Any]:
        """
        Format an alert payload.

        Args:
            rule: The triggered alert rule.
            run: The agent run that triggered the alert.

        Returns:
            Dictionary payload to send to the webhook.
        """
        pass


class GenericAlertFormatter(AlertFormatter):
    """Default generic alert formatter."""

    def __init__(self, message_template: str | None = None) -> None:
        """
        Initialize the formatter.

        Args:
            message_template: Template string for the message.
                Supports: {name}, {trace_id}, {cost}, {tokens}, {duration}, {error}
        """
        self.message_template = message_template or (
            "Alert '{rule_name}' triggered for trace '{name}' (ID: {trace_id})"
        )

    def format(self, rule: AlertRule, run: AgentRun) -> dict[str, Any]:
        """Format a generic webhook payload."""
        message = self.message_template.format(
            rule_name=rule.name,
            name=run.name,
            trace_id=str(run.id),
            cost=run.total_cost_usd or 0,
            tokens=run.total_tokens or 0,
            duration=run.duration_ms or 0,
            error=run.error or "",
        )

        return {
            "text": message,
            "alert_rule": rule.name,
            "trace_id": str(run.id),
            "trace_name": run.name,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": {
                "cost_usd": run.total_cost_usd,
                "total_tokens": run.total_tokens,
                "duration_ms": run.duration_ms,
                "error": run.error,
                "error_count": run.error_count,
                **rule.metadata,
            },
        }


class SlackAlertFormatter(AlertFormatter):
    """
    Formatter for Slack webhook alerts.

    Produces Slack Block Kit formatted messages for rich alerts.
    """

    def __init__(
        self,
        channel: str | None = None,
        username: str = "TraceCraft",
        icon_emoji: str = ":robot_face:",
    ) -> None:
        """
        Initialize the Slack formatter.

        Args:
            channel: Override channel (uses webhook default if None).
            username: Bot username to display.
            icon_emoji: Emoji icon for the bot.
        """
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    def format(self, rule: AlertRule, run: AgentRun) -> dict[str, Any]:
        """Format a Slack Block Kit payload."""
        # Determine severity color
        if run.error:
            color = "danger"
            status_emoji = ":x:"
        elif (run.total_cost_usd or 0) > 1.0:
            color = "warning"
            status_emoji = ":warning:"
        else:
            color = "good"
            status_emoji = ":white_check_mark:"

        # Build blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Alert: {rule.name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Trace:*\n{run.name}"},
                    {"type": "mrkdwn", "text": f"*ID:*\n`{run.id}`"},
                ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Cost:*\n${run.total_cost_usd or 0:.4f}"},
                    {"type": "mrkdwn", "text": f"*Tokens:*\n{run.total_tokens or 0:,}"},
                ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Duration:*\n{run.duration_ms or 0:.0f}ms"},
                    {"type": "mrkdwn", "text": f"*Errors:*\n{run.error_count or 0}"},
                ],
            },
        ]

        # Add error details if present
        if run.error:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{run.error[:500]}```",
                    },
                }
            )

        payload: dict[str, Any] = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ],
        }

        if self.channel:
            payload["channel"] = self.channel

        return payload


class PagerDutyAlertFormatter(AlertFormatter):
    """
    Formatter for PagerDuty Events API v2.

    Creates properly formatted PagerDuty events for incident management.
    """

    def __init__(
        self,
        routing_key: str,
        source: str = "tracecraft",
        component: str | None = None,
        group: str | None = None,
        severity: str = "warning",
    ) -> None:
        """
        Initialize the PagerDuty formatter.

        Args:
            routing_key: PagerDuty integration/routing key.
            source: Source of the alert.
            component: Component name.
            group: Logical grouping.
            severity: Default severity (critical, error, warning, info).
        """
        self.routing_key = routing_key
        self.source = source
        self.component = component
        self.group = group
        self.severity = severity

    def format(self, rule: AlertRule, run: AgentRun) -> dict[str, Any]:
        """Format a PagerDuty Events API v2 payload."""
        # Determine severity based on run state
        if run.error:
            severity = "error"
        elif (run.total_cost_usd or 0) > 5.0:
            severity = "critical"
        elif (run.total_cost_usd or 0) > 1.0:
            severity = "warning"
        else:
            severity = self.severity

        return {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": f"tracecraft-{rule.name}-{run.id}",
            "payload": {
                "summary": f"TraceCraft Alert: {rule.name} - {run.name}",
                "severity": severity,
                "source": self.source,
                "component": self.component,
                "group": self.group,
                "class": "tracecraft_alert",
                "custom_details": {
                    "trace_id": str(run.id),
                    "trace_name": run.name,
                    "cost_usd": run.total_cost_usd,
                    "total_tokens": run.total_tokens,
                    "duration_ms": run.duration_ms,
                    "error": run.error,
                    "error_count": run.error_count,
                    "rule_name": rule.name,
                    **rule.metadata,
                },
            },
        }


class AlertingProcessor(BaseProcessor):
    """
    Processor that sends webhook alerts based on rules.

    This processor evaluates each run against configured rules and
    sends alerts when conditions are met. It supports cooldown periods
    to prevent alert flooding.

    Example:
        from tracecraft.alerting import AlertingProcessor, AlertRule, SlackAlertFormatter

        alerter = AlertingProcessor(
            rules=[
                AlertRule(
                    name="high_cost",
                    condition=lambda run: (run.total_cost_usd or 0) > 1.0,
                    webhook_url="https://hooks.slack.com/...",
                    formatter=SlackAlertFormatter(),
                    cooldown_seconds=300,
                ),
                AlertRule(
                    name="error",
                    condition=lambda run: run.error is not None,
                    webhook_url="https://hooks.slack.com/...",
                    formatter=SlackAlertFormatter(),
                ),
                AlertRule(
                    name="slow_trace",
                    condition=lambda run: (run.duration_ms or 0) > 30000,
                    webhook_url="https://hooks.slack.com/...",
                ),
            ]
        )

        # Add to runtime
        from tracecraft import init
        init(processors=[alerter])
    """

    def __init__(
        self,
        rules: list[AlertRule],
        timeout_seconds: float = 5.0,
        async_send: bool = True,
    ) -> None:
        """
        Initialize the alerting processor.

        Args:
            rules: List of alert rules to evaluate.
            timeout_seconds: Timeout for webhook requests.
            async_send: If True, send alerts in background thread.
        """
        self.rules = rules
        self.timeout_seconds = timeout_seconds
        self.async_send = async_send
        self._default_formatter = GenericAlertFormatter()
        self._cooldown_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Processor name."""
        return "alerting"

    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Check rules and send alerts for matching conditions.

        Args:
            run: The AgentRun to evaluate.

        Returns:
            The run (always passes through - alerts are side effects).
        """
        for rule in self.rules:
            try:
                if self._should_alert(rule, run):
                    self._send_alert(rule, run)
            except Exception:
                logger.exception("Error checking alert rule '%s'", rule.name)

        return run  # Always pass through

    def _should_alert(self, rule: AlertRule, run: AgentRun) -> bool:
        """
        Check if an alert should be sent for this rule.

        Considers both the condition and cooldown period.
        """
        # Check condition
        if not rule.condition(run):
            return False

        # Check cooldown with thread safety
        with self._cooldown_lock:
            if rule._last_alert_time is not None:
                elapsed = (datetime.now(UTC) - rule._last_alert_time).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    logger.debug(
                        "Alert '%s' in cooldown (%.1fs remaining)",
                        rule.name,
                        rule.cooldown_seconds - elapsed,
                    )
                    return False

            # Update cooldown timestamp immediately within lock to prevent
            # race conditions when multiple threads check the same rule
            rule._last_alert_time = datetime.now(UTC)

        return True

    def _send_alert(self, rule: AlertRule, run: AgentRun) -> None:
        """Send an alert via webhook."""
        # Cooldown timestamp is now updated in _should_alert under lock

        if self.async_send:
            import threading

            thread = threading.Thread(
                target=self._send_alert_sync,
                args=(rule, run),
                daemon=True,
            )
            thread.start()
        else:
            self._send_alert_sync(rule, run)

    def _send_alert_sync(self, rule: AlertRule, run: AgentRun) -> None:
        """Send alert synchronously."""
        try:
            import httpx
        except ImportError as err:
            raise ImportError(
                "httpx required for webhook alerts. Install with: pip install httpx"
            ) from err

        # Format the payload
        formatter = rule.formatter or self._default_formatter
        payload = formatter.format(rule, run)

        try:
            response = httpx.post(
                rule.webhook_url,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()

            logger.info(
                "Alert '%s' sent for trace '%s'",
                rule.name,
                run.name,
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "Alert '%s' failed with status %d: %s",
                rule.name,
                e.response.status_code,
                e.response.text[:200],
            )
        except Exception:
            logger.exception("Failed to send alert '%s'", rule.name)


# Convenience factory functions
def create_error_alert(webhook_url: str, **kwargs: Any) -> AlertRule:
    """Create a rule that alerts on any error."""
    return AlertRule(
        name="error",
        condition=lambda run: run.error is not None,
        webhook_url=webhook_url,
        **kwargs,
    )


def create_high_cost_alert(
    webhook_url: str,
    threshold_usd: float = 1.0,
    **kwargs: Any,
) -> AlertRule:
    """Create a rule that alerts when cost exceeds threshold."""
    return AlertRule(
        name="high_cost",
        condition=lambda run: (run.total_cost_usd or 0) > threshold_usd,
        webhook_url=webhook_url,
        metadata={"threshold_usd": threshold_usd},
        **kwargs,
    )


def create_slow_trace_alert(
    webhook_url: str,
    threshold_ms: float = 30000,
    **kwargs: Any,
) -> AlertRule:
    """Create a rule that alerts when duration exceeds threshold."""
    return AlertRule(
        name="slow_trace",
        condition=lambda run: (run.duration_ms or 0) > threshold_ms,
        webhook_url=webhook_url,
        metadata={"threshold_ms": threshold_ms},
        **kwargs,
    )


def create_high_token_alert(
    webhook_url: str,
    threshold_tokens: int = 10000,
    **kwargs: Any,
) -> AlertRule:
    """Create a rule that alerts when token count exceeds threshold."""
    return AlertRule(
        name="high_tokens",
        condition=lambda run: (run.total_tokens or 0) > threshold_tokens,
        webhook_url=webhook_url,
        metadata={"threshold_tokens": threshold_tokens},
        **kwargs,
    )
