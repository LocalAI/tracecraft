"""
Tests for core data models (StepType, Step, AgentRun).

TDD approach: These tests are written BEFORE the implementation.
"""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4


class TestStepType:
    """Tests for the StepType enum."""

    def test_step_type_enum_has_agent(self):
        """StepType should have an AGENT value."""
        from agenttrace.core.models import StepType

        assert StepType.AGENT == "agent"

    def test_step_type_enum_has_llm(self):
        """StepType should have an LLM value."""
        from agenttrace.core.models import StepType

        assert StepType.LLM == "llm"

    def test_step_type_enum_has_tool(self):
        """StepType should have a TOOL value."""
        from agenttrace.core.models import StepType

        assert StepType.TOOL == "tool"

    def test_step_type_enum_has_retrieval(self):
        """StepType should have a RETRIEVAL value."""
        from agenttrace.core.models import StepType

        assert StepType.RETRIEVAL == "retrieval"

    def test_step_type_enum_has_memory(self):
        """StepType should have a MEMORY value."""
        from agenttrace.core.models import StepType

        assert StepType.MEMORY == "memory"

    def test_step_type_enum_has_guardrail(self):
        """StepType should have a GUARDRAIL value."""
        from agenttrace.core.models import StepType

        assert StepType.GUARDRAIL == "guardrail"

    def test_step_type_enum_has_workflow(self):
        """StepType should have a WORKFLOW value."""
        from agenttrace.core.models import StepType

        assert StepType.WORKFLOW == "workflow"

    def test_step_type_enum_has_error(self):
        """StepType should have an ERROR value."""
        from agenttrace.core.models import StepType

        assert StepType.ERROR == "error"

    def test_step_type_is_string_enum(self):
        """StepType values should be strings."""
        from agenttrace.core.models import StepType

        assert isinstance(StepType.AGENT.value, str)
        assert StepType.AGENT == "agent"


class TestStep:
    """Tests for the Step model."""

    def test_step_creation_with_required_fields(self, trace_id, sample_timestamp):
        """Step should be created with required fields."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="openai_chat",
            start_time=sample_timestamp,
        )

        assert step.trace_id == trace_id
        assert step.type == StepType.LLM
        assert step.name == "openai_chat"
        assert step.start_time == sample_timestamp

    def test_step_has_auto_generated_id(self, trace_id, sample_timestamp):
        """Step should have an auto-generated UUID id."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="web_search",
            start_time=sample_timestamp,
        )

        assert isinstance(step.id, UUID)

    def test_step_parent_id_defaults_to_none(self, trace_id, sample_timestamp):
        """Step parent_id should default to None."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="web_search",
            start_time=sample_timestamp,
        )

        assert step.parent_id is None

    def test_step_with_parent_id(self, trace_id, sample_timestamp):
        """Step should accept a parent_id."""
        from agenttrace.core.models import Step, StepType

        parent_id = uuid4()
        step = Step(
            trace_id=trace_id,
            parent_id=parent_id,
            type=StepType.LLM,
            name="completion",
            start_time=sample_timestamp,
        )

        assert step.parent_id == parent_id

    def test_step_optional_fields_default_to_none_or_empty(self, trace_id, sample_timestamp):
        """Step optional fields should have sensible defaults."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="test",
            start_time=sample_timestamp,
        )

        assert step.end_time is None
        assert step.duration_ms is None
        assert step.inputs == {}
        assert step.outputs == {}
        assert step.attributes == {}
        assert step.model_name is None
        assert step.model_provider is None
        assert step.input_tokens is None
        assert step.output_tokens is None
        assert step.cost_usd is None
        assert step.error is None
        assert step.error_type is None
        assert step.children == []

    def test_step_with_inputs_and_outputs(
        self, trace_id, sample_timestamp, mock_inputs, mock_outputs
    ):
        """Step should accept inputs and outputs."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="chat",
            start_time=sample_timestamp,
            inputs=mock_inputs,
            outputs=mock_outputs,
        )

        assert step.inputs == mock_inputs
        assert step.outputs == mock_outputs

    def test_step_with_llm_specific_fields(self, trace_id, sample_timestamp):
        """Step should accept LLM-specific fields."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="gpt4_completion",
            start_time=sample_timestamp,
            model_name="gpt-4",
            model_provider="openai",
            input_tokens=100,
            output_tokens=250,
            cost_usd=0.015,
        )

        assert step.model_name == "gpt-4"
        assert step.model_provider == "openai"
        assert step.input_tokens == 100
        assert step.output_tokens == 250
        assert step.cost_usd == 0.015

    def test_step_with_error_fields(self, trace_id, sample_timestamp):
        """Step should accept error fields."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.ERROR,
            name="failed_call",
            start_time=sample_timestamp,
            error="API rate limit exceeded",
            error_type="RateLimitError",
        )

        assert step.error == "API rate limit exceeded"
        assert step.error_type == "RateLimitError"

    def test_step_with_end_time_and_duration(self, trace_id, sample_timestamp):
        """Step should accept end_time and duration_ms."""
        from agenttrace.core.models import Step, StepType

        end_time = datetime.now(UTC)
        step = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="search",
            start_time=sample_timestamp,
            end_time=end_time,
            duration_ms=150.5,
        )

        assert step.end_time == end_time
        assert step.duration_ms == 150.5

    def test_step_children_is_list_of_steps(self, trace_id, sample_timestamp):
        """Step children should be a list of Step objects."""
        from agenttrace.core.models import Step, StepType

        child_step = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="child",
            start_time=sample_timestamp,
        )

        parent_step = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="parent",
            start_time=sample_timestamp,
            children=[child_step],
        )

        assert len(parent_step.children) == 1
        assert parent_step.children[0].name == "child"


class TestAgentRun:
    """Tests for the AgentRun model."""

    def test_agent_run_creation_with_required_fields(self, sample_timestamp):
        """AgentRun should be created with required fields."""
        from agenttrace.core.models import AgentRun

        run = AgentRun(
            name="research_agent",
            start_time=sample_timestamp,
        )

        assert run.name == "research_agent"
        assert run.start_time == sample_timestamp

    def test_agent_run_has_auto_generated_id(self, sample_timestamp):
        """AgentRun should have an auto-generated UUID id."""
        from agenttrace.core.models import AgentRun

        run = AgentRun(
            name="test_agent",
            start_time=sample_timestamp,
        )

        assert isinstance(run.id, UUID)

    def test_agent_run_optional_fields_default(self, sample_timestamp):
        """AgentRun optional fields should have sensible defaults."""
        from agenttrace.core.models import AgentRun

        run = AgentRun(
            name="test_agent",
            start_time=sample_timestamp,
        )

        assert run.description is None
        assert run.end_time is None
        assert run.duration_ms is None
        assert run.session_id is None
        assert run.user_id is None
        assert run.environment == "development"
        assert run.tags == []
        assert run.input is None
        assert run.output is None
        assert run.steps == []
        assert run.total_tokens == 0
        assert run.total_cost_usd == 0.0
        assert run.error_count == 0
        assert run.should_export is True
        assert run.sample_reason is None

    def test_agent_run_with_all_fields(self, sample_timestamp):
        """AgentRun should accept all fields."""
        from agenttrace.core.models import AgentRun, Step, StepType

        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="llm_call",
            start_time=sample_timestamp,
        )

        end_time = datetime.now(UTC)
        run = AgentRun(
            name="full_agent",
            description="A fully configured agent run",
            start_time=sample_timestamp,
            end_time=end_time,
            duration_ms=2500.0,
            session_id="session-123",
            user_id="user-456",
            environment="production",
            tags=["test", "demo"],
            input={"query": "test query"},
            output={"response": "test response"},
            steps=[step],
            total_tokens=500,
            total_cost_usd=0.025,
            error_count=0,
            should_export=True,
            sample_reason="sampled",
        )

        assert run.description == "A fully configured agent run"
        assert run.session_id == "session-123"
        assert run.user_id == "user-456"
        assert run.environment == "production"
        assert run.tags == ["test", "demo"]
        assert run.input == {"query": "test query"}
        assert run.output == {"response": "test response"}
        assert len(run.steps) == 1
        assert run.total_tokens == 500
        assert run.total_cost_usd == 0.025
        assert run.sample_reason == "sampled"


class TestModelSerialization:
    """Tests for model JSON serialization."""

    def test_step_serializes_to_json(self, trace_id, sample_timestamp):
        """Step should serialize to valid JSON."""
        from agenttrace.core.models import Step, StepType

        step = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="test_step",
            start_time=sample_timestamp,
            inputs={"prompt": "Hello"},
            outputs={"response": "Hi there"},
        )

        json_str = step.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "test_step"
        assert data["type"] == "llm"
        assert data["inputs"] == {"prompt": "Hello"}
        assert data["outputs"] == {"response": "Hi there"}

    def test_agent_run_serializes_to_json(self, sample_timestamp):
        """AgentRun should serialize to valid JSON."""
        from agenttrace.core.models import AgentRun

        run = AgentRun(
            name="test_run",
            start_time=sample_timestamp,
            input={"query": "test"},
            output={"answer": "result"},
        )

        json_str = run.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "test_run"
        assert data["input"] == {"query": "test"}
        assert data["output"] == {"answer": "result"}

    def test_nested_steps_serialize_correctly(self, trace_id, sample_timestamp):
        """Nested steps should serialize correctly."""
        from agenttrace.core.models import Step, StepType

        child = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="child_step",
            start_time=sample_timestamp,
        )

        parent = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="parent_step",
            start_time=sample_timestamp,
            children=[child],
        )

        json_str = parent.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "parent_step"
        assert len(data["children"]) == 1
        assert data["children"][0]["name"] == "child_step"

    def test_step_deserializes_from_json(self, trace_id, sample_timestamp):
        """Step should deserialize from JSON."""
        from agenttrace.core.models import Step, StepType

        original = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="search",
            start_time=sample_timestamp,
            input_tokens=50,
        )

        json_str = original.model_dump_json()
        restored = Step.model_validate_json(json_str)

        assert restored.name == original.name
        assert restored.type == original.type
        assert restored.input_tokens == original.input_tokens

    def test_agent_run_with_steps_serializes(self, sample_timestamp):
        """AgentRun with steps should serialize properly."""
        from agenttrace.core.models import AgentRun, Step, StepType

        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="embedded_step",
            start_time=sample_timestamp,
        )

        run = AgentRun(
            id=run_id,
            name="run_with_steps",
            start_time=sample_timestamp,
            steps=[step],
        )

        json_str = run.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "run_with_steps"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["name"] == "embedded_step"


class TestStepNesting:
    """Tests for step hierarchy/nesting."""

    def test_deeply_nested_steps(self, trace_id, sample_timestamp):
        """Steps should support deep nesting."""
        from agenttrace.core.models import Step, StepType

        # Create a 3-level deep hierarchy
        level3 = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="level3",
            start_time=sample_timestamp,
        )

        level2 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="level2",
            start_time=sample_timestamp,
            children=[level3],
        )

        level1 = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="level1",
            start_time=sample_timestamp,
            children=[level2],
        )

        assert level1.children[0].name == "level2"
        assert level1.children[0].children[0].name == "level3"

    def test_multiple_children_at_same_level(self, trace_id, sample_timestamp):
        """Steps should support multiple children at the same level."""
        from agenttrace.core.models import Step, StepType

        child1 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="tool1",
            start_time=sample_timestamp,
        )

        child2 = Step(
            trace_id=trace_id,
            type=StepType.TOOL,
            name="tool2",
            start_time=sample_timestamp,
        )

        child3 = Step(
            trace_id=trace_id,
            type=StepType.LLM,
            name="llm",
            start_time=sample_timestamp,
        )

        parent = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="agent",
            start_time=sample_timestamp,
            children=[child1, child2, child3],
        )

        assert len(parent.children) == 3
        child_names = [c.name for c in parent.children]
        assert child_names == ["tool1", "tool2", "llm"]

    def test_parent_id_links_to_parent(self, trace_id, sample_timestamp):
        """Children should have parent_id linking to parent."""
        from agenttrace.core.models import Step, StepType

        parent = Step(
            trace_id=trace_id,
            type=StepType.AGENT,
            name="parent",
            start_time=sample_timestamp,
        )

        child = Step(
            trace_id=trace_id,
            parent_id=parent.id,
            type=StepType.TOOL,
            name="child",
            start_time=sample_timestamp,
        )

        assert child.parent_id == parent.id
