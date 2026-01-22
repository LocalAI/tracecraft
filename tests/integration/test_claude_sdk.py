"""
Tests for the Claude Agent SDK adapter.

Tests Claude SDK integration via hook callbacks without requiring
actual Claude SDK installation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from agenttrace.core.context import run_context
from agenttrace.core.models import AgentRun, StepType


class TestClaudeAgentTracerCreation:
    """Tests for tracer instantiation."""

    def test_tracer_creation_without_runtime(self) -> None:
        """Should create tracer without runtime."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer is not None
        assert tracer.runtime is None

    def test_tracer_creation_with_runtime(self) -> None:
        """Should create tracer with provided runtime."""
        from agenttrace import AgentTraceRuntime
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        runtime = AgentTraceRuntime(console=False, jsonl=False)
        tracer = ClaudeAgentTracer(runtime=runtime)
        assert tracer.runtime is runtime

    def test_tracer_internal_state_initialized(self) -> None:
        """Should initialize internal tracking state."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._steps == {}
        assert tracer._subagent_runs == {}
        assert tracer._lock is not None


class TestToolTypeMapping:
    """Tests for tool name to StepType mapping."""

    def test_file_operations_are_tools(self) -> None:
        """Read, Write, Edit should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("Read") == StepType.TOOL
        assert tracer._infer_step_type("Write") == StepType.TOOL
        assert tracer._infer_step_type("Edit") == StepType.TOOL
        assert tracer._infer_step_type("MultiEdit") == StepType.TOOL
        assert tracer._infer_step_type("NotebookEdit") == StepType.TOOL

    def test_search_operations_are_tools(self) -> None:
        """Glob, Grep should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("Glob") == StepType.TOOL
        assert tracer._infer_step_type("Grep") == StepType.TOOL

    def test_bash_is_tool(self) -> None:
        """Bash should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("Bash") == StepType.TOOL
        assert tracer._infer_step_type("KillShell") == StepType.TOOL

    def test_websearch_is_retrieval(self) -> None:
        """WebSearch should be RETRIEVAL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("WebSearch") == StepType.RETRIEVAL

    def test_webfetch_is_tool(self) -> None:
        """WebFetch should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("WebFetch") == StepType.TOOL

    def test_task_is_agent(self) -> None:
        """Task (subagent) should be AGENT type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("Task") == StepType.AGENT

    def test_task_output_is_tool(self) -> None:
        """TaskOutput should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("TaskOutput") == StepType.TOOL

    def test_workflow_tools(self) -> None:
        """Planning and workflow tools should be WORKFLOW type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("EnterPlanMode") == StepType.WORKFLOW
        assert tracer._infer_step_type("ExitPlanMode") == StepType.WORKFLOW
        assert tracer._infer_step_type("Skill") == StepType.WORKFLOW
        assert tracer._infer_step_type("SlashCommand") == StepType.WORKFLOW

    def test_mcp_tools_are_tools(self) -> None:
        """MCP server tools should be TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("mcp__github__list_issues") == StepType.TOOL
        assert tracer._infer_step_type("mcp__postgres__query") == StepType.TOOL
        assert tracer._infer_step_type("mcp__filesystem__read_file") == StepType.TOOL

    def test_unknown_tools_default_to_tool(self) -> None:
        """Unknown tools should default to TOOL type."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer._infer_step_type("UnknownTool") == StepType.TOOL
        assert tracer._infer_step_type("CustomTool") == StepType.TOOL


class TestMetadataExtraction:
    """Tests for tool metadata extraction."""

    def test_extracts_file_path_for_read(self) -> None:
        """Should extract file_path for Read tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata("Read", {"file_path": "/src/main.py", "offset": 0})
        assert metadata["file_path"] == "/src/main.py"
        assert metadata["tool_name"] == "Read"

    def test_extracts_file_path_for_write(self) -> None:
        """Should extract file_path for Write tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "Write", {"file_path": "/output.txt", "content": "data"}
        )
        assert metadata["file_path"] == "/output.txt"

    def test_extracts_file_path_for_edit(self) -> None:
        """Should extract file_path for Edit tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "Edit",
            {"file_path": "/src/app.py", "old_string": "foo", "new_string": "bar"},
        )
        assert metadata["file_path"] == "/src/app.py"

    def test_extracts_command_for_bash(self) -> None:
        """Should extract command and description for Bash tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "Bash", {"command": "pytest tests/", "description": "Run unit tests"}
        )
        assert metadata["command"] == "pytest tests/"
        assert metadata["description"] == "Run unit tests"

    def test_extracts_pattern_for_glob(self) -> None:
        """Should extract pattern for Glob tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata("Glob", {"pattern": "**/*.py", "path": "/src"})
        assert metadata["pattern"] == "**/*.py"
        assert metadata["path"] == "/src"

    def test_extracts_pattern_for_grep(self) -> None:
        """Should extract pattern for Grep tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata("Grep", {"pattern": "def test_", "path": "/tests"})
        assert metadata["pattern"] == "def test_"
        assert metadata["path"] == "/tests"

    def test_extracts_url_for_webfetch(self) -> None:
        """Should extract url for WebFetch tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "WebFetch", {"url": "https://example.com", "prompt": "Extract info"}
        )
        assert metadata["url"] == "https://example.com"

    def test_extracts_query_for_websearch(self) -> None:
        """Should extract query for WebSearch tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata("WebSearch", {"query": "Python async patterns"})
        assert metadata["query"] == "Python async patterns"

    def test_extracts_task_metadata(self) -> None:
        """Should extract subagent_type and description for Task tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "Task",
            {
                "subagent_type": "code-reviewer",
                "description": "Review PR",
                "prompt": "Check for bugs",
            },
        )
        assert metadata["subagent_type"] == "code-reviewer"
        assert metadata["description"] == "Review PR"

    def test_extracts_mcp_server_and_tool(self) -> None:
        """Should extract MCP server name and tool name."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "mcp__github__list_issues", {"owner": "anthropics", "repo": "claude-code"}
        )
        assert metadata["mcp_server"] == "github"
        assert metadata["mcp_tool"] == "list_issues"

    def test_extracts_mcp_tool_with_underscores(self) -> None:
        """Should handle MCP tool names with underscores."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        metadata = tracer._extract_tool_metadata(
            "mcp__filesystem__read_text_file", {"path": "/tmp/test.txt"}
        )
        assert metadata["mcp_server"] == "filesystem"
        assert metadata["mcp_tool"] == "read_text_file"


class TestPreToolUseHook:
    """Tests for the PreToolUse hook callback."""

    @pytest.mark.asyncio
    async def test_creates_step_on_pre_tool_use(self) -> None:
        """Should create a step when PreToolUse hook is called."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/path/to/file.py"},
                },
                tool_use_id="tool-123",
                context=None,
            )

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.type == StepType.TOOL
        assert step.name == "Read"
        assert step.inputs == {"file_path": "/path/to/file.py"}
        assert step.start_time is not None

    @pytest.mark.asyncio
    async def test_tracks_step_by_tool_use_id(self) -> None:
        """Should track step by tool_use_id for later completion."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Bash", "tool_input": {"command": "ls"}},
                tool_use_id="tool-456",
                context=None,
            )

        assert "tool-456" in tracer._steps
        assert tracer._steps["tool-456"].name == "Bash"

    @pytest.mark.asyncio
    async def test_extracts_metadata_for_file_tools(self) -> None:
        """Should extract file_path metadata for file operations."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": "/src/main.py",
                        "old_string": "foo",
                        "new_string": "bar",
                    },
                },
                tool_use_id="tool-789",
                context=None,
            )

        step = run.steps[0]
        assert step.attributes["file_path"] == "/src/main.py"
        assert step.attributes["tool_name"] == "Edit"

    @pytest.mark.asyncio
    async def test_extracts_metadata_for_bash(self) -> None:
        """Should extract command and description for Bash tool."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "pytest tests/",
                        "description": "Run unit tests",
                    },
                },
                tool_use_id="tool-bash",
                context=None,
            )

        step = run.steps[0]
        assert step.attributes["command"] == "pytest tests/"
        assert step.attributes["description"] == "Run unit tests"

    @pytest.mark.asyncio
    async def test_skips_without_run_context(self) -> None:
        """Should skip step creation without active run context."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        # No run context
        result = await tracer._pre_tool_use(
            input_data={"tool_name": "Read", "tool_input": {}},
            tool_use_id="tool-no-run",
            context=None,
        )

        assert result == {}
        assert "tool-no-run" not in tracer._steps

    @pytest.mark.asyncio
    async def test_skips_with_none_tool_use_id(self) -> None:
        """Should skip step creation with None tool_use_id."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            result = await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id=None,
                context=None,
            )

        assert result == {}
        assert len(run.steps) == 0

    @pytest.mark.asyncio
    async def test_handles_missing_tool_name(self) -> None:
        """Should handle missing tool_name in input_data."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_input": {}},  # No tool_name
                tool_use_id="tool-missing",
                context=None,
            )

        step = run.steps[0]
        assert step.name == "unknown"


class TestPostToolUseHook:
    """Tests for the PostToolUse hook callback."""

    @pytest.mark.asyncio
    async def test_completes_step_on_post_tool_use(self) -> None:
        """Should complete step with end_time and outputs."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Create step
            await tracer._pre_tool_use(
                input_data={"tool_name": "Glob", "tool_input": {"pattern": "*.py"}},
                tool_use_id="tool-glob",
                context=None,
            )

            # Complete step
            await tracer._post_tool_use(
                input_data={
                    "tool_name": "Glob",
                    "tool_input": {"pattern": "*.py"},
                    "tool_response": {"matches": ["a.py", "b.py"], "count": 2},
                },
                tool_use_id="tool-glob",
                context=None,
            )

        step = run.steps[0]
        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 0
        assert step.outputs == {"matches": ["a.py", "b.py"], "count": 2}

    @pytest.mark.asyncio
    async def test_truncates_large_string_responses(self) -> None:
        """Should truncate responses larger than 10000 chars."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id="tool-read",
                context=None,
            )

            # Large response
            large_content = "x" * 20000
            await tracer._post_tool_use(
                input_data={"tool_response": large_content},
                tool_use_id="tool-read",
                context=None,
            )

        step = run.steps[0]
        assert len(step.outputs["response"]) == 10000 + len("...[truncated]")
        assert step.outputs["response"].endswith("...[truncated]")

    @pytest.mark.asyncio
    async def test_handles_dict_responses(self) -> None:
        """Should store dict responses directly."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "WebSearch", "tool_input": {}},
                tool_use_id="tool-search",
                context=None,
            )

            await tracer._post_tool_use(
                input_data={
                    "tool_response": {
                        "results": [{"title": "Result 1", "url": "http://example.com"}],
                        "total": 10,
                    }
                },
                tool_use_id="tool-search",
                context=None,
            )

        step = run.steps[0]
        assert step.outputs["results"][0]["title"] == "Result 1"
        assert step.outputs["total"] == 10

    @pytest.mark.asyncio
    async def test_handles_non_string_non_dict_responses(self) -> None:
        """Should convert non-string, non-dict responses to string."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Tool", "tool_input": {}},
                tool_use_id="tool-other",
                context=None,
            )

            await tracer._post_tool_use(
                input_data={"tool_response": ["item1", "item2", "item3"]},
                tool_use_id="tool-other",
                context=None,
            )

        step = run.steps[0]
        assert "response" in step.outputs
        assert "item1" in step.outputs["response"]

    @pytest.mark.asyncio
    async def test_removes_step_from_tracking(self) -> None:
        """Should remove step from tracking after completion."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id="tool-tracked",
                context=None,
            )
            assert "tool-tracked" in tracer._steps

            await tracer._post_tool_use(
                input_data={"tool_response": "content"},
                tool_use_id="tool-tracked",
                context=None,
            )
            assert "tool-tracked" not in tracer._steps

    @pytest.mark.asyncio
    async def test_handles_none_tool_response(self) -> None:
        """Should handle None tool_response gracefully."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id="tool-none",
                context=None,
            )

            await tracer._post_tool_use(
                input_data={},  # No tool_response
                tool_use_id="tool-none",
                context=None,
            )

        step = run.steps[0]
        assert step.end_time is not None
        # outputs may be None or empty since no response was provided

    @pytest.mark.asyncio
    async def test_post_without_pre(self) -> None:
        """PostToolUse without PreToolUse should be handled gracefully."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        # Should not raise
        result = await tracer._post_tool_use(
            input_data={"tool_response": "orphan"},
            tool_use_id="tool-orphan",
            context=None,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_post_with_none_tool_use_id(self) -> None:
        """Should handle None tool_use_id in PostToolUse."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        result = await tracer._post_tool_use(
            input_data={"tool_response": "data"},
            tool_use_id=None,
            context=None,
        )

        assert result == {}


class TestSubagentTracking:
    """Tests for Task (subagent) tool tracking."""

    @pytest.mark.asyncio
    async def test_task_creates_agent_step(self) -> None:
        """Task tool should create AGENT type step."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {
                        "description": "Code review",
                        "prompt": "Review auth.py",
                        "subagent_type": "code-reviewer",
                    },
                },
                tool_use_id="tool-task",
                context=None,
            )

        step = run.steps[0]
        assert step.type == StepType.AGENT
        assert step.name == "Task"
        assert step.attributes["subagent_type"] == "code-reviewer"
        assert step.attributes["description"] == "Code review"

    @pytest.mark.asyncio
    async def test_subagent_stop_completes_step(self) -> None:
        """SubagentStop hook should complete agent step."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {"subagent_type": "explorer"},
                },
                tool_use_id="tool-subagent",
                context=None,
            )

            await tracer._on_subagent_stop(
                input_data={"result": "Found 5 API endpoints"},
                tool_use_id="tool-subagent",
                context=None,
            )

        step = run.steps[0]
        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.outputs == {"result": "Found 5 API endpoints"}

    @pytest.mark.asyncio
    async def test_subagent_stop_removes_from_tracking(self) -> None:
        """SubagentStop should remove step from tracking."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "Task",
                    "tool_input": {"subagent_type": "test"},
                },
                tool_use_id="tool-sub",
                context=None,
            )
            assert "tool-sub" in tracer._steps

            await tracer._on_subagent_stop(
                input_data={"result": "done"},
                tool_use_id="tool-sub",
                context=None,
            )
            assert "tool-sub" not in tracer._steps

    @pytest.mark.asyncio
    async def test_subagent_stop_with_none_id(self) -> None:
        """SubagentStop with None tool_use_id should be handled."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        result = await tracer._on_subagent_stop(
            input_data={"result": "orphan"},
            tool_use_id=None,
            context=None,
        )

        assert result == {}

    @pytest.mark.asyncio
    async def test_subagent_stop_without_pre(self) -> None:
        """SubagentStop without PreToolUse should be handled gracefully."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        # Should not raise
        result = await tracer._on_subagent_stop(
            input_data={"result": "orphan"},
            tool_use_id="tool-orphan",
            context=None,
        )

        assert result == {}


class TestStopHook:
    """Tests for the Stop hook."""

    @pytest.mark.asyncio
    async def test_stop_clears_incomplete_steps(self) -> None:
        """Stop hook should mark incomplete steps with error."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Create step but don't complete it
            await tracer._pre_tool_use(
                input_data={"tool_name": "Bash", "tool_input": {"command": "sleep 100"}},
                tool_use_id="tool-incomplete",
                context=None,
            )

            assert len(tracer._steps) == 1

            # Stop called before completion
            await tracer._on_stop(input_data={}, tool_use_id=None, context=None)

        step = run.steps[0]
        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.error == "Agent stopped before tool completed"
        assert len(tracer._steps) == 0  # Cleared

    @pytest.mark.asyncio
    async def test_stop_clears_multiple_incomplete_steps(self) -> None:
        """Stop hook should handle multiple incomplete steps."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            # Create multiple incomplete steps
            for i in range(3):
                await tracer._pre_tool_use(
                    input_data={"tool_name": f"Tool_{i}", "tool_input": {}},
                    tool_use_id=f"tool-{i}",
                    context=None,
                )

            assert len(tracer._steps) == 3

            await tracer._on_stop(input_data={}, tool_use_id=None, context=None)

        # All steps should have error
        for step in run.steps:
            assert step.end_time is not None
            assert step.error == "Agent stopped before tool completed"

        assert len(tracer._steps) == 0

    @pytest.mark.asyncio
    async def test_stop_with_no_pending_steps(self) -> None:
        """Stop hook should handle case with no pending steps."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        # Should not raise
        result = await tracer._on_stop(input_data={}, tool_use_id=None, context=None)

        assert result == {}


def _claude_sdk_available() -> bool:
    """Check if claude-agent-sdk is available."""
    try:
        import claude_agent_sdk  # noqa: F401

        return True
    except ImportError:
        return False


class TestGetHooksAndOptions:
    """Tests for get_hooks() and get_options() methods."""

    def test_get_hooks_raises_without_sdk(self) -> None:
        """get_hooks should raise ImportError without Claude SDK."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        # This test assumes claude-agent-sdk is not installed
        # If it is installed, skip this test
        try:
            import claude_agent_sdk  # noqa: F401

            pytest.skip("claude-agent-sdk is installed")
        except ImportError:
            with pytest.raises(ImportError, match="claude-agent-sdk is required"):
                tracer.get_hooks()

    def test_get_options_raises_without_sdk(self) -> None:
        """get_options should raise ImportError without Claude SDK."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()

        try:
            import claude_agent_sdk  # noqa: F401

            pytest.skip("claude-agent-sdk is installed")
        except ImportError:
            with pytest.raises(ImportError, match="claude-agent-sdk is required"):
                tracer.get_options()

    @pytest.mark.skipif(
        not _claude_sdk_available(),
        reason="claude-agent-sdk not installed",
    )
    def test_get_hooks_returns_all_hook_types(self) -> None:
        """get_hooks should return matchers for all hook types."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        hooks = tracer.get_hooks()

        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert "Stop" in hooks
        assert "SubagentStop" in hooks

    @pytest.mark.skipif(
        not _claude_sdk_available(),
        reason="claude-agent-sdk not installed",
    )
    def test_get_options_creates_valid_options(self) -> None:
        """get_options should create ClaudeAgentOptions with hooks."""
        from claude_agent_sdk import ClaudeAgentOptions

        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        options = tracer.get_options(allowed_tools=["Read", "Glob"])

        assert isinstance(options, ClaudeAgentOptions)
        assert options.allowed_tools == ["Read", "Glob"]
        assert options.hooks is not None

    @pytest.mark.skipif(
        not _claude_sdk_available(),
        reason="claude-agent-sdk not installed",
    )
    def test_get_options_merges_user_hooks(self) -> None:
        """get_options should merge user hooks with tracer hooks."""
        from claude_agent_sdk import HookMatcher

        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        async def custom_hook(
            input_data: dict[str, Any], tool_use_id: str | None, context: Any
        ) -> dict[str, Any]:
            return {}

        tracer = ClaudeAgentTracer()
        options = tracer.get_options(hooks={"PreToolUse": [HookMatcher(hooks=[custom_hook])]})

        # Should have both tracer hook and custom hook
        assert len(options.hooks["PreToolUse"]) == 2


class TestThreadSafety:
    """Tests for thread-safety."""

    @pytest.mark.asyncio
    async def test_concurrent_pre_tool_use(self) -> None:
        """Should handle concurrent PreToolUse calls safely."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        errors: list[Exception] = []
        num_calls = 20

        async def make_call(i: int) -> None:
            try:
                with run_context(run):
                    await tracer._pre_tool_use(
                        input_data={
                            "tool_name": f"Tool_{i}",
                            "tool_input": {"index": i},
                        },
                        tool_use_id=f"tool-{i}",
                        context=None,
                    )
            except Exception as e:
                errors.append(e)

        await asyncio.gather(*[make_call(i) for i in range(num_calls)])

        assert len(errors) == 0
        assert len(run.steps) == num_calls

    @pytest.mark.asyncio
    async def test_concurrent_post_tool_use(self) -> None:
        """Should handle concurrent PostToolUse calls safely."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        num_calls = 20

        # First create all steps
        with run_context(run):
            for i in range(num_calls):
                await tracer._pre_tool_use(
                    input_data={"tool_name": f"Tool_{i}", "tool_input": {}},
                    tool_use_id=f"tool-{i}",
                    context=None,
                )

        # Then complete them concurrently
        async def complete_call(i: int) -> None:
            await tracer._post_tool_use(
                input_data={"tool_response": f"result_{i}"},
                tool_use_id=f"tool-{i}",
                context=None,
            )

        await asyncio.gather(*[complete_call(i) for i in range(num_calls)])

        # All steps should be completed
        for step in run.steps:
            assert step.end_time is not None

    @pytest.mark.asyncio
    async def test_concurrent_pre_and_post(self) -> None:
        """Should handle interleaved pre and post calls."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        num_pairs = 10

        async def tool_call_pair(i: int) -> None:
            with run_context(run):
                await tracer._pre_tool_use(
                    input_data={"tool_name": f"Tool_{i}", "tool_input": {}},
                    tool_use_id=f"tool-{i}",
                    context=None,
                )
                await asyncio.sleep(0.001)  # Small delay
                await tracer._post_tool_use(
                    input_data={"tool_response": f"result_{i}"},
                    tool_use_id=f"tool-{i}",
                    context=None,
                )

        await asyncio.gather(*[tool_call_pair(i) for i in range(num_pairs)])

        assert len(run.steps) == num_pairs
        for step in run.steps:
            assert step.end_time is not None


class TestTraceContextManager:
    """Tests for the trace() context manager."""

    def test_trace_creates_runtime_if_needed(self) -> None:
        """trace() should create a runtime if none provided."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        assert tracer.runtime is None

        with tracer.trace("test_session") as run:
            assert tracer.runtime is not None
            assert run.name == "test_session"

    def test_trace_uses_provided_runtime(self) -> None:
        """trace() should use provided runtime."""
        from agenttrace import AgentTraceRuntime
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        runtime = AgentTraceRuntime(console=False, jsonl=False)
        tracer = ClaudeAgentTracer(runtime=runtime)

        with tracer.trace("test_session") as run:
            assert tracer.runtime is runtime


class TestClear:
    """Tests for the clear() method."""

    def test_clear_resets_state(self) -> None:
        """clear() should reset all tracking state."""
        from uuid import uuid4

        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer
        from agenttrace.core.models import Step, StepType

        tracer = ClaudeAgentTracer()

        # Add some state
        tracer._steps["test"] = Step(
            trace_id=uuid4(),
            type=StepType.TOOL,
            name="test",
            start_time=datetime.now(UTC),
        )
        tracer._subagent_runs["test"] = AgentRun(name="test", start_time=datetime.now(UTC))

        tracer.clear()

        assert len(tracer._steps) == 0
        assert len(tracer._subagent_runs) == 0

    @pytest.mark.asyncio
    async def test_clear_after_operations(self) -> None:
        """clear() should work after hook operations."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id="tool-1",
                context=None,
            )

        assert len(tracer._steps) == 1

        tracer.clear()

        assert len(tracer._steps) == 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_input_data(self) -> None:
        """Should handle empty input_data dict."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={},  # Empty
                tool_use_id="tool-empty",
                context=None,
            )

        step = run.steps[0]
        assert step.name == "unknown"
        assert step.inputs == {}

    @pytest.mark.asyncio
    async def test_special_characters_in_tool_name(self) -> None:
        """Should handle special characters in tool names."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={
                    "tool_name": "mcp__server-name__tool_with_underscores",
                    "tool_input": {},
                },
                tool_use_id="tool-special",
                context=None,
            )

        step = run.steps[0]
        assert step.name == "mcp__server-name__tool_with_underscores"
        assert step.type == StepType.TOOL

    @pytest.mark.asyncio
    async def test_very_large_tool_input(self) -> None:
        """Should handle very large tool input dicts."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        large_input = {"data": "x" * 100000, "nested": {"key": "value" * 1000}}

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": large_input},
                tool_use_id="tool-large",
                context=None,
            )

        step = run.steps[0]
        assert step.inputs == large_input

    @pytest.mark.asyncio
    async def test_unicode_in_responses(self) -> None:
        """Should handle unicode in tool responses."""
        from agenttrace.adapters.claude_sdk import ClaudeAgentTracer

        tracer = ClaudeAgentTracer()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        with run_context(run):
            await tracer._pre_tool_use(
                input_data={"tool_name": "Read", "tool_input": {}},
                tool_use_id="tool-unicode",
                context=None,
            )

            await tracer._post_tool_use(
                input_data={"tool_response": "Hello 世界 🌍 émojis and spëcial çharacters"},
                tool_use_id="tool-unicode",
                context=None,
            )

        step = run.steps[0]
        assert "世界" in step.outputs["response"]
        assert "🌍" in step.outputs["response"]
