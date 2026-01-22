"""
Alerting system for AgentTrace.

Provides webhook alerting and quality score monitoring for production deployments.

Example:
    from agenttrace.alerting import (
        AlertingProcessor,
        AlertRule,
        SlackAlertFormatter,
        create_error_alert,
        QualityScoreProcessor,
        QualityThreshold,
        QualityMetric,
    )

    # Set up webhook alerting
    alerter = AlertingProcessor(
        rules=[
            create_error_alert("https://hooks.slack.com/..."),
            AlertRule(
                name="high_cost",
                condition=lambda run: (run.total_cost_usd or 0) > 1.0,
                webhook_url="https://hooks.slack.com/...",
                formatter=SlackAlertFormatter(),
            ),
        ]
    )

    # Set up quality monitoring
    quality_monitor = QualityScoreProcessor(
        thresholds=[
            QualityThreshold(metric=QualityMetric.FAITHFULNESS, min_value=0.8),
            QualityThreshold(metric=QualityMetric.LATENCY, max_value=5000),
        ],
        on_alert=lambda alert: print(f"Quality alert: {alert.message}"),
    )
"""

from __future__ import annotations

from agenttrace.alerting.quality import (
    QualityAlert,
    QualityMetric,
    QualityScoreAggregator,
    QualityScoreProcessor,
    QualityThreshold,
)
from agenttrace.alerting.webhooks import (
    AlertFormatter,
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

__all__ = [
    # Webhook alerting
    "AlertRule",
    "AlertingProcessor",
    "AlertFormatter",
    "GenericAlertFormatter",
    "SlackAlertFormatter",
    "PagerDutyAlertFormatter",
    # Factory functions
    "create_error_alert",
    "create_high_cost_alert",
    "create_slow_trace_alert",
    "create_high_token_alert",
    # Quality scoring
    "QualityMetric",
    "QualityThreshold",
    "QualityAlert",
    "QualityScoreProcessor",
    "QualityScoreAggregator",
]
