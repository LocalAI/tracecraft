"""
Playground screen for the TUI.

Provides an interactive interface for replaying and editing LLM calls.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

import difflib
from typing import TYPE_CHECKING, Any

from rich.text import Text

# Import theme constants
from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    SURFACE_HIGHLIGHT,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

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
    from tracecraft.core.models import Step
    from tracecraft.storage.sqlite import SQLiteTraceStore


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
            Binding("d", "toggle_diff", "Diff"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Playground */
    PlaygroundScreen {{
        align: center middle;
        background: rgba(11, 14, 17, 0.8);
    }}

    #playground-container {{
        width: 90%;
        height: 90%;
        min-width: 80;
        max-width: 150;
        border: solid {ACCENT_AMBER};
        background: {SURFACE};
    }}

    #playground-header {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        border-bottom: solid {BORDER};
    }}

    #playground-header Label {{
        text-style: bold;
        color: {ACCENT_AMBER};
    }}

    #prompt-section {{
        height: 40%;
        padding: 1;
        border-bottom: solid {BORDER};
    }}

    #prompt-section Label {{
        text-style: bold;
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    #prompt-editor {{
        height: 1fr;
        background: {BACKGROUND};
        border: solid {BORDER};
    }}

    #prompt-editor:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #output-section {{
        height: 1fr;
        padding: 1;
    }}

    #output-panels {{
        height: 1fr;
    }}

    .output-panel {{
        width: 1fr;
        border: solid {BORDER};
        margin: 0 1;
        padding: 1;
        background: {BACKGROUND};
    }}

    .output-panel Label {{
        text-style: bold;
        margin-bottom: 1;
        color: {TEXT_MUTED};
    }}

    .output-content {{
        height: 1fr;
        overflow-y: auto;
        color: {TEXT_PRIMARY};
    }}

    #status-bar {{
        height: 3;
        background: {SURFACE_HIGHLIGHT};
        padding: 0 1;
        border-top: solid {BORDER};
    }}

    #status-bar Static {{
        margin-right: 2;
        color: {TEXT_MUTED};
    }}

    #model-info {{
        color: {INFO_BLUE};
    }}

    #replay-status {{
        color: {ACCENT_AMBER};
    }}

    #action-buttons {{
        height: auto;
        align: center middle;
    }}

    #action-buttons Button {{
        margin: 0 1;
        background: {SURFACE_HIGHLIGHT};
        border: solid {BORDER};
    }}

    #action-buttons Button:hover {{
        background: {SURFACE_HIGHLIGHT};
        border: solid {ACCENT_AMBER};
        color: {ACCENT_AMBER};
    }}

    #action-buttons Button:focus {{
        border: solid {ACCENT_AMBER};
    }}

    #run-btn {{
        background: {ACCENT_AMBER};
        color: {BACKGROUND};
    }}

    #run-btn:hover {{
        background: #D4A836;
    }}
    """

    def __init__(
        self,
        step: Step,
        original_output: str = "",
        save_dir: str = ".tracecraft/iterations",
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
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(**kwargs)
        self._step = step
        self._original_output = original_output
        self._modified_output = ""
        self._is_running = False
        self._save_dir = save_dir
        self._last_prompt = ""
        self._last_result: Any = None  # ReplayResult from last run
        self._iteration_count = 0
        self._diff_mode = False  # Toggle for diff view

        # SQLite persistence (optional)
        self._store = store
        self._trace_id = trace_id

        # Initialize iteration history
        from tracecraft.playground.comparison import IterationHistory

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
                    Label("SYSTEM PROMPT"),
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
                            Label("ORIGINAL"),
                            Static(
                                self._truncate_output(self._original_output),
                                id="original-output",
                                classes="output-content",
                            ),
                            classes="output-panel",
                        ),
                        # New output
                        Vertical(
                            Label("REPLAY"),
                            Static(
                                "Press [r] to run.",
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
                    Static(f"MODEL: {self._step.model_name or 'unknown'}", id="model-info"),
                    Static("", id="replay-status"),
                    Horizontal(
                        Button("RUN [R]", id="run-btn", variant="primary"),
                        Button("DIFF [D]", id="diff-btn"),
                        Button("SAVE [S]", id="save-btn"),
                        Button("BEST [N]", id="note-btn"),
                        Button("COPY [C]", id="copy-btn"),
                        Button("BACK [ESC]", id="back-btn"),
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

        status.update("RUNNING")
        new_output.update("Executing replay.")

        try:
            from tracecraft.playground.runner import get_provider_for_step

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
                new_output.update(f"[#C44536]Error: {result.error}[/]")
                status.update("ERROR")
            else:
                self._modified_output = result.output
                self._last_prompt = modified_prompt
                self._last_result = result
                self._iteration_count += 1
                self._diff_mode = False  # Reset diff mode on new replay

                # Reset diff button label
                try:
                    diff_btn = self.query_one("#diff-btn", Button)
                    diff_btn.label = "DIFF [D]"
                except Exception:  # noqa: BLE001
                    pass  # nosec B110

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
                persistence_note = " [saved]" if self._store else ""
                status.update(
                    f"DONE: {result.input_tokens}+{result.output_tokens}t, "
                    f"{result.duration_ms:.0f}ms | #{self._iteration_count}{persistence_note}"
                )

        except ImportError as e:
            new_output.update(f"[#C44536]Error: {e}[/]")
            status.update("ERROR")
        except Exception as e:
            new_output.update(f"[#C44536]Error: {e}[/]")
            status.update("ERROR")
        finally:
            self._is_running = False

    def action_save(self) -> None:
        """Save the iteration history to a file."""
        from pathlib import Path

        if not self._history.iterations:
            self.notify(
                "No iterations to save. Run replay first.",
                title="EMPTY",
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
                f"Saved {len(self._history.iterations)} iteration(s) to {save_path}",
                title="SAVED",
                timeout=5,
            )
        except Exception as e:
            self.notify(
                f"Save failed: {e}",
                title="ERROR",
                severity="error",
            )

    def action_add_note(self) -> None:
        """Add a note to the last iteration (mark as best)."""
        if not self._history.iterations:
            self.notify(
                "No iterations. Run replay first.",
                title="EMPTY",
                severity="warning",
            )
            return

        # Mark the last iteration as "best"
        last = self._history.iterations[-1]
        if "best" in last.notes.lower():
            last.notes = last.notes.replace(" - BEST", "").replace("BEST", "")
            self.notify("Removed best mark.", title="UPDATED")
        else:
            last.notes = f"{last.notes} - BEST"
            self.notify("Marked as best.", title="UPDATED")

    def action_copy_output(self) -> None:
        """Copy the new output to clipboard."""
        if self._modified_output:
            # Try to copy to clipboard
            try:
                import pyperclip

                pyperclip.copy(self._modified_output)
                self.notify("Output copied to clipboard.", title="COPIED")
            except ImportError:
                self.notify(
                    "pyperclip not installed.",
                    title="MISSING",
                    severity="warning",
                )
        else:
            self.notify("No output. Run replay first.", title="EMPTY")

    def action_cancel(self) -> None:
        """Close the playground screen."""
        self.dismiss()

    def action_toggle_diff(self) -> None:
        """Toggle diff view mode."""
        if not self._modified_output:
            self.notify("No replay output. Run replay first.", title="EMPTY")
            return

        self._diff_mode = not self._diff_mode
        new_output = self.query_one("#new-output", Static)
        diff_btn = self.query_one("#diff-btn", Button)

        if self._diff_mode:
            # Show diff view
            diff_content = self._render_diff()
            new_output.update(diff_content)
            diff_btn.label = "TEXT [D]"
            self.notify("Diff view enabled.", title="DIFF")
        else:
            # Show normal output
            new_output.update(self._truncate_output(self._modified_output))
            diff_btn.label = "DIFF [D]"
            self.notify("Normal view restored.", title="TEXT")

    def _render_diff(self) -> Text:
        """
        Render a diff between original and replay outputs.

        Returns:
            Rich Text object with colored diff highlighting.
        """
        original_lines = self._original_output.splitlines(keepends=True)
        modified_lines = self._modified_output.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile="original",
            tofile="replay",
            lineterm="",
        )

        result = Text()
        for line in diff:
            line_stripped = line.rstrip("\n")
            if line.startswith("+++") or line.startswith("---"):
                # File headers - muted
                result.append(line_stripped + "\n", style=TEXT_MUTED)
            elif line.startswith("@@"):
                # Hunk headers - amber accent
                result.append(line_stripped + "\n", style=ACCENT_AMBER)
            elif line.startswith("+"):
                # Additions - green
                result.append(line_stripped + "\n", style=SUCCESS_GREEN)
            elif line.startswith("-"):
                # Deletions - red
                result.append(line_stripped + "\n", style=DANGER_RED)
            else:
                # Context lines - normal
                result.append(line_stripped + "\n", style=TEXT_PRIMARY)

        if not result.plain:
            result.append("No differences found.", style=TEXT_MUTED)

        return result

    def on_button_pressed(self, event: Any) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "run-btn":
            self.run_worker(self.action_run_replay())
        elif button_id == "diff-btn":
            self.action_toggle_diff()
        elif button_id == "save-btn":
            self.action_save()
        elif button_id == "note-btn":
            self.action_add_note()
        elif button_id == "copy-btn":
            self.action_copy_output()
        elif button_id == "back-btn":
            self.action_cancel()
