#!/usr/bin/env python3
"""
Claude Agent SDK - Production Configuration

Demonstrates production-ready configuration patterns for tracing
Claude agents with TraceCraft.

This example shows:
- Environment-aware configuration
- Sampling for high-throughput
- PII redaction
- JSONL export for analysis
- Error handling

Prerequisites:
    - pip install tracecraft claude-code-sdk
    - ANTHROPIC_API_KEY environment variable

Usage:
    python examples/02-frameworks/claude_sdk/03_production_config.py
"""

from __future__ import annotations

import asyncio
import os

from tracecraft import TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from tracecraft.core.config import (
    ProcessorOrder,
    RedactionConfig,
    SamplingConfig,
    TraceCraftConfig,
)


def create_production_runtime() -> tuple[TraceCraftRuntime, TraceCraftConfig]:
    """Create a production-optimized runtime.

    Returns:
        Tuple of (runtime, config) for access to configuration settings.
    """
    config = TraceCraftConfig(
        service_name="claude-agent-production",
        # Processor ordering: redact PII before sampling decision
        processor_order=ProcessorOrder.SAFETY,
        # Enable PII redaction (emails, phone numbers, etc.)
        redaction=RedactionConfig(
            enabled=True,
            allowlist=["user_id", "session_id"],  # Safe to keep
        ),
        # Sample 10% in production, but keep all errors
        sampling=SamplingConfig(
            rate=0.1,  # 10%
            always_keep_errors=True,
            always_keep_slow=True,
            slow_threshold_ms=5000.0,  # 5 seconds
        ),
        # Disable console in production, enable JSONL
        console_enabled=False,
        jsonl_enabled=True,
        jsonl_path="traces/claude_agent.jsonl",
    )

    runtime = TraceCraftRuntime(
        console=config.console_enabled,
        jsonl=config.jsonl_enabled,
        jsonl_path=config.jsonl_path,
        config=config,
    )
    return runtime, config


def create_development_runtime() -> tuple[TraceCraftRuntime, TraceCraftConfig]:
    """Create a development-optimized runtime.

    Returns:
        Tuple of (runtime, config) for access to configuration settings.
    """
    config = TraceCraftConfig(
        service_name="claude-agent-dev",
        # Full capture in development
        sampling=SamplingConfig(rate=1.0),
        # Disable redaction for debugging
        redaction=RedactionConfig(enabled=False),
        # Console output for development
        console_enabled=True,
        jsonl_enabled=True,
    )

    runtime = TraceCraftRuntime(
        console=config.console_enabled,
        jsonl=config.jsonl_enabled,
        config=config,
    )
    return runtime, config


async def main() -> None:
    """Run example with environment-aware configuration."""
    # Select runtime based on environment
    env = os.environ.get("APP_ENV", "development")

    if env == "production":
        runtime, config = create_production_runtime()
        print("Using PRODUCTION configuration")
    else:
        runtime, config = create_development_runtime()
        print("Using DEVELOPMENT configuration")

    tracer = ClaudeTraceCraftr(runtime=runtime)

    print("\nConfiguration:")
    print(f"  Service: {config.service_name}")
    print(f"  Sampling: {config.sampling.rate * 100}%")
    print(f"  Redaction: {config.redaction.enabled}")
    print(f"  Console: {config.console_enabled}")
    print(f"  JSONL: {config.jsonl_enabled}")
    print("=" * 60)

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nSet ANTHROPIC_API_KEY to run with Claude SDK")
        print("\nConfiguration patterns demonstrated above can be used with:")
        print_usage_example()
        return

    try:
        from claude_code_sdk import query
    except ImportError:
        print("\nInstall claude-code-sdk: pip install claude-code-sdk")
        print("\nConfiguration patterns demonstrated above can be used with:")
        print_usage_example()
        return

    with runtime.run("production_task") as run:
        try:
            async for message in query(
                prompt="List files in the current directory",
                options=tracer.get_options(
                    allowed_tools=["Glob"],
                    max_turns=3,
                ),
            ):
                if hasattr(message, "content"):
                    print(message.content)
        except Exception as e:
            # Errors are captured in trace
            print(f"Error: {e}")
            run.error_count += 1

    print("=" * 60)
    print("\nRun completed:")
    print(f"  Steps: {len(run.steps)}")
    print(f"  Errors: {run.error_count}")
    print(f"  Duration: {run.duration_ms:.0f}ms")

    if config.jsonl_enabled:
        print(f"\nTrace exported to: {config.jsonl_path}")


def print_usage_example() -> None:
    """Print usage example."""
    print(
        """
```python
from tracecraft import TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

# Production configuration
runtime = create_production_runtime()
tracer = ClaudeTraceCraftr(runtime=runtime)

with runtime.run("task_name") as run:
    async for message in query(
        prompt="Your prompt",
        options=tracer.get_options(allowed_tools=["Read", "Glob"])
    ):
        print(message)
```

Configuration Options:
----------------------

ProcessorOrder.SAFETY (default):
  - Enrichment -> Redaction -> Sampling
  - PII is always redacted before sampling decision
  - Use for compliance-sensitive environments

ProcessorOrder.EFFICIENCY:
  - Sampling -> Redaction -> Enrichment
  - Samples first to reduce processing overhead
  - Use for high-throughput, cost-sensitive environments

SamplingConfig:
  - rate: 0.0-1.0 (percentage of traces to keep)
  - always_keep_errors: True to keep all error traces
  - always_keep_slow: True to keep slow traces
  - slow_threshold_ms: Threshold for "slow" traces

RedactionConfig:
  - enabled: True to redact PII (emails, phones, etc.)
  - allowlist: Fields to never redact
  - custom_patterns: Additional regex patterns to redact
"""
    )


if __name__ == "__main__":
    asyncio.run(main())
