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
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PatchConfig:
    """Configuration for patching an LLM provider method."""

    provider: str
    trace_name: str
    sync_method_path: str  # e.g., "resources.chat.completions.Completions.create"
    async_method_path: str  # e.g., "resources.chat.completions.AsyncCompletions.create"


def _create_patched_method(
    original: Callable[..., Any],
    trace_name: str,
    provider: str,
    is_async: bool = False,
) -> Callable[..., Any]:
    """
    Create a patched version of an LLM client method.

    Args:
        original: The original method to wrap.
        trace_name: Name for the trace step.
        provider: Provider name (e.g., "openai", "anthropic").
        is_async: Whether this is an async method.

    Returns:
        Patched method that wraps calls with tracing.
    """
    from tracecraft.instrumentation.decorators import trace_llm

    if is_async:

        async def patched_async(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            model = kwargs.get("model", "unknown")

            @trace_llm(name=trace_name, model=model, provider=provider)
            async def traced_call() -> Any:
                return await original(self_client, *args, **kwargs)

            return await traced_call()

        return patched_async
    else:

        def patched_sync(self_client: Any, *args: Any, **kwargs: Any) -> Any:
            model = kwargs.get("model", "unknown")

            @trace_llm(name=trace_name, model=model, provider=provider)
            def traced_call() -> Any:
                return original(self_client, *args, **kwargs)

            return traced_call()

        return patched_sync


def _get_nested_attr(obj: Any, path: str) -> Any:
    """Get a nested attribute from an object using dot notation."""
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _set_nested_attr(obj: Any, path: str, value: Any) -> None:
    """Set a nested attribute on an object using dot notation."""
    parts = path.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


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

    # Provider configurations for patching
    _PROVIDER_CONFIGS: dict[str, PatchConfig] = {
        "openai": PatchConfig(
            provider="openai",
            trace_name="openai.chat.completions.create",
            sync_method_path="resources.chat.completions.Completions.create",
            async_method_path="resources.chat.completions.AsyncCompletions.create",
        ),
        "anthropic": PatchConfig(
            provider="anthropic",
            trace_name="anthropic.messages.create",
            sync_method_path="resources.messages.Messages.create",
            async_method_path="resources.messages.AsyncMessages.create",
        ),
    }

    # OTel instrumentor class names
    _OTEL_INSTRUMENTORS: dict[str, str] = {
        "openai": "opentelemetry.instrumentation.openai.OpenAIInstrumentor",
        "anthropic": "opentelemetry.instrumentation.anthropic.AnthropicInstrumentor",
    }

    def __init__(self) -> None:
        """Initialize the auto-instrumentor."""
        self._instrumentors: list[Any] = []
        self._patchers: list[Callable[[], None]] = []
        self._enabled = False
        self._instrumented: dict[str, bool] = {
            "openai": False,
            "anthropic": False,
        }

    @property
    def is_enabled(self) -> bool:
        """Check if auto-instrumentation is enabled."""
        return self._enabled

    def _try_otel_instrumentation(self, provider: str) -> bool:
        """
        Try to use OpenTelemetry instrumentation for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic").

        Returns:
            True if OTel instrumentation was successful.
        """
        otel_path = self._OTEL_INSTRUMENTORS.get(provider)
        if not otel_path:
            return False

        try:
            module_path, class_name = otel_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            instrumentor_class = getattr(module, class_name)
            instrumentor = instrumentor_class()
            instrumentor.instrument()
            self._instrumentors.append(instrumentor)
            logger.info("%s auto-instrumentation enabled via OpenTelemetry", provider.title())
            return True
        except ImportError:
            logger.debug("OpenTelemetry %s instrumentation not available", provider)
            return False

    def _patch_provider(self, provider: str) -> None:
        """
        Manually patch a provider's client for tracing.

        Args:
            provider: Provider name (e.g., "openai", "anthropic").

        Raises:
            ImportError: If the provider module is not installed.
        """
        config = self._PROVIDER_CONFIGS.get(provider)
        if not config:
            raise ValueError(f"Unknown provider: {provider}")

        # Import the provider module
        module = __import__(provider)

        # Get original methods
        original_sync = _get_nested_attr(module, config.sync_method_path)
        original_async = _get_nested_attr(module, config.async_method_path)

        # Create patched methods
        patched_sync = _create_patched_method(
            original_sync, config.trace_name, config.provider, is_async=False
        )
        patched_async = _create_patched_method(
            original_async, config.trace_name, config.provider, is_async=True
        )

        # Capture paths for closure (mypy type narrowing doesn't work in default args)
        sync_path = config.sync_method_path
        async_path = config.async_method_path

        # Apply patches
        _set_nested_attr(module, sync_path, patched_sync)
        _set_nested_attr(module, async_path, patched_async)

        # Store unpatcher
        def unpatch(
            mod: Any = module,
            s_path: str = sync_path,
            a_path: str = async_path,
            orig_sync: Any = original_sync,
            orig_async: Any = original_async,
        ) -> None:
            _set_nested_attr(mod, s_path, orig_sync)
            _set_nested_attr(mod, a_path, orig_async)

        self._patchers.append(unpatch)

    def _instrument_provider(self, provider: str) -> bool:
        """
        Enable auto-instrumentation for a specific provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic").

        Returns:
            True if instrumentation was successful.
        """
        if self._instrumented.get(provider, False):
            logger.debug("%s already instrumented", provider.title())
            return True

        # Try OTel first
        if self._try_otel_instrumentation(provider):
            self._instrumented[provider] = True
            return True

        # Fall back to manual patching
        try:
            self._patch_provider(provider)
            self._instrumented[provider] = True
            logger.info("%s auto-instrumentation enabled via patching", provider.title())
            return True
        except ImportError:
            logger.warning(
                "%s not installed. Install with: pip install %s",
                provider.title(),
                provider,
            )
            return False
        except Exception:
            logger.exception("Failed to instrument %s", provider.title())
            return False

    def instrument_openai(self) -> bool:
        """Enable auto-instrumentation for OpenAI."""
        return self._instrument_provider("openai")

    def instrument_anthropic(self) -> bool:
        """Enable auto-instrumentation for Anthropic."""
        return self._instrument_provider("anthropic")

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

    def _uninstrument_provider(self, provider: str) -> None:
        """
        Disable auto-instrumentation for a specific provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic").
        """
        if not self._instrumented.get(provider, False):
            return

        # Uninstrument OTel instrumentors for this provider
        provider_title = provider.title()
        for instrumentor in list(self._instrumentors):
            if (
                hasattr(instrumentor, "__class__")
                and provider_title in instrumentor.__class__.__name__
            ):
                try:
                    instrumentor.uninstrument()
                    self._instrumentors.remove(instrumentor)
                except Exception:
                    logger.exception("Failed to uninstrument %s", provider_title)

        self._instrumented[provider] = False

    def uninstrument_openai(self) -> None:
        """Disable OpenAI auto-instrumentation."""
        self._uninstrument_provider("openai")

    def uninstrument_anthropic(self) -> None:
        """Disable Anthropic auto-instrumentation."""
        self._uninstrument_provider("anthropic")

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
        self._instrumented = {k: False for k in self._instrumented}


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
