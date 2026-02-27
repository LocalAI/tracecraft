# Claude SDK Integration

TraceCraft integrates with the Claude Agent SDK through the `ClaudeTraceCraftr` adapter, which
hooks into the SDK's `PreToolUse`, `PostToolUse`, `Stop`, and `SubagentStop` events to capture
every tool call and subagent invocation as a TraceCraft Step — with no changes to your Claude
agent prompts or tool definitions.

## Installation

```bash
pip install "tracecraft[claude-sdk]"
```

This installs TraceCraft with `claude-code-sdk` support. The `claude-code-sdk` package must also
be installed:

```bash
pip install claude-code-sdk
```

## Quick Start

```python
import asyncio
import tracecraft
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query, ClaudeCodeOptions

# Initialize TraceCraft
tracecraft.init(console=True)

# Create the tracer
tracer = ClaudeTraceCraftr()

async def main() -> None:
    # trace() creates an AgentRun and hooks into the SDK
    with tracer.trace("code_analysis") as run:
        async for message in query(
            prompt="Read the README.md file and summarize it in three bullet points.",
            options=tracer.get_options(allowed_tools=["Read"]),
        ):
            print(message)

    # run.steps contains one TOOL step per Read call
    for step in run.steps:
        print(f"{step.type.value}: {step.name} ({step.duration_ms:.0f}ms)")

asyncio.run(main())
```

## How It Works

`ClaudeTraceCraftr` works through Claude SDK's hook system. When you call `tracer.get_options()`,
it returns a `ClaudeCodeOptions` object with four hook handlers pre-configured:

| Hook | When called | What TraceCraft does |
|---|---|---|
| `PreToolUse` | Before any tool runs | Creates a `Step`, records `start_time` and `inputs` |
| `PostToolUse` | After the tool returns | Completes the step with `end_time`, `duration_ms`, and `outputs` |
| `Stop` | Agent finishes normally | Closes any uncompleted steps |
| `SubagentStop` | A Task subagent finishes | Closes the `AGENT`-typed step for that subagent |

Each hook is identified by a `tool_use_id` that correlates `PreToolUse` with its matching
`PostToolUse`. Tool responses longer than 10,000 characters are automatically truncated to
`...[truncated]` to prevent memory bloat.

## Tool Type Mapping

The adapter maps Claude SDK tool names to TraceCraft `StepType` values:

| Tool | StepType | Notes |
|---|---|---|
| `Read` | `TOOL` | File read |
| `Write` | `TOOL` | File write |
| `Edit` | `TOOL` | File edit |
| `MultiEdit` | `TOOL` | Multiple file edits |
| `NotebookEdit` | `TOOL` | Jupyter notebook edit |
| `Glob` | `TOOL` | File pattern search |
| `Grep` | `TOOL` | Content search |
| `Bash` | `TOOL` | Shell command |
| `KillShell` | `TOOL` | Terminate shell |
| `WebFetch` | `TOOL` | HTTP fetch |
| `WebSearch` | `RETRIEVAL` | Web search (retrieval) |
| `Task` | `AGENT` | Subagent invocation |
| `TaskOutput` | `TOOL` | Read subagent output |
| `AskUserQuestion` | `TOOL` | Interactive prompt |
| `TodoWrite` | `TOOL` | Task list management |
| `EnterPlanMode` | `WORKFLOW` | Enter planning mode |
| `ExitPlanMode` | `WORKFLOW` | Exit planning mode |
| `Skill` | `WORKFLOW` | Skill invocation |
| `SlashCommand` | `WORKFLOW` | Slash command |
| `mcp__*` | `TOOL` | Any MCP server tool |

Any tool not in this table defaults to `StepType.TOOL`.

## Basic Examples

### Basic Tracing

```python
import asyncio
import tracecraft
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

tracecraft.init()
tracer = ClaudeTraceCraftr()

async def main() -> None:
    with tracer.trace("find_and_count_functions") as run:
        async for message in query(
            prompt="Use Grep to count how many Python functions are defined in src/.",
            options=tracer.get_options(allowed_tools=["Grep"]),
        ):
            pass  # Process messages as needed

    print(f"Steps captured: {len(run.steps)}")
    for step in run.steps:
        print(f"  {step.type.value}: {step.name}")

asyncio.run(main())
```

### trace() Context Manager

`ClaudeTraceCraftr.trace(name)` is a context manager that:

1. Creates a `TraceCraftRuntime` if one has not been provided.
2. Opens an `AgentRun` with the given name.
3. Yields the `AgentRun` so you can inspect or annotate it.
4. Closes the run and exports it when the block exits.

```python
import asyncio
from tracecraft import TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

# Supply an existing runtime to reuse exporters
runtime = TraceCraftRuntime(console=True, jsonl=True)
tracer = ClaudeTraceCraftr(runtime=runtime)

async def run_task(prompt: str, task_name: str) -> None:
    with tracer.trace(task_name) as run:
        async for message in query(
            prompt=prompt,
            options=tracer.get_options(allowed_tools=["Read", "Grep", "Glob"]),
        ):
            pass
        # Annotate the run before it closes
        run.attributes["prompt_hash"] = hash(prompt)

asyncio.run(run_task("Find all TODO comments in the codebase.", "find_todos"))
```

## Custom Hooks

The `get_options()` method merges your custom hooks with the tracing hooks. Both run for every
event — you do not lose your own hook logic by enabling tracing.

### Audit Logging Hook

```python
import asyncio
import logging
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query, HookMatcher

logger = logging.getLogger("audit")
tracer = ClaudeTraceCraftr()

async def audit_pre_tool(input_data: dict, tool_use_id: str | None, _ctx) -> dict:
    """Log every tool call to the audit log before it runs."""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    logger.info("TOOL_START tool=%s id=%s input=%s", tool_name, tool_use_id, tool_input)
    return {}

my_hooks = {
    "PreToolUse": [HookMatcher(hooks=[audit_pre_tool])],
}

async def main() -> None:
    with tracer.trace("audited_session"):
        async for message in query(
            prompt="List all Python files in src/.",
            # Tracing hooks and audit hook both run
            options=tracer.get_options(
                allowed_tools=["Glob"],
                hooks=my_hooks,
            ),
        ):
            pass

asyncio.run(main())
```

### Safety Hooks

```python
import asyncio
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query, HookMatcher

tracer = ClaudeTraceCraftr()

BLOCKED_PATTERNS = ["rm -rf", "sudo ", "curl | bash", "wget | sh"]

async def safety_check(input_data: dict, tool_use_id: str | None, _ctx) -> dict:
    """Block dangerous shell commands before they execute."""
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            # Returning a non-empty dict with "error" blocks the tool
            return {"error": f"Blocked: command contains '{pattern}'"}

    return {}

safety_hooks = {
    "PreToolUse": [HookMatcher(hooks=[safety_check])],
}

async def main() -> None:
    with tracer.trace("safe_session"):
        async for message in query(
            prompt="Run 'ls -la' in the current directory.",
            options=tracer.get_options(
                allowed_tools=["Bash"],
                hooks=safety_hooks,
            ),
        ):
            pass

asyncio.run(main())
```

## Streaming Support

Claude SDK messages stream as they arrive. TraceCraft captures tool-level spans regardless of
how you consume the message stream:

```python
import asyncio
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query, TextBlock, ToolUseBlock

tracer = ClaudeTraceCraftr()

async def main() -> None:
    with tracer.trace("streaming_session") as run:
        async for message in query(
            prompt="Read src/tracecraft/core/models.py and list its public classes.",
            options=tracer.get_options(allowed_tools=["Read"]),
        ):
            # Process message content blocks as they stream in
            if hasattr(message, "content"):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        print(f"\n[Tool: {block.name}]")
        print()

    # Steps are fully formed after the stream ends
    print(f"\nTotal tool steps: {len(run.steps)}")

asyncio.run(main())
```

## Subagent Tracing

When Claude uses the `Task` tool to spawn a subagent, TraceCraft creates an `AGENT`-typed step
and waits for the `SubagentStop` hook to close it with the subagent's result.

### Task Tool Tracing

```python
import asyncio
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

tracer = ClaudeTraceCraftr()

async def main() -> None:
    with tracer.trace("multi_agent_workflow") as run:
        async for message in query(
            prompt=(
                "Use the Task tool to spawn a subagent that reads CLAUDE.md "
                "and returns a one-sentence summary."
            ),
            options=tracer.get_options(allowed_tools=["Task", "Read"]),
        ):
            pass

    # The Task step appears as AGENT type; its child steps are inside the subagent run
    agent_steps = [s for s in run.steps if s.type.value == "agent"]
    for step in agent_steps:
        print(f"Subagent: {step.name}")
        if step.outputs:
            print(f"  Result: {step.outputs.get('result', '')[:200]}")

asyncio.run(main())
```

### Nested Workflows

```python
import asyncio
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

tracer = ClaudeTraceCraftr()

async def main() -> None:
    with tracer.trace("nested_workflow") as run:
        async for message in query(
            prompt=(
                "First, use Task to find all test files. "
                "Then, use Task to count the total number of test functions found."
            ),
            options=tracer.get_options(allowed_tools=["Task", "Glob", "Grep"]),
        ):
            pass

    # Both Task steps appear as AGENT type in run.steps
    print(f"Run '{run.name}' captured {len(run.steps)} steps")
    for step in run.steps:
        indent = "  " if step.parent_id else ""
        print(f"{indent}{step.type.value}: {step.name} ({step.duration_ms:.0f}ms)")

asyncio.run(main())
```

## Production Configuration

### Environment-Aware Config

```python
import os
import asyncio
import tracecraft
from tracecraft import TraceCraftConfig, TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
from claude_code_sdk import query

def build_runtime() -> TraceCraftRuntime:
    env = os.getenv("APP_ENV", "development")
    config = TraceCraftConfig(
        service_name="my-claude-agent",
        environment=env,
    )
    if env == "production":
        return TraceCraftRuntime(config=config, jsonl=True, otlp=True)
    return TraceCraftRuntime(config=config, console=True)

runtime = build_runtime()
tracer = ClaudeTraceCraftr(runtime=runtime)

async def main() -> None:
    with tracer.trace("production_task"):
        async for message in query(
            prompt="Analyze the project structure.",
            options=tracer.get_options(allowed_tools=["Glob", "Read"]),
        ):
            pass

asyncio.run(main())
```

### Sampling

```python
import tracecraft
from tracecraft import TraceCraftConfig, TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

# Trace only 20% of runs in high-volume production
config = TraceCraftConfig(
    service_name="my-claude-agent",
    sampling_rate=0.2,
)
runtime = TraceCraftRuntime(config=config, jsonl=True)
tracer = ClaudeTraceCraftr(runtime=runtime)
```

### Redaction

```python
import tracecraft
from tracecraft import TraceCraftConfig, TraceCraftRuntime
from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr

# Redact sensitive fields from step inputs and outputs
config = TraceCraftConfig(
    service_name="my-claude-agent",
    redact_fields=["password", "api_key", "token", "secret"],
    redact_patterns=[r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],  # emails
)
runtime = TraceCraftRuntime(config=config, jsonl=True)
tracer = ClaudeTraceCraftr(runtime=runtime)
```

## Best Practices

### 1. Reuse the Tracer Across Calls

Create `ClaudeTraceCraftr` once and reuse it. Each call to `tracer.trace()` opens a new
`AgentRun` but shares the same runtime and exporters:

```python
# module-level singleton
tracer = ClaudeTraceCraftr(runtime=TraceCraftRuntime(console=True, jsonl=True))

async def handle_task(prompt: str, name: str) -> None:
    with tracer.trace(name):
        async for message in query(prompt=prompt, options=tracer.get_options()):
            pass
```

### 2. Provide Descriptive Trace Names

The trace name appears in the TUI and JSONL output. Include context that helps you filter and
search later:

```python
with tracer.trace(f"refactor_{repo_name}_{ticket_id}"):
    ...
```

### 3. Restrict allowed_tools

Pass only the tools your agent needs. This reduces the attack surface and keeps traces focused:

```python
options=tracer.get_options(allowed_tools=["Read", "Grep", "Glob"])
```

### 4. Call clear() When Reusing the Tracer

If you reuse a `ClaudeTraceCraftr` instance across many runs in a long-lived process, call
`tracer.clear()` between sessions to release any residual step state:

```python
async def run_batch(prompts: list[str]) -> None:
    for i, prompt in enumerate(prompts):
        with tracer.trace(f"task_{i}"):
            async for message in query(prompt=prompt, options=tracer.get_options()):
                pass
        tracer.clear()  # Reset between runs
```

### 5. Always Await Within the trace() Block

All `query()` calls must complete inside the `with tracer.trace()` block. Exiting the block
before the stream ends will close the run early and may leave steps without an `end_time`:

```python
# Correct: stream fully consumed inside the context
with tracer.trace("my_task") as run:
    async for message in query(prompt=prompt, options=tracer.get_options()):
        process(message)

# Incorrect: generator not consumed inside the context
with tracer.trace("my_task") as run:
    gen = query(prompt=prompt, options=tracer.get_options())
# Consuming gen here is outside the run context
```

## Troubleshooting

### Steps Not Captured

**Symptom:** `run.steps` is empty after the session completes.

**Cause:** The hooks were not passed to `query()`, or `tracer.trace()` was not used.

**Fix:** Always use `tracer.get_options()` when calling `query()`, and call `query()` inside
the `tracer.trace()` block:

```python
with tracer.trace("my_task") as run:
    async for message in query(
        prompt="...",
        options=tracer.get_options(allowed_tools=["Read"]),  # hooks included here
    ):
        pass
```

### Incomplete Steps (Missing end_time)

**Symptom:** Some steps have `end_time = None` or `duration_ms = None`.

**Cause:** The agent session ended unexpectedly before `PostToolUse` was called for some tools,
or the `query()` generator was abandoned before the `Stop` hook fired.

**Fix:** Ensure the full message stream is consumed inside the `with tracer.trace()` block.
If the session can be interrupted, the `Stop` hook will still fire and close open steps with
an `"Agent stopped before tool completed"` error message.

### Memory Issues

**Symptom:** Memory grows in a long-running process that handles many Claude sessions.

**Cause:** The internal `_steps` dict in `ClaudeTraceCraftr` retains step references from
completed sessions.

**Fix:** Call `tracer.clear()` after each completed session:

```python
with tracer.trace("session"):
    async for message in query(prompt=prompt, options=tracer.get_options()):
        pass
tracer.clear()
```

## Hook Event Reference

### PreToolUse

Called before a tool executes. Return an empty dict `{}` to allow the call. Return a dict with
an `"error"` key to block the call.

```
input_data keys:
  tool_name   str  — Name of the tool (e.g., "Read", "Bash")
  tool_input  dict — Arguments passed to the tool

tool_use_id   str | None  — Unique ID correlating with PostToolUse
```

### PostToolUse

Called after a tool returns. The `tool_response` field contains the tool output.

```
input_data keys:
  tool_name      str   — Name of the tool
  tool_input     dict  — Arguments that were passed to the tool
  tool_response  any   — Return value from the tool (str, dict, or other)

tool_use_id   str | None  — Same ID as the matching PreToolUse
```

### Stop

Called when the Claude agent finishes its session (normal completion or error). `tool_use_id`
is typically `None`. TraceCraft uses this hook to close any steps that were opened but not
yet completed.

### SubagentStop

Called when a `Task` subagent completes. `tool_use_id` matches the `PreToolUse` ID for the
`Task` call that spawned the subagent. The `input_data` dict may contain a `"result"` key
with the subagent's final output.

```
input_data keys:
  result  any  — Output from the completed subagent (optional)

tool_use_id   str | None  — ID of the Task tool call that created the subagent
```

## Next Steps

- [LangChain Integration](langchain.md)
- [LlamaIndex Integration](llamaindex.md)
- [Auto-Instrumentation](auto-instrumentation.md)
- [User Guide](../user-guide/index.md)
