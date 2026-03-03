# LangChain Integration

TraceCraft provides native integration with LangChain through the `TraceCraftCallbackHandler`.

## Installation

```bash
pip install "tracecraft[langchain]"
```

This installs TraceCraft with LangChain support (`langchain-core>=0.1`).

## Quick Start

```python
import tracecraft
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Initialize TraceCraft
tracecraft.init()

# Create LangChain components
llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}")
])
chain = prompt | llm

# Create callback handler
handler = TraceCraftCallbackHandler()

# Use with invoke
response = chain.invoke(
    {"input": "Hello!"},
    config={"callbacks": [handler]}
)
```

## How It Works

The `TraceCraftCallbackHandler` implements LangChain's callback interface and automatically captures:

- Chain start/end events
- LLM invocations with model info
- Tool calls
- Retriever queries
- Token usage
- Errors and retries

All events are converted to TraceCraft spans with proper hierarchy.

## Basic Examples

### Simple Chain

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

llm = ChatOpenAI(model="gpt-4o-mini")
prompt = ChatPromptTemplate.from_template("Tell me about {topic}")
chain = prompt | llm

handler = TraceCraftCallbackHandler()
result = chain.invoke(
    {"topic": "TraceCraft"},
    config={"callbacks": [handler]}
)
```

### Multi-Step Chain

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

# Chain with multiple steps
translate_prompt = ChatPromptTemplate.from_template(
    "Translate to French: {text}"
)
summarize_prompt = ChatPromptTemplate.from_template(
    "Summarize in 10 words: {text}"
)

chain = (
    translate_prompt
    | llm
    | StrOutputParser()
    | (lambda x: {"text": x})
    | summarize_prompt
    | llm
    | StrOutputParser()
)

handler = TraceCraftCallbackHandler()
result = chain.invoke(
    {"text": "TraceCraft is amazing!"},
    config={"callbacks": [handler]}
)
```

## Agent Examples

### ReAct Agent

```python
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

tools = [calculator, get_weather]
llm = ChatOpenAI(model="gpt-4o-mini")

# Create ReAct agent
prompt = PromptTemplate.from_template(
    "Answer the following question: {input}\n"
    "You have access to these tools: {tools}\n"
    "{agent_scratchpad}"
)
agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Trace execution
handler = TraceCraftCallbackHandler()
result = agent_executor.invoke(
    {"input": "What's 15 * 7 and what's the weather in Seattle?"},
    config={"callbacks": [handler]}
)
```

### OpenAI Functions Agent

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

llm = ChatOpenAI(model="gpt-4o-mini")

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

agent = create_openai_functions_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

handler = TraceCraftCallbackHandler()
result = agent_executor.invoke(
    {"input": "Calculate 42 * 18"},
    config={"callbacks": [handler]}
)
```

## RAG Examples

### Basic RAG

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import Chroma

# Setup
embeddings = OpenAIEmbeddings()
vectorstore = Chroma(embedding_function=embeddings)
retriever = vectorstore.as_retriever()

llm = ChatOpenAI(model="gpt-4o-mini")

template = """Answer based on this context:
{context}

Question: {question}
"""
prompt = ChatPromptTemplate.from_template(template)

# RAG chain
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Trace RAG pipeline
handler = TraceCraftCallbackHandler()
result = chain.invoke(
    "What is TraceCraft?",
    config={"callbacks": [handler]}
)
```

### Advanced RAG with Reranking

```python
from langchain_core.runnables import RunnableLambda

def rerank(docs):
    """Rerank documents by relevance."""
    # Your reranking logic
    return sorted(docs, key=lambda d: d.metadata.get("score", 0), reverse=True)[:3]

# RAG with reranking
chain = (
    {
        "context": retriever | RunnableLambda(rerank),
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | StrOutputParser()
)

handler = TraceCraftCallbackHandler()
result = chain.invoke(
    "Explain TraceCraft's architecture",
    config={"callbacks": [handler]}
)
```

## Streaming

TraceCraft supports LangChain streaming:

```python
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)
prompt = ChatPromptTemplate.from_template("Tell me about {topic}")
chain = prompt | llm

handler = TraceCraftCallbackHandler()

# Stream tokens
for chunk in chain.stream(
    {"topic": "AI observability"},
    config={"callbacks": [handler]}
):
    print(chunk.content, end="", flush=True)
```

## LangGraph Integration

TraceCraft works with LangGraph:

```python
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage, AIMessage

# Define graph
graph = StateGraph()

def agent_node(state):
    # Agent logic
    return {"messages": state["messages"] + [AIMessage(content="Response")]}

graph.add_node("agent", agent_node)
graph.set_entry_point("agent")
graph.set_finish_point("agent")

app = graph.compile()

# Trace execution
handler = TraceCraftCallbackHandler()
result = app.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    config={"callbacks": [handler]}
)
```

## Advanced Usage

### Per-Run Configuration

```python
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun
from datetime import UTC, datetime

# Create explicit run
run = AgentRun(name="langchain_rag", start_time=datetime.now(UTC))

with run_context(run):
    handler = TraceCraftCallbackHandler()
    result = chain.invoke(
        {"input": "query"},
        config={"callbacks": [handler]}
    )

# Export the run
tracecraft.get_runtime().end_run(run)
```

### Custom Metadata

```python
handler = TraceCraftCallbackHandler()

# Add custom metadata to the handler
handler.metadata = {
    "user_id": "user-123",
    "session_id": "session-456",
}

result = chain.invoke(
    {"input": "query"},
    config={"callbacks": [handler]}
)
```

### Multiple Handlers

Combine TraceCraft with other handlers:

```python
from langchain.callbacks import StdOutCallbackHandler

tracecraft_handler = TraceCraftCallbackHandler()
stdout_handler = StdOutCallbackHandler()

result = chain.invoke(
    {"input": "query"},
    config={"callbacks": [tracecraft_handler, stdout_handler]}
)
```

## Best Practices

### 1. Initialize Once

Create the runtime once at application startup:

```python
# app.py
import tracecraft

# Initialize at startup
tracecraft.init(service_name="my-langchain-app")

# Use throughout your app
def some_function():
    handler = TraceCraftCallbackHandler()
    ...
```

### 2. Use Context Managers for Runs

Group related chains into runs:

```python
runtime = tracecraft.get_runtime()

with runtime.run("multi_chain_workflow"):
    handler = TraceCraftCallbackHandler()

    # Execute multiple chains in same run
    result1 = chain1.invoke(input1, config={"callbacks": [handler]})
    result2 = chain2.invoke(input2, config={"callbacks": [handler]})
```

### 3. Clear Handlers Between Runs

If reusing handlers:

```python
handler = TraceCraftCallbackHandler()

for query in queries:
    result = chain.invoke(
        {"input": query},
        config={"callbacks": [handler]}
    )
    handler.clear()  # Clear state for next run
```

### 4. Handle Errors Gracefully

```python
handler = TraceCraftCallbackHandler()

try:
    result = chain.invoke(
        {"input": "query"},
        config={"callbacks": [handler]}
    )
except Exception as e:
    # Error is automatically captured in trace
    print(f"Chain failed: {e}")
```

## Troubleshooting

### Callbacks Not Firing

Ensure you pass the handler via config:

```python
# Correct
chain.invoke(input, config={"callbacks": [handler]})

# Incorrect
chain.invoke(input)  # Handler not passed
```

### Missing Spans

Make sure TraceCraft is initialized:

```python
import tracecraft
tracecraft.init()  # Required!
```

### Duplicate Traces

Don't create a new handler for each invocation if you want grouped traces:

```python
# Good - reuse handler for grouped traces
handler = TraceCraftCallbackHandler()
for item in items:
    chain.invoke(item, config={"callbacks": [handler]})

# Creates separate traces for each
for item in items:
    handler = TraceCraftCallbackHandler()  # New handler each time
    chain.invoke(item, config={"callbacks": [handler]})
```

## Next Steps

- [LlamaIndex Integration](llamaindex.md)
- [PydanticAI Integration](pydantic-ai.md)
- [User Guide](../user-guide/)
