"""
Tests for context propagation using contextvars.

TDD approach: These tests are written BEFORE the implementation.
"""

import asyncio

import pytest


class TestCurrentStep:
    """Tests for current step context management."""

    def test_get_current_step_returns_none_when_not_set(self):
        """get_current_step should return None when no step is set."""
        # Clear any existing context first
        from tracecraft.core.context import get_current_step, set_current_step

        set_current_step(None)

        assert get_current_step() is None

    def test_set_current_step(self, sample_step):
        """set_current_step should set the current step."""
        from tracecraft.core.context import get_current_step, set_current_step

        set_current_step(sample_step)

        assert get_current_step() == sample_step

        # Clean up
        set_current_step(None)

    def test_set_current_step_returns_token(self, sample_step):
        """set_current_step should return a token for resetting."""
        from tracecraft.core.context import set_current_step

        token = set_current_step(sample_step)

        assert token is not None

        # Clean up
        set_current_step(None)

    def test_reset_current_step_with_token(self, trace_id, sample_timestamp):
        """reset_current_step should restore previous value using token."""
        from tracecraft.core.context import (
            get_current_step,
            reset_current_step,
            set_current_step,
        )
        from tracecraft.core.models import Step, StepType

        step1 = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="step1",
            start_time=sample_timestamp,
        )
        step2 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="step2",
            start_time=sample_timestamp,
        )

        # Set first step
        set_current_step(step1)
        # Set second step, save token
        token = set_current_step(step2)

        assert get_current_step() == step2

        # Reset to previous
        reset_current_step(token)

        assert get_current_step() == step1

        # Clean up
        set_current_step(None)


class TestCurrentRun:
    """Tests for current run context management."""

    def test_get_current_run_returns_none_when_not_set(self):
        """get_current_run should return None when no run is set."""
        from tracecraft.core.context import get_current_run, set_current_run

        set_current_run(None)

        assert get_current_run() is None

    def test_set_current_run(self, sample_run):
        """set_current_run should set the current run."""
        from tracecraft.core.context import get_current_run, set_current_run

        set_current_run(sample_run)

        assert get_current_run() == sample_run

        # Clean up
        set_current_run(None)

    def test_set_current_run_returns_token(self, sample_run):
        """set_current_run should return a token for resetting."""
        from tracecraft.core.context import set_current_run

        token = set_current_run(sample_run)

        assert token is not None

        # Clean up
        set_current_run(None)

    def test_reset_current_run_with_token(self, sample_timestamp):
        """reset_current_run should restore previous value using token."""
        from tracecraft.core.context import (
            get_current_run,
            reset_current_run,
            set_current_run,
        )
        from tracecraft.core.models import AgentRun

        run1 = AgentRun(name="run1", start_time=sample_timestamp)
        run2 = AgentRun(name="run2", start_time=sample_timestamp)

        # Set first run
        set_current_run(run1)
        # Set second run, save token
        token = set_current_run(run2)

        assert get_current_run() == run2

        # Reset to previous
        reset_current_run(token)

        assert get_current_run() == run1

        # Clean up
        set_current_run(None)


class TestAsyncPropagation:
    """Tests for context propagation through async/await."""

    @pytest.mark.asyncio
    async def test_context_propagates_through_await(self, sample_step):
        """Context should propagate through async/await calls."""
        from tracecraft.core.context import get_current_step, set_current_step

        set_current_step(sample_step)

        async def inner_async():
            # Should see the same step
            return get_current_step()

        result = await inner_async()
        assert result == sample_step

        # Clean up
        set_current_step(None)

    @pytest.mark.asyncio
    async def test_context_propagates_through_nested_async(self, sample_step):
        """Context should propagate through multiple nested async calls."""
        from tracecraft.core.context import get_current_step, set_current_step

        set_current_step(sample_step)

        async def level2():
            return get_current_step()

        async def level1():
            return await level2()

        result = await level1()
        assert result == sample_step

        # Clean up
        set_current_step(None)

    @pytest.mark.asyncio
    async def test_run_context_propagates_through_await(self, sample_run):
        """Run context should propagate through async/await calls."""
        from tracecraft.core.context import get_current_run, set_current_run

        set_current_run(sample_run)

        async def inner_async():
            return get_current_run()

        result = await inner_async()
        assert result == sample_run

        # Clean up
        set_current_run(None)


class TestContextIsolation:
    """Tests for context isolation between concurrent tasks."""

    @pytest.mark.asyncio
    async def test_concurrent_tasks_have_isolated_step_context(self, trace_id, sample_timestamp):
        """Different concurrent tasks should have isolated step context."""
        from tracecraft.core.context import get_current_step, set_current_step
        from tracecraft.core.models import Step, StepType

        step1 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="task1_step",
            start_time=sample_timestamp,
        )
        step2 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="task2_step",
            start_time=sample_timestamp,
        )

        results = {}

        async def task1():
            set_current_step(step1)
            await asyncio.sleep(0.01)  # Yield control
            results["task1"] = get_current_step()

        async def task2():
            set_current_step(step2)
            await asyncio.sleep(0.01)  # Yield control
            results["task2"] = get_current_step()

        # Run tasks concurrently
        await asyncio.gather(task1(), task2())

        # Each task should see its own step
        assert results["task1"].name == "task1_step"
        assert results["task2"].name == "task2_step"

    @pytest.mark.asyncio
    async def test_concurrent_tasks_have_isolated_run_context(self, sample_timestamp):
        """Different concurrent tasks should have isolated run context."""
        from tracecraft.core.context import get_current_run, set_current_run
        from tracecraft.core.models import AgentRun

        run1 = AgentRun(name="task1_run", start_time=sample_timestamp)
        run2 = AgentRun(name="task2_run", start_time=sample_timestamp)

        results = {}

        async def task1():
            set_current_run(run1)
            await asyncio.sleep(0.01)
            results["task1"] = get_current_run()

        async def task2():
            set_current_run(run2)
            await asyncio.sleep(0.01)
            results["task2"] = get_current_run()

        await asyncio.gather(task1(), task2())

        assert results["task1"].name == "task1_run"
        assert results["task2"].name == "task2_run"

    @pytest.mark.asyncio
    async def test_child_task_inherits_parent_context(self, sample_step):
        """Child tasks created from a coroutine should inherit parent context."""
        from tracecraft.core.context import get_current_step, set_current_step

        set_current_step(sample_step)

        async def child_task():
            # Child should inherit parent's context
            return get_current_step()

        # Create child task while parent has context set
        task = asyncio.create_task(child_task())
        result = await task

        assert result == sample_step

        # Clean up
        set_current_step(None)


class TestStepContextManager:
    """Tests for step context manager helper."""

    def test_step_context_manager_sets_and_resets(self, sample_step):
        """step_context should set step on enter and reset on exit."""
        from tracecraft.core.context import (
            get_current_step,
            set_current_step,
            step_context,
        )

        set_current_step(None)

        with step_context(sample_step):
            assert get_current_step() == sample_step

        assert get_current_step() is None

    def test_step_context_manager_restores_previous(self, trace_id, sample_timestamp):
        """step_context should restore previous step on exit."""
        from tracecraft.core.context import (
            get_current_step,
            set_current_step,
            step_context,
        )
        from tracecraft.core.models import Step, StepType

        outer_step = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="outer",
            start_time=sample_timestamp,
        )
        inner_step = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="inner",
            start_time=sample_timestamp,
        )

        set_current_step(outer_step)

        with step_context(inner_step):
            assert get_current_step() == inner_step

        assert get_current_step() == outer_step

        # Clean up
        set_current_step(None)

    def test_step_context_manager_handles_exception(self, sample_step):
        """step_context should reset even if exception occurs."""
        from tracecraft.core.context import (
            get_current_step,
            set_current_step,
            step_context,
        )

        set_current_step(None)

        try:
            with step_context(sample_step):
                assert get_current_step() == sample_step
                raise ValueError("test error")
        except ValueError:
            pass

        assert get_current_step() is None

    @pytest.mark.asyncio
    async def test_step_context_manager_async(self, sample_step):
        """step_context should work in async context."""
        from tracecraft.core.context import (
            get_current_step,
            set_current_step,
            step_context,
        )

        set_current_step(None)

        async def async_work():
            with step_context(sample_step):
                await asyncio.sleep(0.001)
                return get_current_step()

        result = await async_work()
        assert result == sample_step
        assert get_current_step() is None


class TestRunContextManager:
    """Tests for run context manager helper."""

    def test_run_context_manager_sets_and_resets(self, sample_run):
        """run_context should set run on enter and reset on exit."""
        from tracecraft.core.context import (
            get_current_run,
            run_context,
            set_current_run,
        )

        set_current_run(None)

        with run_context(sample_run):
            assert get_current_run() == sample_run

        assert get_current_run() is None

    def test_run_context_manager_handles_exception(self, sample_run):
        """run_context should reset even if exception occurs."""
        from tracecraft.core.context import (
            get_current_run,
            run_context,
            set_current_run,
        )

        set_current_run(None)

        try:
            with run_context(sample_run):
                assert get_current_run() == sample_run
                raise ValueError("test error")
        except ValueError:
            pass

        assert get_current_run() is None
