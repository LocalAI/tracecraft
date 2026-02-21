# Security Guide

Trace Craft follows a security-first design philosophy: sensitive data is protected by default, not as an afterthought. This guide covers PII redaction, credential handling, compliance considerations, and best practices for operating Trace Craft in security-conscious environments.

---

## Overview

### Security-First Design Philosophy

Trace Craft makes safe behavior the default:

- **PII redaction is enabled by default.** You must explicitly disable it.
- **17 built-in patterns** cover the most common credential and PII types out of the box.
- **No data leaves your infrastructure** unless you configure an exporter to send it somewhere.
- **Redaction runs before export** in the default `SAFETY` processor order.

### What Is Protected by Default

Out of the box, with no configuration changes, Trace Craft redacts:

- Email addresses
- Phone numbers
- Credit card numbers
- Social Security Numbers (SSN)
- API keys for OpenAI, Anthropic, AWS, GitHub, Google, Azure, Stripe, Slack
- Bearer tokens and JWT patterns
- Private key headers (PEM format)
- Generic `api_key=` and `password=` parameter patterns

---

## PII Redaction

### 17 Built-in Patterns

The following patterns are included in `DEFAULT_RULES` and are active when `RedactionConfig(enabled=True)` (the default):

| Pattern Name | Matches | Example |
|---|---|---|
| `email` | RFC 5321 email addresses | `user@example.com` |
| `phone` | US/international phone numbers | `+1-555-123-4567`, `(555) 123-4567` |
| `credit_card` | 16-digit card numbers | `4111 1111 1111 1111` |
| `ssn` | US Social Security Numbers | `123-45-6789` |
| `openai_api_key` | OpenAI API keys (`sk-...`) | `sk-abc123...` |
| `anthropic_api_key` | Anthropic API keys (`sk-ant-...`) | `sk-ant-abc123...` |
| `aws_access_key` | AWS Access Key IDs (`AKIA...`) | `AKIAIOSFODNN7EXAMPLE` |
| `aws_secret_key` | AWS Secret Access Keys (40-char) | `wJalrXUtnFEMI/K7MDENG/...` |
| `bearer_token` | Bearer/JWT tokens | `Bearer eyJhbGci...` |
| `github_token` | GitHub personal access tokens | `ghp_abc123...` |
| `google_api_key` | Google API keys (`AIza...`) | `AIzaSy...` |
| `azure_connection_string` | Azure storage connection strings | `AccountKey=abc123...` |
| `generic_api_key_param` | `api_key=` URL/config params | `api_key=abc123` |
| `private_key` | PEM private key headers | `-----BEGIN RSA PRIVATE KEY-----` |
| `slack_token` | Slack bot/user tokens | `xoxb-123...` |
| `stripe_key` | Stripe API keys | `sk_live_abc123`, `pk_test_...` |
| `password_field` | `password=`, `secret=`, `token=` patterns | `password=mysecret` |

### Redaction Modes

Three modes control what happens when a pattern is matched:

=== "MASK (default)"

    Replace matched text with `[REDACTED]`. Preserves structure while hiding values.

    ```python
    from tracecraft.core.config import RedactionConfig
    from tracecraft.processors.redaction import RedactionMode

    config = RedactionConfig(
        enabled=True,
        mode=RedactionMode.MASK,  # -> [REDACTED]
    )
    ```

    Before: `"Contact user@example.com for support"`
    After:  `"Contact [REDACTED] for support"`

=== "HASH"

    Replace matched text with a truncated SHA-256 hex digest. Useful for correlation without exposing the original value.

    ```python
    config = RedactionConfig(
        enabled=True,
        mode=RedactionMode.HASH,  # -> [HASH:a1b2c3d4e5f6g7h8]
    )
    ```

    Before: `"sk-abc123..."`
    After:  `"[HASH:3d4e7a1b2c5f6890]"`

=== "REMOVE"

    Delete the matched text entirely. Use when even the presence of a placeholder is undesirable.

    ```python
    config = RedactionConfig(
        enabled=True,
        mode=RedactionMode.REMOVE,  # -> ""
    )
    ```

    Before: `"Contact user@example.com for support"`
    After:  `"Contact  for support"`

### Configuration

Enable redaction via `TraceCraftConfig`:

```python
import tracecraft
from tracecraft.core.config import TraceCraftConfig, RedactionConfig
from tracecraft.processors.redaction import RedactionMode

config = TraceCraftConfig(
    redaction=RedactionConfig(
        enabled=True,             # Default: True
        mode=RedactionMode.MASK,  # Default: MASK
    ),
)

runtime = tracecraft.init(config=config)
```

Or via environment variable:

```bash
TRACECRAFT_REDACTION_ENABLED=true
```

---

## Custom Redaction Rules

### Pattern-Based Rules

Add custom regex patterns to catch domain-specific sensitive data:

```python
from tracecraft.core.config import TraceCraftConfig, RedactionConfig
from tracecraft.processors.redaction import RedactionRule

# Redact internal employee IDs (format: EMP-XXXXXX)
employee_id_rule = RedactionRule(
    name="employee_id",
    pattern=r"EMP-\d{6}",
)

# Redact internal session tokens (format: sess_<uuid>)
session_token_rule = RedactionRule(
    name="session_token",
    pattern=r"sess_[a-f0-9]{32}",
)

config = TraceCraftConfig(
    redaction=RedactionConfig(
        enabled=True,
        custom_patterns=[
            r"EMP-\d{6}",
            r"sess_[a-f0-9]{32}",
        ],
    ),
)
```

Patterns are compiled as Python `re` patterns and applied to all string values in the trace dict.

!!! warning "ReDoS Safety"
    Avoid patterns with nested quantifiers or catastrophic backtracking characteristics. Trace Craft's built-in patterns are designed to be ReDoS-safe, and custom patterns should be too. Test patterns with tools like `regexr.com` or Python's `re` module before deploying.

### Field-Based Rules

Redact entire fields by path rather than scanning content. This is faster and guarantees the field is always masked regardless of its value.

```python
from tracecraft.processors.redaction import RedactionRule, RedactionProcessor

# Always mask these fields regardless of content
sensitive_fields = RedactionRule(
    name="sensitive_fields",
    field_paths=[
        "api_key",
        "credentials.password",
        "auth.token",
        "user.ssn",
    ],
)

# Use RedactionProcessor directly for advanced configuration
processor = RedactionProcessor(
    include_defaults=True,   # Keep the 17 built-in patterns
    rules=[sensitive_fields],
)
```

Field paths use dot notation to match nested dict keys. Both the full path (`credentials.password`) and the leaf key (`password`) are checked.

### Allowlisting

Prevent specific values or patterns from being redacted. Useful when legitimate test data matches a built-in pattern.

```python
from tracecraft.core.config import RedactionConfig

config = RedactionConfig(
    enabled=True,
    # Exact values that should never be redacted
    allowlist=[
        "test@example.com",       # Test email used in documentation
        "sk-test-placeholder",    # Literal placeholder in templates
    ],
    # Regex patterns for values to never redact
    allowlist_patterns=[
        r"example\.com$",         # Any example.com domain
        r"AKIA_TEST_[A-Z]+",      # Test AWS key IDs
    ],
)
```

Allowlist matching uses `fullmatch` — the entire string must match the pattern, not just a prefix.

---

## Credential Handling

### Excluding Inputs at the Decorator Level

The safest approach is to never capture sensitive inputs in the first place. Use `exclude_inputs` to mark parameters as excluded:

```python
import tracecraft

@tracecraft.trace_llm(
    name="llm_call",
    model="gpt-4",
    provider="openai",
    exclude_inputs=["api_key"],   # api_key appears as "[EXCLUDED]" in trace
)
def call_llm(prompt: str, api_key: str) -> str:
    return openai_client.chat(prompt, api_key=api_key)
```

Excluded parameters are recorded as `"[EXCLUDED]"` so you can see the parameter was passed without seeing its value.

### Disabling Input Capture Entirely

For functions that only handle credentials or where inputs are irrelevant:

```python
@tracecraft.trace_tool(
    name="auth_service",
    capture_inputs=False,   # No inputs captured at all
)
def authenticate(username: str, password: str) -> bool:
    return auth_backend.verify(username, password)
```

### Best Practices for API Keys

- Store API keys in environment variables or a secrets manager, never in source code.
- Use `exclude_inputs=["api_key", "secret_key", "token"]` on any function that receives credentials as parameters.
- For service-to-service calls, prefer `capture_inputs=False` on the entire function rather than maintaining an exclusion list.
- Audit your traces periodically to verify no credentials appear even with redaction enabled.

---

## Compliance Considerations

Trace Craft provides tools to help meet compliance requirements, but compliance is the responsibility of your organization. This section outlines common patterns.

### GDPR

The General Data Protection Regulation requires data minimization and provides individuals the right to erasure.

**Data Minimization:**

```python
from tracecraft.core.config import TraceCraftConfig, RedactionConfig, SamplingConfig

# Collect only what you need
config = TraceCraftConfig(
    redaction=RedactionConfig(enabled=True),
    sampling=SamplingConfig(rate=0.1),  # Only keep 10% of traces
)
```

Use `capture_inputs=False` on any function that processes user-provided content if you do not need those inputs for debugging.

**Right to Erasure:**

For GDPR erasure requests, traces stored in SQLite can be deleted by trace ID. If using JSONL storage, traces are immutable after write; implement a retention policy to delete files after the retention window expires.

**Cross-Border Transfers:**

If exporting to cloud-based backends (OTLP, MLflow), verify the endpoint is in a compliant region before enabling it. Use `otlp_endpoint` to point to a region-local collector.

### HIPAA

The Health Insurance Portability and Accountability Act requires protection of PHI (Protected Health Information).

**PHI Handling:**

PHI includes names, dates, phone numbers, geographic data, social security numbers, and other identifiers. Trace Craft's built-in patterns cover several of these (phone, SSN, email), but you should add custom rules for domain-specific identifiers:

```python
from tracecraft.processors.redaction import RedactionRule
from tracecraft.core.config import RedactionConfig

phi_rules = [
    RedactionRule(name="mrn", pattern=r"MRN-\d{8,12}"),      # Medical Record Number
    RedactionRule(name="npi", pattern=r"\bNPI:\s*\d{10}\b"),  # National Provider ID
    RedactionRule(name="dob", pattern=r"\b\d{1,2}/\d{1,2}/\d{4}\b"),  # Dates of birth
]

config = RedactionConfig(
    enabled=True,
    custom_patterns=[r.pattern for r in phi_rules if r.pattern],
)
```

Store PHI traces in on-premises storage only. Do not use cloud-based OTLP endpoints for PHI unless the provider has a signed BAA.

### SOC 2

SOC 2 Type II audits require evidence of access controls, audit logging, and data protection.

**Audit Logging:**

Every trace includes `start_time`, `end_time`, `name`, and `session_id`. Use `user_id` on runs to tie traces to specific users for audit trails:

```python
with runtime.run("agent_task", user_id="user-12345", session_id="sess-abc") as run:
    result = process_request(request)
```

**Access Controls:**

Restrict access to the JSONL or SQLite storage files using filesystem permissions. For shared environments, use per-tenant runtimes with separate storage backends.

---

## Data Retention

### Trace Lifecycle

A trace's lifecycle:

1. **Created** — `start_run()` creates the `AgentRun` object in memory.
2. **Enriched/Redacted/Sampled** — Processor pipeline runs at `end_run()`.
3. **Exported** — Written to JSONL, SQLite, or sent to OTLP endpoint.
4. **Retained** — Stored according to your retention policy.
5. **Deleted** — Removed after the retention window expires.

### Retention Recommendations by Environment

| Environment | Recommended Retention | Rationale |
|---|---|---|
| Development | 7 days | Short-lived, for immediate debugging |
| Staging | 30 days | Enough for regression analysis |
| Production | 90-365 days | Compliance, incident investigation |
| HIPAA/PCI | As required by regulation | Typically 6-7 years |

### Storage Backend Security

=== "JSONL"

    - Set file permissions to `600` (owner read/write only).
    - Use a dedicated directory with restricted access.
    - Rotate files daily or weekly; delete old files per retention policy.
    - Never commit JSONL trace files to version control.

    ```bash
    chmod 600 traces/tracecraft.jsonl
    chmod 700 traces/
    ```

=== "SQLite"

    - Apply the same filesystem permissions as JSONL.
    - Enable WAL mode for better concurrent access: `SQLiteTraceStore(path, wal_mode=True)`.
    - Back up with `sqlite3 traces.db .dump | gzip > backup.sql.gz`.
    - Delete rows past the retention window: `DELETE FROM traces WHERE start_time < datetime('now', '-90 days')`.

=== "MLflow"

    - Secure the MLflow tracking server with authentication.
    - Use TLS on the tracking server endpoint.
    - Configure MLflow's artifact store with appropriate IAM policies.

---

## Secure Exporter Configuration

### OTLP with TLS

Always use TLS for OTLP connections to external collectors:

```python
from tracecraft.exporters.otlp import OTLPExporter

# HTTPS endpoint with bearer token authentication
exporter = OTLPExporter(
    endpoint="https://otel-collector.internal:4317",
    headers={
        "Authorization": "Bearer my-secret-token",
        "X-Tenant-ID": "tenant-abc",
    },
)
```

### Authentication Headers

Load credentials from environment variables, not source code:

```python
import os
from tracecraft.exporters.otlp import OTLPExporter

exporter = OTLPExporter(
    endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    headers={
        "Authorization": f"Bearer {os.environ['OTEL_AUTH_TOKEN']}",
    },
)
```

Standard OpenTelemetry environment variables are also supported:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com:4317
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer mytoken
```

### mTLS Considerations

For mutual TLS (where the client also presents a certificate), configure your OTLP endpoint URL to use the `https://` scheme and provide the appropriate certificates through your HTTP client configuration. The specific mechanism depends on your OTLP library; consult the `opentelemetry-exporter-otlp-proto-grpc` documentation for gRPC mTLS setup.

---

## Access Control Patterns

### Multi-Tenant Isolation

Use separate runtime instances to enforce tenant isolation. Each runtime can have its own storage backend and configuration:

```python
import tracecraft
from tracecraft.core.config import TraceCraftConfig
from tracecraft.storage.sqlite import SQLiteTraceStore

def create_tenant_runtime(tenant_id: str) -> tracecraft.TALRuntime:
    """Create an isolated runtime for a tenant."""
    store = SQLiteTraceStore(f"traces/{tenant_id}.db")
    config = TraceCraftConfig(service_name=f"service-{tenant_id}")
    return tracecraft.TALRuntime(
        console=False,
        jsonl=False,
        config=config,
        storage=store,
    )

tenant_a = create_tenant_runtime("tenant-a")
tenant_b = create_tenant_runtime("tenant-b")

# Each tenant's traces go to their own isolated database
with tenant_a.trace_context():
    with tenant_a.run("agent_task") as run:
        process_tenant_a()

with tenant_b.trace_context():
    with tenant_b.run("agent_task") as run:
        process_tenant_b()
```

### Role-Based Access

Trace Craft does not implement RBAC directly; access control is enforced at the storage layer:

- **JSONL files:** Use filesystem ACLs to restrict read access.
- **SQLite:** Use filesystem permissions per database file.
- **MLflow:** Use MLflow's experiment-level access controls.
- **OTLP backends (Jaeger, Grafana Tempo, etc.):** Use the backend's native RBAC.

### Audit Logging

Attach user and session identifiers to every run for audit trails:

```python
from functools import wraps
import tracecraft

def with_audit_context(user_id: str, session_id: str):
    """Decorator that attaches audit context to every run."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            runtime = tracecraft.get_runtime()
            with runtime.run(
                name=func.__name__,
                user_id=user_id,
                session_id=session_id,
            ) as run:
                return func(*args, **kwargs)
        return wrapper
    return decorator
```

---

## Security Checklist for Production

Use this checklist before deploying Trace Craft to a production environment:

- [ ] **Redaction enabled.** `RedactionConfig(enabled=True)` is the default; verify it has not been disabled.
- [ ] **Sensitive parameters excluded.** All functions accepting API keys, passwords, or tokens use `exclude_inputs` or `capture_inputs=False`.
- [ ] **Storage permissions set.** JSONL and SQLite files have `600` permissions; parent directories have `700`.
- [ ] **OTLP endpoint uses TLS.** All OTLP endpoints use `https://` or gRPC with TLS.
- [ ] **Credentials loaded from environment.** No API keys or tokens hardcoded in source code or configuration files.
- [ ] **Retention policy documented.** You know how long traces are kept and have a deletion process.
- [ ] **JSONL files not in version control.** `.gitignore` includes the trace directory.
- [ ] **Processor order configured.** `ProcessorOrder.SAFETY` is default; if using `EFFICIENCY`, you have verified compliance implications.
- [ ] **Custom patterns added.** Any domain-specific PII types (MRNs, employee IDs, etc.) have custom redaction rules.
- [ ] **Allowlist reviewed.** The redaction allowlist contains only known-safe test values, not production data patterns.
- [ ] **Audit identifiers attached.** Runs include `user_id` and `session_id` for audit trails where required.
- [ ] **Redaction verified end-to-end.** Sample traces have been manually inspected to confirm no sensitive data appears in exported output.

---

## Common Security Configurations

### Maximum Security Setup

```python
import tracecraft
from tracecraft.core.config import (
    TraceCraftConfig,
    RedactionConfig,
    SamplingConfig,
    ProcessorOrder,
)
from tracecraft.processors.redaction import RedactionMode, RedactionRule
from tracecraft.exporters.otlp import OTLPExporter
from tracecraft.exporters.async_pipeline import AsyncBatchExporter
import os

# Domain-specific sensitive patterns
domain_rules = [
    RedactionRule(name="employee_id", pattern=r"EMP-\d{6}"),
    RedactionRule(name="internal_token", pattern=r"int_[a-f0-9]{48}"),
]

config = TraceCraftConfig(
    service_name="secure-service",
    processor_order=ProcessorOrder.SAFETY,  # Redact before sampling
    redaction=RedactionConfig(
        enabled=True,
        mode=RedactionMode.HASH,  # Hash rather than mask for correlation
        custom_patterns=[r.pattern for r in domain_rules if r.pattern],
        allowlist=["test@example.com"],
    ),
    sampling=SamplingConfig(
        rate=0.1,
        always_keep_errors=True,
    ),
)

otlp = OTLPExporter(
    endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
    headers={"Authorization": f"Bearer {os.environ['OTEL_AUTH_TOKEN']}"},
)
batch = AsyncBatchExporter(exporter=otlp, batch_size=50, flush_interval_seconds=5.0)

runtime = tracecraft.init(
    console=False,
    jsonl=False,
    exporters=[batch],
    config=config,
)
```

### Development with Safety

Keep redaction active during development to catch accidental PII in test data early.

```python
import tracecraft
from tracecraft.core.config import TraceCraftConfig, RedactionConfig

config = TraceCraftConfig(
    redaction=RedactionConfig(
        enabled=True,  # Keep redaction active even locally
        allowlist=[
            "dev@example.com",  # Your development test email
        ],
    ),
)

runtime = tracecraft.init(
    console=True,
    jsonl=True,
    config=config,
)
```

### Compliance-Ready Configuration (HIPAA/PCI)

```python
import tracecraft
from tracecraft.core.config import (
    TraceCraftConfig,
    RedactionConfig,
    SamplingConfig,
    ProcessorOrder,
)
from tracecraft.processors.redaction import RedactionMode, RedactionRule
from tracecraft.storage.sqlite import SQLiteTraceStore
from pathlib import Path

# Add PHI-specific patterns
phi_rules = [
    RedactionRule(name="mrn", pattern=r"MRN-\d{8,12}"),
    RedactionRule(name="dob", pattern=r"\b\d{1,2}/\d{1,2}/\d{4}\b"),
]

config = TraceCraftConfig(
    service_name="hipaa-compliant-agent",
    processor_order=ProcessorOrder.SAFETY,
    redaction=RedactionConfig(
        enabled=True,
        mode=RedactionMode.MASK,
        custom_patterns=[r.pattern for r in phi_rules if r.pattern],
    ),
    sampling=SamplingConfig(
        rate=1.0,              # Keep 100% for audit completeness
        always_keep_errors=True,
    ),
)

# On-premises storage only — no cloud export
store_path = Path("/secure/traces/hipaa_traces.db")
store = SQLiteTraceStore(store_path)

runtime = tracecraft.init(
    console=False,
    jsonl=False,          # Disable JSONL; use SQLite with controlled access
    config=config,
    storage=store,
)
```

---

## Troubleshooting

### Redaction Not Working

**Symptoms:** Sensitive values appear unmodified in exported traces.

**Checklist:**

- Verify `RedactionConfig(enabled=True)` is set in your `TraceCraftConfig`.
- Confirm the config is passed to `tracecraft.init()`.
- Check the `TRACECRAFT_REDACTION_ENABLED` environment variable is not set to `false`.
- Verify the value matches the pattern. Use Python's `re.search()` to test your pattern against sample data.
- Check if the value is in the allowlist — allowlisted values are never redacted.
- Confirm the field is a string type. Redaction only applies to string values; numeric or dict values are processed recursively.

### Sensitive Data in Traces Despite Redaction

**Symptoms:** Specific sensitive values pass through redaction.

**Checklist:**

- The built-in patterns may not cover your specific format. Add a `RedactionRule` with a custom pattern that matches your data.
- Check if the value is split across multiple fields. Redaction operates per-string; a value split across two dict keys is not caught by a single-field pattern.
- If the value is a number (not a string), pattern matching does not apply. Use field-based redaction with `field_paths` for numeric fields.
- Review the `REMOVE` mode if even the `[REDACTED]` placeholder is unacceptable.

### Certificate Errors on OTLP Export

**Symptoms:** `SSL: CERTIFICATE_VERIFY_FAILED` errors in logs; traces not reaching the backend.

**Checklist:**

- Verify the OTLP endpoint certificate is issued by a trusted CA.
- For self-signed certificates, add the CA certificate to the system trust store or configure the exporter's HTTP client to trust it.
- Confirm the endpoint hostname matches the certificate CN or SAN.
- Check for certificate expiration: `openssl s_client -connect collector.example.com:4317 | openssl x509 -noout -dates`.
- If using a corporate proxy that performs TLS inspection, add the proxy's root CA to the trust store.
