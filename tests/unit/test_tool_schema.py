"""
Tests for tool schema capture in adapters.

TDD approach: Tests for capturing tool definitions and schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tracecraft.core.context import run_context
from tracecraft.core.models import AgentRun


class TestLangChainToolSchemaCapture:
    """Tests for tool schema capture in LangChain adapter."""

    def test_on_tool_start_captures_description(self) -> None:
        """on_tool_start should capture tool description."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {
            "name": "search_tool",
            "description": "Search the web for information",
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="test query",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" in step.inputs
            assert step.inputs["tool_schema"]["description"] == "Search the web for information"

    def test_on_tool_start_captures_args_schema_dict(self) -> None:
        """on_tool_start should capture args_schema as dict."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {
            "name": "calculator",
            "args_schema": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression"}},
                "required": ["expression"],
            },
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="2 + 2",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" in step.inputs
            assert "args_schema" in step.inputs["tool_schema"]
            assert step.inputs["tool_schema"]["args_schema"]["type"] == "object"

    def test_on_tool_start_captures_args(self) -> None:
        """on_tool_start should capture tool args."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {
            "name": "weather_tool",
            "args": {"location": "string", "unit": "string"},
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="NYC",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" in step.inputs
            assert step.inputs["tool_schema"]["args"]["location"] == "string"

    def test_on_tool_start_captures_return_type(self) -> None:
        """on_tool_start should capture return type."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {
            "name": "get_price",
            "return_type": "float",
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="AAPL",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" in step.inputs
            assert step.inputs["tool_schema"]["return_type"] == "float"

    def test_on_tool_start_captures_docstring(self) -> None:
        """on_tool_start should capture function docstring."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        def sample_func(x: str) -> str:
            """This is a sample function that does something."""
            return x

        serialized = {
            "name": "sample_tool",
            "func": sample_func,
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="test",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" in step.inputs
            assert "docstring" in step.inputs["tool_schema"]
            assert "sample function" in step.inputs["tool_schema"]["docstring"]

    def test_on_tool_start_no_schema_when_empty(self) -> None:
        """on_tool_start should not include tool_schema when empty."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {"name": "simple_tool"}

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="test",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert "tool_schema" not in step.inputs
            assert step.inputs["input"] == "test"

    def test_on_tool_start_preserves_input(self) -> None:
        """on_tool_start should always preserve the input string."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))

        serialized = {
            "name": "tool_with_schema",
            "description": "A tool",
        }

        with run_context(run):
            run_id = uuid4()
            handler.on_tool_start(
                serialized=serialized,
                input_str="my input data",
                run_id=run_id,
            )

            step = handler._get_step(run_id)
            assert step is not None
            assert step.inputs["input"] == "my input data"


class TestExtractToolSchema:
    """Tests for the _extract_tool_schema helper method."""

    def test_extract_empty_serialized(self) -> None:
        """Should return None for empty serialized dict."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        result = handler._extract_tool_schema({})

        assert result is None

    def test_extract_multiple_fields(self) -> None:
        """Should extract multiple schema fields."""
        from tracecraft.adapters.langchain import TraceCraftCallbackHandler

        handler = TraceCraftCallbackHandler()
        serialized = {
            "name": "multi_field_tool",
            "description": "Does multiple things",
            "args": {"a": "int", "b": "str"},
            "return_type": "dict",
        }

        result = handler._extract_tool_schema(serialized)

        assert result is not None
        assert result["description"] == "Does multiple things"
        assert result["args"] == {"a": "int", "b": "str"}
        assert result["return_type"] == "dict"
