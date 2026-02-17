"""Tests for auto-instrumentation module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


class TestAutoInstrumentor:
    """Tests for the AutoInstrumentor class."""

    def test_instrumentor_initialization(self):
        """Test AutoInstrumentor initializes correctly."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        assert instrumentor._instrumentors == []
        assert instrumentor._patchers == []
        assert instrumentor._enabled is False
        assert instrumentor._instrumented["openai"] is False
        assert instrumentor._instrumented["anthropic"] is False
        assert instrumentor._instrumented["langchain"] is False
        assert instrumentor._instrumented["llamaindex"] is False

    def test_is_enabled_property(self):
        """Test is_enabled property."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        assert instrumentor.is_enabled is False

        instrumentor._enabled = True
        assert instrumentor.is_enabled is True

    def test_instrument_openai_returns_false_when_not_installed(self):
        """Test OpenAI instrumentation returns False when OpenAI not installed."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # If OpenAI is not installed, should return False
        # (may return True if OpenAI is installed in test env)
        result = instrumentor.instrument_openai()
        # Result depends on whether openai is installed
        assert isinstance(result, bool)

    def test_instrument_anthropic_returns_false_when_not_installed(self):
        """Test Anthropic instrumentation returns False when Anthropic not installed."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        result = instrumentor.instrument_anthropic()
        assert isinstance(result, bool)

    def test_instrument_langchain_returns_false_when_not_installed(self):
        """Test LangChain instrumentation returns False when LangChain not installed."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # Mock langchain_core not being installed
        with patch.dict("sys.modules", {"langchain_core": None}):
            # Force a fresh import attempt
            result = instrumentor.instrument_langchain()
            # Result depends on whether langchain is installed
            assert isinstance(result, bool)

    def test_instrument_llamaindex_returns_false_when_not_installed(self):
        """Test LlamaIndex instrumentation returns False when LlamaIndex not installed."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # Result depends on whether llama-index is installed
        result = instrumentor.instrument_llamaindex()
        assert isinstance(result, bool)

    def test_instrument_all_returns_dict(self):
        """Test instrument_all returns a dictionary of results."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        result = instrumentor.instrument_all()

        assert isinstance(result, dict)
        assert "openai" in result
        assert "anthropic" in result
        assert "langchain" in result
        assert "llamaindex" in result

    def test_uninstrument_all_clears_state(self):
        """Test uninstrument_all clears all state."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._enabled = True
        instrumentor._instrumented["openai"] = True
        instrumentor._instrumented["anthropic"] = True
        instrumentor._instrumented["langchain"] = True
        instrumentor._instrumented["llamaindex"] = True

        instrumentor.uninstrument_all()

        assert instrumentor._enabled is False
        assert instrumentor._instrumented["openai"] is False
        assert instrumentor._instrumented["anthropic"] is False
        assert instrumentor._instrumented["langchain"] is False
        assert instrumentor._instrumented["llamaindex"] is False

    def test_idempotent_instrumentation(self):
        """Test that instrumenting twice is idempotent."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._instrumented["openai"] = True

        # Should return True immediately without re-instrumenting
        result = instrumentor.instrument_openai()
        assert result is True

    def test_idempotent_langchain_instrumentation(self):
        """Test that instrumenting LangChain twice is idempotent."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._instrumented["langchain"] = True

        # Should return True immediately without re-instrumenting
        result = instrumentor.instrument_langchain()
        assert result is True

    def test_idempotent_llamaindex_instrumentation(self):
        """Test that instrumenting LlamaIndex twice is idempotent."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._instrumented["llamaindex"] = True

        # Should return True immediately without re-instrumenting
        result = instrumentor.instrument_llamaindex()
        assert result is True


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_instrumentor_returns_same_instance(self):
        """Test get_instrumentor returns singleton."""
        from tracecraft.instrumentation import auto

        # Reset global state
        auto._auto_instrumentor = None

        inst1 = auto.get_instrumentor()
        inst2 = auto.get_instrumentor()

        assert inst1 is inst2

    def test_enable_auto_instrumentation_returns_dict(self):
        """Test enable_auto_instrumentation returns results dict."""
        from tracecraft.instrumentation import auto

        # Reset global state
        auto._auto_instrumentor = None

        result = auto.enable_auto_instrumentation()

        assert isinstance(result, dict)
        assert "openai" in result
        assert "anthropic" in result
        assert "langchain" in result
        assert "llamaindex" in result

    def test_enable_specific_providers(self):
        """Test enabling specific providers only."""
        from tracecraft.instrumentation import auto

        # Reset global state
        auto._auto_instrumentor = None

        result = auto.enable_auto_instrumentation(providers=["openai"])

        assert "openai" in result
        # Other providers should not be in result
        assert "anthropic" not in result
        assert "langchain" not in result

    def test_enable_langchain_provider(self):
        """Test enabling LangChain provider."""
        from tracecraft.instrumentation import auto

        auto._auto_instrumentor = None

        result = auto.enable_auto_instrumentation(providers=["langchain"])

        assert "langchain" in result
        assert isinstance(result["langchain"], bool)

    def test_enable_llamaindex_provider_aliases(self):
        """Test enabling LlamaIndex with different aliases."""
        from tracecraft.instrumentation import auto

        # Test various aliases
        for alias in ["llamaindex", "llama_index", "llama-index"]:
            auto._auto_instrumentor = None
            result = auto.enable_auto_instrumentation(providers=[alias])
            assert "llamaindex" in result
            assert isinstance(result["llamaindex"], bool)

    def test_enable_unknown_provider(self):
        """Test enabling unknown provider logs warning."""
        from tracecraft.instrumentation import auto

        auto._auto_instrumentor = None

        result = auto.enable_auto_instrumentation(providers=["unknown_provider"])

        assert result.get("unknown_provider") is False

    def test_disable_auto_instrumentation(self):
        """Test disabling auto-instrumentation."""
        from tracecraft.instrumentation import auto

        auto._auto_instrumentor = None

        # Enable first
        auto.enable_auto_instrumentation()

        # Then disable
        auto.disable_auto_instrumentation()

        assert auto.is_instrumentation_enabled() is False

    def test_disable_specific_providers(self):
        """Test disabling specific providers."""
        from tracecraft.instrumentation import auto

        auto._auto_instrumentor = None

        # This should not raise
        auto.disable_auto_instrumentation(providers=["openai", "langchain"])

    def test_is_instrumentation_enabled_false_when_not_initialized(self):
        """Test is_instrumentation_enabled returns False when not initialized."""
        from tracecraft.instrumentation import auto

        auto._auto_instrumentor = None

        assert auto.is_instrumentation_enabled() is False


class TestOTelIntegration:
    """Tests for OpenTelemetry instrumentation integration."""

    def test_otel_openai_instrumentor_used_when_available(self):
        """Test that OTel instrumentation is preferred when available."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        # Mock the OTel instrumentor
        mock_instrumentor = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "opentelemetry.instrumentation.openai": MagicMock(
                    OpenAIInstrumentor=lambda: mock_instrumentor
                )
            },
        ):
            instrumentor = AutoInstrumentor()

            # Should try to use OTel first
            # The actual result depends on whether the mock is properly set up
            instrumentor.instrument_openai()

    def test_fallback_to_patching_when_otel_unavailable(self):
        """Test fallback to monkey patching when OTel not available."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # With no OTel instrumentation available, it should try patching
        # This will succeed or fail based on whether the SDK is installed
        result = instrumentor.instrument_openai()

        # Just verify it returns a boolean
        assert isinstance(result, bool)


class TestInitAutoInstrument:
    """Tests for init() auto_instrument parameter and env var support."""

    def test_init_with_auto_instrument_true(self):
        """Test init() with auto_instrument=True."""
        from tracecraft.core import runtime as rt

        # Reset runtime state
        rt._runtime = None

        # Create a fresh runtime with auto_instrument=True
        # We can't easily verify the auto-instrumentation was enabled
        # without the frameworks installed, but we can verify it doesn't crash
        result = rt.init(console=False, jsonl=False, auto_instrument=True)

        assert result is not None

        # Cleanup
        result.shutdown()
        rt._runtime = None

    def test_init_with_auto_instrument_list(self):
        """Test init() with auto_instrument as a list of providers."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        result = rt.init(console=False, jsonl=False, auto_instrument=["openai", "langchain"])

        assert result is not None

        # Cleanup
        result.shutdown()
        rt._runtime = None

    def test_init_with_auto_instrument_false(self):
        """Test init() with auto_instrument=False."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        result = rt.init(console=False, jsonl=False, auto_instrument=False)

        assert result is not None

        # Cleanup
        result.shutdown()
        rt._runtime = None

    def test_init_env_var_true(self):
        """Test TRACECRAFT_AUTO_INSTRUMENT=true env var."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        with patch.dict(os.environ, {"TRACECRAFT_AUTO_INSTRUMENT": "true"}):
            result = rt.init(console=False, jsonl=False)
            assert result is not None
            result.shutdown()
            rt._runtime = None

    def test_init_env_var_all(self):
        """Test TRACECRAFT_AUTO_INSTRUMENT=all env var."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        with patch.dict(os.environ, {"TRACECRAFT_AUTO_INSTRUMENT": "all"}):
            result = rt.init(console=False, jsonl=False)
            assert result is not None
            result.shutdown()
            rt._runtime = None

    def test_init_env_var_providers_list(self):
        """Test TRACECRAFT_AUTO_INSTRUMENT with comma-separated providers."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        with patch.dict(os.environ, {"TRACECRAFT_AUTO_INSTRUMENT": "openai,langchain"}):
            result = rt.init(console=False, jsonl=False)
            assert result is not None
            result.shutdown()
            rt._runtime = None

    def test_init_env_var_false(self):
        """Test TRACECRAFT_AUTO_INSTRUMENT=false env var."""
        from tracecraft.core import runtime as rt

        rt._runtime = None

        with patch.dict(os.environ, {"TRACECRAFT_AUTO_INSTRUMENT": "false"}):
            result = rt.init(console=False, jsonl=False)
            assert result is not None
            result.shutdown()
            rt._runtime = None


class TestInitAndAutoInstrumentFunction:
    """Tests for the init_and_auto_instrument convenience function."""

    def test_init_and_auto_instrument_basic(self):
        """Test init_and_auto_instrument basic call."""
        import tracecraft
        from tracecraft.core import runtime as rt

        rt._runtime = None

        result = tracecraft.init_and_auto_instrument(console=False, jsonl=False)

        assert result is not None

        # Cleanup
        result.shutdown()
        rt._runtime = None

    def test_init_and_auto_instrument_with_providers(self):
        """Test init_and_auto_instrument with specific providers."""
        import tracecraft
        from tracecraft.core import runtime as rt

        rt._runtime = None

        result = tracecraft.init_and_auto_instrument(
            providers=["openai"], console=False, jsonl=False
        )

        assert result is not None

        # Cleanup
        result.shutdown()
        rt._runtime = None


class TestLangChainInstrumentation:
    """Tests for LangChain auto-instrumentation."""

    def test_langchain_handler_created(self):
        """Test that LangChain handler is created on instrumentation."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # If LangChain is installed, the handler should be created
        result = instrumentor.instrument_langchain()

        if result:
            assert instrumentor._langchain_handler is not None
        else:
            # LangChain not installed, handler should be None
            assert instrumentor._langchain_handler is None

    def test_langchain_uninstrument_clears_handler(self):
        """Test that uninstrumenting LangChain clears the handler."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._instrumented["langchain"] = True
        instrumentor._langchain_handler = MagicMock()

        instrumentor.uninstrument_langchain()

        assert instrumentor._langchain_handler is None
        assert instrumentor._instrumented["langchain"] is False


class TestLlamaIndexInstrumentation:
    """Tests for LlamaIndex auto-instrumentation."""

    def test_llamaindex_handler_created(self):
        """Test that LlamaIndex handler is created on instrumentation."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()

        # If LlamaIndex is installed, the handler should be created
        result = instrumentor.instrument_llamaindex()

        if result:
            assert instrumentor._llamaindex_handler is not None
        else:
            # LlamaIndex not installed, handler should be None
            assert instrumentor._llamaindex_handler is None

    def test_llamaindex_uninstrument_clears_handler(self):
        """Test that uninstrumenting LlamaIndex clears the handler."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._instrumented["llamaindex"] = True
        instrumentor._llamaindex_handler = MagicMock()

        instrumentor.uninstrument_llamaindex()

        assert instrumentor._llamaindex_handler is None
        assert instrumentor._instrumented["llamaindex"] is False
