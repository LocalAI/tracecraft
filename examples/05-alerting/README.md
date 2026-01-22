# 05 - Alerting

> **Status: Coming Soon** - This section is planned but examples are not yet implemented.
> The alerting APIs documented here are available in the core library.

Set up monitoring and alerting for your agent systems.

## Overview

AgentTrace supports alerting through:

- **Webhook Alerts** - Send to Slack, PagerDuty, custom endpoints
- **Quality Monitoring** - Alert on quality score thresholds

## Examples

| # | Example | Description |
|---|---------|-------------|
| 1 | `01_slack_alerts.py` | Slack webhook integration |
| 2 | `02_pagerduty.py` | PagerDuty incident creation |
| 3 | `03_quality_monitoring.py` | Quality score thresholds |
| 4 | `04_custom_alerts.py` | Custom alert rules and conditions |

## Prerequisites

- Slack webhook URL or PagerDuty routing key
- `pip install httpx` (for HTTP requests)

## Slack Alerts

```python
from agenttrace.alerting import AlertingProcessor, AlertRule, SlackAlertFormatter

alerter = AlertingProcessor(
    rules=[
        AlertRule(
            name="high_cost",
            condition=lambda run: (run.total_cost_usd or 0) > 1.0,
            webhook_url=os.environ["SLACK_WEBHOOK_URL"],
            formatter=SlackAlertFormatter(channel="#alerts"),
            cooldown_seconds=300,
        ),
        AlertRule(
            name="error",
            condition=lambda run: run.error is not None,
            webhook_url=os.environ["SLACK_WEBHOOK_URL"],
            formatter=SlackAlertFormatter(channel="#errors"),
        ),
    ]
)

runtime = agenttrace.init(processors=[alerter])
```

### Slack Message Format

The `SlackAlertFormatter` produces Block Kit messages with:

- Alert severity color (red/yellow/green)
- Trace name and ID
- Cost and token counts
- Duration
- Error details (if applicable)

## PagerDuty Integration

```python
from agenttrace.alerting import AlertRule, PagerDutyAlertFormatter

alerter = AlertingProcessor(
    rules=[
        AlertRule(
            name="critical_error",
            condition=lambda run: run.error is not None,
            webhook_url="https://events.pagerduty.com/v2/enqueue",
            formatter=PagerDutyAlertFormatter(
                routing_key=os.environ["PAGERDUTY_ROUTING_KEY"],
                severity="error",
            ),
        ),
    ]
)
```

## Quality Monitoring

Monitor quality metrics from evaluation frameworks:

```python
from agenttrace.alerting import QualityScoreProcessor, QualityThreshold, QualityMetric

quality_monitor = QualityScoreProcessor(
    thresholds=[
        QualityThreshold(
            metric=QualityMetric.FAITHFULNESS,
            min_value=0.8,  # Alert if below 0.8
            window_size=20,
        ),
        QualityThreshold(
            metric=QualityMetric.LATENCY,
            max_value=5000,  # Alert if > 5 seconds
            window_size=10,
        ),
        QualityThreshold(
            metric=QualityMetric.ERROR_RATE,
            max_value=0.05,  # Alert if > 5% error rate
            window_size=100,
        ),
    ],
    on_alert=lambda alert: send_to_slack(alert),
)
```

## Built-in Alert Rules

Quick helpers for common patterns:

```python
from agenttrace.alerting import (
    create_error_alert,
    create_high_cost_alert,
    create_slow_trace_alert,
    create_high_token_alert,
)

alerter = AlertingProcessor(
    rules=[
        create_error_alert(webhook_url=slack_url),
        create_high_cost_alert(webhook_url=slack_url, threshold_usd=1.0),
        create_slow_trace_alert(webhook_url=slack_url, threshold_ms=30000),
        create_high_token_alert(webhook_url=slack_url, threshold_tokens=10000),
    ]
)
```

## Cooldown and Deduplication

Prevent alert flooding:

```python
AlertRule(
    name="error",
    condition=lambda run: run.error is not None,
    webhook_url=slack_url,
    cooldown_seconds=300,  # Only alert once per 5 minutes per rule
)
```

## Custom Alert Conditions

Define complex conditions:

```python
def is_suspicious(run: AgentRun) -> bool:
    """Detect suspicious patterns."""
    # High token usage with low cost (possible misconfiguration)
    if (run.total_tokens or 0) > 10000 and (run.total_cost_usd or 0) < 0.01:
        return True
    # Very long duration with few steps
    if (run.duration_ms or 0) > 60000 and len(run.steps) < 3:
        return True
    return False

AlertRule(
    name="suspicious_activity",
    condition=is_suspicious,
    webhook_url=slack_url,
)
```

## Testing Alerts

Test your alert configuration:

```python
# Create a test run that triggers alerts
test_run = AgentRun(
    name="test_alert",
    error="Test error",
    total_cost_usd=2.0,
)

alerter.process(test_run)  # Should trigger alerts
```

## Next Steps

- [06-evaluation/](../06-evaluation/) - Set up quality metrics
- [04-production/](../04-production/) - Production deployment patterns
