"""
PII redaction processor.

Detects and redacts sensitive information like emails, phone numbers,
API keys, credit cards, and custom patterns.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RedactionMode(Enum):
    """Mode for handling redacted content."""

    MASK = "mask"  # Replace with [REDACTED]
    HASH = "hash"  # Replace with truncated SHA256 hash
    REMOVE = "remove"  # Remove entirely


@dataclass
class RedactionRule:
    """A rule for detecting and redacting sensitive data."""

    name: str
    pattern: str | None = None
    field_paths: list[str] = field(default_factory=list)
    replacement: str | None = None

    def __post_init__(self) -> None:
        """Compile the regex pattern if provided."""
        self._compiled_pattern: re.Pattern[str] | None = None
        if self.pattern:
            self._compiled_pattern = re.compile(self.pattern)

    @property
    def compiled_pattern(self) -> re.Pattern[str] | None:
        """Get the compiled regex pattern."""
        return self._compiled_pattern


# Default built-in rules for common PII patterns
# Patterns are designed to be ReDoS-safe by avoiding nested quantifiers
# and unbounded repetitions where possible
DEFAULT_RULES: list[RedactionRule] = [
    # Email addresses - use possessive-like pattern with atomic group simulation
    # Limit local part to 64 chars, domain parts to 63 chars per RFC 5321
    RedactionRule(
        name="email",
        pattern=r"[a-zA-Z0-9](?:[a-zA-Z0-9._-]{0,62}[a-zA-Z0-9])?@[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,61}[a-zA-Z0-9])?\.[a-zA-Z]{2,}",
    ),
    # Phone numbers - simplified pattern with explicit structure
    # Matches formats: +1-555-123-4567, (555) 123-4567, 555-123-4567, 5551234567
    RedactionRule(
        name="phone",
        pattern=r"(?:\+\d{1,3}[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}",
    ),
    # Credit card numbers (with or without dashes/spaces)
    # Uses explicit structure to avoid backtracking
    RedactionRule(
        name="credit_card",
        pattern=r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    ),
    # Social Security Numbers - simple fixed format
    RedactionRule(
        name="ssn",
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
    ),
    # === API Keys and Tokens ===
    # OpenAI API keys (sk-...)
    RedactionRule(
        name="openai_api_key",
        pattern=r"sk-[a-zA-Z0-9_-]{10,128}",
    ),
    # Anthropic API keys (sk-ant-...)
    RedactionRule(
        name="anthropic_api_key",
        pattern=r"sk-ant-[a-zA-Z0-9_-]{10,128}",
    ),
    # AWS Access Key IDs (AKIA...)
    RedactionRule(
        name="aws_access_key",
        pattern=r"\bAKIA[A-Z0-9]{16}\b",
    ),
    # AWS Secret Access Keys (40 character base64-like string)
    RedactionRule(
        name="aws_secret_key",
        pattern=r"\b[A-Za-z0-9/+=]{40}\b",
    ),
    # Bearer tokens (JWT-like)
    RedactionRule(
        name="bearer_token",
        pattern=r"Bearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?",
    ),
    # GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
    RedactionRule(
        name="github_token",
        pattern=r"gh[pousr]_[a-zA-Z0-9]{36,}",
    ),
    # Google API keys (AIza...)
    RedactionRule(
        name="google_api_key",
        pattern=r"AIza[a-zA-Z0-9_-]{35}",
    ),
    # Azure connection strings with AccountKey
    RedactionRule(
        name="azure_connection_string",
        pattern=r"AccountKey=[A-Za-z0-9+/=]{20,}",
    ),
    # Generic api_key parameter in URLs or configs
    RedactionRule(
        name="generic_api_key_param",
        pattern=r"api_key=[A-Za-z0-9_-]{8,128}",
    ),
    # Private key headers (PEM format)
    RedactionRule(
        name="private_key",
        pattern=r"-----BEGIN\s+(?:RSA\s+)?(?:PRIVATE|EC)\s+KEY-----",
    ),
    # Slack tokens (xoxb-, xoxp-, xoxa-, xoxr-)
    RedactionRule(
        name="slack_token",
        pattern=r"xox[bpar]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]{20,}",
    ),
    # Stripe API keys (sk_live_, sk_test_, pk_live_, pk_test_)
    RedactionRule(
        name="stripe_key",
        pattern=r"[sp]k_(?:live|test)_[a-zA-Z0-9]{20,}",
    ),
    # Generic password/secret field patterns in text
    RedactionRule(
        name="password_field",
        pattern=r'(?:password|passwd|pwd|secret|token)\s*[=:]\s*["\']?[^\s"\']{4,}["\']?',
    ),
]


class RedactionProcessor:
    """
    Processor for detecting and redacting sensitive information.

    Supports multiple redaction modes, custom patterns, field-based
    redaction, and allowlists.
    """

    def __init__(
        self,
        mode: RedactionMode = RedactionMode.MASK,
        rules: list[RedactionRule] | None = None,
        include_defaults: bool = True,
        allowlist: list[str] | None = None,
        allowlist_patterns: list[str] | None = None,
    ) -> None:
        """
        Initialize the redaction processor.

        Args:
            mode: How to handle redacted content (MASK, HASH, REMOVE).
            rules: Custom redaction rules to apply.
            include_defaults: Whether to include default PII rules.
            allowlist: Exact values to never redact.
            allowlist_patterns: Regex patterns for values to never redact.
        """
        self.mode = mode
        self.rules: list[RedactionRule] = []
        self.allowlist: set[str] = set(allowlist or [])
        self.allowlist_patterns: list[re.Pattern[str]] = [
            re.compile(p) for p in (allowlist_patterns or [])
        ]

        if include_defaults:
            self.rules.extend(DEFAULT_RULES)

        if rules:
            self.rules.extend(rules)

    def _is_allowlisted(self, value: str) -> bool:
        """Check if a value is in the allowlist."""
        if value in self.allowlist:
            return True
        # Use fullmatch to require entire string match, not just prefix
        return any(p.fullmatch(value) for p in self.allowlist_patterns)

    def _get_replacement(self, match: str, rule: RedactionRule) -> str:
        """Get the replacement string for a redacted value."""
        if self._is_allowlisted(match):
            return match

        if rule.replacement:
            return rule.replacement

        if self.mode == RedactionMode.MASK:
            return "[REDACTED]"
        elif self.mode == RedactionMode.HASH:
            hash_value = hashlib.sha256(match.encode()).hexdigest()[:16]
            return f"[HASH:{hash_value}]"
        elif self.mode == RedactionMode.REMOVE:
            return ""
        return "[REDACTED]"

    def redact_text(self, text: str) -> str:
        """
        Redact sensitive information from text.

        Args:
            text: The text to redact.

        Returns:
            The redacted text.
        """
        if not text:
            return text

        result = text

        for rule in self.rules:
            if rule.compiled_pattern:
                # Capture rule in closure to avoid B023
                def make_replacer(r: RedactionRule) -> Callable[[re.Match[str]], str]:
                    def replacer(m: re.Match[str]) -> str:
                        return self._get_replacement(m.group(), r)

                    return replacer

                result = rule.compiled_pattern.sub(make_replacer(rule), result)

        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively redact sensitive information from a dictionary.

        Args:
            data: The dictionary to redact.

        Returns:
            A new dictionary with sensitive information redacted.
        """
        if not data:
            return data

        result = deepcopy(data)
        self._redact_dict_in_place(result, [])
        return result

    def _redact_dict_in_place(
        self,
        data: dict[str, Any] | list[Any],
        path: list[str],
    ) -> None:
        """Recursively redact a dictionary or list in place."""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = path + [key]
                path_str = ".".join(current_path)

                # Check field path rules
                should_redact_field = False
                for rule in self.rules:
                    if path_str in rule.field_paths or key in rule.field_paths:
                        should_redact_field = True
                        break

                if should_redact_field and isinstance(value, str):
                    data[key] = self._get_replacement(
                        value,
                        RedactionRule(name="field_path"),
                    )
                elif isinstance(value, str):
                    data[key] = self.redact_text(value)
                elif isinstance(value, (dict, list)):
                    self._redact_dict_in_place(value, current_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, str):
                    data[i] = self.redact_text(item)
                elif isinstance(item, (dict, list)):
                    self._redact_dict_in_place(item, path)
