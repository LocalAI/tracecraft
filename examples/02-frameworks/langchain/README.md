# LangChain Integration Examples

Trace LangChain applications using the `TraceCraftCallbackHandler`.

## Prerequisites

```bash
pip install langchain-openai langchain
export OPENAI_API_KEY=sk-...
```

## Integration Pattern

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler
from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun

handler = TraceCraftCallbackHandler()
run = AgentRun(name="my_chain", start_time=datetime.now(UTC))

with run_context(run):
    result = chain.invoke(input, config={"callbacks": [handler]})

runtime.end_run(run)
handler.clear()
```

## Examples

| File | Description |
|------|-------------|
| `01_simple_chain.py` | Basic LCEL chains with prompts and LLM |
| `02_tools_and_agents.py` | Tool binding and manual tool calling loop |
| `03_rag_pipeline.py` | RAG with vector stores and retrievers |
| `04_streaming.py` | Streaming response handling |

## What Gets Traced

- **LLM calls**: Model, messages, response, tokens
- **Tool calls**: Tool name, inputs, outputs
- **Retrieval**: Query, documents retrieved
- **Chain steps**: Each runnable in the chain

## Key Patterns

### Tool Binding (Modern Pattern)

```python
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

@tool
def my_tool(arg: str) -> str:
    """Tool description."""
    return result

llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools([my_tool])
response = llm_with_tools.invoke(messages, config={"callbacks": [handler]})
```

### RAG Pipeline

```python
from langchain_core.runnables import RunnablePassthrough

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
result = rag_chain.invoke(query, config={"callbacks": [handler]})
```

### Streaming

```python
for chunk in chain.stream(input, config={"callbacks": [handler]}):
    print(chunk, end="", flush=True)
```

## Notes

- Always call `handler.clear()` after `runtime.end_run()` when reusing handlers
- For LangGraph workflows, see the `langgraph/` directory
- The callback handler works with all LCEL runnables
