# LlamaIndex Integration

TraceCraft integrates with LlamaIndex through the `TraceCraftSpanHandler`.

## Installation

```bash
pip install "tracecraft[llamaindex]"
```

## Quick Start

```python
import tracecraft
from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# Initialize TraceCraft
tracecraft.init()

# Set global handler
import llama_index.core
llama_index.core.global_handler = TraceCraftSpanHandler()

# Use LlamaIndex normally
documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("What is TraceCraft?")
```

## Query Engines

```python
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

# Automatically traced
response = query_engine.query("Your question")
```

## Chat Engines

```python
chat_engine = index.as_chat_engine()

# Traced conversation
response = chat_engine.chat("Hello")
response = chat_engine.chat("Follow-up question")
```

## Agents

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool

def calculator(a: int, b: int) -> int:
    return a + b

tool = FunctionTool.from_defaults(fn=calculator)
agent = ReActAgent.from_tools([tool])

# Traced agent execution
response = agent.query("What is 5 + 3?")
```

## Next Steps

- [LangChain Integration](langchain.md)
- [User Guide](../user-guide/index.md)
