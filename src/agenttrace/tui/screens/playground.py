"""
Playground screen for the TUI.

Provides an interactive interface for replaying and editing LLM calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Footer, Header, Label, Static, TextArea

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any
    ModalScreen = object

if TYPE_CHECKING:
    from agenttrace.core.models import Step
    from agenttrace.storage.sqlite import SQLiteTraceStore


class PlaygroundScreen(ModalScreen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Playground screen for replaying and editing LLM calls.

    Allows editing the system prompt and comparing outputs.
    Tracks iteration history for saving successful prompt iterations.
    """

    BINDINGS = (
        [
            Binding("escape", "cancel", "Back"),
            Binding("r", "run_replay", "Run"),
            Binding("s", "save", "Save"),
            Binding("c", "copy_output", "Copy"),
            Binding("n", "add_note", "Note"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = """
    PlaygroundScreen {
        align: center middle;
    }

    #playground-container {
        width: 90%;
        height: 90%;
        border: solid $primary;
        background: $surface;
    }

    #playground-header {
        height: 3;
        background: $primary;
        padding: 0 1;
    }

    #playground-header Label {
        text-style: bold;
    }

    #prompt-section {
        height: 40%;
        padding: 1;
        border-bottom: solid $primary-darken-2;
    }

    #prompt-section Label {
        text-style: bold;
        margin-bottom: 1;
    }

    #prompt-editor {
        height: 1fr;
    }

    #output-section {
        height: 1fr;
        padding: 1;
    }

    #output-panels {
        height: 1fr;
    }

    .output-panel {
        width: 1fr;
        border: solid $primary-darken-2;
        margin: 0 1;
        padding: 1;
    }

    .output-panel Label {
        text-style: bold;
        margin-bottom: 1;
    }

    .output-content {
        height: 1fr;
        overflow-y: auto;
    }

    #status-bar {
        height: 3;
        background: $surface;
        padding: 0 1;
        border-top: solid $primary-darken-2;
    }

    #status-bar Static {
        margin-right: 2;
    }

    #action-buttons {
        height: auto;
        align: center middle;
    }

    #action-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        step: Step,
        original_output: str = "",
        save_dir: str = ".agenttrace/iterations",
        *,
        store: SQLiteTraceStore | None = None,
        trace_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the playground screen.

        Args:
            step: The step to replay.
            original_output: The original output from the trace.
            save_dir: Directory to save iteration history files (fallback).
            store: Optional SQLite store for auto-persistence.
            trace_id: Optional trace ID (required if store is provided).
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install agenttrace[tui]")
        super().__init__(**kwargs)
        self._step = step
        self._original_output = original_output
        self._modified_output = ""
        self._is_running = False
        self._save_dir = save_dir
        self._last_prompt = ""
        self._last_result: Any = None  # ReplayResult from last run
        self._iteration_count = 0

        # SQLite persistence (optional)
        self._store = store
        self._trace_id = trace_id

        # Initialize iteration history
        from agenttrace.playground.comparison import IterationHistory

        # Load existing iterations from store if available
        if store and trace_id:
            self._history = IterationHistory.load_from_store(store, trace_id, step)
            self._iteration_count = len(self._history.iterations)
        else:
            self._history = IterationHistory.from_step(step)

    def compose(self) -> ComposeResult:
        """Compose the playground layout."""
        yield Container(
            Vertical(
                # Header
                Horizontal(
                    Label(f"Playground: {self._step.name}"),
                    id="playground-header",
                ),
                # Prompt editor section
                Vertical(
                    Label("System Prompt (editable):"),
                    TextArea(
                        self._extract_prompt(),
                        id="prompt-editor",
                    ),
                    id="prompt-section",
                ),
                # Output comparison section
                Vertical(
                    Horizontal(
                        # Original output
                        Vertical(
                            Label("Original Output"),
                            Static(
                                self._truncate_output(self._original_output),
                                id="original-output",
                                classes="output-content",
                            ),
                            classes="output-panel",
                        ),
                        # New output
                        Vertical(
                            Label("New Output"),
                            Static(
                                "(press [r] to run)",
                                id="new-output",
                                classes="output-content",
                            ),
                            classes="output-panel",
                        ),
                        id="output-panels",
                    ),
                    id="output-section",
                ),
                # Status bar
                Horizontal(
                    Static(f"Model: {self._step.model_name or 'unknown'}", id="model-info"),
                    Static("", id="replay-status"),
                    Horizontal(
                        Button("Run [r]", id="run-btn", variant="primary"),
                        Button("Save [s]", id="save-btn"),
                        Button("Best [n]", id="note-btn"),
                        Button("Copy [c]", id="copy-btn"),
                        Button("Back [esc]", id="back-btn"),
                        id="action-buttons",
                    ),
                    id="status-bar",
                ),
            ),
            id="playground-container",
        )

    def _extract_prompt(self) -> str:
        """Extract the system prompt from the step."""
        inputs = self._step.inputs or {}

        # Check for system prompt
        if "system_prompt" in inputs:
            return inputs["system_prompt"]
        if "system" in inputs:
            return inputs["system"]

        # Check messages for system
        if "messages" in inputs:
            for msg in inputs["messages"]:
                if msg.get("role") == "system":
                    return msg.get("content", "")

        # Fall back to prompt field
        if "prompt" in inputs:
            return inputs["prompt"]

        return "(No system prompt found)"

    def _truncate_output(self, text: str, max_lines: int = 50) -> str:
        """Truncate output for display."""
        lines = text.split("\n")
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        return text

    async def action_run_replay(self) -> None:
        """Run the replay with the modified prompt."""
        if self._is_running:
            return

        self._is_running = True
        status = self.query_one("#replay-status", Static)
        new_output = self.query_one("#new-output", Static)

        status.update("Running...")
        new_output.update("Running replay...")

        try:
            from agenttrace.playground.runner import get_provider_for_step

            # Get the modified prompt
            editor = self.query_one("#prompt-editor", TextArea)
            modified_prompt = editor.text

            # Find a provider
            provider = get_provider_for_step(self._step)
            if provider is None:
                new_output.update(
                    f"[red]Error: No provider for model {self._step.model_name}[/red]"
                )
                status.update("Error")
                self._is_running = False
                return

            # Run the replay
            result = await provider.replay(self._step, modified_prompt=modified_prompt)

            if result.error:
                new_output.update(f"[red]Error: {result.error}[/red]")
                status.update("Error")
            else:
                self._modified_output = result.output
                self._last_prompt = modified_prompt
                self._last_result = result
                self._iteration_count += 1

                # Persist to SQLite if store available (auto-save on each replay)
                if self._store and self._trace_id:
                    self._history.save_iteration_to_store(
                        store=self._store,
                        trace_id=self._trace_id,
                        prompt=modified_prompt,
                        result=result,
                        notes=f"Iteration {self._iteration_count}",
                    )
                else:
                    # Add to iteration history (in-memory only)
                    self._history.add_iteration(
                        prompt=modified_prompt,
                        result=result,
                        notes=f"Iteration {self._iteration_count}",
                    )

                new_output.update(self._truncate_output(result.output))
                persistence_note = " [auto-saved]" if self._store else ""
                status.update(
                    f"Done: {result.input_tokens}+{result.output_tokens} tokens, "
                    f"{result.duration_ms:.0f}ms | Iterations: {self._iteration_count}{persistence_note}"
                )

        except ImportError as e:
            new_output.update(f"[red]Error: {e}[/red]")
            status.update("Error")
        except Exception as e:
            new_output.update(f"[red]Error: {e}[/red]")
            status.update("Error")
        finally:
            self._is_running = False

    def action_save(self) -> None:
        """Save the iteration history to a file."""
        from pathlib import Path

        if not self._history.iterations:
            self.notify(
                "No iterations to save. Run a replay first.",
                title="Nothing to Save",
                severity="warning",
            )
            return

        try:
            # Create save directory
            save_dir = Path(self._save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from step name and timestamp
            from datetime import UTC, datetime

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() else "_" for c in self._step.name)
            filename = f"{safe_name}_{timestamp}.json"
            save_path = save_dir / filename

            # Save the history
            self._history.save(save_path)

            self.notify(
                f"Saved {len(self._history.iterations)} iteration(s) to:\n{save_path}",
                title="Saved",
                timeout=5,
            )
        except Exception as e:
            self.notify(
                f"Failed to save: {e}",
                title="Save Error",
                severity="error",
            )

    def action_add_note(self) -> None:
        """Add a note to the last iteration (mark as best)."""
        if not self._history.iterations:
            self.notify(
                "No iterations yet. Run a replay first.",
                title="No Iterations",
                severity="warning",
            )
            return

        # Mark the last iteration as "best"
        last = self._history.iterations[-1]
        if "best" in last.notes.lower():
            last.notes = last.notes.replace(" - BEST", "").replace("BEST", "")
            self.notify("Removed 'best' mark from last iteration", title="Note Updated")
        else:
            last.notes = f"{last.notes} - BEST"
            self.notify("Marked last iteration as BEST", title="Note Updated")

    def action_copy_output(self) -> None:
        """Copy the new output to clipboard."""
        if self._modified_output:
            # Try to copy to clipboard
            try:
                import pyperclip

                pyperclip.copy(self._modified_output)
                self.notify("Output copied to clipboard", title="Copied")
            except ImportError:
                self.notify(
                    "pyperclip not installed. Install with: pip install pyperclip",
                    title="Copy Failed",
                    severity="warning",
                )
        else:
            self.notify("No output to copy. Run replay first.", title="Copy")

    def action_cancel(self) -> None:
        """Close the playground screen."""
        self.dismiss()

    def on_button_pressed(self, event: Any) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "run-btn":
            self.run_worker(self.action_run_replay())
        elif button_id == "save-btn":
            self.action_save()
        elif button_id == "note-btn":
            self.action_add_note()
        elif button_id == "copy-btn":
            self.action_copy_output()
        elif button_id == "back-btn":
            self.action_cancel()
