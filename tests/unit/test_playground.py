"""Tests for the playground module."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from tracecraft.core.models import AgentRun, Step, StepType
from tracecraft.playground.providers.base import BaseReplayProvider, ReplayResult


class TestReplayResult:
    """Tests for ReplayResult dataclass."""

    def test_replay_result_creation(self) -> None:
        """Test creating a ReplayResult."""
        result = ReplayResult(
            output="Hello, world!",
            input_tokens=10,
            output_tokens=5,
            duration_ms=100.0,
            model="gpt-4o",
        )

        assert result.output == "Hello, world!"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.duration_ms == 100.0
        assert result.model == "gpt-4o"
        assert result.succeeded is True

    def test_replay_result_with_error(self) -> None:
        """Test ReplayResult with an error."""
        result = ReplayResult(
            output="",
            error="API rate limit exceeded",
        )

        assert result.succeeded is False
        assert result.error == "API rate limit exceeded"

    def test_replay_result_defaults(self) -> None:
        """Test ReplayResult default values."""
        result = ReplayResult(output="test")

        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.duration_ms == 0.0
        assert result.model == ""
        assert result.error is None
        assert result.raw_response == {}


class TestBaseReplayProvider:
    """Tests for BaseReplayProvider abstract class."""

    @pytest.fixture
    def sample_step(self) -> Step:
        """Create a sample LLM step."""
        return Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="gpt4_call",
            start_time=datetime.now(UTC),
            model_name="gpt-4o",
            inputs={
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello!"},
                ],
                "temperature": 0.7,
                "max_tokens": 100,
            },
            outputs={"result": "Hello! How can I help you today?"},
        )

    def test_extract_messages_from_messages_field(self, sample_step: Step) -> None:
        """Test extracting messages from the messages field."""

        class TestProvider(BaseReplayProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def supported_models(self) -> list[str]:
                return ["gpt"]

            async def replay(self, step, modified_prompt=None, **kwargs):
                return ReplayResult(output="test")

        provider = TestProvider()
        messages = provider._extract_messages(sample_step)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_extract_messages_from_prompt_field(self) -> None:
        """Test extracting messages from prompt field."""
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            inputs={"prompt": "What is 2+2?"},
        )

        class TestProvider(BaseReplayProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def supported_models(self) -> list[str]:
                return ["test"]

            async def replay(self, step, modified_prompt=None, **kwargs):
                return ReplayResult(output="test")

        provider = TestProvider()
        messages = provider._extract_messages(step)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "What is 2+2?"

    def test_extract_model_params(self, sample_step: Step) -> None:
        """Test extracting model parameters."""

        class TestProvider(BaseReplayProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def supported_models(self) -> list[str]:
                return ["test"]

            async def replay(self, step, modified_prompt=None, **kwargs):
                return ReplayResult(output="test")

        provider = TestProvider()
        params = provider._extract_model_params(sample_step)

        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 100

    def test_can_replay_matching_model(self, sample_step: Step) -> None:
        """Test can_replay returns True for matching models."""

        class TestProvider(BaseReplayProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def supported_models(self) -> list[str]:
                return ["gpt-4"]

            async def replay(self, step, modified_prompt=None, **kwargs):
                return ReplayResult(output="test")

        provider = TestProvider()
        assert provider.can_replay(sample_step) is True

    def test_can_replay_non_matching_model(self, sample_step: Step) -> None:
        """Test can_replay returns False for non-matching models."""
        sample_step.model_name = "claude-3-opus"

        class TestProvider(BaseReplayProvider):
            @property
            def name(self) -> str:
                return "test"

            @property
            def supported_models(self) -> list[str]:
                return ["gpt"]

            async def replay(self, step, modified_prompt=None, **kwargs):
                return ReplayResult(output="test")

        provider = TestProvider()
        assert provider.can_replay(sample_step) is False


class TestOpenAIReplayProvider:
    """Tests for OpenAIReplayProvider."""

    def test_provider_name(self) -> None:
        """Test provider name."""
        from tracecraft.playground.providers.openai import OpenAIReplayProvider

        provider = OpenAIReplayProvider()
        assert provider.name == "openai"

    def test_supported_models(self) -> None:
        """Test supported models."""
        from tracecraft.playground.providers.openai import OpenAIReplayProvider

        provider = OpenAIReplayProvider()
        assert "gpt-4" in provider.supported_models
        assert "gpt-4o" in provider.supported_models
        assert "o1" in provider.supported_models

    def test_can_replay_gpt4(self) -> None:
        """Test can_replay for GPT-4."""
        from tracecraft.playground.providers.openai import OpenAIReplayProvider

        provider = OpenAIReplayProvider()
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="gpt-4o-2024-08-06",
        )
        assert provider.can_replay(step) is True

    def test_cannot_replay_claude(self) -> None:
        """Test can_replay returns False for Claude."""
        from tracecraft.playground.providers.openai import OpenAIReplayProvider

        provider = OpenAIReplayProvider()
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="claude-3-opus",
        )
        assert provider.can_replay(step) is False


class TestAnthropicReplayProvider:
    """Tests for AnthropicReplayProvider."""

    def test_provider_name(self) -> None:
        """Test provider name."""
        from tracecraft.playground.providers.anthropic import AnthropicReplayProvider

        provider = AnthropicReplayProvider()
        assert provider.name == "anthropic"

    def test_supported_models(self) -> None:
        """Test supported models."""
        from tracecraft.playground.providers.anthropic import AnthropicReplayProvider

        provider = AnthropicReplayProvider()
        assert "claude-3" in provider.supported_models
        assert "claude-sonnet" in provider.supported_models
        assert "claude-opus" in provider.supported_models

    def test_can_replay_claude(self) -> None:
        """Test can_replay for Claude."""
        from tracecraft.playground.providers.anthropic import AnthropicReplayProvider

        provider = AnthropicReplayProvider()
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="claude-3-opus-20240229",
        )
        assert provider.can_replay(step) is True

    def test_cannot_replay_gpt(self) -> None:
        """Test can_replay returns False for GPT."""
        from tracecraft.playground.providers.anthropic import AnthropicReplayProvider

        provider = AnthropicReplayProvider()
        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="gpt-4o",
        )
        assert provider.can_replay(step) is False


class TestRunnerFunctions:
    """Tests for runner functions."""

    @pytest.fixture
    def sample_run(self) -> AgentRun:
        """Create a sample AgentRun."""
        run_id = uuid4()
        step = Step(
            trace_id=run_id,
            type=StepType.LLM,
            name="gpt4_call",
            start_time=datetime.now(UTC),
            model_name="gpt-4o",
            inputs={
                "messages": [
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ]
            },
            outputs={"result": "Hello!"},
        )
        return AgentRun(
            id=run_id,
            name="test_run",
            start_time=datetime.now(UTC),
            steps=[step],
        )

    @pytest.fixture
    def sample_jsonl_file(self, sample_run: AgentRun, tmp_path: Path) -> Path:
        """Create a sample JSONL file."""
        file_path = tmp_path / "traces.jsonl"
        with file_path.open("w") as f:
            f.write(sample_run.model_dump_json() + "\n")
        return file_path

    def test_get_provider_for_step_openai(self) -> None:
        """Test get_provider_for_step returns OpenAI provider."""
        from tracecraft.playground.runner import get_provider_for_step

        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="gpt-4o",
        )

        provider = get_provider_for_step(step)
        assert provider is not None
        assert provider.name == "openai"

    def test_get_provider_for_step_anthropic(self) -> None:
        """Test get_provider_for_step returns Anthropic provider."""
        from tracecraft.playground.runner import get_provider_for_step

        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="claude-3-sonnet",
        )

        provider = get_provider_for_step(step)
        assert provider is not None
        assert provider.name == "anthropic"

    def test_get_provider_for_step_unknown(self) -> None:
        """Test get_provider_for_step returns None for unknown models."""
        from tracecraft.playground.runner import get_provider_for_step

        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="test",
            start_time=datetime.now(UTC),
            model_name="llama-3-70b",
        )

        provider = get_provider_for_step(step)
        assert provider is None

    @pytest.mark.asyncio
    async def test_replay_step_not_found(self, tmp_path: Path) -> None:
        """Test replay_step raises ValueError for non-existent step."""
        from tracecraft.playground.runner import replay_step

        file_path = tmp_path / "empty.jsonl"
        file_path.touch()

        with pytest.raises(ValueError, match="Step not found"):
            await replay_step(
                trace_id="non-existent",
                step_id="also-non-existent",
                trace_source=file_path,
            )


class TestComparison:
    """Tests for comparison module."""

    def test_iteration_creation(self) -> None:
        """Test creating an Iteration."""
        from tracecraft.playground.comparison import Iteration

        iteration = Iteration(
            prompt="You are a helpful assistant.",
            output="Hello! How can I help?",
            tokens=50,
            duration_ms=200.0,
            notes="First attempt",
        )

        assert iteration.prompt == "You are a helpful assistant."
        assert iteration.output == "Hello! How can I help?"
        assert iteration.tokens == 50
        assert iteration.duration_ms == 200.0

    def test_iteration_from_replay_result(self) -> None:
        """Test creating Iteration from ReplayResult."""
        from tracecraft.playground.comparison import Iteration

        result = ReplayResult(
            output="Test output",
            input_tokens=10,
            output_tokens=20,
            duration_ms=150.0,
        )

        iteration = Iteration.from_replay_result(
            prompt="Test prompt",
            result=result,
            notes="Test notes",
        )

        assert iteration.prompt == "Test prompt"
        assert iteration.output == "Test output"
        assert iteration.tokens == 30
        assert iteration.duration_ms == 150.0
        assert iteration.notes == "Test notes"

    def test_iteration_to_dict(self) -> None:
        """Test Iteration to_dict."""
        from tracecraft.playground.comparison import Iteration

        iteration = Iteration(
            prompt="test",
            output="output",
            tokens=10,
        )

        data = iteration.to_dict()
        assert data["prompt"] == "test"
        assert data["output"] == "output"
        assert data["tokens"] == 10

    def test_iteration_from_dict(self) -> None:
        """Test Iteration from_dict."""
        from tracecraft.playground.comparison import Iteration

        data = {
            "prompt": "test",
            "output": "output",
            "timestamp": "2024-01-01T00:00:00+00:00",
            "tokens": 10,
            "duration_ms": 100.0,
            "notes": "test notes",
        }

        iteration = Iteration.from_dict(data)
        assert iteration.prompt == "test"
        assert iteration.output == "output"
        assert iteration.tokens == 10

    def test_iteration_history_creation(self) -> None:
        """Test creating IterationHistory."""
        from tracecraft.playground.comparison import IterationHistory

        history = IterationHistory(
            step_id="abc123",
            step_name="gpt4_call",
            model="gpt-4o",
            original_prompt="You are helpful.",
            original_output="Hello!",
        )

        assert history.step_id == "abc123"
        assert history.step_name == "gpt4_call"
        assert history.model == "gpt-4o"
        assert len(history.iterations) == 0

    def test_iteration_history_add_iteration(self) -> None:
        """Test adding iteration to history."""
        from tracecraft.playground.comparison import IterationHistory

        history = IterationHistory(
            step_id="abc123",
            step_name="gpt4_call",
            model="gpt-4o",
            original_prompt="You are helpful.",
            original_output="Hello!",
        )

        result = ReplayResult(
            output="New output",
            input_tokens=10,
            output_tokens=5,
        )

        history.add_iteration(
            prompt="Modified prompt",
            result=result,
            notes="test",
        )

        assert len(history.iterations) == 1
        assert history.iterations[0].prompt == "Modified prompt"

    def test_iteration_history_save_load(self, tmp_path: Path) -> None:
        """Test saving and loading iteration history."""
        from tracecraft.playground.comparison import IterationHistory

        history = IterationHistory(
            step_id="abc123",
            step_name="gpt4_call",
            model="gpt-4o",
            original_prompt="You are helpful.",
            original_output="Hello!",
        )

        result = ReplayResult(output="New output", input_tokens=10, output_tokens=5)
        history.add_iteration("Modified", result, "test")

        # Save
        save_path = tmp_path / "history.json"
        history.save(save_path)
        assert save_path.exists()

        # Load
        loaded = IterationHistory.load(save_path)
        assert loaded.step_id == "abc123"
        assert loaded.step_name == "gpt4_call"
        assert len(loaded.iterations) == 1

    def test_generate_diff(self) -> None:
        """Test generate_diff function."""
        from tracecraft.playground.comparison import generate_diff

        diff = generate_diff("Hello world", "Hello there")
        assert "world" in diff or "there" in diff

    def test_calculate_similarity(self) -> None:
        """Test calculate_similarity function."""
        from tracecraft.playground.comparison import calculate_similarity

        # Identical strings
        assert calculate_similarity("hello", "hello") == 1.0

        # Completely different
        assert calculate_similarity("abc", "xyz") < 0.5

        # Partial match
        similarity = calculate_similarity("hello world", "hello there")
        assert 0.3 < similarity < 0.8


class TestCLIPlaygroundCommand:
    """Tests for the CLI playground command."""

    def test_playground_command_exists(self) -> None:
        """Test playground command is registered."""
        from tracecraft.cli.main import playground

        assert callable(playground)

    def test_playground_command_in_app(self) -> None:
        """Test playground command is in the app."""
        from tracecraft.cli.main import app

        command_callbacks = [
            cmd.callback.__name__ for cmd in app.registered_commands if cmd.callback
        ]
        assert "playground" in command_callbacks


class TestIterationHistoryFromStep:
    """Tests for creating IterationHistory from a Step."""

    def test_iteration_history_from_step(self) -> None:
        """Test creating IterationHistory from a Step."""
        from tracecraft.playground.comparison import IterationHistory

        step = Step(
            trace_id=uuid4(),
            type=StepType.LLM,
            name="gpt4_call",
            start_time=datetime.now(UTC),
            model_name="gpt-4o",
            inputs={
                "system_prompt": "You are helpful.",
                "messages": [{"role": "user", "content": "Hi"}],
            },
            outputs={"result": "Hello!"},
        )

        history = IterationHistory.from_step(step)

        assert history.step_id == str(step.id)
        assert history.step_name == "gpt4_call"
        assert history.model == "gpt-4o"
        assert history.original_prompt == "You are helpful."
        assert history.original_output == "Hello!"
        assert len(history.iterations) == 0

    def test_iteration_history_best_iteration(self) -> None:
        """Test finding the best iteration."""
        from tracecraft.playground.comparison import IterationHistory

        history = IterationHistory(
            step_id="abc",
            step_name="test",
            model="gpt-4o",
            original_prompt="prompt",
            original_output="output",
        )

        # Add iterations
        result1 = ReplayResult(output="output1", input_tokens=10, output_tokens=5)
        result2 = ReplayResult(output="output2", input_tokens=10, output_tokens=5)
        result3 = ReplayResult(output="output3", input_tokens=10, output_tokens=5)

        history.add_iteration("prompt1", result1, "first try")
        history.add_iteration("prompt2", result2, "second try - BEST")
        history.add_iteration("prompt3", result3, "third try")

        # Best should be the one marked "best"
        best = history.best_iteration
        assert best is not None
        assert best.prompt == "prompt2"
        assert "BEST" in best.notes


class TestPlaygroundScreenInit:
    """Tests for PlaygroundScreen initialization."""

    def test_playground_screen_creates_history(self) -> None:
        """Test that PlaygroundScreen creates an IterationHistory."""
        try:
            from tracecraft.tui.screens.playground import TEXTUAL_AVAILABLE, PlaygroundScreen

            if not TEXTUAL_AVAILABLE:
                pytest.skip("Textual not installed")

            step = Step(
                trace_id=uuid4(),
                type=StepType.LLM,
                name="test_step",
                start_time=datetime.now(UTC),
                model_name="gpt-4o",
                inputs={"system_prompt": "Be helpful"},
                outputs={"result": "Hello"},
            )

            screen = PlaygroundScreen(step=step, original_output="Hello")

            assert screen._history is not None
            assert screen._history.step_name == "test_step"
            assert screen._iteration_count == 0

        except ImportError:
            pytest.skip("Textual not installed")
