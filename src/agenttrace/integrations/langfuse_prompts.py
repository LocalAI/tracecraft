"""
Langfuse prompt provider for AgentTrace.

Allows fetching prompts from Langfuse while using AgentTrace for tracing.
Supports prompt versioning, labels, and caching.
"""

from __future__ import annotations

from typing import Any


class LangfusePromptProvider:
    """
    Fetch prompts from Langfuse for use with AgentTrace tracing.

    This allows you to manage prompts in Langfuse's prompt management UI
    while using AgentTrace for observability and tracing.

    Example:
        from agenttrace.integrations.langfuse_prompts import LangfusePromptProvider
        import agenttrace

        prompts = LangfusePromptProvider()

        @agenttrace.trace_llm(name="chat")
        def chat(user_input: str):
            prompt = prompts.get("research_agent_v2")
            return client.chat(
                model=prompt.config.get("model", "gpt-4o"),
                messages=[
                    {"role": "system", "content": prompt.compile()},
                    {"role": "user", "content": user_input}
                ]
            )
    """

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        """
        Initialize the Langfuse prompt provider.

        Args:
            public_key: Langfuse public key. Uses LANGFUSE_PUBLIC_KEY env var if not provided.
            secret_key: Langfuse secret key. Uses LANGFUSE_SECRET_KEY env var if not provided.
            host: Langfuse host URL. Uses LANGFUSE_HOST env var if not provided.
            cache_ttl_seconds: Cache TTL in seconds. Default 300 (5 minutes).
        """
        try:
            from langfuse import Langfuse, get_client
        except ImportError:
            raise ImportError("langfuse required. Install with: pip install langfuse")

        # Use get_client() for modern SDK pattern, fall back to direct instantiation
        if public_key or secret_key or host:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
        else:
            self._client = get_client()

        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = cache_ttl_seconds

    def get(
        self,
        name: str,
        version: int | None = None,
        label: str | None = None,
        cache: bool = True,
        **compile_vars: Any,
    ) -> PromptWrapper:
        """
        Get a prompt from Langfuse.

        Args:
            name: Prompt name.
            version: Specific version number (optional).
            label: Label like "production", "staging", or "latest".
            cache: Whether to cache the prompt. Default True.
            **compile_vars: Variables to compile into the prompt.

        Returns:
            PromptWrapper with the prompt content and metadata.

        Example:
            # Get production version (default)
            prompt = provider.get("movie-critic")

            # Get specific version
            prompt = provider.get("movie-critic", version=2)

            # Get staging version
            prompt = provider.get("movie-critic", label="staging")

            # Compile with variables
            prompt = provider.get("movie-critic", criticlevel="expert", movie="Dune 2")
            print(prompt.text)  # Compiled prompt text
        """
        import time

        cache_key = f"{name}:{version}:{label}"

        # Check cache
        if cache and cache_key in self._cache:
            cached_prompt, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                # Return cached prompt with new compile vars
                return PromptWrapper(cached_prompt, compile_vars)

        # Fetch from Langfuse
        kwargs: dict[str, Any] = {"name": name}
        if version is not None:
            kwargs["version"] = version
        if label is not None:
            kwargs["label"] = label

        prompt = self._client.get_prompt(**kwargs)

        # Cache the prompt
        if cache:
            self._cache[cache_key] = (prompt, time.time())

        return PromptWrapper(prompt, compile_vars)

    def get_chat(
        self,
        name: str,
        version: int | None = None,
        label: str | None = None,
        cache: bool = True,
        **compile_vars: Any,
    ) -> ChatPromptWrapper:
        """
        Get a chat prompt from Langfuse.

        Chat prompts return a list of messages instead of a single string.

        Args:
            name: Prompt name.
            version: Specific version number (optional).
            label: Label like "production", "staging", or "latest".
            cache: Whether to cache the prompt. Default True.
            **compile_vars: Variables to compile into the prompt.

        Returns:
            ChatPromptWrapper with the compiled messages.

        Example:
            prompt = provider.get_chat("movie-critic-chat", criticlevel="expert")
            messages = prompt.messages
            # [
            #   {"role": "system", "content": "You are an expert movie critic"},
            #   {"role": "user", "content": "Do you like Dune 2?"}
            # ]
        """
        import time

        cache_key = f"chat:{name}:{version}:{label}"

        # Check cache
        if cache and cache_key in self._cache:
            cached_prompt, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return ChatPromptWrapper(cached_prompt, compile_vars)

        # Fetch from Langfuse
        kwargs: dict[str, Any] = {"name": name, "type": "chat"}
        if version is not None:
            kwargs["version"] = version
        if label is not None:
            kwargs["label"] = label

        prompt = self._client.get_prompt(**kwargs)

        # Cache the prompt
        if cache:
            self._cache[cache_key] = (prompt, time.time())

        return ChatPromptWrapper(prompt, compile_vars)

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()

    def list_prompts(self) -> list[dict[str, Any]]:
        """
        List all available prompts.

        Returns:
            List of prompt metadata dicts.
        """
        # Note: This requires Langfuse API access
        # The SDK might not expose this directly
        try:
            prompts = self._client.client.prompts.list()
            return [
                {
                    "name": p.name,
                    "version": p.version,
                    "labels": p.labels,
                }
                for p in prompts.data
            ]
        except AttributeError:
            raise NotImplementedError(
                "list_prompts requires direct API access. "
                "Use the Langfuse UI to view available prompts."
            )


class PromptWrapper:
    """Wrapper around a Langfuse prompt with compilation support."""

    def __init__(self, prompt: Any, compile_vars: dict[str, Any]) -> None:
        self._prompt = prompt
        self._compile_vars = compile_vars

    @property
    def name(self) -> str:
        """Prompt name."""
        return self._prompt.name

    @property
    def version(self) -> int:
        """Prompt version number."""
        return self._prompt.version

    @property
    def labels(self) -> list[str]:
        """Prompt labels."""
        return getattr(self._prompt, "labels", [])

    @property
    def config(self) -> dict[str, Any]:
        """Prompt configuration (model, temperature, etc.)."""
        return getattr(self._prompt, "config", {})

    @property
    def text(self) -> str:
        """Compiled prompt text."""
        return self.compile()

    def compile(self, **extra_vars: Any) -> str:
        """
        Compile the prompt with variables.

        Args:
            **extra_vars: Additional variables to merge with init vars.

        Returns:
            Compiled prompt string.
        """
        all_vars = {**self._compile_vars, **extra_vars}
        if all_vars:
            return self._prompt.compile(**all_vars)
        return self._prompt.compile()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for tracing metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "labels": self.labels,
            "config": self.config,
        }


class ChatPromptWrapper:
    """Wrapper around a Langfuse chat prompt with compilation support."""

    def __init__(self, prompt: Any, compile_vars: dict[str, Any]) -> None:
        self._prompt = prompt
        self._compile_vars = compile_vars

    @property
    def name(self) -> str:
        """Prompt name."""
        return self._prompt.name

    @property
    def version(self) -> int:
        """Prompt version number."""
        return self._prompt.version

    @property
    def labels(self) -> list[str]:
        """Prompt labels."""
        return getattr(self._prompt, "labels", [])

    @property
    def config(self) -> dict[str, Any]:
        """Prompt configuration (model, temperature, etc.)."""
        return getattr(self._prompt, "config", {})

    @property
    def messages(self) -> list[dict[str, str]]:
        """Compiled messages list."""
        return self.compile()

    def compile(self, **extra_vars: Any) -> list[dict[str, str]]:
        """
        Compile the chat prompt with variables.

        Args:
            **extra_vars: Additional variables to merge with init vars.

        Returns:
            List of message dicts with 'role' and 'content'.
        """
        all_vars = {**self._compile_vars, **extra_vars}
        if all_vars:
            return self._prompt.compile(**all_vars)
        return self._prompt.compile()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for tracing metadata."""
        return {
            "name": self.name,
            "version": self.version,
            "labels": self.labels,
            "config": self.config,
        }


def create_tracing_callback(
    provider: LangfusePromptProvider,
    prompt_name: str,
    **prompt_kwargs: Any,
) -> dict[str, Any]:
    """
    Create trace metadata for a prompt fetch.

    Useful for adding prompt info to AgentTrace step attributes.

    Args:
        provider: LangfusePromptProvider instance.
        prompt_name: Name of the prompt to fetch.
        **prompt_kwargs: Additional kwargs for get().

    Returns:
        Dict with prompt metadata for tracing.

    Example:
        import agenttrace
        from agenttrace.integrations.langfuse_prompts import (
            LangfusePromptProvider,
            create_tracing_callback
        )

        prompts = LangfusePromptProvider()

        @agenttrace.trace_llm(name="chat")
        def chat(user_input: str):
            prompt = prompts.get("research_agent")
            metadata = create_tracing_callback(prompts, "research_agent")

            # Add to current step
            step = agenttrace.current_step()
            if step:
                step.attributes.update(metadata)

            return client.chat(...)
    """
    prompt = provider.get(prompt_name, **prompt_kwargs)
    return {
        "langfuse_prompt_name": prompt.name,
        "langfuse_prompt_version": prompt.version,
        "langfuse_prompt_labels": prompt.labels,
        "langfuse_prompt_config": prompt.config,
    }
