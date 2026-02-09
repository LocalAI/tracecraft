"""Auto-instrumentation discovery and setup for LLM SDKs.

This module provides utilities for automatically instrumenting
popular LLM SDKs with OpenTelemetry.
"""

from __future__ import annotations

import importlib
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Registry of known instrumentors
# Format: sdk_name -> (module_path, class_name)
INSTRUMENTORS: dict[str, tuple[str, str]] = {
    "openai": ("opentelemetry.instrumentation.openai", "OpenAIInstrumentor"),
    "anthropic": ("opentelemetry.instrumentation.anthropic", "AnthropicInstrumentor"),
    "langchain": ("opentelemetry.instrumentation.langchain", "LangchainInstrumentor"),
    "llamaindex": ("opentelemetry.instrumentation.llamaindex", "LlamaIndexInstrumentor"),
    "cohere": ("opentelemetry.instrumentation.cohere", "CohereInstrumentor"),
    "bedrock": ("opentelemetry.instrumentation.bedrock", "BedrockInstrumentor"),
    "vertexai": ("opentelemetry.instrumentation.vertexai", "VertexAIInstrumentor"),
    "mistral": ("opentelemetry.instrumentation.mistralai", "MistralAIInstrumentor"),
    "groq": ("opentelemetry.instrumentation.groq", "GroqInstrumentor"),
}

# Pip package names for each SDK
INSTRUMENTOR_PACKAGES: dict[str, str] = {
    "openai": "opentelemetry-instrumentation-openai",
    "anthropic": "opentelemetry-instrumentation-anthropic",
    "langchain": "opentelemetry-instrumentation-langchain",
    "llamaindex": "opentelemetry-instrumentation-llamaindex",
    "cohere": "opentelemetry-instrumentation-cohere",
    "bedrock": "opentelemetry-instrumentation-bedrock",
    "vertexai": "opentelemetry-instrumentation-vertexai",
    "mistral": "opentelemetry-instrumentation-mistralai",
    "groq": "opentelemetry-instrumentation-groq",
}


def get_available_instrumentors() -> list[str]:
    """Get list of SDK names that can be instrumented.

    Returns:
        List of SDK names (e.g., ["openai", "anthropic", ...]).
    """
    return list(INSTRUMENTORS.keys())


def instrument_sdk(sdk: str) -> bool:
    """Instrument a single SDK.

    Args:
        sdk: The SDK name to instrument (e.g., "openai", "anthropic").

    Returns:
        True if instrumentation succeeded, False otherwise.

    Raises:
        ValueError: If the SDK name is not recognized.
    """
    if sdk not in INSTRUMENTORS:
        valid_sdks = ", ".join(sorted(INSTRUMENTORS.keys()))
        raise ValueError(f"Unknown SDK: {sdk}. Valid options: {valid_sdks}")

    module_name, class_name = INSTRUMENTORS[sdk]

    try:
        module = importlib.import_module(module_name)
        instrumentor_class: Any = getattr(module, class_name)
        instrumentor = instrumentor_class()

        # Check if already instrumented (handle both property and method patterns)
        if hasattr(instrumentor, "is_instrumented_by_opentelemetry"):
            is_instrumented = instrumentor.is_instrumented_by_opentelemetry
            # Handle case where it's a method that needs to be called
            if callable(is_instrumented):
                is_instrumented = is_instrumented()
            if is_instrumented:
                return True  # Already instrumented

        instrumentor.instrument()
        return True

    except ImportError:
        package = INSTRUMENTOR_PACKAGES.get(sdk, f"opentelemetry-instrumentation-{sdk}")
        warnings.warn(
            f"Instrumentation not installed for '{sdk}'. Install with: pip install {package}",
            stacklevel=2,
        )
        return False

    except AttributeError as e:
        warnings.warn(f"Failed to instrument '{sdk}': {e}", stacklevel=2)
        return False

    except RuntimeError as e:
        # Instrumentors may raise RuntimeError if already instrumented differently
        warnings.warn(f"Failed to instrument '{sdk}': {e}", stacklevel=2)
        return False


def instrument_sdks(sdks: list[str]) -> list[str]:
    """Auto-instrument multiple SDKs.

    Args:
        sdks: List of SDK names to instrument.

    Returns:
        List of SDK names that were successfully instrumented.

    Example:
        >>> instrumented = instrument_sdks(["openai", "anthropic"])
        >>> print(f"Instrumented: {instrumented}")
        Instrumented: ['openai', 'anthropic']
    """
    instrumented = []
    for sdk in sdks:
        try:
            if instrument_sdk(sdk):
                instrumented.append(sdk)
        except ValueError as e:
            warnings.warn(str(e), stacklevel=2)

    return instrumented


def uninstrument_sdk(sdk: str) -> bool:
    """Remove instrumentation from a single SDK.

    Args:
        sdk: The SDK name to uninstrument.

    Returns:
        True if uninstrumentation succeeded, False otherwise.
    """
    if sdk not in INSTRUMENTORS:
        return False

    module_name, class_name = INSTRUMENTORS[sdk]

    try:
        module = importlib.import_module(module_name)
        instrumentor_class: Any = getattr(module, class_name)
        instrumentor = instrumentor_class()
        instrumentor.uninstrument()
        return True
    except (ImportError, AttributeError, RuntimeError):
        return False
