#!/usr/bin/env python3
"""LangChain RAG Pipeline - Trace retrieval-augmented generation with AgentTrace.

Demonstrates how to trace RAG pipelines including document retrieval,
context injection, and LLM generation.

Prerequisites:
    - pip install langchain-openai langchain-community faiss-cpu

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langchain/03_rag_pipeline.py

Expected Output:
    - Trace showing retrieval and generation steps
    - Retrieved documents captured in trace
    - Token usage for embeddings and LLM
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import agenttrace
from agenttrace.adapters.langchain import AgentTraceCallbackHandler
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun


def check_prerequisites() -> bool:
    """Verify all prerequisites are met."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return False

    try:
        import langchain_community  # noqa: F401
        import langchain_openai  # noqa: F401
    except ImportError:
        print("Error: Required packages not installed")
        print("Install with: pip install langchain-openai langchain-community faiss-cpu")
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def simple_rag_example() -> None:
    """Demonstrate simple RAG with in-memory vector store."""
    from langchain_community.vectorstores import FAISS
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    print("\n--- Simple RAG Example ---")

    # Sample documents
    documents = [
        "AgentTrace is an observability SDK for AI agents.",
        "AgentTrace supports LangChain, LlamaIndex, and PydanticAI.",
        "Traces can be exported to JSONL, HTML, or OTLP backends.",
        "The library uses a decorator-based API for manual tracing.",
        "Processors can enrich traces with cost and token data.",
    ]

    # Create embeddings and vector store
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_texts(documents, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    # Create RAG chain
    prompt = ChatPromptTemplate.from_template(
        """Answer based on the context:

Context: {context}

Question: {question}

Answer:"""
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def format_docs(docs: list) -> str:
        return "\n".join(doc.page_content for doc in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    handler = AgentTraceCallbackHandler()
    run = AgentRun(name="langchain_simple_rag", start_time=datetime.now(UTC))

    with run_context(run):
        result = chain.invoke(
            "What frameworks does AgentTrace support?",
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Answer: {result}")


def conversational_rag_example() -> None:
    """Demonstrate conversational RAG with history."""
    from langchain_community.vectorstores import FAISS
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_core.runnables import RunnablePassthrough
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    print("\n--- Conversational RAG Example ---")

    # Sample documents about a fictional product
    documents = [
        "CloudSync Pro is a file synchronization service.",
        "CloudSync Pro offers 100GB free storage for new users.",
        "Premium plans start at $9.99/month with 1TB storage.",
        "CloudSync Pro supports Windows, macOS, Linux, iOS, and Android.",
        "End-to-end encryption is enabled by default on all plans.",
        "The maximum file size is 5GB for free users and 50GB for premium.",
    ]

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_texts(documents, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer questions about CloudSync Pro based on this context:\n\n{context}",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def format_docs(docs: list) -> str:
        return "\n".join(doc.page_content for doc in docs)

    chain = (
        {
            "context": retriever | format_docs,
            "question": RunnablePassthrough(),
            "chat_history": lambda _: [],
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    handler = AgentTraceCallbackHandler()
    run = AgentRun(name="langchain_conversational_rag", start_time=datetime.now(UTC))

    with run_context(run):
        # First question
        result1 = chain.invoke(
            "What is CloudSync Pro?",
            config={"callbacks": [handler]},
        )
        print("Q1: What is CloudSync Pro?")
        print(f"A1: {result1}")

        # Follow-up question
        result2 = chain.invoke(
            "How much does it cost?",
            config={"callbacks": [handler]},
        )
        print("\nQ2: How much does it cost?")
        print(f"A2: {result2}")

    runtime.end_run(run)
    handler.clear()


def rag_with_sources_example() -> None:
    """Demonstrate RAG with source attribution."""
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    print("\n--- RAG with Sources Example ---")

    # Documents with metadata
    docs = [
        Document(
            page_content="Python 3.12 introduced new syntax for type parameters.",
            metadata={"source": "python_docs.md", "section": "What's New"},
        ),
        Document(
            page_content="The match statement was added in Python 3.10.",
            metadata={"source": "python_docs.md", "section": "Pattern Matching"},
        ),
        Document(
            page_content="Async comprehensions are supported since Python 3.6.",
            metadata={"source": "async_guide.md", "section": "Comprehensions"},
        ),
    ]

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vectorstore = FAISS.from_documents(docs, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    prompt = ChatPromptTemplate.from_template(
        """Answer with source citations.

Context:
{context}

Question: {question}

Provide your answer and cite sources."""
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def format_docs_with_sources(docs: list) -> str:
        formatted = []
        for doc in docs:
            source = doc.metadata.get("source", "unknown")
            section = doc.metadata.get("section", "")
            formatted.append(f"[{source} - {section}]: {doc.page_content}")
        return "\n".join(formatted)

    chain = (
        {"context": retriever | format_docs_with_sources, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    handler = AgentTraceCallbackHandler()
    run = AgentRun(name="langchain_rag_with_sources", start_time=datetime.now(UTC))

    with run_context(run):
        result = chain.invoke(
            "When was the match statement added to Python?",
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Answer: {result}")


def main() -> None:
    """Run the LangChain RAG examples."""
    print("=" * 60)
    print("AgentTrace LangChain RAG Pipelines")
    print("=" * 60)

    simple_rag_example()
    conversational_rag_example()
    rag_with_sources_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey patterns demonstrated:")
    print("  - Simple RAG with FAISS vector store")
    print("  - Conversational RAG with chat history")
    print("  - RAG with source attribution")
    print("\nTrace shows:")
    print("  - Retriever execution with query")
    print("  - Retrieved document contents")
    print("  - LLM generation with context")
    print("\nNext steps:")
    print("- Try 04_streaming.py for streaming responses")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
