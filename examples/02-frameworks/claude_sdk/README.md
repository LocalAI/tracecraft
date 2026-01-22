# Claude Agent SDK Integration

AgentTrace integration with the Claude Agent SDK (Claude Code SDK) for observability
of Claude-powered agents.

## Prerequisites

```bash
pip install agenttrace claude-code-sdk
export ANTHROPIC_API_KEY="your-api-key"
```

## Quick Start

```python
from agenttrace import AgentTraceRuntime
from agenttrace.adapters.claude_sdk import ClaudeAgentTracer
from claude_code_sdk import query

# Initialize tracing
runtime = AgentTraceRuntime(console=True, jsonl=True)
tracer = ClaudeAgentTracer(runtime=runtime)

# Trace an agent task
with runtime.run("code_analysis") as run:
    async for message in query(
        prompt="Analyze the code structure",
        options=tracer.get_options(
            allowed_tools=["Read", "Glob", "Grep"]
        )
    ):
        print(message)
```

## Examples

| Example | Description |
|---------|-------------|
| `01_basic_tracing.py` | Basic integration, console output, step summary |
| `02_custom_hooks.py` | Merging custom hooks with tracer, audit logging |
| `03_production_config.py` | Environment-aware config, sampling, redaction |

## How It Works

ClaudeAgentTracer uses the Claude SDK's hook system to capture agent execution:

- **PreToolUse**: Creates a Step when a tool is about to be executed
- **PostToolUse**: Completes the Step with outputs and timing
- **Stop**: Handles agent completion, marks incomplete steps
- **SubagentStop**: Captures subagent (Task tool) completion

## Tool Type Mapping

| Claude Tool | AgentTrace StepType |
|-------------|---------------------|
| Read, Write, Edit | TOOL |
| Bash, KillShell | TOOL |
| Glob, Grep | TOOL |
| WebFetch | TOOL |
| WebSearch | RETRIEVAL |
| Task | AGENT |
| EnterPlanMode, ExitPlanMode | WORKFLOW |
| mcp__*__* | TOOL |

## Custom Hooks

ClaudeAgentTracer's `get_options()` method automatically merges your custom hooks
with the tracing hooks:

```python
from claude_code_sdk import HookMatcher

async def my_audit_hook(input_data, tool_use_id, context):
    # Log file operations
    if input_data.get("tool_name") == "Write":
        print(f"Writing to: {input_data.get('tool_input', {}).get('file_path')}")
    return {}

options = tracer.get_options(
    allowed_tools=["Read", "Write"],
    hooks={
        "PostToolUse": [HookMatcher(hooks=[my_audit_hook])]
    }
)
```

## Production Configuration

```python
from agenttrace.core.config import (
    AgentTraceConfig,
    ProcessorOrder,
    RedactionConfig,
    SamplingConfig,
)

config = AgentTraceConfig(
    service_name="my-claude-agent",
    processor_order=ProcessorOrder.SAFETY,  # Redact before sampling
    redaction=RedactionConfig(enabled=True),
    sampling=SamplingConfig(
        rate=0.1,  # 10% sampling
        always_keep_errors=True,
    ),
    console_enabled=False,
    jsonl_enabled=True,
)

runtime = AgentTraceRuntime(config=config)
tracer = ClaudeAgentTracer(runtime=runtime)
```

## API Reference

### ClaudeAgentTracer

```python
class ClaudeAgentTracer:
    def __init__(self, runtime: TALRuntime | None = None):
        """Create tracer, optionally with a runtime."""

    def get_hooks(self) -> dict[str, list]:
        """Get hook matchers for Claude SDK."""

    def get_options(self, **kwargs) -> ClaudeAgentOptions:
        """Create ClaudeAgentOptions with tracing hooks merged."""

    def trace(self, name: str) -> ContextManager[AgentRun]:
        """Context manager for tracing (creates runtime if needed)."""

    def clear(self) -> None:
        """Clear internal tracking state."""
```
