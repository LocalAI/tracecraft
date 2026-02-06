"""
Tests for the redaction processor.

Tests PII detection and redaction with various modes and patterns.
"""

from __future__ import annotations

import re

from tracecraft.processors.redaction import (
    RedactionMode,
    RedactionProcessor,
    RedactionRule,
)


class TestRedactionMode:
    """Tests for RedactionMode enum."""

    def test_redaction_mode_mask(self) -> None:
        """MASK mode should exist."""
        assert RedactionMode.MASK.value == "mask"

    def test_redaction_mode_hash(self) -> None:
        """HASH mode should exist."""
        assert RedactionMode.HASH.value == "hash"

    def test_redaction_mode_remove(self) -> None:
        """REMOVE mode should exist."""
        assert RedactionMode.REMOVE.value == "remove"


class TestRedactionRule:
    """Tests for RedactionRule."""

    def test_rule_with_pattern(self) -> None:
        """Rule with regex pattern."""
        rule = RedactionRule(name="email", pattern=r"[\w\.-]+@[\w\.-]+")
        assert rule.name == "email"
        assert rule.pattern is not None

    def test_rule_with_field_path(self) -> None:
        """Rule with JSON field path."""
        rule = RedactionRule(name="password", field_paths=["password", "secret"])
        assert rule.name == "password"
        assert "password" in rule.field_paths

    def test_rule_custom_replacement(self) -> None:
        """Rule with custom replacement text."""
        rule = RedactionRule(
            name="custom",
            pattern=r"secret",
            replacement="***SECRET***",
        )
        assert rule.replacement == "***SECRET***"


class TestRedactionProcessorBasicPatterns:
    """Tests for basic pattern matching."""

    def test_redact_email_pattern(self) -> None:
        """Should redact email addresses."""
        processor = RedactionProcessor()
        text = "Contact me at john.doe@example.com for details"
        result = processor.redact_text(text)
        assert "john.doe@example.com" not in result
        assert "[REDACTED]" in result

    def test_redact_multiple_emails(self) -> None:
        """Should redact multiple email addresses."""
        processor = RedactionProcessor()
        text = "Emails: a@b.com and c@d.org"
        result = processor.redact_text(text)
        assert "a@b.com" not in result
        assert "c@d.org" not in result
        assert result.count("[REDACTED]") == 2

    def test_redact_phone_pattern(self) -> None:
        """Should redact phone numbers."""
        processor = RedactionProcessor()
        text = "Call me at 555-123-4567 or (555) 987-6543"
        result = processor.redact_text(text)
        assert "555-123-4567" not in result
        assert "(555) 987-6543" not in result

    def test_redact_phone_international(self) -> None:
        """Should redact international phone numbers."""
        processor = RedactionProcessor()
        text = "International: +1-555-123-4567"
        result = processor.redact_text(text)
        assert "+1-555-123-4567" not in result

    def test_redact_api_key_pattern(self) -> None:
        """Should redact API keys (sk-...)."""
        processor = RedactionProcessor()
        text = "API key: sk-abc123def456ghi789"
        result = processor.redact_text(text)
        assert "sk-abc123def456ghi789" not in result
        assert "[REDACTED]" in result

    def test_redact_api_key_openai_format(self) -> None:
        """Should redact OpenAI-style API keys."""
        processor = RedactionProcessor()
        text = "Key: sk-proj-abcdefghijklmnop1234567890"
        result = processor.redact_text(text)
        assert "sk-proj-" not in result

    def test_redact_credit_card(self) -> None:
        """Should redact credit card numbers."""
        processor = RedactionProcessor()
        text = "Card: 4532-1234-5678-9012"
        result = processor.redact_text(text)
        assert "4532-1234-5678-9012" not in result

    def test_redact_credit_card_no_dashes(self) -> None:
        """Should redact credit card numbers without dashes."""
        processor = RedactionProcessor()
        text = "Card: 4532123456789012"
        result = processor.redact_text(text)
        assert "4532123456789012" not in result

    def test_redact_ssn(self) -> None:
        """Should redact Social Security Numbers."""
        processor = RedactionProcessor()
        text = "SSN: 123-45-6789"
        result = processor.redact_text(text)
        assert "123-45-6789" not in result


class TestRedactionProcessorCustomPatterns:
    """Tests for custom pattern support."""

    def test_redact_custom_pattern(self) -> None:
        """Should support custom regex patterns."""
        custom_rule = RedactionRule(
            name="internal_id",
            pattern=r"ID-\d{6}",
        )
        processor = RedactionProcessor(rules=[custom_rule])
        text = "User ID-123456 logged in"
        result = processor.redact_text(text)
        assert "ID-123456" not in result

    def test_redact_custom_pattern_with_replacement(self) -> None:
        """Custom pattern with custom replacement."""
        custom_rule = RedactionRule(
            name="code",
            pattern=r"CODE-\w+",
            replacement="[CODE-HIDDEN]",
        )
        processor = RedactionProcessor(rules=[custom_rule])
        text = "Use CODE-ABC123 for discount"
        result = processor.redact_text(text)
        assert "[CODE-HIDDEN]" in result
        assert "CODE-ABC123" not in result

    def test_redact_with_builtin_and_custom(self) -> None:
        """Should apply both built-in and custom rules."""
        custom_rule = RedactionRule(name="custom", pattern=r"CUSTOM-\d+")
        processor = RedactionProcessor(rules=[custom_rule], include_defaults=True)
        text = "Email: a@b.com, Custom: CUSTOM-999"
        result = processor.redact_text(text)
        assert "a@b.com" not in result
        assert "CUSTOM-999" not in result


class TestRedactionProcessorFieldPaths:
    """Tests for JSON path-based redaction."""

    def test_redact_path_based(self) -> None:
        """Should redact fields by JSON path."""
        rule = RedactionRule(name="password", field_paths=["password"])
        processor = RedactionProcessor(rules=[rule], include_defaults=False)
        data = {"username": "john", "password": "secret123"}
        result = processor.redact_dict(data)
        assert result["username"] == "john"
        assert result["password"] == "[REDACTED]"

    def test_redact_nested_path(self) -> None:
        """Should redact nested fields."""
        rule = RedactionRule(name="credentials", field_paths=["auth.token"])
        processor = RedactionProcessor(rules=[rule], include_defaults=False)
        data = {"auth": {"token": "abc123", "user": "john"}}
        result = processor.redact_dict(data)
        assert result["auth"]["token"] == "[REDACTED]"
        assert result["auth"]["user"] == "john"

    def test_redact_multiple_paths(self) -> None:
        """Should redact multiple field paths."""
        rule = RedactionRule(
            name="secrets",
            field_paths=["password", "api_key", "token"],
        )
        processor = RedactionProcessor(rules=[rule], include_defaults=False)
        data = {"password": "pass", "api_key": "key", "token": "tok", "user": "john"}
        result = processor.redact_dict(data)
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        assert result["user"] == "john"


class TestRedactionProcessorAllowlist:
    """Tests for allowlist functionality."""

    def test_redact_allowlist_email(self) -> None:
        """Should not redact allowlisted emails."""
        processor = RedactionProcessor(
            allowlist=["support@company.com"],
        )
        text = "Contact support@company.com or user@example.com"
        result = processor.redact_text(text)
        assert "support@company.com" in result
        assert "user@example.com" not in result

    def test_redact_allowlist_pattern(self) -> None:
        """Should support regex patterns in allowlist."""
        processor = RedactionProcessor(
            allowlist_patterns=[r".*@company\.com$"],
        )
        text = "Contact admin@company.com or user@example.com"
        result = processor.redact_text(text)
        assert "admin@company.com" in result
        assert "user@example.com" not in result


class TestRedactionModes:
    """Tests for different redaction modes."""

    def test_redact_mode_mask(self) -> None:
        """MASK mode should replace with [REDACTED]."""
        processor = RedactionProcessor(mode=RedactionMode.MASK)
        text = "Email: test@example.com"
        result = processor.redact_text(text)
        assert "[REDACTED]" in result
        assert "test@example.com" not in result

    def test_redact_mode_hash(self) -> None:
        """HASH mode should replace with SHA256 hash."""
        processor = RedactionProcessor(mode=RedactionMode.HASH)
        text = "Email: test@example.com"
        result = processor.redact_text(text)
        # Should contain a hash pattern
        assert re.search(r"\[HASH:[a-f0-9]{16}\]", result)
        assert "test@example.com" not in result

    def test_redact_mode_hash_deterministic(self) -> None:
        """HASH mode should produce deterministic hashes."""
        processor = RedactionProcessor(mode=RedactionMode.HASH)
        text1 = "Email: same@email.com here"
        text2 = "Email: same@email.com there"
        result1 = processor.redact_text(text1)
        result2 = processor.redact_text(text2)
        # Extract hashes
        hash1 = re.search(r"\[HASH:([a-f0-9]+)\]", result1)
        hash2 = re.search(r"\[HASH:([a-f0-9]+)\]", result2)
        assert hash1 and hash2
        assert hash1.group(1) == hash2.group(1)

    def test_redact_mode_remove(self) -> None:
        """REMOVE mode should remove sensitive data entirely."""
        processor = RedactionProcessor(mode=RedactionMode.REMOVE)
        text = "Email: test@example.com here"
        result = processor.redact_text(text)
        assert "test@example.com" not in result
        assert "[REDACTED]" not in result
        assert "Email:  here" in result


class TestRedactionRecursive:
    """Tests for recursive data structure handling."""

    def test_redact_recursive_dict(self) -> None:
        """Should recursively redact nested dicts."""
        processor = RedactionProcessor()
        data = {
            "user": "john",
            "contact": {
                "email": "john@example.com",
                "nested": {
                    "backup_email": "backup@example.com",
                },
            },
        }
        result = processor.redact_dict(data)
        assert "john@example.com" not in str(result)
        assert "backup@example.com" not in str(result)

    def test_redact_recursive_list(self) -> None:
        """Should recursively redact lists."""
        processor = RedactionProcessor()
        data = {
            "emails": ["a@b.com", "c@d.com"],
            "users": [
                {"email": "x@y.com"},
                {"email": "z@w.com"},
            ],
        }
        result = processor.redact_dict(data)
        assert "a@b.com" not in str(result)
        assert "c@d.com" not in str(result)
        assert "x@y.com" not in str(result)
        assert "z@w.com" not in str(result)

    def test_redact_mixed_nested_structures(self) -> None:
        """Should handle complex nested structures."""
        processor = RedactionProcessor()
        data = {
            "items": [
                {
                    "data": [
                        {"contact": "user@email.com"},
                    ],
                },
            ],
        }
        result = processor.redact_dict(data)
        assert "user@email.com" not in str(result)

    def test_redact_preserves_structure(self) -> None:
        """Redaction should preserve data structure."""
        processor = RedactionProcessor()
        data = {
            "users": [{"email": "a@b.com", "name": "John"}],
            "count": 1,
            "active": True,
        }
        result = processor.redact_dict(data)
        assert isinstance(result["users"], list)
        assert isinstance(result["users"][0], dict)
        assert result["count"] == 1
        assert result["active"] is True
        assert result["users"][0]["name"] == "John"


class TestRedactionEdgeCases:
    """Tests for edge cases."""

    def test_redact_empty_string(self) -> None:
        """Should handle empty strings."""
        processor = RedactionProcessor()
        assert processor.redact_text("") == ""

    def test_redact_no_sensitive_data(self) -> None:
        """Should return unchanged text when no sensitive data."""
        processor = RedactionProcessor()
        text = "Hello, this is a normal message."
        assert processor.redact_text(text) == text

    def test_redact_empty_dict(self) -> None:
        """Should handle empty dicts."""
        processor = RedactionProcessor()
        assert processor.redact_dict({}) == {}

    def test_redact_none_values(self) -> None:
        """Should handle None values in dicts."""
        processor = RedactionProcessor()
        data = {"email": None, "name": "John"}
        result = processor.redact_dict(data)
        assert result["email"] is None
        assert result["name"] == "John"

    def test_redact_non_string_values(self) -> None:
        """Should handle non-string values."""
        processor = RedactionProcessor()
        data = {"count": 42, "rate": 3.14, "active": True}
        result = processor.redact_dict(data)
        assert result == data


class TestExpandedAPIKeyPatterns:
    """Tests for expanded API key detection patterns."""

    def test_redact_openai_api_key(self) -> None:
        """Should redact OpenAI API keys (sk-...)."""
        processor = RedactionProcessor()
        text = "Use API key: sk-abcd1234efgh5678ijkl9012mnop3456"
        result = processor.redact_text(text)
        assert "sk-abcd1234" not in result
        assert "[REDACTED]" in result

    def test_redact_anthropic_api_key(self) -> None:
        """Should redact Anthropic API keys (sk-ant-...)."""
        processor = RedactionProcessor()
        text = "Anthropic key: sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
        result = processor.redact_text(text)
        assert "sk-ant-api03" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_access_key(self) -> None:
        """Should redact AWS access key IDs (AKIA...)."""
        processor = RedactionProcessor()
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        result = processor.redact_text(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_secret_key(self) -> None:
        """Should redact AWS secret access keys."""
        processor = RedactionProcessor()
        text = "Secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        result = processor.redact_text(text)
        assert "wJalrXUtnFEMI" not in result
        assert "[REDACTED]" in result

    def test_redact_bearer_token(self) -> None:
        """Should redact Bearer tokens."""
        processor = RedactionProcessor()
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0"
        result = processor.redact_text(text)
        assert "eyJhbGciOi" not in result
        assert "[REDACTED]" in result

    def test_redact_github_token(self) -> None:
        """Should redact GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)."""
        processor = RedactionProcessor()
        tokens = [
            "ghp_abcdefghijklmnopqrstuvwxyz1234567890",  # PAT
            "gho_abcdefghijklmnopqrstuvwxyz1234567890",  # OAuth
            "ghu_abcdefghijklmnopqrstuvwxyz1234567890",  # User-to-server
            "ghs_abcdefghijklmnopqrstuvwxyz1234567890",  # Server-to-server
            "ghr_abcdefghijklmnopqrstuvwxyz1234567890",  # Refresh
        ]
        for token in tokens:
            text = f"Token: {token}"
            result = processor.redact_text(text)
            assert token not in result, f"Failed to redact {token[:10]}..."
            assert "[REDACTED]" in result

    def test_redact_google_api_key(self) -> None:
        """Should redact Google API keys (AIza...)."""
        processor = RedactionProcessor()
        text = "Google key: AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe"
        result = processor.redact_text(text)
        assert "AIzaSyDaGm" not in result
        assert "[REDACTED]" in result

    def test_redact_azure_connection_string(self) -> None:
        """Should redact Azure connection strings."""
        processor = RedactionProcessor()
        text = "Connection: DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=abc123def456ghi789+jkl="
        result = processor.redact_text(text)
        assert "AccountKey=" not in result or "abc123def456" not in result
        assert "[REDACTED]" in result

    def test_redact_generic_api_key_param(self) -> None:
        """Should redact generic api_key=... patterns."""
        processor = RedactionProcessor()
        text = "URL: https://api.example.com?api_key=super_secret_key_12345"
        result = processor.redact_text(text)
        assert "super_secret_key" not in result
        assert "[REDACTED]" in result

    def test_redact_private_key_header(self) -> None:
        """Should redact private key headers."""
        processor = RedactionProcessor()
        text = "Key: -----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        result = processor.redact_text(text)
        assert "BEGIN RSA PRIVATE KEY" not in result
        assert "[REDACTED]" in result

    def test_redact_slack_token(self) -> None:
        """Should redact Slack tokens (xoxb-, xoxp-, xoxa-, xoxr-)."""
        processor = RedactionProcessor()
        # Pattern: xox[bpar]-{10+ digits}-{10+ digits}-{20+ alphanum}
        # Build tokens programmatically to avoid GitHub secret scanning
        digits = "0" * 10
        suffix = "A" * 24
        for prefix in ["xoxb", "xoxp"]:
            token = f"{prefix}-{digits}-{digits}-{suffix}"
            text = f"Slack: {token}"
            result = processor.redact_text(text)
            assert token not in result
            assert "[REDACTED]" in result

    def test_redact_stripe_key(self) -> None:
        """Should redact Stripe API keys (sk_live_, sk_test_, pk_live_, pk_test_)."""
        processor = RedactionProcessor()
        # Pattern: [sp]k_{live|test}_{20+ alphanum}
        # Use obviously fake keys with "FAKE" to avoid GitHub secret scanning
        keys = [
            "REMOVED_STRIPE_KEY",
            "REMOVED_STRIPE_KEY",
            "REMOVED_STRIPE_KEY",
            "REMOVED_STRIPE_KEY",
        ]
        for key in keys:
            text = f"Stripe: {key}"
            result = processor.redact_text(text)
            assert key not in result, f"Failed to redact {key[:15]}..."
            assert "[REDACTED]" in result

    def test_preserves_non_sensitive_text(self) -> None:
        """Should preserve normal text around API keys."""
        processor = RedactionProcessor()
        text = "Use sk-abcd1234efgh5678ijkl9012mnop3456 for auth"
        result = processor.redact_text(text)
        assert result.startswith("Use ")
        assert result.endswith(" for auth")
