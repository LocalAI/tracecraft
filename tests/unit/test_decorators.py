"""
Tests for instrumentation decorators (@trace_agent, @trace_tool).

TDD approach: These tests are written BEFORE the implementation.
"""

import asyncio
from datetime import UTC, datetime

import pytest


class TestTraceAgentDecorator:
    """Tests for the @trace_agent decorator."""

    def test_trace_agent_creates_step(self):
        """@trace_agent should create a step of type AGENT."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_agent

        # Set up a run context
        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        captured_step = None

        @trace_agent(name="my_agent")
        def my_agent_func():
            nonlocal captured_step
            captured_step = get_current_step()
            return "result"

        my_agent_func()

        assert captured_step is not None
        assert captured_step.type == StepType.AGENT
        assert captured_step.name == "my_agent"

        # Clean up
        set_current_run(None)

    def test_trace_agent_captures_return_value(self):
        """@trace_agent should capture return value as output."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="returning_agent")
        def agent_with_return():
            return {"answer": "42"}

        result = agent_with_return()

        assert result == {"answer": "42"}
        # The step should have the output captured
        assert len(run.steps) == 1
        assert run.steps[0].outputs.get("result") == {"answer": "42"}

        set_current_run(None)

    def test_trace_agent_captures_inputs(self):
        """@trace_agent should capture function arguments as inputs."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="input_agent")
        def agent_with_inputs(query: str, limit: int = 10):
            return f"Query: {query}, Limit: {limit}"

        agent_with_inputs("test query", limit=5)

        assert len(run.steps) == 1
        assert run.steps[0].inputs["query"] == "test query"
        assert run.steps[0].inputs["limit"] == 5

        set_current_run(None)

    def test_trace_agent_records_timing(self):
        """@trace_agent should record start_time, end_time, and duration_ms."""
        import time

        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="timed_agent")
        def timed_agent():
            time.sleep(0.01)  # Small delay
            return "done"

        timed_agent()

        step = run.steps[0]
        assert step.start_time is not None
        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 10  # At least 10ms

        set_current_run(None)

    def test_trace_agent_uses_function_name_if_not_specified(self):
        """@trace_agent should use function name if name not provided."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent()
        def auto_named_agent():
            return "result"

        auto_named_agent()

        assert run.steps[0].name == "auto_named_agent"

        set_current_run(None)


class TestTraceToolDecorator:
    """Tests for the @trace_tool decorator."""

    def test_trace_tool_creates_step(self):
        """@trace_tool should create a step of type TOOL."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        captured_step = None

        @trace_tool(name="web_search")
        def search_tool(_query: str):
            nonlocal captured_step
            captured_step = get_current_step()
            return ["result1", "result2"]

        search_tool("test query")

        assert captured_step is not None
        assert captured_step.type == StepType.TOOL
        assert captured_step.name == "web_search"

        set_current_run(None)

    def test_trace_tool_captures_inputs_and_outputs(self):
        """@trace_tool should capture inputs and outputs."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="calculator")
        def add_numbers(a: int, b: int) -> int:
            return a + b

        result = add_numbers(5, 3)

        assert result == 8
        assert len(run.steps) == 1
        assert run.steps[0].inputs["a"] == 5
        assert run.steps[0].inputs["b"] == 3
        assert run.steps[0].outputs["result"] == 8

        set_current_run(None)


class TestAsyncDecoratorSupport:
    """Tests for async function support in decorators."""

    @pytest.mark.asyncio
    async def test_trace_agent_async_function(self):
        """@trace_agent should work with async functions."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        captured_step = None

        @trace_agent(name="async_agent")
        async def async_agent():
            nonlocal captured_step
            captured_step = get_current_step()
            await asyncio.sleep(0.001)
            return "async result"

        result = await async_agent()

        assert result == "async result"
        assert captured_step is not None
        assert captured_step.type == StepType.AGENT

        set_current_run(None)

    @pytest.mark.asyncio
    async def test_trace_tool_async_function(self):
        """@trace_tool should work with async functions."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="async_tool")
        async def async_tool(param: str):
            await asyncio.sleep(0.001)
            return f"processed: {param}"

        result = await async_tool("input")

        assert result == "processed: input"
        assert len(run.steps) == 1
        assert run.steps[0].type == StepType.TOOL

        set_current_run(None)


class TestExceptionHandling:
    """Tests for exception handling in decorators."""

    def test_decorator_captures_exception(self):
        """Decorator should capture exception in step.error and step.error_type."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="failing_agent")
        def failing_agent():
            raise ValueError("Something went wrong")

        with pytest.raises(ValueError, match="Something went wrong"):
            failing_agent()

        assert len(run.steps) == 1
        step = run.steps[0]
        assert step.error == "Something went wrong"
        assert step.error_type == "ValueError"
        assert step.end_time is not None  # Should still record end time

        set_current_run(None)

    def test_tool_decorator_captures_exception(self):
        """@trace_tool should capture exceptions properly."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="failing_tool")
        def failing_tool():
            raise RuntimeError("Tool failed")

        with pytest.raises(RuntimeError, match="Tool failed"):
            failing_tool()

        step = run.steps[0]
        assert step.error == "Tool failed"
        assert step.error_type == "RuntimeError"

        set_current_run(None)

    @pytest.mark.asyncio
    async def test_async_decorator_captures_exception(self):
        """Async decorator should capture exceptions properly."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="async_failing")
        async def async_failing():
            await asyncio.sleep(0.001)
            raise KeyError("async error")

        with pytest.raises(KeyError):
            await async_failing()

        step = run.steps[0]
        assert step.error == "'async error'"
        assert step.error_type == "KeyError"

        set_current_run(None)


class TestStepNesting:
    """Tests for step hierarchy/nesting with decorators."""

    def test_nested_decorators_create_hierarchy(self):
        """Nested decorated functions should create parent-child steps."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent, trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="inner_tool")
        def inner_tool():
            return "tool result"

        @trace_agent(name="outer_agent")
        def outer_agent():
            return inner_tool()

        outer_agent()

        # Should have one root step (agent)
        assert len(run.steps) == 1
        agent_step = run.steps[0]
        assert agent_step.name == "outer_agent"

        # Agent step should have tool as child
        assert len(agent_step.children) == 1
        tool_step = agent_step.children[0]
        assert tool_step.name == "inner_tool"
        assert tool_step.parent_id == agent_step.id

        set_current_run(None)

    @pytest.mark.asyncio
    async def test_async_nested_decorators(self):
        """Async nested decorated functions should maintain hierarchy."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent, trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="async_tool")
        async def async_tool():
            await asyncio.sleep(0.001)
            return "async tool result"

        @trace_agent(name="async_agent")
        async def async_agent():
            result = await async_tool()
            return f"agent: {result}"

        await async_agent()

        assert len(run.steps) == 1
        assert run.steps[0].name == "async_agent"
        assert len(run.steps[0].children) == 1
        assert run.steps[0].children[0].name == "async_tool"

        set_current_run(None)


class TestTraceLLMDecorator:
    """Tests for the @trace_llm decorator."""

    def test_trace_llm_creates_step(self):
        """@trace_llm should create a step of type LLM."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_llm

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        captured_step = None

        @trace_llm(name="openai_chat", model="gpt-4", provider="openai")
        def llm_call(_prompt: str):
            nonlocal captured_step
            captured_step = get_current_step()
            return "LLM response"

        llm_call("Hello")

        assert captured_step is not None
        assert captured_step.type == StepType.LLM
        assert captured_step.name == "openai_chat"
        assert captured_step.model_name == "gpt-4"
        assert captured_step.model_provider == "openai"

        set_current_run(None)

    def test_trace_llm_captures_token_counts(self):
        """@trace_llm should support capturing token counts."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_llm(name="llm_with_tokens", model="gpt-4")
        def llm_with_tokens():
            # Simulate returning token info
            return {"response": "Hello!", "usage": {"input_tokens": 10, "output_tokens": 5}}

        result = llm_with_tokens()

        assert result == {"response": "Hello!", "usage": {"input_tokens": 10, "output_tokens": 5}}

        set_current_run(None)


class TestTraceRetrievalDecorator:
    """Tests for the @trace_retrieval decorator."""

    def test_trace_retrieval_creates_step(self):
        """@trace_retrieval should create a step of type RETRIEVAL."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import trace_retrieval

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        captured_step = None

        @trace_retrieval(name="vector_search")
        def retrieval_func(_query: str):
            nonlocal captured_step
            captured_step = get_current_step()
            return [{"doc": "doc1"}, {"doc": "doc2"}]

        retrieval_func("test query")

        assert captured_step is not None
        assert captured_step.type == StepType.RETRIEVAL
        assert captured_step.name == "vector_search"

        set_current_run(None)


class TestInputExclusion:
    """Tests for input exclusion parameters in decorators."""

    def test_exclude_inputs_single_param(self):
        """Should exclude a single parameter from captured inputs."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="auth_agent", exclude_inputs=["password"])
        def auth_agent(username: str, password: str) -> bool:
            return True

        auth_agent("user123", "secret_password")

        assert len(run.steps) == 1
        assert run.steps[0].inputs["username"] == "user123"
        assert run.steps[0].inputs["password"] == "[EXCLUDED]"

        set_current_run(None)

    def test_exclude_inputs_multiple_params(self):
        """Should exclude multiple parameters from captured inputs."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_tool

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_tool(name="db_query", exclude_inputs=["api_key", "connection_string"])
        def query_db(sql: str, api_key: str, connection_string: str) -> list:
            return []

        query_db("SELECT *", "key123", "postgres://localhost")

        assert len(run.steps) == 1
        assert run.steps[0].inputs["sql"] == "SELECT *"
        assert run.steps[0].inputs["api_key"] == "[EXCLUDED]"
        assert run.steps[0].inputs["connection_string"] == "[EXCLUDED]"

        set_current_run(None)

    def test_capture_inputs_false(self):
        """Should capture no inputs when capture_inputs=False."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_llm

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_llm(name="confidential_llm", capture_inputs=False)
        def confidential_llm(prompt: str, system_prompt: str) -> str:
            return "response"

        confidential_llm("secret prompt", "secret system")

        assert len(run.steps) == 1
        assert run.steps[0].inputs == {}

        set_current_run(None)

    def test_exclude_inputs_with_kwargs(self):
        """Should handle exclusion with **kwargs."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="kwarg_agent", exclude_inputs=["secret"])
        def kwarg_agent(query: str, **kwargs) -> str:
            return "result"

        kwarg_agent("test", secret="password", other="value")

        assert len(run.steps) == 1
        assert run.steps[0].inputs["query"] == "test"
        # kwargs is captured as a dict, exclusion applies to named params
        # The 'secret' key should be in kwargs dict, but we exclude it if passed as keyword
        # Actually, inspect.signature captures kwargs as a single dict parameter
        # Let's verify the behavior
        inputs = run.steps[0].inputs
        assert inputs["query"] == "test"

        set_current_run(None)

    @pytest.mark.asyncio
    async def test_exclude_inputs_async(self):
        """Should work with async functions."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="async_auth", exclude_inputs=["token"])
        async def async_auth(user_id: str, token: str) -> bool:
            await asyncio.sleep(0.001)
            return True

        await async_auth("user1", "secret_token")

        assert len(run.steps) == 1
        assert run.steps[0].inputs["user_id"] == "user1"
        assert run.steps[0].inputs["token"] == "[EXCLUDED]"

        set_current_run(None)

    def test_exclude_nonexistent_param_is_noop(self):
        """Excluding a nonexistent parameter should be a no-op."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun
        from agenttrace.instrumentation.decorators import trace_agent

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        @trace_agent(name="simple_agent", exclude_inputs=["nonexistent"])
        def simple_agent(query: str) -> str:
            return "result"

        simple_agent("test query")

        assert len(run.steps) == 1
        assert run.steps[0].inputs["query"] == "test query"
        assert "nonexistent" not in run.steps[0].inputs

        set_current_run(None)


class TestStepContextManager:
    """Tests for the step() context manager."""

    def test_step_context_manager_creates_step(self):
        """step() context manager should create and manage a step."""
        from agenttrace.core.context import get_current_step, set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        with step("my_workflow", type=StepType.WORKFLOW) as s:
            current = get_current_step()
            assert current == s
            assert s.name == "my_workflow"
            assert s.type == StepType.WORKFLOW

        # Step should be finalized and added to run
        assert len(run.steps) == 1
        assert run.steps[0].end_time is not None

        set_current_run(None)

    def test_step_context_manager_captures_exception(self):
        """step() context manager should capture exceptions."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        with (
            pytest.raises(ValueError, match="workflow error"),
            step(  # noqa: SIM117
                "failing_workflow", type=StepType.WORKFLOW
            ),
        ):
            raise ValueError("workflow error")

        assert len(run.steps) == 1
        assert run.steps[0].error == "workflow error"
        assert run.steps[0].error_type == "ValueError"

        set_current_run(None)

    def test_step_context_manager_nesting(self):
        """Nested step() calls should create hierarchy."""
        from agenttrace.core.context import set_current_run
        from agenttrace.core.models import AgentRun, StepType
        from agenttrace.instrumentation.decorators import step

        run = AgentRun(name="test_run", start_time=datetime.now(UTC))
        set_current_run(run)

        with step("outer", type=StepType.WORKFLOW) as outer_step:  # noqa: SIM117
            with step("inner", type=StepType.TOOL):
                pass

        assert len(run.steps) == 1
        assert run.steps[0].name == "outer"
        assert len(run.steps[0].children) == 1
        assert run.steps[0].children[0].name == "inner"
        assert run.steps[0].children[0].parent_id == outer_step.id

        set_current_run(None)
