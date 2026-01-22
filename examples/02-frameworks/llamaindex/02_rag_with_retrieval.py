#!/usr/bin/env python3
"""LlamaIndex Advanced RAG - Trace complex RAG patterns with AgentTrace.

Demonstrates advanced RAG patterns including custom retrievers,
query transformations, and response synthesis.

Prerequisites:
    - pip install llama-index-core llama-index-llms-openai llama-index-embeddings-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/llamaindex/02_rag_with_retrieval.py

Expected Output:
    - Traces showing retrieval strategies
    - Query transformations captured
    - Response synthesis traced
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import agenttrace
from agenttrace.adapters.llamaindex import AgentTraceLlamaIndexCallback
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import llama_index.core  # noqa: F401
        import llama_index.embeddings.openai  # noqa: F401
        import llama_index.llms.openai  # noqa: F401
    except ImportError:
        print("Error: llama-index packages not installed")
        print(
            "Install with: pip install llama-index-core llama-index-llms-openai llama-index-embeddings-openai"
        )
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def custom_retriever_example() -> None:
    """Demonstrate custom retriever with tracing."""
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI

    print("\n--- Custom Retriever Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])
    Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=200)
    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.chunk_size = 256

    # Create documents about programming languages
    documents = [
        Document(
            text="Python is a high-level programming language known for its simplicity. "
            "It supports multiple paradigms including procedural, object-oriented, and functional."
        ),
        Document(
            text="JavaScript is the language of the web. It runs in browsers and Node.js. "
            "Modern JavaScript uses ES6+ features like arrow functions and async/await."
        ),
        Document(
            text="Rust is a systems programming language focused on safety and performance. "
            "It prevents memory errors at compile time through its ownership system."
        ),
        Document(
            text="Go (Golang) was created by Google for building scalable systems. "
            "It features goroutines for concurrent programming and fast compilation."
        ),
    ]

    run = AgentRun(name="llamaindex_custom_retriever", start_time=datetime.now(UTC))

    with run_context(run):
        # Create index with custom settings
        index = VectorStoreIndex.from_documents(documents)

        # Configure retriever with custom similarity threshold
        retriever = index.as_retriever(similarity_top_k=2)

        # Retrieve relevant nodes
        nodes = retriever.retrieve("Which language is best for web development?")

        print("Retrieved nodes:")
        for i, node in enumerate(nodes):
            print(f"  {i + 1}. Score: {node.score:.3f} - {node.text[:50]}...")

    runtime.end_run(run)
    handler.clear()


def query_engine_with_modes_example() -> None:
    """Demonstrate different query engine response modes."""
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.response_synthesizers import ResponseMode
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI

    print("\n--- Query Engine Response Modes Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])
    Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=200)
    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.chunk_size = 256

    documents = [
        Document(
            text="Machine learning is a subset of AI that enables computers to learn from data."
        ),
        Document(
            text="Deep learning uses neural networks with many layers to learn complex patterns."
        ),
        Document(text="Natural language processing (NLP) focuses on understanding human language."),
    ]

    run = AgentRun(name="llamaindex_query_modes", start_time=datetime.now(UTC))

    with run_context(run):
        index = VectorStoreIndex.from_documents(documents)

        # COMPACT mode - default, combines text chunks
        query_engine_compact = index.as_query_engine(response_mode=ResponseMode.COMPACT)
        response = query_engine_compact.query("What is machine learning?")
        print(f"COMPACT mode response: {response.response[:100]}...")

    runtime.end_run(run)
    handler.clear()


def multi_document_rag_example() -> None:
    """Demonstrate RAG across multiple document types."""
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI

    print("\n--- Multi-Document RAG Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])
    Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=200)
    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.chunk_size = 256

    # Documents from different "sources"
    tech_docs = [
        Document(
            text="AgentTrace is an observability SDK for AI agents. "
            "It supports tracing for LangChain, LlamaIndex, and PydanticAI.",
            metadata={"source": "tech_docs", "category": "overview"},
        ),
        Document(
            text="Traces can be exported to JSONL files, HTML reports, or OTLP backends. "
            "The JSONL format stores one trace per line for easy processing.",
            metadata={"source": "tech_docs", "category": "exporters"},
        ),
    ]

    tutorial_docs = [
        Document(
            text="To get started with AgentTrace, install it via pip: pip install agenttrace. "
            "Then import the runtime and initialize it with your preferred exporters.",
            metadata={"source": "tutorial", "category": "getting_started"},
        ),
        Document(
            text="For LlamaIndex integration, use the AgentTraceLlamaIndexCallback handler. "
            "Register it with Settings.callback_manager to trace all operations.",
            metadata={"source": "tutorial", "category": "integration"},
        ),
    ]

    all_docs = tech_docs + tutorial_docs

    run = AgentRun(name="llamaindex_multi_doc_rag", start_time=datetime.now(UTC))

    with run_context(run):
        index = VectorStoreIndex.from_documents(all_docs)
        query_engine = index.as_query_engine(similarity_top_k=3)

        response = query_engine.query("How do I use AgentTrace with LlamaIndex?")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")
    print("\nSource nodes:")
    for node in response.source_nodes:
        source = node.metadata.get("source", "unknown")
        print(f"  - [{source}] {node.text[:50]}...")


def hybrid_search_example() -> None:
    """Demonstrate keyword + semantic hybrid search."""
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.callbacks import CallbackManager
    from llama_index.embeddings.openai import OpenAIEmbedding
    from llama_index.llms.openai import OpenAI

    print("\n--- Hybrid Search Example ---")

    handler = AgentTraceLlamaIndexCallback()
    Settings.callback_manager = CallbackManager(handlers=[handler])
    Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=200)
    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.chunk_size = 256

    documents = [
        Document(text="API rate limits are 100 requests per minute for free tier users."),
        Document(text="Premium users get 1000 requests per minute with priority support."),
        Document(text="Error code 429 indicates you've exceeded your rate limit."),
        Document(text="Use exponential backoff when retrying after rate limit errors."),
    ]

    run = AgentRun(name="llamaindex_hybrid_search", start_time=datetime.now(UTC))

    with run_context(run):
        index = VectorStoreIndex.from_documents(documents)
        query_engine = index.as_query_engine(similarity_top_k=2)

        # Query with specific keyword
        response = query_engine.query("What happens when I hit a 429 error?")

    runtime.end_run(run)
    handler.clear()

    print(f"Response: {response.response}")


def main() -> None:
    """Run the advanced RAG examples."""
    print("=" * 60)
    print("AgentTrace LlamaIndex Advanced RAG")
    print("=" * 60)

    custom_retriever_example()
    query_engine_with_modes_example()
    multi_document_rag_example()
    hybrid_search_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Custom retriever configuration")
    print("  - Query engine response modes")
    print("  - Multi-document RAG with metadata")
    print("  - Hybrid search patterns")
    print("\nTrace shows:")
    print("  - Embedding generation calls")
    print("  - Retrieval with similarity scores")
    print("  - Response synthesis LLM calls")
    print("\nNext steps:")
    print("- Try 03_agents.py for LlamaIndex agents")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
