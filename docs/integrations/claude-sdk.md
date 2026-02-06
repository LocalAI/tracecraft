# Claude SDK Integration

TraceCraft integrates with the Claude Agent SDK through the `ClaudeTraceCraftr` adapter, which uses Claude's hook system to capture agent execution as TraceCraft Steps.

## Installation

```bash
pip install "tracecraft[claude-sdk]"
```

## Quick Start

```python
from tracecraft import TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

# Create runtime and tracer
runtime = TraceCraftRuntime(console=True)
tracer = ClaudeTraceCraftr(runtime=runtime)

# Trace a Claude agent session
with tracer.trace("my_task") as run:
    async for message in query(
        prompt="Analyze the code",
        options=tracer.get_options(allowed_tools=["Read", "Grep"])
    ):
        print(message)
```

## Using Hooks Directly

If you need more control, you can use the hooks directly:

```python
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import ClaudeCodeOptions

tracer = ClaudeTraceCraftr()

# Get hooks dict for ClaudeCodeOptions
hooks = tracer.get_hooks()

# Or create options with hooks automatically merged
options = tracer.get_options(
    allowed_tools=["Read", "Write", "Bash"],
    max_turns=10,
)
```

## Tool Type Mapping

The adapter automatically maps Claude SDK tools to TraceCraft step types:

| Tool | Step Type |
|------|-----------|
| Read, Write, Edit, Bash | `TOOL` |
| WebSearch | `RETRIEVAL` |
| Task | `AGENT` |
| EnterPlanMode, ExitPlanMode | `WORKFLOW` |
| MCP tools (`mcp__*`) | `TOOL` |

## Combining with Custom Hooks

The `get_options()` method merges tracing hooks with your custom hooks:

```python
from claude_code_sdk import HookMatcher

# Your custom hooks
my_hooks = {
    "PreToolUse": [HookMatcher(hooks=[my_pre_hook])],
}

# Tracing hooks are merged with custom hooks
options = tracer.get_options(hooks=my_hooks)
```

## Next Steps

- [Auto-Instrumentation](auto-instrumentation.md)
- [LangChain Integration](langchain.md)
- [User Guide](../user-guide/index.md)
