"""Tests for Langfuse prompt provider integration."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agenttrace.integrations.langfuse_prompts import ChatPromptWrapper, PromptWrapper


class TestPromptWrapper:
    """Tests for PromptWrapper class."""

    def test_properties(self):
        """Test prompt wrapper properties."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test-prompt"
        mock_prompt.version = 3
        mock_prompt.labels = ["production", "v3"]
        mock_prompt.config = {"model": "gpt-4", "temperature": 0.7}

        wrapper = PromptWrapper(mock_prompt, {})

        assert wrapper.name == "test-prompt"
        assert wrapper.version == 3
        assert wrapper.labels == ["production", "v3"]
        assert wrapper.config == {"model": "gpt-4", "temperature": 0.7}

    def test_compile_without_vars(self):
        """Test compile without variables."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Static prompt"

        wrapper = PromptWrapper(mock_prompt, {})
        result = wrapper.compile()

        assert result == "Static prompt"
        mock_prompt.compile.assert_called_once_with()

    def test_compile_with_init_vars(self):
        """Test compile with initialization variables."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Hello, World!"

        wrapper = PromptWrapper(mock_prompt, {"name": "World"})
        result = wrapper.compile()

        assert result == "Hello, World!"
        mock_prompt.compile.assert_called_once_with(name="World")

    def test_compile_with_extra_vars(self):
        """Test compile with extra variables."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Hello, World! How are you?"

        wrapper = PromptWrapper(mock_prompt, {"name": "World"})
        wrapper.compile(greeting="How are you?")

        mock_prompt.compile.assert_called_once_with(name="World", greeting="How are you?")

    def test_text_property(self):
        """Test text property calls compile."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Compiled text"

        wrapper = PromptWrapper(mock_prompt, {})
        result = wrapper.text

        assert result == "Compiled text"

    def test_to_dict(self):
        """Test to_dict method."""
        mock_prompt = MagicMock()
        mock_prompt.name = "test"
        mock_prompt.version = 1
        mock_prompt.labels = ["prod"]
        mock_prompt.config = {"model": "gpt-4"}

        wrapper = PromptWrapper(mock_prompt, {})
        result = wrapper.to_dict()

        assert result == {
            "name": "test",
            "version": 1,
            "labels": ["prod"],
            "config": {"model": "gpt-4"},
        }

    def test_handles_missing_labels(self):
        """Test handling when labels attribute is missing."""
        mock_prompt = MagicMock(spec=["name", "version", "config", "compile"])
        mock_prompt.name = "test"
        mock_prompt.version = 1
        mock_prompt.config = {}

        wrapper = PromptWrapper(mock_prompt, {})

        # Should return empty list when labels not present
        assert wrapper.labels == []

    def test_handles_missing_config(self):
        """Test handling when config attribute is missing."""
        mock_prompt = MagicMock(spec=["name", "version", "labels", "compile"])
        mock_prompt.name = "test"
        mock_prompt.version = 1
        mock_prompt.labels = []

        wrapper = PromptWrapper(mock_prompt, {})

        # Should return empty dict when config not present
        assert wrapper.config == {}


class TestChatPromptWrapper:
    """Tests for ChatPromptWrapper class."""

    def test_properties(self):
        """Test chat prompt wrapper properties."""
        mock_prompt = MagicMock()
        mock_prompt.name = "chat-prompt"
        mock_prompt.version = 2
        mock_prompt.labels = ["staging"]
        mock_prompt.config = {"model": "claude-3"}

        wrapper = ChatPromptWrapper(mock_prompt, {})

        assert wrapper.name == "chat-prompt"
        assert wrapper.version == 2
        assert wrapper.labels == ["staging"]
        assert wrapper.config == {"model": "claude-3"}

    def test_compile_returns_messages(self):
        """Test compile returns list of messages."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]

        wrapper = ChatPromptWrapper(mock_prompt, {})
        result = wrapper.compile()

        assert len(result) == 2
        assert result[0]["role"] == "system"

    def test_messages_property(self):
        """Test messages property calls compile."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = [
            {"role": "user", "content": "Hi"},
        ]

        wrapper = ChatPromptWrapper(mock_prompt, {})
        result = wrapper.messages

        assert len(result) == 1

    def test_compile_with_vars(self):
        """Test compile with variables."""
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = [
            {"role": "user", "content": "Hello, World!"},
        ]

        wrapper = ChatPromptWrapper(mock_prompt, {"name": "World"})
        wrapper.compile()

        mock_prompt.compile.assert_called_once_with(name="World")

    def test_to_dict(self):
        """Test to_dict method."""
        mock_prompt = MagicMock()
        mock_prompt.name = "chat"
        mock_prompt.version = 1
        mock_prompt.labels = []
        mock_prompt.config = {}

        wrapper = ChatPromptWrapper(mock_prompt, {})
        result = wrapper.to_dict()

        assert result["name"] == "chat"


# Tests that require langfuse to be installed
@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="langfuse not installed",
)
class TestLangfusePromptProvider:
    """Tests for LangfusePromptProvider class - requires langfuse."""

    def test_initializes_with_default_client(self):
        """Test initialization uses get_client() by default."""
        pass  # Would require langfuse

    def test_initializes_with_custom_credentials(self):
        """Test initialization with custom credentials."""
        pass  # Would require langfuse


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="langfuse not installed",
)
class TestLangfusePromptProviderGet:
    """Tests for get() method - requires langfuse."""

    def test_gets_prompt_by_name(self):
        """Test getting prompt by name."""
        pass  # Would require langfuse

    def test_caches_prompt(self):
        """Test that prompts are cached."""
        pass  # Would require langfuse


@pytest.mark.skipif(
    True,  # Skip - optional dependency not in test environment
    reason="langfuse not installed",
)
class TestCreateTracingCallback:
    """Tests for create_tracing_callback function - requires langfuse."""

    def test_creates_tracing_metadata(self):
        """Test creating tracing callback metadata."""
        pass  # Would require langfuse
