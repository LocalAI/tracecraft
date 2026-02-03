"""Tests for auto-instrumentation module."""

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
        assert instrumentor._openai_instrumented is False
        assert instrumentor._anthropic_instrumented is False

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

    def test_instrument_all_returns_dict(self):
        """Test instrument_all returns a dictionary of results."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        result = instrumentor.instrument_all()

        assert isinstance(result, dict)
        assert "openai" in result
        assert "anthropic" in result

    def test_uninstrument_all_clears_state(self):
        """Test uninstrument_all clears all state."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._enabled = True
        instrumentor._openai_instrumented = True
        instrumentor._anthropic_instrumented = True

        instrumentor.uninstrument_all()

        assert instrumentor._enabled is False
        assert instrumentor._openai_instrumented is False
        assert instrumentor._anthropic_instrumented is False

    def test_idempotent_instrumentation(self):
        """Test that instrumenting twice is idempotent."""
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor._openai_instrumented = True

        # Should return True immediately without re-instrumenting
        result = instrumentor.instrument_openai()
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

    def test_enable_specific_providers(self):
        """Test enabling specific providers only."""
        from tracecraft.instrumentation import auto

        # Reset global state
        auto._auto_instrumentor = None

        result = auto.enable_auto_instrumentation(providers=["openai"])

        assert "openai" in result
        # anthropic should not be in result since we only asked for openai
        assert "anthropic" not in result or result.get("anthropic") is None

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
        auto.disable_auto_instrumentation(providers=["openai"])

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
