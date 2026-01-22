# LlamaIndex Integration Examples

Trace LlamaIndex applications using the `AgentTraceLlamaIndexCallback`.

## Prerequisites

```bash
pip install llama-index-core llama-index-llms-openai llama-index-agent-openai
export OPENAI_API_KEY=sk-...
```

## Integration Pattern

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from agenttrace.adapters.llamaindex import AgentTraceLlamaIndexCallback
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun

handler = AgentTraceLlamaIndexCallback()
Settings.callback_manager = CallbackManager(handlers=[handler])

run = AgentRun(name="my_query", start_time=datetime.now(UTC))

with run_context(run):
    response = index.as_query_engine().query("Your question")

runtime.end_run(run)
handler.clear()
```

## Examples

| File | Description |
|------|-------------|
| `01_basic_query.py` | Completion, chat, RAG, and streaming |
| `02_rag_with_retrieval.py` | Custom retrievers, query modes, multi-document RAG |
| `03_agents.py` | ReAct agents with function tools and query engine tools |

## What Gets Traced

- **LLM calls**: Model, prompt, response, tokens
- **Retrieval**: Query, retrieved nodes, scores
- **Agent steps**: Reasoning, tool selection, tool execution
- **Embeddings**: Text chunks being embedded

## Key Patterns

### Basic RAG

```python
from llama_index.core import VectorStoreIndex, Document

documents = [Document(text="Your content here")]
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

response = query_engine.query("Your question")
```

### ReAct Agent with Tools

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool

def my_function(arg: str) -> str:
    """Function description."""
    return result

tool = FunctionTool.from_defaults(fn=my_function)
agent = ReActAgent.from_tools([tool], llm=llm, verbose=False)

response = agent.chat("Your request")
```

### Query Engine as Tool

```python
from llama_index.core.tools import QueryEngineTool, ToolMetadata

tool = QueryEngineTool(
    query_engine=index.as_query_engine(),
    metadata=ToolMetadata(
        name="knowledge_base",
        description="Searches the knowledge base.",
    ),
)
agent = ReActAgent.from_tools([tool], llm=llm)
```

## Notes

- Set `Settings.callback_manager` before creating indexes or agents
- Always call `handler.clear()` after `runtime.end_run()`
- Use `Settings.llm` to set the default LLM for all operations
