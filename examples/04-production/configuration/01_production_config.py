#!/usr/bin/env python3
"""
Production Configuration Example

Demonstrates production-ready configuration patterns including:
- Environment detection
- Privacy-first defaults (redaction enabled)
- Input exclusion for sensitive parameters
- Environment-aware exporter defaults
- Configurable processor ordering

Run: python examples/04-production/configuration/01_production_config.py
"""

import os

# =============================================================================
# Pattern 1: Environment Detection
# =============================================================================


def demo_environment_detection():
    """Demonstrate automatic environment detection."""
    print("\n" + "=" * 60)
    print("Pattern 1: Environment Detection")
    print("=" * 60)

    from agenttrace.core.env_config import detect_environment, get_environment_defaults

    # Detect environment from various indicators
    env = detect_environment()
    print(f"\nDetected environment: {env}")

    # Get environment-specific defaults
    defaults = get_environment_defaults(env)
    print(f"Default settings for '{env}': {defaults}")

    # Simulate different environments
    print("\n--- Simulating different environments ---")

    # Production (AWS Lambda)
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "my-lambda"
    env = detect_environment()
    defaults = get_environment_defaults(env)
    print(f"With AWS_LAMBDA_FUNCTION_NAME: env={env}, defaults={defaults}")
    del os.environ["AWS_LAMBDA_FUNCTION_NAME"]

    # CI environment
    os.environ["CI"] = "true"
    env = detect_environment()
    defaults = get_environment_defaults(env)
    print(f"With CI=true: env={env}, defaults={defaults}")
    del os.environ["CI"]

    # Explicit override
    os.environ["AGENTTRACE_ENVIRONMENT"] = "staging"
    env = detect_environment()
    defaults = get_environment_defaults(env)
    print(f"With AGENTTRACE_ENVIRONMENT=staging: env={env}, defaults={defaults}")
    del os.environ["AGENTTRACE_ENVIRONMENT"]


# =============================================================================
# Pattern 2: Privacy-First Defaults
# =============================================================================


def demo_privacy_first_defaults():
    """Demonstrate redaction enabled by default."""
    print("\n" + "=" * 60)
    print("Pattern 2: Privacy-First Defaults (Redaction Enabled)")
    print("=" * 60)

    from agenttrace.core.config import AgentTraceConfig, RedactionConfig

    # Default config has redaction ENABLED
    config = AgentTraceConfig()
    print(f"\nDefault redaction enabled: {config.redaction.enabled}")

    # To disable (e.g., for debugging):
    debug_config = AgentTraceConfig(redaction=RedactionConfig(enabled=False))
    print(f"Debug config redaction enabled: {debug_config.redaction.enabled}")

    # Production config with custom redaction settings
    production_config = AgentTraceConfig(
        redaction=RedactionConfig(
            enabled=True,
            allowlist=["user_id"],  # Don't redact user IDs
            custom_patterns=[r"\bAPI_KEY_\w+\b"],  # Redact custom API key patterns
        )
    )
    print(f"Production config with allowlist: {production_config.redaction.allowlist}")


# =============================================================================
# Pattern 3: Input Exclusion
# =============================================================================


def demo_input_exclusion():
    """Demonstrate excluding sensitive inputs from traces."""
    print("\n" + "=" * 60)
    print("Pattern 3: Input Exclusion for Sensitive Parameters")
    print("=" * 60)

    import agenttrace
    from agenttrace import trace_agent, trace_llm, trace_tool
    from agenttrace.core.config import AgentTraceConfig, RedactionConfig

    # Initialize runtime (disable file exporters for demo)
    runtime = agenttrace.TALRuntime(
        console=True,
        jsonl=False,
        config=AgentTraceConfig(
            redaction=RedactionConfig(enabled=False),  # Disable for clear demo
        ),
    )

    # Example 1: Exclude specific parameters
    @trace_agent(name="auth_agent", exclude_inputs=["api_key", "password"])
    def authenticate(user: str, api_key: str, password: str) -> bool:
        """Authenticate user - sensitive params are excluded from trace."""
        return True

    # Example 2: Exclude all inputs
    @trace_tool(name="secure_fetch", capture_inputs=False)
    def fetch_secure_data(credentials: dict, endpoint: str) -> dict:
        """Fetch data - no inputs captured at all."""
        return {"data": "sensitive"}

    # Example 3: LLM with excluded API key
    @trace_llm(name="llm_call", model="gpt-4", exclude_inputs=["api_key"])
    def call_llm(prompt: str, api_key: str) -> str:
        """LLM call with API key excluded."""
        return f"Response to: {prompt}"

    print("\nExecuting functions with input exclusion...")
    print("(Excluded inputs show as '[EXCLUDED]' in traces)")

    with runtime.trace_context():
        with runtime.run("input_exclusion_demo") as run:
            # These would normally log sensitive data, but inputs are excluded
            authenticate("user123", "secret-api-key", "password123")
            fetch_secure_data({"token": "secret"}, "https://api.example.com")
            call_llm("Hello!", "sk-secret-key")

    print("\nCheck the console output - sensitive parameters show as [EXCLUDED]")


# =============================================================================
# Pattern 4: Environment-Aware Mode
# =============================================================================


def demo_environment_aware_mode():
    """Demonstrate environment-aware initialization mode."""
    print("\n" + "=" * 60)
    print("Pattern 4: Environment-Aware Init Mode")
    print("=" * 60)

    # Auto mode - detects environment and sets appropriate defaults
    print("\n--- Mode: auto (default) ---")
    print("Detects environment and sets console/jsonl accordingly")
    print("  - Development: console=True, jsonl=True")
    print("  - Production: console=False, jsonl=False (OTLP recommended)")
    print("  - CI/Test: console=False, jsonl=False")

    # Local development mode
    print("\n--- Mode: local ---")
    print("Forces development defaults regardless of environment")
    print("  - console=True, jsonl=True")

    # Production mode
    print("\n--- Mode: production ---")
    print("Forces production defaults")
    print("  - console=False, jsonl=False")
    print("  - Encourages OTLP export to observability platform")

    # Example usage:
    # agenttrace.init(mode="local")       # Force local defaults
    # agenttrace.init(mode="production")  # Force production defaults
    # agenttrace.init(mode="auto")        # Detect from environment (default)


# =============================================================================
# Pattern 5: Processor Ordering
# =============================================================================


def demo_processor_ordering():
    """Demonstrate configurable processor ordering."""
    print("\n" + "=" * 60)
    print("Pattern 5: Processor Pipeline Ordering")
    print("=" * 60)

    from agenttrace.core.config import (
        AgentTraceConfig,
        ProcessorOrder,
        RedactionConfig,
        SamplingConfig,
    )
    from agenttrace.core.runtime import TALRuntime

    # SAFETY order (default): Enrich -> Redact -> Sample
    # - Redacts PII before sampling decision
    # - Best for compliance-sensitive environments
    print("\n--- SAFETY Order (default) ---")
    print("Pipeline: Enrichment -> Redaction -> Sampling")
    print("Ensures PII is redacted before any data leaves")

    safety_config = AgentTraceConfig(
        processor_order=ProcessorOrder.SAFETY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.5),
        console_enabled=False,
        jsonl_enabled=False,
    )

    safety_runtime = TALRuntime(console=False, jsonl=False, config=safety_config)
    processors = [p.name for p in safety_runtime._processors]
    print(f"Processors: {processors}")

    # EFFICIENCY order: Sample -> Redact -> Enrich
    # - Samples first to reduce processing overhead
    # - Best for high-throughput environments
    print("\n--- EFFICIENCY Order ---")
    print("Pipeline: Sampling -> Redaction -> Enrichment")
    print("Samples first to reduce processing overhead")

    efficiency_config = AgentTraceConfig(
        processor_order=ProcessorOrder.EFFICIENCY,
        redaction=RedactionConfig(enabled=True),
        sampling=SamplingConfig(rate=0.5),
        console_enabled=False,
        jsonl_enabled=False,
    )

    efficiency_runtime = TALRuntime(console=False, jsonl=False, config=efficiency_config)
    processors = [p.name for p in efficiency_runtime._processors]
    print(f"Processors: {processors}")


# =============================================================================
# Pattern 6: Custom Environment Names
# =============================================================================


def demo_custom_environments():
    """Demonstrate custom environment validation."""
    print("\n" + "=" * 60)
    print("Pattern 6: Custom Environment Names")
    print("=" * 60)

    import warnings

    # Known environments work without warning
    print("\n--- Known Environments (no warning) ---")
    known_envs = ["development", "staging", "production", "test", "local", "ci", "qa"]
    print(f"Built-in environments: {known_envs}")

    # Custom environments work but show a warning
    print("\n--- Custom Environment (shows warning) ---")
    os.environ["AGENTTRACE_ENVIRONMENT"] = "my-custom-env"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from agenttrace.core.env_config import detect_environment

        env = detect_environment()
        if w:
            print(f"Warning: {w[-1].message}")
        print(f"Environment still works: {env}")

    del os.environ["AGENTTRACE_ENVIRONMENT"]


# =============================================================================
# Pattern 7: Complete Production Setup
# =============================================================================


def demo_complete_production_setup():
    """Demonstrate a complete production-ready configuration."""
    print("\n" + "=" * 60)
    print("Pattern 7: Complete Production Setup")
    print("=" * 60)

    from agenttrace.core.config import (
        AgentTraceConfig,
        ProcessorOrder,
        RedactionConfig,
        SamplingConfig,
    )
    from agenttrace.core.runtime import TALRuntime

    # Production configuration
    production_config = AgentTraceConfig(
        service_name="my-production-agent",
        # Processor pipeline
        processor_order=ProcessorOrder.SAFETY,  # Redact before sampling
        # Privacy: Enable redaction with allowlist
        redaction=RedactionConfig(
            enabled=True,
            allowlist=["user_id", "session_id"],  # These are safe to keep
        ),
        # Sampling: Keep 10% of traces, but always keep errors
        sampling=SamplingConfig(
            rate=0.1,  # 10% sampling
            always_keep_errors=True,  # Always capture errors
            always_keep_slow=True,  # Always capture slow traces
            slow_threshold_ms=5000.0,  # 5 second threshold
        ),
        # Exporters: Disable console/jsonl in production
        console_enabled=False,
        jsonl_enabled=False,
        # Depth limit for nested steps
        max_step_depth=50,
    )

    print("\nProduction Configuration:")
    print(f"  Service name: {production_config.service_name}")
    print(f"  Processor order: {production_config.processor_order.value}")
    print(f"  Redaction enabled: {production_config.redaction.enabled}")
    print(f"  Sampling rate: {production_config.sampling.rate * 100}%")
    print(f"  Always keep errors: {production_config.sampling.always_keep_errors}")
    print(f"  Max step depth: {production_config.max_step_depth}")

    # Create runtime with config
    runtime = TALRuntime(console=False, jsonl=False, config=production_config)
    print(f"\nRuntime created with {len(runtime._processors)} processors")


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all production configuration demos."""
    print("\n" + "#" * 60)
    print("# AgentTrace Production Configuration Examples")
    print("#" * 60)

    demo_environment_detection()
    demo_privacy_first_defaults()
    demo_input_exclusion()
    demo_environment_aware_mode()
    demo_processor_ordering()
    demo_custom_environments()
    demo_complete_production_setup()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
