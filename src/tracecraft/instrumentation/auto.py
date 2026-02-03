"""
Auto-instrumentation for LLM provider clients.

Automatically instruments OpenAI, Anthropic, and other LLM clients
to capture traces without manual decoration.

This module leverages OpenTelemetry instrumentation libraries to
automatically trace LLM API calls.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class AutoInstrumentor:
    """
    Manages auto-instrumentation for LLM providers.

    Uses OpenTelemetry instrumentation libraries to automatically
    capture LLM calls. Falls back to monkey-patching when OTel
    instrumentation is not available.

    Example:
        ```python
        from tracecraft.instrumentation.auto import AutoInstrumentor

        instrumentor = AutoInstrumentor()
        instrumentor.instrument_all()

        # Now all OpenAI/Anthropic calls are traced
        client = openai.OpenAI()
        response = client.chat.completions.create(...)
        ```
    """

    def __init__(self) -> None:
        """Initialize the auto-instrumentor."""
        self._instrumentors: list[Any] = []
        self._patchers: list[Callable[[], None]] = []
        self._enabled = False
        self._openai_instrumented = False
        self._anthropic_instrumented = False

    @property
    def is_enabled(self) -> bool:
        """Check if auto-instrumentation is enabled."""
        return self._enabled

    def instrument_openai(self) -> bool:
        """
        Enable auto-instrumentation for OpenAI.

        Attempts to use OpenTelemetry instrumentation first, falls back
        to manual patching if not available.

        Returns:
            True if instrumentation was successful.
        """
        if self._openai_instrumented:
            logger.debug("OpenAI already instrumented")
            return True

        # Try OpenTelemetry instrumentation first
        try:
            from opentelemetry.instrumentation.openai import OpenAIInstrumentor

            instrumentor = OpenAIInstrumentor()
            instrumentor.instrument()
            self._instrumentors.append(instrumentor)
            self._openai_instrumented = True
            logger.info("OpenAI auto-instrumentation enabled via OpenTelemetry")
            return True
        except ImportError:
            logger.debug("OpenTelemetry OpenAI instrumentation not available")

        # Fall back to manual patching
        try:
            self._patch_openai()
            self._openai_instrumented = True
            logger.info("OpenAI auto-instrumentation enabled via patching")
            return True
        except ImportError:
            logger.warning("OpenAI not installed. Install with: pip install openai")
            return False
        except Exception:
            logger.exception("Failed to instrument OpenAI")
            return False

    def _patch_openai(self) -> None:
        """Manually patch OpenAI client for tracing."""
        import openai

        original_create = openai.resources.chat.completions.Completions.create
        original_acreate = openai.resources.chat.completions.AsyncCompletions.create

        def patched_create(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            from tracecraft.instrumentation.decorators import trace_llm

            model = kwargs.get("model", "unknown")

            @trace_llm(name="openai.chat.completions.create", model=model, provider="openai")
            def traced_call() -> Any:
                return original_create(self_client, *args, **kwargs)

            return traced_call()

        async def patched_acreate(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            from tracecraft.instrumentation.decorators import trace_llm

            model = kwargs.get("model", "unknown")

            @trace_llm(name="openai.chat.completions.create", model=model, provider="openai")
            async def traced_call() -> Any:
                return await original_acreate(self_client, *args, **kwargs)

            return await traced_call()

        openai.resources.chat.completions.Completions.create = patched_create
        openai.resources.chat.completions.AsyncCompletions.create = patched_acreate

        def unpatch() -> None:
            openai.resources.chat.completions.Completions.create = original_create
            openai.resources.chat.completions.AsyncCompletions.create = original_acreate

        self._patchers.append(unpatch)

    def instrument_anthropic(self) -> bool:
        """
        Enable auto-instrumentation for Anthropic.

        Returns:
            True if instrumentation was successful.
        """
        if self._anthropic_instrumented:
            logger.debug("Anthropic already instrumented")
            return True

        # Try OpenTelemetry instrumentation first
        try:
            from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

            instrumentor = AnthropicInstrumentor()
            instrumentor.instrument()
            self._instrumentors.append(instrumentor)
            self._anthropic_instrumented = True
            logger.info("Anthropic auto-instrumentation enabled via OpenTelemetry")
            return True
        except ImportError:
            logger.debug("OpenTelemetry Anthropic instrumentation not available")

        # Fall back to manual patching
        try:
            self._patch_anthropic()
            self._anthropic_instrumented = True
            logger.info("Anthropic auto-instrumentation enabled via patching")
            return True
        except ImportError:
            logger.warning("Anthropic not installed. Install with: pip install anthropic")
            return False
        except Exception:
            logger.exception("Failed to instrument Anthropic")
            return False

    def _patch_anthropic(self) -> None:
        """Manually patch Anthropic client for tracing."""
        import anthropic

        original_create = anthropic.resources.messages.Messages.create
        original_acreate = anthropic.resources.messages.AsyncMessages.create

        def patched_create(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            from tracecraft.instrumentation.decorators import trace_llm

            model = kwargs.get("model", "unknown")

            @trace_llm(name="anthropic.messages.create", model=model, provider="anthropic")
            def traced_call() -> Any:
                return original_create(self_client, *args, **kwargs)

            return traced_call()

        async def patched_acreate(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            from tracecraft.instrumentation.decorators import trace_llm

            model = kwargs.get("model", "unknown")

            @trace_llm(name="anthropic.messages.create", model=model, provider="anthropic")
            async def traced_call() -> Any:
                return await original_acreate(self_client, *args, **kwargs)

            return await traced_call()

        anthropic.resources.messages.Messages.create = patched_create
        anthropic.resources.messages.AsyncMessages.create = patched_acreate

        def unpatch() -> None:
            anthropic.resources.messages.Messages.create = original_create
            anthropic.resources.messages.AsyncMessages.create = original_acreate

        self._patchers.append(unpatch)

    def instrument_all(self) -> dict[str, bool]:
        """
        Enable all available auto-instrumentation.

        Returns:
            Dictionary mapping provider name to success status.

        Example:
            ```python
            instrumentor = AutoInstrumentor()
            results = instrumentor.instrument_all()
            print(results)  # {'openai': True, 'anthropic': True}
            ```
        """
        results = {
            "openai": self.instrument_openai(),
            "anthropic": self.instrument_anthropic(),
        }
        self._enabled = any(results.values())
        return results

    def uninstrument_openai(self) -> None:
        """Disable OpenAI auto-instrumentation."""
        if not self._openai_instrumented:
            return

        # Uninstrument OTel instrumentors
        for instrumentor in list(self._instrumentors):
            if hasattr(instrumentor, "__class__") and "OpenAI" in instrumentor.__class__.__name__:
                try:
                    instrumentor.uninstrument()
                    self._instrumentors.remove(instrumentor)
                except Exception:
                    logger.exception("Failed to uninstrument OpenAI")

        self._openai_instrumented = False

    def uninstrument_anthropic(self) -> None:
        """Disable Anthropic auto-instrumentation."""
        if not self._anthropic_instrumented:
            return

        # Uninstrument OTel instrumentors
        for instrumentor in list(self._instrumentors):
            if (
                hasattr(instrumentor, "__class__")
                and "Anthropic" in instrumentor.__class__.__name__
            ):
                try:
                    instrumentor.uninstrument()
                    self._instrumentors.remove(instrumentor)
                except Exception:
                    logger.exception("Failed to uninstrument Anthropic")

        self._anthropic_instrumented = False

    def uninstrument_all(self) -> None:
        """Disable all auto-instrumentation."""
        # Uninstrument OTel instrumentors
        for instrumentor in self._instrumentors:
            try:
                instrumentor.uninstrument()
            except Exception:
                logger.exception("Failed to uninstrument %s", type(instrumentor))

        # Call unpatchers
        for unpatch in self._patchers:
            try:
                unpatch()
            except Exception:
                logger.exception("Failed to unpatch")

        self._instrumentors.clear()
        self._patchers.clear()
        self._enabled = False
        self._openai_instrumented = False
        self._anthropic_instrumented = False


# Global instrumentor instance
_auto_instrumentor: AutoInstrumentor | None = None


def get_instrumentor() -> AutoInstrumentor:
    """
    Get the global AutoInstrumentor instance.

    Returns:
        The global AutoInstrumentor.
    """
    global _auto_instrumentor

    if _auto_instrumentor is None:
        _auto_instrumentor = AutoInstrumentor()

    return _auto_instrumentor


def enable_auto_instrumentation(
    providers: list[str] | None = None,
) -> dict[str, bool]:
    """
    Enable auto-instrumentation for LLM providers.

    Args:
        providers: List of providers to instrument. If None, instruments all.
            Valid providers: "openai", "anthropic"

    Returns:
        Dictionary mapping provider name to success status.

    Example:
        ```python
        import tracecraft
        from tracecraft.instrumentation.auto import enable_auto_instrumentation

        tracecraft.init()
        results = enable_auto_instrumentation()

        # Now OpenAI/Anthropic calls are automatically traced
        client = openai.OpenAI()
        response = client.chat.completions.create(...)  # Automatically traced!
        ```
    """
    instrumentor = get_instrumentor()

    if providers is None:
        return instrumentor.instrument_all()

    results: dict[str, bool] = {}
    for provider in providers:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            results["openai"] = instrumentor.instrument_openai()
        elif provider_lower == "anthropic":
            results["anthropic"] = instrumentor.instrument_anthropic()
        else:
            logger.warning("Unknown provider: %s", provider)
            results[provider] = False

    return results


def disable_auto_instrumentation(
    providers: list[str] | None = None,
) -> None:
    """
    Disable auto-instrumentation.

    Args:
        providers: List of providers to uninstrument. If None, uninstruments all.

    Example:
        ```python
        from tracecraft.instrumentation.auto import disable_auto_instrumentation

        disable_auto_instrumentation()  # Disable all
        disable_auto_instrumentation(["openai"])  # Disable only OpenAI
        ```
    """
    instrumentor = get_instrumentor()

    if providers is None:
        instrumentor.uninstrument_all()
        return

    for provider in providers:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            instrumentor.uninstrument_openai()
        elif provider_lower == "anthropic":
            instrumentor.uninstrument_anthropic()


def is_instrumentation_enabled() -> bool:
    """
    Check if auto-instrumentation is currently enabled.

    Returns:
        True if any provider is instrumented.
    """
    if _auto_instrumentor is None:
        return False
    return _auto_instrumentor.is_enabled
