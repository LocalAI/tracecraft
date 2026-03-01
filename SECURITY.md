# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please do NOT create public GitHub issues for security vulnerabilities.**

Instead, please report security vulnerabilities by emailing: **<security@tracecraft.io>**

Alternatively, you can use GitHub's private vulnerability reporting feature:

1. Go to the [Security tab](../../security) of this repository
2. Click "Report a vulnerability"
3. Fill out the form with details about the vulnerability

### What to Include

When reporting a vulnerability, please include:

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Any suggested fixes (if available)

### Response Timeline

- **Acknowledgment**: Within 48 hours of receiving your report
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity, but we aim to resolve critical issues within 30 days

### What to Expect

1. You will receive an acknowledgment of your report
2. We will investigate and validate the issue
3. We will work on a fix and coordinate disclosure timing with you
4. We will publicly acknowledge your contribution (unless you prefer to remain anonymous)

## Security Measures in TraceCraft

TraceCraft includes several built-in security features:

### PII Redaction

The SDK includes built-in PII redaction capabilities to prevent sensitive data from being included in traces:

```python
from tracecraft.processors import RedactionProcessor

# Configure redaction patterns
redactor = RedactionProcessor(
    patterns=["email", "phone", "ssn", "credit_card"]
)
```

### Client-Side Sampling

Control data volume and reduce exposure with client-side sampling:

```python
import tracecraft

tracecraft.init(
    sampling_rate=0.1  # Only trace 10% of requests
)
```

### No Credential Storage

TraceCraft is designed to never store credentials in traces. API keys and secrets are automatically filtered from trace data.

### Secure Defaults

- TLS is enforced for OTLP exports
- Sensitive headers are redacted by default
- No persistent storage of raw LLM responses without explicit opt-in

## Security Best Practices

When using TraceCraft:

1. **Use environment variables** for API keys and secrets
2. **Enable PII redaction** in production environments
3. **Configure sampling** to limit data exposure
4. **Review trace data** before sending to third-party backends
5. **Keep dependencies updated** using `uv sync` regularly

## Vulnerability Disclosure Policy

We follow a coordinated disclosure process:

1. Reporter submits vulnerability privately
2. We validate and assess the issue
3. We develop and test a fix
4. We release the fix and publish a security advisory
5. We publicly credit the reporter (if desired)

We request that you:

- Give us reasonable time to address the issue before public disclosure
- Make a good faith effort to avoid privacy violations and data destruction
- Not exploit the vulnerability beyond what is necessary to demonstrate it

## Security Advisories

Security advisories for TraceCraft are published on the [GitHub Security Advisories](../../security/advisories) page.

---

Thank you for helping keep TraceCraft and its users safe!
