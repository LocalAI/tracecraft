#!/usr/bin/env python3
"""Configuration - All AgentTrace configuration options.

Learn how to configure AgentTrace using environment variables,
configuration objects, and runtime settings.

Prerequisites:
    - AgentTrace installed (pip install agenttrace)
    - Completed previous getting-started examples

Environment Variables:
    - All AGENTTRACE_* variables demonstrated in this example

External Services:
    - None required

Usage:
    python examples/01-getting-started/04_configuration.py

    # Or with environment variables:
    AGENTTRACE_SERVICE_NAME=my-app python examples/01-getting-started/04_configuration.py

Expected Output:
    - Demonstration of various configuration patterns
    - Shows how env vars and code config interact
"""

from __future__ import annotations

import os

import agenttrace
from agenttrace.core.config import (
    AgentTraceConfig,
    ExporterConfig,
    RedactionConfig,
    SamplingConfig,
    load_config,
    load_config_from_env,
)
from agenttrace.instrumentation.decorators import trace_llm

# ============================================================================
# Pattern 1: Default Configuration
# ============================================================================


def demo_default_config() -> None:
    """Demonstrate default configuration.

    By default, AgentTrace enables:
    - Console output (rich tree view)
    - JSONL file output (traces/agenttrace.jsonl)
    - No sampling (all traces captured)
    - PII redaction ENABLED (privacy-first default)
    - No OTLP export

    Note: Redaction is enabled by default for privacy compliance.
    To disable: RedactionConfig(enabled=False)
    """
    print("\n--- Pattern 1: Default Configuration ---")

    runtime = agenttrace.init()

    @trace_llm(name="demo_llm", model="gpt-4o-mini")
    def demo_call(prompt: str) -> str:
        return f"Response: {prompt}"

    with runtime.run("default_config_demo"):
        demo_call("Testing default config")

    print("Default config: console=True, jsonl=True")


# ============================================================================
# Pattern 2: Init Parameters
# ============================================================================


def demo_init_params() -> None:
    """Demonstrate configuration via init() parameters.

    The simplest way to configure AgentTrace is through init():
    """
    print("\n--- Pattern 2: Init Parameters ---")

    runtime = agenttrace.init(
        # Exporter settings
        console=True,  # Enable console output
        jsonl=True,  # Enable JSONL output
        jsonl_path="traces/custom.jsonl",  # Custom JSONL path
        # Note: More settings available via config object (see Pattern 4)
    )

    @trace_llm(name="demo_llm", model="gpt-4o-mini")
    def demo_call(prompt: str) -> str:
        return f"Response: {prompt}"

    with runtime.run("init_params_demo"):
        demo_call("Testing init params")

    print("Configured via init() parameters")


# ============================================================================
# Pattern 3: Environment Variables
# ============================================================================


def demo_env_variables() -> None:
    """Demonstrate configuration via environment variables.

    AgentTrace reads these environment variables:

    Core Settings:
        AGENTTRACE_SERVICE_NAME     - Service name for traces (default: "agenttrace")
        AGENTTRACE_CONSOLE_ENABLED  - Enable console output (default: true)
        AGENTTRACE_JSONL_ENABLED    - Enable JSONL output (default: true)
        AGENTTRACE_JSONL_PATH       - Path for JSONL file

    OTLP Export:
        AGENTTRACE_OTLP_ENABLED     - Enable OTLP export (default: false)
        AGENTTRACE_OTLP_ENDPOINT    - OTLP collector endpoint

    Processing:
        AGENTTRACE_SAMPLING_RATE       - Sampling rate 0.0-1.0 (default: 1.0)
        AGENTTRACE_SAMPLING_KEEP_ERRORS - Always keep error traces (default: true)
        AGENTTRACE_REDACTION_ENABLED   - Enable PII redaction (default: TRUE - privacy first!)

    Environment Detection:
        AGENTTRACE_ENVIRONMENT         - Explicit environment name (development, staging, production, etc.)
    """
    print("\n--- Pattern 3: Environment Variables ---")

    # Show current environment
    print("\nCurrent AGENTTRACE_* environment variables:")
    for key, value in sorted(os.environ.items()):
        if key.startswith("AGENTTRACE_"):
            print(f"  {key}={value}")

    # Load config from environment
    config = load_config_from_env()
    print(f"\nLoaded config: service_name={config.service_name}")
    print(f"  console_enabled={config.console_enabled}")
    print(f"  jsonl_enabled={config.jsonl_enabled}")
    print(f"  sampling.rate={config.sampling.rate}")

    # Example: Set environment variables programmatically
    print("\nExample: Setting env vars programmatically")
    os.environ["AGENTTRACE_SERVICE_NAME"] = "demo-service"
    os.environ["AGENTTRACE_SAMPLING_RATE"] = "0.5"

    # Reload config to pick up changes
    config = load_config_from_env()
    print("  After setting env vars:")
    print(f"  service_name={config.service_name}")
    print(f"  sampling.rate={config.sampling.rate}")

    # Clean up
    del os.environ["AGENTTRACE_SERVICE_NAME"]
    del os.environ["AGENTTRACE_SAMPLING_RATE"]


# ============================================================================
# Pattern 4: Configuration Object
# ============================================================================


def demo_config_object() -> None:
    """Demonstrate configuration via AgentTraceConfig object.

    For full control, create a configuration object directly:
    """
    print("\n--- Pattern 4: Configuration Object ---")

    # Create config with nested configurations
    config = AgentTraceConfig(
        service_name="my-production-service",
        console_enabled=True,
        jsonl_enabled=True,
        jsonl_path="traces/production.jsonl",
        # Sampling configuration
        sampling=SamplingConfig(
            rate=0.5,  # Sample 50% of traces
            always_keep_errors=True,  # But always keep errors
            always_keep_slow=True,  # And slow traces
            slow_threshold_ms=5000,  # > 5 seconds is slow
        ),
        # Redaction configuration
        redaction=RedactionConfig(
            enabled=True,  # Enable PII redaction
            # mode=RedactionMode.MASK,  # or HASH, REMOVE
            custom_patterns=[  # Custom regex patterns
                r"sk-[a-zA-Z0-9]+",  # OpenAI API keys
            ],
            allowlist=["test@example.com"],  # Never redact these
        ),
        # Exporter configuration
        exporter=ExporterConfig(
            console_enabled=True,
            console_verbose=False,
            jsonl_enabled=True,
            jsonl_path="traces/production.jsonl",
            otlp_enabled=False,  # Would need OTLP collector
            # otlp_endpoint="http://localhost:4317",
        ),
    )

    print("Config object created:")
    print(f"  service_name: {config.service_name}")
    print(f"  sampling.rate: {config.sampling.rate}")
    print(f"  redaction.enabled: {config.redaction.enabled}")

    # Use with init() via config parameter
    runtime = agenttrace.init(
        console=config.console_enabled,
        jsonl=config.jsonl_enabled,
        jsonl_path=config.jsonl_path,
        # config=config,  # Full config support (coming soon)
    )

    @trace_llm(name="demo_llm", model="gpt-4o-mini")
    def demo_call(prompt: str) -> str:
        return f"Response: {prompt}"

    with runtime.run("config_object_demo"):
        demo_call("Testing config object")


# ============================================================================
# Pattern 5: Load Config with Overrides
# ============================================================================


def demo_config_overrides() -> None:
    """Demonstrate loading config with overrides.

    Use load_config() to load from env and override specific values:
    """
    print("\n--- Pattern 5: Config with Overrides ---")

    # Load from env, but override specific values
    config = load_config(
        service_name="override-service",  # Override this
        # Other values come from environment
    )

    print("Config with overrides:")
    print(f"  service_name: {config.service_name} (overridden)")
    print(f"  console_enabled: {config.console_enabled} (from env/default)")


# ============================================================================
# Pattern 6: Conditional Configuration
# ============================================================================


def demo_conditional_config() -> None:
    """Demonstrate conditional configuration based on environment.

    A common pattern is to configure differently for dev/staging/prod:
    """
    print("\n--- Pattern 6: Conditional Configuration ---")

    env = os.environ.get("APP_ENV", "development")

    if env == "production":
        config = AgentTraceConfig(
            service_name="my-app-prod",
            console_enabled=False,  # No console in prod
            jsonl_enabled=True,
            sampling=SamplingConfig(
                rate=0.1,  # Sample 10% in prod
                always_keep_errors=True,
            ),
            redaction=RedactionConfig(
                enabled=True,  # Always redact in prod
            ),
        )
    elif env == "staging":
        config = AgentTraceConfig(
            service_name="my-app-staging",
            console_enabled=True,
            jsonl_enabled=True,
            sampling=SamplingConfig(
                rate=0.5,  # Sample 50% in staging
            ),
        )
    else:  # development
        config = AgentTraceConfig(
            service_name="my-app-dev",
            console_enabled=True,
            jsonl_enabled=True,
            sampling=SamplingConfig(
                rate=1.0,  # Capture all in dev
            ),
        )

    print(f"Environment: {env}")
    print(f"  service_name: {config.service_name}")
    print(f"  console_enabled: {config.console_enabled}")
    print(f"  sampling.rate: {config.sampling.rate}")
    print(f"  redaction.enabled: {config.redaction.enabled}")


# ============================================================================
# Pattern 7: Privacy-First Redaction Defaults
# ============================================================================


def demo_redaction_defaults() -> None:
    """Demonstrate privacy-first redaction defaults.

    As of version 0.2.0, redaction is ENABLED by default for privacy compliance.
    This means PII like emails, phone numbers, and credit cards are automatically
    masked in traces.

    To disable redaction (e.g., for debugging):
    - Set AGENTTRACE_REDACTION_ENABLED=false
    - Or use RedactionConfig(enabled=False)
    """
    print("\n--- Pattern 7: Privacy-First Redaction Defaults ---")

    # Default: redaction is ON
    default_config = AgentTraceConfig()
    print(f"\nDefault redaction enabled: {default_config.redaction.enabled}")
    print("  (Privacy-first default - PII is automatically masked)")

    # To disable for debugging
    debug_config = AgentTraceConfig(redaction=RedactionConfig(enabled=False))
    print(f"\nDebug redaction enabled: {debug_config.redaction.enabled}")
    print("  (Explicitly disabled for debugging)")

    # Custom allowlist
    custom_config = AgentTraceConfig(
        redaction=RedactionConfig(
            enabled=True,
            allowlist=["user_id", "session_id"],  # Safe to keep
            allowlist_patterns=[r"^demo_"],  # Safe prefixes
        )
    )
    print(f"\nCustom allowlist: {custom_config.redaction.allowlist}")


# ============================================================================
# Pattern 8: Input Exclusion for Sensitive Parameters
# ============================================================================


def demo_input_exclusion() -> None:
    """Demonstrate excluding sensitive inputs from traces.

    Decorators support input exclusion for sensitive parameters:
    - exclude_inputs: List of parameter names to exclude
    - capture_inputs: Set to False to capture no inputs at all

    Excluded parameters show as "[EXCLUDED]" in traces.
    """
    print("\n--- Pattern 8: Input Exclusion ---")

    from agenttrace.instrumentation.decorators import trace_agent, trace_llm, trace_tool

    # Example 1: Exclude specific parameters
    @trace_agent(name="auth_agent", exclude_inputs=["api_key", "password"])
    def authenticate(user: str, api_key: str, password: str) -> bool:
        """Auth function - api_key and password excluded from trace."""
        return True

    print("\n1. Exclude specific parameters:")
    print("   @trace_agent(exclude_inputs=['api_key', 'password'])")
    print("   -> Sensitive params show as '[EXCLUDED]'")

    # Example 2: Exclude all inputs
    @trace_tool(name="secure_fetch", capture_inputs=False)
    def fetch_secure(credentials: dict, url: str) -> dict:
        """Fetch function - no inputs captured at all."""
        return {"data": "result"}

    print("\n2. Exclude all inputs:")
    print("   @trace_tool(capture_inputs=False)")
    print("   -> No input data captured in trace")

    # Example 3: LLM with excluded API key
    @trace_llm(name="llm_call", model="gpt-4", exclude_inputs=["api_key"])
    def call_llm(prompt: str, api_key: str) -> str:
        """LLM call - api_key excluded."""
        return f"Response: {prompt}"

    print("\n3. LLM with excluded API key:")
    print("   @trace_llm(model='gpt-4', exclude_inputs=['api_key'])")


# ============================================================================
# Pattern 9: Configuration Summary
# ============================================================================


def print_config_reference() -> None:
    """Print a complete configuration reference."""
    print("\n--- Configuration Reference ---")
    print("""
Environment Variables:
  AGENTTRACE_SERVICE_NAME         Service name (default: "agenttrace")
  AGENTTRACE_CONSOLE_ENABLED      Console output (default: true)
  AGENTTRACE_JSONL_ENABLED        JSONL output (default: true)
  AGENTTRACE_JSONL_PATH           JSONL file path
  AGENTTRACE_OTLP_ENABLED         OTLP export (default: false)
  AGENTTRACE_OTLP_ENDPOINT        OTLP endpoint
  AGENTTRACE_SAMPLING_RATE        Sampling rate 0.0-1.0 (default: 1.0)
  AGENTTRACE_SAMPLING_KEEP_ERRORS Keep error traces (default: true)
  AGENTTRACE_REDACTION_ENABLED    PII redaction (default: TRUE!)
  AGENTTRACE_ENVIRONMENT          Environment name (auto-detected if not set)

Config Classes:
  AgentTraceConfig  - Main configuration container
  ExporterConfig    - Exporter settings
  SamplingConfig    - Sampling settings
  RedactionConfig   - PII redaction settings (enabled by default!)

Common Patterns:
  1. Default           - agenttrace.init()
  2. Init params       - agenttrace.init(console=True, jsonl=True, ...)
  3. Environment vars  - Set AGENTTRACE_* vars
  4. Config object     - AgentTraceConfig(...)
  5. With overrides    - load_config(service_name="override")
  6. Conditional       - Different configs per environment
  7. Redaction         - Enabled by default, disable for debugging
  8. Input exclusion   - @trace_agent(exclude_inputs=['password'])

Decorator Input Exclusion:
  @trace_agent(exclude_inputs=['api_key'])  - Exclude specific params
  @trace_agent(capture_inputs=False)        - Exclude all inputs
""")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Run the configuration example."""
    print("=" * 60)
    print("AgentTrace Configuration Example")
    print("=" * 60)

    demo_default_config()
    demo_init_params()
    demo_env_variables()
    demo_config_object()
    demo_config_overrides()
    demo_conditional_config()
    demo_redaction_defaults()
    demo_input_exclusion()
    print_config_reference()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Try 02-frameworks/ for LLM framework integrations")
    print("- Try 03-exporters/ for export options")
    print("- Try 04-production/ for production patterns")


if __name__ == "__main__":
    main()
