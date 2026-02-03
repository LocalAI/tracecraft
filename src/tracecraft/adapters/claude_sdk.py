"""
Claude Agent SDK adapter for TraceCraft.

Provides ClaudeTraceCraftr that integrates with Claude SDK hooks
to capture agent execution as TraceCraft Steps.
"""

from __future__ import annotations

import threading
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tracecraft.core.context import get_current_run
from tracecraft.core.models import AgentRun, Step, StepType

if TYPE_CHECKING:
    from tracecraft.core.runtime import TALRuntime


__all__ = [
    "ClaudeTraceCraftr",
    "TOOL_TYPE_MAP",
    "MAX_RESPONSE_LENGTH",
]

# Maximum response length before truncation (in characters)
MAX_RESPONSE_LENGTH: int = 10000

# Tool name to StepType mapping
TOOL_TYPE_MAP: dict[str, StepType] = {
    # File operations
    "Read": StepType.TOOL,
    "Write": StepType.TOOL,
    "Edit": StepType.TOOL,
    "MultiEdit": StepType.TOOL,
    "NotebookEdit": StepType.TOOL,
    # Search operations
    "Glob": StepType.TOOL,
    "Grep": StepType.TOOL,
    # Shell
    "Bash": StepType.TOOL,
    "KillShell": StepType.TOOL,
    # Web operations
    "WebFetch": StepType.TOOL,
    "WebSearch": StepType.RETRIEVAL,
    # Agent/Task
    "Task": StepType.AGENT,
    "TaskOutput": StepType.TOOL,
    # User interaction
    "AskUserQuestion": StepType.TOOL,
    # Planning and workflow
    "TodoWrite": StepType.TOOL,
    "EnterPlanMode": StepType.WORKFLOW,
    "ExitPlanMode": StepType.WORKFLOW,
    # Skills and commands
    "Skill": StepType.WORKFLOW,
    "SlashCommand": StepType.WORKFLOW,
}


@dataclass
class ClaudeTraceCraftr:
    """
    Tracer for Claude Agent SDK that creates TraceCraft Steps from hooks.

    Integrates with the Claude SDK's hook system (PreToolUse, PostToolUse,
    Stop, SubagentStop) to capture agent execution as TraceCraft Steps.

    Usage:
        ```python
        from tracecraft import TraceCraftRuntime
        from tracecraft.adapters.claude_sdk import ClaudeTraceCraftr
        from claude_code_sdk import query

        runtime = TraceCraftRuntime(console=True)
        tracer = ClaudeTraceCraftr(runtime=runtime)

        with runtime.run("my_task") as run:
            async for message in query(
                prompt="Analyze the code",
                options=tracer.get_options(allowed_tools=["Read", "Grep"])
            ):
                print(message)
        ```
    """

    runtime: TALRuntime | None = None

    # Internal tracking
    _steps: dict[str, Step] = field(default_factory=dict)  # tool_use_id -> Step
    _subagent_runs: dict[str, AgentRun] = field(default_factory=dict)  # tool_use_id -> subagent run
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        """Ensure mutable defaults are properly initialized."""
        # dataclass field(default_factory=...) handles this, but we ensure
        # the lock is always present even if somehow missing
        if self._lock is None:
            self._lock = threading.Lock()

    def get_hooks(self) -> dict[str, list[Any]]:
        """
        Get hooks dict for ClaudeAgentOptions.

        Returns a dict mapping hook event names to lists of HookMatcher objects.
        These hooks are used to intercept tool execution and create TraceCraft Steps.

        Returns:
            Dict mapping hook event names to HookMatcher lists.

        Raises:
            ImportError: If claude-agent-sdk is not installed.
        """
        # Import here to avoid hard dependency
        try:
            from claude_code_sdk import HookMatcher
        except ImportError as err:
            raise ImportError(
                "claude-code-sdk is required for Claude SDK integration. "
                "Install with: pip install claude-code-sdk"
            ) from err

        return {
            "PreToolUse": [HookMatcher(hooks=[self._pre_tool_use])],
            "PostToolUse": [HookMatcher(hooks=[self._post_tool_use])],
            "Stop": [HookMatcher(hooks=[self._on_stop])],
            "SubagentStop": [HookMatcher(hooks=[self._on_subagent_stop])],
        }

    def get_options(self, **kwargs: Any) -> Any:
        """
        Create ClaudeAgentOptions with tracing hooks.

        Merges the tracer's hooks with any user-provided hooks, allowing
        custom hooks to work alongside tracing.

        Args:
            **kwargs: Arguments passed to ClaudeAgentOptions.
                Special handling for 'hooks' key - merged with tracer hooks.

        Returns:
            ClaudeAgentOptions configured with tracing hooks.

        Raises:
            ImportError: If claude-agent-sdk is not installed.
        """
        try:
            from claude_code_sdk import ClaudeCodeOptions
        except ImportError as err:
            raise ImportError(
                "claude-code-sdk is required for Claude SDK integration. "
                "Install with: pip install claude-code-sdk"
            ) from err

        hooks = kwargs.pop("hooks", {})
        # Merge our hooks with any user-provided hooks
        merged_hooks = {**self.get_hooks()}
        for event, matchers in hooks.items():
            if event in merged_hooks:
                merged_hooks[event].extend(matchers)
            else:
                merged_hooks[event] = matchers

        return ClaudeCodeOptions(hooks=merged_hooks, **kwargs)

    @contextmanager
    def trace(self, name: str) -> Generator[AgentRun, None, None]:
        """
        Context manager for tracing a Claude agent session.

        Creates a runtime if needed and starts a traced run.

        Args:
            name: Name for the traced run.

        Yields:
            The AgentRun being traced.
        """
        if self.runtime is None:
            from tracecraft import init

            self.runtime = init()

        with self.runtime.run(name) as run:
            yield run

    def _infer_step_type(self, tool_name: str) -> StepType:
        """
        Infer StepType from tool name.

        Args:
            tool_name: Name of the Claude SDK tool.

        Returns:
            Appropriate StepType for the tool.
        """
        # Check direct mapping
        if tool_name in TOOL_TYPE_MAP:
            return TOOL_TYPE_MAP[tool_name]

        # MCP tools (mcp__server__tool format)
        if tool_name.startswith("mcp__"):
            return StepType.TOOL

        # Default to TOOL
        return StepType.TOOL

    def _extract_tool_metadata(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """
        Extract relevant metadata from tool input.

        Args:
            tool_name: Name of the tool.
            tool_input: Input arguments to the tool.

        Returns:
            Dict of extracted metadata.
        """
        metadata: dict[str, Any] = {"tool_name": tool_name}

        if tool_name in ("Read", "Write", "Edit", "MultiEdit"):
            metadata["file_path"] = tool_input.get("file_path")
        elif tool_name == "Bash":
            metadata["command"] = tool_input.get("command")
            metadata["description"] = tool_input.get("description")
        elif tool_name in ("Glob", "Grep"):
            metadata["pattern"] = tool_input.get("pattern")
            metadata["path"] = tool_input.get("path")
        elif tool_name == "WebFetch":
            metadata["url"] = tool_input.get("url")
        elif tool_name == "WebSearch":
            metadata["query"] = tool_input.get("query")
        elif tool_name == "Task":
            metadata["subagent_type"] = tool_input.get("subagent_type")
            metadata["description"] = tool_input.get("description")
        elif tool_name.startswith("mcp__"):
            # MCP tools: extract server and tool name from mcp__server__tool
            parts = tool_name.split("__")
            if len(parts) >= 3:
                metadata["mcp_server"] = parts[1]
                metadata["mcp_tool"] = "__".join(parts[2:])

        return metadata

    async def _pre_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """
        Hook called before tool execution.

        Creates a Step and adds it to the current run.

        Args:
            input_data: Hook input data including tool_name and tool_input.
            tool_use_id: Unique ID for this tool use (correlates pre/post).
            _context: Hook context (reserved for future use).

        Returns:
            Empty dict (no modifications to tool execution).
        """
        run = get_current_run()
        if run is None or tool_use_id is None:
            return {}

        tool_name = input_data.get("tool_name", "unknown")
        tool_input = input_data.get("tool_input", {})

        step_type = self._infer_step_type(tool_name)
        attributes = self._extract_tool_metadata(tool_name, tool_input)

        # Create step
        step = Step(
            trace_id=run.id,
            type=step_type,
            name=tool_name,
            start_time=datetime.now(UTC),
            inputs=tool_input,
            attributes=attributes,
        )

        # Track step for later completion
        with self._lock:
            self._steps[tool_use_id] = step

        # Add to run
        run.steps.append(step)

        return {}  # No modifications to tool execution

    async def _post_tool_use(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """
        Hook called after tool execution.

        Completes the Step with end_time and outputs.

        Args:
            input_data: Hook input data including tool_response.
            tool_use_id: Unique ID for this tool use (correlates pre/post).
            _context: Hook context (reserved for future use).

        Returns:
            Empty dict (no modifications).
        """
        if tool_use_id is None:
            return {}

        with self._lock:
            step = self._steps.pop(tool_use_id, None)

        if step is None:
            return {}

        # Complete step
        step.end_time = datetime.now(UTC)
        step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000

        # Capture output
        tool_response = input_data.get("tool_response")
        if tool_response is not None:
            # Truncate large responses to prevent memory issues
            if isinstance(tool_response, str) and len(tool_response) > MAX_RESPONSE_LENGTH:
                step.outputs = {"response": tool_response[:MAX_RESPONSE_LENGTH] + "...[truncated]"}
            elif isinstance(tool_response, dict):
                step.outputs = tool_response
            else:
                response_str = str(tool_response)
                if len(response_str) > MAX_RESPONSE_LENGTH:
                    response_str = response_str[:MAX_RESPONSE_LENGTH] + "...[truncated]"
                step.outputs = {"response": response_str}

        return {}

    async def _on_stop(
        self,
        _input_data: dict[str, Any],
        _tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """
        Hook called when agent stops.

        Cleans up any incomplete steps, marking them with an error.

        Args:
            _input_data: Hook input data.
            _tool_use_id: Tool use ID (usually None for Stop).
            _context: Hook context (reserved for future use).

        Returns:
            Empty dict (no modifications).
        """
        # Clean up any incomplete steps
        with self._lock:
            for step in self._steps.values():
                if step.end_time is None:
                    step.end_time = datetime.now(UTC)
                    step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000
                    step.error = "Agent stopped before tool completed"
            self._steps.clear()

        return {}

    async def _on_subagent_stop(
        self,
        input_data: dict[str, Any],
        tool_use_id: str | None,
        _context: Any,
    ) -> dict[str, Any]:
        """
        Hook called when a subagent completes.

        Completes the Task step that spawned the subagent.

        Args:
            input_data: Hook input data including result from subagent.
            tool_use_id: Tool use ID of the Task tool that spawned subagent.
            _context: Hook context (reserved for future use).

        Returns:
            Empty dict (no modifications).
        """
        if tool_use_id is None:
            return {}

        with self._lock:
            step = self._steps.pop(tool_use_id, None)

        if step is not None and step.type == StepType.AGENT:
            # Mark subagent step complete
            step.end_time = datetime.now(UTC)
            step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000

            # Capture subagent result from input_data if available
            if "result" in input_data:
                step.outputs = {"result": input_data["result"]}

        return {}

    def clear(self) -> None:
        """Clear tracked state. Call when reusing tracer for a new session."""
        with self._lock:
            self._steps.clear()
            self._subagent_runs.clear()
