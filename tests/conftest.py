"""
Pytest configuration and shared fixtures for AgentTrace tests.
"""

from datetime import datetime
from uuid import uuid4

import pytest


@pytest.fixture
def trace_id():
    """Generate a unique trace ID for tests."""
    return uuid4()


@pytest.fixture
def sample_timestamp():
    """Generate a sample timestamp for tests."""
    return datetime.now()


@pytest.fixture
def mock_inputs():
    """Sample inputs for testing."""
    return {"query": "What is the weather?", "context": ["doc1", "doc2"]}


@pytest.fixture
def mock_outputs():
    """Sample outputs for testing."""
    return {"response": "The weather is sunny.", "confidence": 0.95}


@pytest.fixture
def sample_step(trace_id, sample_timestamp):
    """Create a sample Step for testing."""
    from agenttrace.core.models import Step, StepType

    return Step(
        trace_id=trace_id,
        type=StepType.TOOL,
        name="sample_tool",
        start_time=sample_timestamp,
    )


@pytest.fixture
def sample_run(sample_timestamp):
    """Create a sample AgentRun for testing."""
    from agenttrace.core.models import AgentRun

    return AgentRun(
        name="sample_run",
        start_time=sample_timestamp,
    )
