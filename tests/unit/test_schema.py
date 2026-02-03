"""
Tests for the schema engine.

Tests OTel GenAI and OpenInference attribute mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import Step, StepType
from tracecraft.schema.canonical import SchemaDialect, SchemaEngine
from tracecraft.schema.openinference import OpenInferenceMapper
from tracecraft.schema.otel_genai import OTelGenAIMapper


@pytest.fixture
def llm_step() -> Step:
    """Create a sample LLM step."""
    return Step(
        trace_id=uuid4(),
        type=StepType.LLM,
        name="chat_completion",
        start_time=datetime.now(UTC),
        model_name="gpt-4",
        model_provider="openai",
        input_tokens=100,
        output_tokens=50,
        inputs={"prompt": "Hello, how are you?"},
        outputs={"result": "I'm doing well, thank you!"},
    )


@pytest.fixture
def agent_step() -> Step:
    """Create a sample agent step."""
    return Step(
        trace_id=uuid4(),
        type=StepType.AGENT,
        name="research_agent",
        start_time=datetime.now(UTC),
        inputs={"query": "Find information about Python"},
        outputs={"result": "Python is a programming language..."},
        attributes={
            "agent_id": "agent-001",
            "agent_description": "An agent that researches topics",
        },
    )


@pytest.fixture
def agent_step_minimal() -> Step:
    """Create an agent step without optional attributes."""
    return Step(
        trace_id=uuid4(),
        type=StepType.AGENT,
        name="simple_agent",
        start_time=datetime.now(UTC),
        inputs={"input": "test"},
        outputs={"output": "result"},
    )


@pytest.fixture
def tool_step() -> Step:
    """Create a sample tool step."""
    return Step(
        trace_id=uuid4(),
        type=StepType.TOOL,
        name="web_search",
        start_time=datetime.now(UTC),
        inputs={"query": "weather today"},
        outputs={"results": ["sunny", "warm"]},
    )


@pytest.fixture
def retrieval_step() -> Step:
    """Create a sample retrieval step."""
    return Step(
        trace_id=uuid4(),
        type=StepType.RETRIEVAL,
        name="vector_search",
        start_time=datetime.now(UTC),
        inputs={"query": "Python documentation"},
        outputs={"documents": [{"id": "1", "text": "Python is..."}]},
    )


class TestOTelGenAIMapper:
    """Tests for OTel GenAI attribute mapping."""

    def test_otel_genai_model_attr(self, llm_step: Step) -> None:
        """Should map model name to gen_ai.request.model."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["gen_ai.request.model"] == "gpt-4"

    def test_otel_genai_system_attr(self, llm_step: Step) -> None:
        """Should map provider to gen_ai.system."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["gen_ai.system"] == "openai"

    def test_otel_genai_input_tokens(self, llm_step: Step) -> None:
        """Should map input tokens to gen_ai.usage.input_tokens."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["gen_ai.usage.input_tokens"] == 100

    def test_otel_genai_output_tokens(self, llm_step: Step) -> None:
        """Should map output tokens to gen_ai.usage.output_tokens."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["gen_ai.usage.output_tokens"] == 50

    def test_otel_genai_operation_name(self, llm_step: Step) -> None:
        """Should include operation name."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["gen_ai.operation.name"] == "chat"

    def test_otel_genai_skips_non_llm(self, tool_step: Step) -> None:
        """Should return minimal attrs for non-LLM steps."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(tool_step)
        assert "gen_ai.request.model" not in attrs
        assert "gen_ai.usage.input_tokens" not in attrs

    def test_otel_genai_agent_name(self, agent_step: Step) -> None:
        """Should map agent name to gen_ai.agent.name."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step)
        assert attrs["gen_ai.agent.name"] == "research_agent"

    def test_otel_genai_agent_id(self, agent_step: Step) -> None:
        """Should map agent ID from attributes to gen_ai.agent.id."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step)
        assert attrs["gen_ai.agent.id"] == "agent-001"

    def test_otel_genai_agent_description(self, agent_step: Step) -> None:
        """Should map agent description to gen_ai.agent.description."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step)
        assert attrs["gen_ai.agent.description"] == "An agent that researches topics"

    def test_otel_genai_agent_operation_name(self, agent_step: Step) -> None:
        """Should set operation name to invoke_agent for agent steps."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step)
        assert attrs["gen_ai.operation.name"] == "invoke_agent"

    def test_otel_genai_agent_minimal(self, agent_step_minimal: Step) -> None:
        """Should handle agent step without optional attributes."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step_minimal)
        assert attrs["gen_ai.agent.name"] == "simple_agent"
        assert attrs["gen_ai.operation.name"] == "invoke_agent"
        assert "gen_ai.agent.id" not in attrs
        assert "gen_ai.agent.description" not in attrs

    def test_otel_genai_content_recording_disabled_by_default(self, llm_step: Step) -> None:
        """Should not record content by default."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step)
        assert "gen_ai.request.messages" not in attrs
        assert "gen_ai.response.messages" not in attrs

    def test_otel_genai_content_recording_enabled(self, llm_step: Step) -> None:
        """Should record content when enable_content_recording=True."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(llm_step, enable_content_recording=True)
        assert "gen_ai.request.messages" in attrs
        assert "gen_ai.response.messages" in attrs
        # Content should be serialized to JSON
        assert "Hello, how are you?" in attrs["gen_ai.request.messages"]
        assert "I'm doing well" in attrs["gen_ai.response.messages"]

    def test_otel_genai_content_recording_agent(self, agent_step: Step) -> None:
        """Should record content for agent steps when enabled."""
        mapper = OTelGenAIMapper()
        attrs = mapper.map_step(agent_step, enable_content_recording=True)
        assert "gen_ai.request.messages" in attrs
        assert "gen_ai.response.messages" in attrs
        assert "Find information about Python" in attrs["gen_ai.request.messages"]


class TestOpenInferenceMapper:
    """Tests for OpenInference attribute mapping."""

    def test_openinference_input(self, llm_step: Step) -> None:
        """Should map inputs to input.value."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(llm_step)
        assert "input.value" in attrs
        assert "Hello, how are you?" in str(attrs["input.value"])

    def test_openinference_output(self, llm_step: Step) -> None:
        """Should map outputs to output.value."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(llm_step)
        assert "output.value" in attrs
        assert "I'm doing well" in str(attrs["output.value"])

    def test_openinference_llm_model(self, llm_step: Step) -> None:
        """Should map model name to llm.model_name."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["llm.model_name"] == "gpt-4"

    def test_openinference_llm_token_count(self, llm_step: Step) -> None:
        """Should map token counts."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(llm_step)
        assert attrs["llm.token_count.prompt"] == 100
        assert attrs["llm.token_count.completion"] == 50
        assert attrs["llm.token_count.total"] == 150

    def test_openinference_retrieval_documents(
        self,
        retrieval_step: Step,
    ) -> None:
        """Should map retrieval outputs as documents."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(retrieval_step)
        assert "retrieval.documents" in attrs

    def test_openinference_tool_name(self, tool_step: Step) -> None:
        """Should map tool name."""
        mapper = OpenInferenceMapper()
        attrs = mapper.map_step(tool_step)
        assert attrs["tool.name"] == "web_search"


class TestSchemaDialect:
    """Tests for SchemaDialect enum."""

    def test_dialect_otel_genai(self) -> None:
        """OTEL_GENAI dialect should exist."""
        assert SchemaDialect.OTEL_GENAI.value == "otel_genai"

    def test_dialect_openinference(self) -> None:
        """OPENINFERENCE dialect should exist."""
        assert SchemaDialect.OPENINFERENCE.value == "openinference"

    def test_dialect_both(self) -> None:
        """BOTH dialect should exist."""
        assert SchemaDialect.BOTH.value == "both"


class TestSchemaEngine:
    """Tests for SchemaEngine."""

    def test_engine_otel_only(self, llm_step: Step) -> None:
        """Should only include OTel GenAI attributes."""
        engine = SchemaEngine(dialect=SchemaDialect.OTEL_GENAI)
        attrs = engine.map_step(llm_step)
        assert "gen_ai.request.model" in attrs
        assert "input.value" not in attrs

    def test_engine_openinference_only(self, llm_step: Step) -> None:
        """Should only include OpenInference attributes."""
        engine = SchemaEngine(dialect=SchemaDialect.OPENINFERENCE)
        attrs = engine.map_step(llm_step)
        assert "input.value" in attrs
        assert "gen_ai.request.model" not in attrs

    def test_dual_dialect_both(self, llm_step: Step) -> None:
        """Should include both OTel GenAI and OpenInference attributes."""
        engine = SchemaEngine(dialect=SchemaDialect.BOTH)
        attrs = engine.map_step(llm_step)
        # OTel GenAI
        assert "gen_ai.request.model" in attrs
        assert "gen_ai.usage.input_tokens" in attrs
        # OpenInference
        assert "input.value" in attrs
        assert "output.value" in attrs
        assert "llm.model_name" in attrs

    def test_engine_default_is_otel_genai(self, llm_step: Step) -> None:
        """Default dialect should be OTEL_GENAI (industry standard)."""
        engine = SchemaEngine()
        attrs = engine.map_step(llm_step)
        assert "gen_ai.request.model" in attrs
        # OpenInference attributes should NOT be present with default dialect
        assert "input.value" not in attrs
        assert engine.dialect == SchemaDialect.OTEL_GENAI

    def test_engine_includes_step_type(self, llm_step: Step) -> None:
        """Should include step type in common attributes."""
        engine = SchemaEngine()
        attrs = engine.map_step(llm_step)
        assert attrs.get("tracecraft.step.type") == "llm"

    def test_engine_includes_step_name(self, llm_step: Step) -> None:
        """Should include step name in common attributes."""
        engine = SchemaEngine()
        attrs = engine.map_step(llm_step)
        assert attrs.get("tracecraft.step.name") == "chat_completion"


class TestSchemaEngineEdgeCases:
    """Tests for edge cases in schema mapping."""

    def test_map_step_without_model(self) -> None:
        """Should handle steps without model name."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="completion",
            start_time=datetime.now(UTC),
        )
        engine = SchemaEngine()
        attrs = engine.map_step(step)
        assert "gen_ai.request.model" not in attrs or attrs["gen_ai.request.model"] is None

    def test_map_step_without_tokens(self) -> None:
        """Should handle steps without token counts."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="completion",
            start_time=datetime.now(UTC),
            model_name="gpt-4",
        )
        engine = SchemaEngine()
        attrs = engine.map_step(step)
        # Should not have token attributes if not set
        assert attrs.get("gen_ai.usage.input_tokens") is None

    def test_map_step_with_error(self) -> None:
        """Should include error information."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="completion",
            start_time=datetime.now(UTC),
            error="Connection failed",
            error_type="ConnectionError",
        )
        engine = SchemaEngine()
        attrs = engine.map_step(step)
        assert attrs.get("error.message") == "Connection failed"
        assert attrs.get("error.type") == "ConnectionError"
