#!/usr/bin/env python3
"""LangChain Simple Chain - Basic LCEL chain with AgentTrace.

Demonstrates how to use the AgentTrace callback handler to automatically
trace LangChain chains, including prompts, LLM calls, and outputs.

Prerequisites:
    - Basic Python and LangChain knowledge
    - pip install langchain-openai

Environment Variables:
    - OPENAI_API_KEY: Your OpenAI API key

External Services:
    - OpenAI API

Usage:
    python examples/02-frameworks/langchain/01_simple_chain.py

Expected Output:
    - Trace showing chain execution with prompt and LLM steps
    - JSONL output with full trace data
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
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        return False

    try:
        import langchain_openai  # noqa: F401
    except ImportError:
        print("Error: langchain-openai not installed")
        print("Install with: pip install langchain-openai")
        return False

    return True


# Initialize AgentTrace
runtime = agenttrace.init(
    console=True,
    jsonl=True,
    jsonl_path="traces.jsonl",
)


def simple_chain_example() -> None:
    """Demonstrate simple chain tracing with LCEL."""
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    print("\n--- Simple Chain Example ---")

    # Create an LCEL chain: prompt -> llm
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant. Be very concise."),
            ("human", "{input}"),
        ]
    )
    llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=100)
    chain = prompt | llm

    # Create AgentTrace callback handler
    # This automatically traces all LangChain operations
    handler = AgentTraceCallbackHandler()

    # Create a run to group traces
    run = AgentRun(name="langchain_simple_chain", start_time=datetime.now(UTC))

    with run_context(run):
        # The handler captures:
        # - Chain start/end
        # - Prompt formatting
        # - LLM invocation with model info
        # - Token usage and timing
        result = chain.invoke(
            {"input": "What is 2 + 2? Just the number."},
            config={"callbacks": [handler]},
        )

    # Export the run
    runtime.end_run(run)
    handler.clear()

    print(f"Result: {result.content}")


def chain_with_tools_example() -> None:
    """Demonstrate chain with tool binding."""
    from langchain_core.tools import tool
    from langchain_openai import ChatOpenAI

    print("\n--- Chain with Tools Example ---")

    @tool
    def calculator(expression: str) -> str:
        """Calculate a math expression."""
        try:
            return str(eval(expression))  # noqa: S307
        except Exception as e:
            return f"Error: {e}"

    llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=100)
    llm_with_tools = llm.bind_tools([calculator])

    handler = AgentTraceCallbackHandler()
    run = AgentRun(name="langchain_tools", start_time=datetime.now(UTC))

    with run_context(run):
        # Tool calls are traced separately from the LLM call
        result = llm_with_tools.invoke(
            "What is 15 * 7?",
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Result: {result}")


def multi_step_chain_example() -> None:
    """Demonstrate multi-step chain with proper hierarchy."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    print("\n--- Multi-Step Chain Example ---")

    llm = ChatOpenAI(model="gpt-4o-mini", max_tokens=100)

    # Two-step translation chain
    step1_prompt = ChatPromptTemplate.from_template("Translate to French: {input}")
    step2_prompt = ChatPromptTemplate.from_template("Translate back to English: {text}")

    chain = (
        step1_prompt
        | llm
        | StrOutputParser()
        | (lambda x: {"text": x})
        | step2_prompt
        | llm
        | StrOutputParser()
    )

    handler = AgentTraceCallbackHandler()
    run = AgentRun(name="langchain_multi_step", start_time=datetime.now(UTC))

    with run_context(run):
        # The trace shows both LLM calls with their hierarchy
        result = chain.invoke(
            {"input": "Hello, how are you?"},
            config={"callbacks": [handler]},
        )

    runtime.end_run(run)
    handler.clear()

    print(f"Result: {result}")


def main() -> None:
    """Run the LangChain examples."""
    print("=" * 60)
    print("AgentTrace LangChain Integration")
    print("=" * 60)

    simple_chain_example()
    chain_with_tools_example()
    multi_step_chain_example()

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)
    print("\nKey points:")
    print("  - Use AgentTraceCallbackHandler for automatic tracing")
    print("  - Pass handler via config={'callbacks': [handler]}")
    print("  - Chain operations are traced hierarchically")
    print("  - Tools and LLM calls are captured separately")
    print("\nNext steps:")
    print("- Try 02_tools_and_agents.py for agent examples")
    print("- Try 03_rag_pipeline.py for RAG patterns")


if __name__ == "__main__":
    if not check_prerequisites():
        sys.exit(1)
    main()
