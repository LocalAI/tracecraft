#!/usr/bin/env python3
"""LlamaIndex Basic Query - Trace LlamaIndex operations with TraceCraft.

Demonstrates how to use the TraceCraft span handler to automatically trace
LlamaIndex operations including completions, chat, RAG, and streaming.

Prerequisites:
    - Basic LlamaIndex knowledge
    - pip install llama-index-core llama-index-llms-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/llamaindex/01_basic_query.py

Expected Output:
    - Traces showing LLM calls, embeddings, and retrieval
    - RAG pipeline traced end-to-end
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import tracecraft
from tracecraft.adapters.llamaindex import TraceCraftLlamaIndexCallback
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import llama_index.core  # noqa: F401
        import llama_index.llms.openai  # noqa: F401
    except ImportError:
        print("Error: llama-index packages not installed")
        print("Install with: pip install llama-index-core llama-index-llms-openai")
        return False

    return True


# Initialize TraceCraft
runtime = tracecraft.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def simple_completion_example() -> None:
    """Demonstrate simple LLM completion tracing."""
    from llama_index.core import Settings
    from llama_index.core.callbacks import CallbackManager
    from llama_index.llms.openai import OpenAI

    print("\n--- Simple Completion Example ---")

    # Set up TraceCraft callback handler
    handler = TraceCraftLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    # Create LLM
    llm = OpenAI(model="gpt-4o-mini", max_tokens=100)

    run = AgentRun(name="llamaindex_completion", start_time=datetime.now(UTC))

    with run_context(run):
        # The handler traces the LLM call automatically
        response = llm.complete("What is the capital of France? Be concise.")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.text}")


def chat_example() -> None:
    """Demonstrate chat completion tracing."""
    from llama_index.core import Settings
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.llms import ChatMessage
    from llama_index.llms.openai import OpenAI

    print("\n--- Chat Example ---")

    handler = TraceCraftLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    llm = OpenAI(model="gpt-4o-mini", max_tokens=100)

    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="What is 2 + 2?"),
    ]

    run = AgentRun(name="llamaindex_chat", start_time=datetime.now(UTC))

    with run_context(run):
        response = llm.chat(messages)

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.message.content}")


def rag_example() -> None:
    """Demonstrate RAG (index + query) tracing.

    This traces the full RAG pipeline:
    - Document indexing (embedding calls)
    - Vector retrieval
    - LLM response generation
    """
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager
    from llama_index.llms.openai import OpenAI

    print("\n--- RAG Example ---")

    handler = TraceCraftLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])
    Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=200)
    Settings.chunk_size = 256

    # Create simple documents
    documents = [
        Document(text="The capital of France is Paris. Paris is known for the Eiffel Tower."),
        Document(
            text="The capital of Germany is Berlin. Berlin is known for the Brandenburg Gate."
        ),
        Document(text="The capital of Italy is Rome. Rome is known for the Colosseum."),
    ]

    run = AgentRun(name="llamaindex_rag", start_time=datetime.now(UTC))

    with run_context(run):
        # Create index (traces embedding calls)
        index = VectorStoreIndex.from_documents(documents)

        # Query (traces retrieval and LLM calls)
        query_engine = index.as_query_engine()
        response = query_engine.query("What is the capital of France and what is it known for?")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")


def streaming_example() -> None:
    """Demonstrate streaming completion tracing."""
    from llama_index.core import Settings
    from llama_index.core.callbacks import CallbackManager
    from llama_index.llms.openai import OpenAI

    print("\n--- Streaming Example ---")

    handler = TraceCraftLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])

    llm = OpenAI(model="gpt-4o-mini", max_tokens=100)

    run = AgentRun(name="llamaindex_streaming", start_time=datetime.now(UTC))

    with run_context(run):
        stream = llm.stream_complete("Count from 1 to 5.")
        chunks = []
        for chunk in stream:
            chunks.append(chunk.text)

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {''.join(chunks)}")


def main() -> None:
    """Run the LlamaIndex examples."""
    print("=" * 60)
    print("TraceCraft LlamaIndex Integration")
    print("=" * 60)

    simple_completion_example()
    chat_example()
    rag_example()
    streaming_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey points:")
    print("  - Use TraceCraftLlamaIndexCallback with Settings.callback_manager")
    print("  - All LlamaIndex operations are traced automatically")
    print("  - RAG pipelines show embeddings, retrieval, and generation")
    print("\nNext steps:")
    print("- Try 02_rag_with_retrieval.py for advanced RAG")
    print("- Try 03_agents.py for LlamaIndex agents")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
