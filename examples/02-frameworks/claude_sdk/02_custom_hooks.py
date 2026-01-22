#!/usr/bin/env python3
"""
Claude Agent SDK - Custom Hooks with Tracing

Demonstrates combining AgentTrace tracing with custom hooks.

This example shows how to:
- Add custom hooks alongside tracing hooks
- Log file operations for audit
- Block dangerous commands

Prerequisites:
    - pip install agenttrace claude-code-sdk
    - ANTHROPIC_API_KEY environment variable

Usage:
    python examples/02-frameworks/claude_sdk/02_custom_hooks.py
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from agenttrace import AgentTraceRuntime
from agenttrace.adapters.claude_sdk import ClaudeAgentTracer


async def main() -> None:
    """Run Claude agent with custom hooks and tracing."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY to run this example")
        print("\nThis example demonstrates custom hooks with tracing:")
        print_custom_hooks_demo()
        return

    try:
        from claude_code_sdk import HookMatcher, query
    except ImportError:
        print("Install claude-code-sdk: pip install claude-code-sdk")
        print("\nThis example demonstrates custom hooks with tracing:")
        print_custom_hooks_demo()
        return

    # Initialize tracing
    runtime = AgentTraceRuntime(console=True, jsonl=False)
    tracer = ClaudeAgentTracer(runtime=runtime)

    # Custom audit hook for file operations
    audit_log: list[str] = []

    async def audit_file_operations(
        input_data: dict[str, Any], tool_use_id: str | None, context: Any
    ) -> dict[str, Any]:
        """Log all file operations for audit."""
        if input_data.get("hook_event_name") == "PostToolUse":
            tool_name = input_data.get("tool_name", "")
            if tool_name in ["Write", "Edit", "Read"]:
                file_path = input_data.get("tool_input", {}).get("file_path", "unknown")
                audit_log.append(f"{datetime.now(UTC)}: {tool_name} on {file_path}")
        return {}

    # Custom safety hook to block dangerous commands
    async def block_dangerous_commands(
        input_data: dict[str, Any], tool_use_id: str | None, context: Any
    ) -> dict[str, Any]:
        """Block potentially dangerous Bash commands."""
        if input_data.get("hook_event_name") != "PreToolUse":
            return {}

        if input_data.get("tool_name") == "Bash":
            command = input_data.get("tool_input", {}).get("command", "")
            dangerous_patterns = ["rm -rf", "sudo", "> /dev/", "mkfs"]

            for pattern in dangerous_patterns:
                if pattern in command:
                    return {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"Blocked: contains '{pattern}'",
                        }
                    }
        return {}

    print("Running Claude agent with custom hooks...")
    print("=" * 60)

    with runtime.run("safe_code_task") as run:
        async for message in query(
            prompt="Read the README.md file and summarize it",
            options=tracer.get_options(
                allowed_tools=["Read", "Glob"],
                max_turns=5,
                # Merge custom hooks with tracer hooks
                hooks={
                    "PostToolUse": [HookMatcher(hooks=[audit_file_operations])],
                    "PreToolUse": [HookMatcher(matcher="Bash", hooks=[block_dangerous_commands])],
                },
            ),
        ):
            if hasattr(message, "content"):
                print(message.content)

    print("=" * 60)
    print(f"\nAudit Log ({len(audit_log)} operations):")
    for entry in audit_log:
        print(f"  {entry}")


def print_custom_hooks_demo() -> None:
    """Print custom hooks demonstration."""
    print(
        """
Custom Hooks with Tracing
=========================

ClaudeAgentTracer's get_options() method merges your custom hooks
with the tracing hooks automatically.

Example: Adding Audit Logging
-----------------------------

```python
from agenttrace import AgentTraceRuntime
from agenttrace.adapters.claude_sdk import ClaudeAgentTracer
from claude_code_sdk import query, HookMatcher

runtime = AgentTraceRuntime(console=True)
tracer = ClaudeAgentTracer(runtime=runtime)

# Custom audit hook
audit_log = []

async def audit_file_operations(input_data, tool_use_id, context):
    if input_data.get("hook_event_name") == "PostToolUse":
        tool_name = input_data.get("tool_name", "")
        if tool_name in ["Write", "Edit", "Read"]:
            file_path = input_data.get("tool_input", {}).get("file_path")
            audit_log.append(f"{tool_name}: {file_path}")
    return {}

# Use tracer.get_options() to merge hooks
with runtime.run("my_task") as run:
    async for message in query(
        prompt="Read the config file",
        options=tracer.get_options(
            allowed_tools=["Read"],
            hooks={
                "PostToolUse": [HookMatcher(hooks=[audit_file_operations])]
            }
        )
    ):
        print(message)

print(f"Audit log: {audit_log}")
```

Example: Safety Hook to Block Commands
--------------------------------------

```python
async def block_dangerous_commands(input_data, tool_use_id, context):
    if input_data.get("hook_event_name") != "PreToolUse":
        return {}

    if input_data.get("tool_name") == "Bash":
        command = input_data.get("tool_input", {}).get("command", "")
        if "rm -rf" in command:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Blocked dangerous command"
                }
            }
    return {}

options = tracer.get_options(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[block_dangerous_commands])]
    }
)
```

Hook Events Available
---------------------
- PreToolUse: Before tool execution (can block with permissionDecision: "deny")
- PostToolUse: After tool execution (can capture outputs)
- Stop: When agent stops
- SubagentStop: When a subagent (Task tool) completes
"""
    )


if __name__ == "__main__":
    asyncio.run(main())
