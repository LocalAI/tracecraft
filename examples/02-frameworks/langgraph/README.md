# LangGraph Examples

Trace LangGraph state graphs and agents using AgentTrace. LangGraph uses the same callback system as LangChain, so no separate adapter is needed.

## Prerequisites

```bash
pip install langgraph langchain-openai
export OPENAI_API_KEY=sk-...
```

## Integration

LangGraph integrates through the same `AgentTraceCallbackHandler` used for LangChain:

```python
from agenttrace.adapters.langchain import AgentTraceCallbackHandler
from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun

handler = AgentTraceCallbackHandler()
run = AgentRun(name="langgraph_example", start_time=datetime.now(UTC))

with run_context(run):
    result = graph.invoke(
        initial_state,
        config={"callbacks": [handler]}
    )

runtime.end_run(run)
handler.clear()
```

## Examples

| Example | Description |
|---------|-------------|
| `01_simple_graph.py` | Basic state graph with single and multi-turn LLM nodes |
| `02_multi_node_graph.py` | Conditional routing with expert nodes and sequential pipelines |
| `03_react_agent.py` | ReAct agents with tools (prebuilt and custom) |

## What Gets Traced

- **State Graph Execution**: Graph nodes and edges
- **LLM Calls**: Model name, input/output tokens, latency
- **Tool Execution**: Tool inputs, outputs, and timing
- **Conditional Routing**: Routing decisions and branch paths

## Example Output

```
langgraph_react (1591.5ms) [269 tokens]
└── unknown 1591.4ms
    ├── unknown 903.8ms
    │   └── ChatOpenAI (gpt-4o-mini) 903.1ms [98/20 tokens]
    ├── unknown 0.7ms
    │   └── calculator 0.2ms
    └── unknown 685.8ms
        └── ChatOpenAI (gpt-4o-mini) 685.2ms [129/22 tokens]
```

## Running Examples

```bash
# Simple graph
python examples/02-frameworks/langgraph/01_simple_graph.py

# Multi-node with routing
python examples/02-frameworks/langgraph/02_multi_node_graph.py

# ReAct agent with tools
python examples/02-frameworks/langgraph/03_react_agent.py
```

## Key Patterns

### Simple State Graph

```python
from langgraph.graph import END, StateGraph

graph = StateGraph(State)
graph.add_node("chat", chat_node)
graph.set_entry_point("chat")
graph.add_edge("chat", END)
app = graph.compile()
```

### Conditional Routing

```python
def route_query(state: State) -> str:
    return "math" if "math" in state["category"] else "general"

graph.add_conditional_edges(
    "classifier",
    route_query,
    {"math": "math_expert", "general": "general_expert"}
)
```

### ReAct Agent

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(llm, [tool1, tool2])
result = agent.invoke({"messages": [("user", query)]})
```

## See Also

- [LangChain Examples](../langchain/) - Related callback-based integration
- [02-frameworks README](../README.md) - All framework integrations
