"""Tests for MLflow integration.

Note: Most MLflow functionality requires mlflow to be installed.
These tests cover basic integration points.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType


@pytest.fixture
def sample_traces():
    """Create sample traces for testing."""
    trace_id_1 = uuid4()
    trace_id_2 = uuid4()
    return [
        AgentRun(
            id=trace_id_1,
            name="test-run-1",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_1,
                    name="llm-step-1",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={
                        "input": "What is Python?",
                        "context": "Python is a programming language.",
                    },
                    outputs={"output": "Python is a high-level programming language."},
                    model_name="gpt-4",
                    input_tokens=10,
                    output_tokens=20,
                ),
            ],
        ),
        AgentRun(
            id=trace_id_2,
            name="test-run-2",
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
            steps=[
                Step(
                    id=uuid4(),
                    trace_id=trace_id_2,
                    name="llm-step-2",
                    type=StepType.LLM,
                    start_time=datetime.now(UTC),
                    end_time=datetime.now(UTC),
                    inputs={
                        "messages": [{"role": "user", "content": "Explain AI"}],
                    },
                    outputs={"response": "AI refers to artificial intelligence systems."},
                    model_name="claude-3",
                ),
            ],
        ),
    ]


class TestMlflowExporterAvailability:
    """Tests for MLflow exporter availability."""

    def test_mlflow_exporter_is_importable(self):
        """Test that MLflowExporter can be imported."""
        from tracecraft.exporters.mlflow import MLflowExporter

        assert MLflowExporter is not None

    def test_create_mlflow_exporter_is_importable(self):
        """Test that create_mlflow_exporter can be imported."""
        from tracecraft.exporters.mlflow import create_mlflow_exporter

        assert callable(create_mlflow_exporter)


class TestMlflowExporterWithMock:
    """Tests using mocked MLflow."""

    def test_mlflow_exporter_class_exists(self):
        """Test MLflowExporter class can be imported."""
        from tracecraft.exporters.mlflow import MLflowExporter

        # Should be a class
        assert MLflowExporter is not None
