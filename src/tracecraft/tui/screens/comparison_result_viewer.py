"""
Comparison result viewer screen.

Displays LLM comparison output with navigation, save, and delete options.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tracecraft.tui.theme import (
    ACCENT_AMBER,
    BACKGROUND,
    BORDER,
    DANGER_RED,
    INFO_BLUE,
    SUCCESS_GREEN,
    SURFACE,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

if TYPE_CHECKING:
    from tracecraft.comparison.models import ComparisonResult

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, ScrollableContainer, Vertical
    from textual.reactive import reactive
    from textual.screen import Screen
    from textual.widgets import Footer, Header, Label, Markdown, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    ComposeResult = Any  # type: ignore[misc,assignment]
    Screen = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

RESULTS_DIR = Path.home() / ".config" / "tracecraft" / "comparison_results"


class ComparisonResultViewer(Screen if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Screen for viewing trace comparison results.

    Supports multiple comparisons with navigation, save, copy, and delete.

    Keybindings:
        n/]: Next comparison
        p/[: Previous comparison
        s: Save current comparison
        y: Copy to clipboard
        d: Delete current comparison
        q/Escape: Close
    """

    BINDINGS = (
        [
            Binding("escape", "close", "Close"),
            Binding("q", "close", "Close"),
            Binding("n", "next", "Next"),
            Binding("bracketright", "next", "Next", show=False),
            Binding("p", "prev", "Prev"),
            Binding("bracketleft", "prev", "Prev", show=False),
            Binding("s", "save", "Save"),
            Binding("y", "copy", "Copy"),
            Binding("d", "delete", "Delete"),
        ]
        if TEXTUAL_AVAILABLE
        else []
    )

    CSS = f"""
    /* NOIR SIGNAL - Comparison Result Viewer */
    ComparisonResultViewer {{
        background: {BACKGROUND};
    }}

    #result-container {{
        height: 1fr;
        padding: 1;
    }}

    #nav-row {{
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: {SURFACE};
        border: solid {BORDER};
    }}

    #nav-indicator {{
        color: {INFO_BLUE};
        text-style: bold;
    }}

    #metadata-row {{
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: {SURFACE};
        border: solid {BORDER};
    }}

    .meta-item {{
        margin-right: 3;
        color: {TEXT_PRIMARY};
    }}

    #result-scroll {{
        height: 1fr;
        border: solid {BORDER};
        background: {SURFACE};
        padding: 1;
    }}

    #result-content {{
        color: {TEXT_PRIMARY};
    }}

    #status-indicator {{
        text-align: center;
        margin-top: 1;
        height: auto;
    }}
    """

    # Reactive index to trigger updates
    current_index: reactive[int] = reactive(0)

    def __init__(
        self,
        comparisons: list[ComparisonResult],
        on_delete: Callable[[ComparisonResult], None] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the result viewer.

        Args:
            comparisons: List of comparison results to display.
            on_delete: Callback when a comparison is deleted.
        """
        if not TEXTUAL_AVAILABLE:
            raise ImportError("textual required for TUI. Install with: pip install tracecraft[tui]")
        super().__init__(*args, **kwargs)
        self._comparisons = list(comparisons)  # Make a copy
        self._on_delete = on_delete
        self.current_index = 0

    @property
    def result(self) -> ComparisonResult | None:
        """Get the currently displayed comparison result."""
        if 0 <= self.current_index < len(self._comparisons):
            return self._comparisons[self.current_index]
        return None

    def compose(self) -> ComposeResult:
        """Compose the viewer layout."""
        yield Header()

        with Vertical(id="result-container"):
            # Navigation row (shows 1/3 etc)
            with Horizontal(id="nav-row"):
                yield Static("", id="nav-indicator")

            # Metadata row
            with Horizontal(id="metadata-row"):
                yield Static("", id="meta-prompt", classes="meta-item")
                yield Static("", id="meta-model", classes="meta-item")
                yield Static("", id="meta-tokens", classes="meta-item")
                yield Static("", id="meta-cost", classes="meta-item")

            # Result content
            with ScrollableContainer(id="result-scroll"):
                yield Markdown("", id="result-content")

            # Status indicator
            yield Label("", id="status-indicator")

        yield Footer()

    def on_mount(self) -> None:
        """Called when screen is mounted."""
        self._update_display()

    def watch_current_index(self, _old: int, _new: int) -> None:
        """React to index changes."""
        self._update_display()

    def _update_display(self) -> None:
        """Update all display elements for current comparison."""
        from tracecraft.comparison.prompts import PromptManager

        result = self.result
        if not result:
            return

        # Update navigation indicator
        nav = self.query_one("#nav-indicator", Static)
        total = len(self._comparisons)
        if total > 1:
            nav.update(
                f"[{INFO_BLUE}]Comparison {self.current_index + 1}/{total}[/] (n/p to navigate)"
            )
        else:
            nav.update(f"[{INFO_BLUE}]Comparison 1/1[/]")

        # Update metadata
        prompt_manager = PromptManager()
        prompt = prompt_manager.get_prompt(result.request.prompt_id)
        prompt_name = prompt.name if prompt else result.request.prompt_id

        self.query_one("#meta-prompt", Static).update(
            f"[{INFO_BLUE}]Prompt:[/] [{ACCENT_AMBER}]{prompt_name}[/]"
        )
        self.query_one("#meta-model", Static).update(
            f"[{INFO_BLUE}]Model:[/] [{ACCENT_AMBER}]{result.request.model}[/]"
        )
        self.query_one("#meta-tokens", Static).update(
            f"[{INFO_BLUE}]Tokens:[/] [{ACCENT_AMBER}]{result.tokens_used}[/]"
        )
        self.query_one("#meta-cost", Static).update(
            f"[{INFO_BLUE}]Cost:[/] [{ACCENT_AMBER}]${result.cost_usd:.4f}[/]"
        )

        # Update content
        content = self.query_one("#result-content", Markdown)
        content.update(result.output)

        # Clear status
        self.query_one("#status-indicator", Label).update("")

    def action_close(self) -> None:
        """Close the viewer and return to main screen."""
        self.app.pop_screen()

    def action_next(self) -> None:
        """Go to next comparison."""
        if self.current_index < len(self._comparisons) - 1:
            self.current_index += 1
        else:
            self.notify("At last comparison", severity="warning", timeout=1)

    def action_prev(self) -> None:
        """Go to previous comparison."""
        if self.current_index > 0:
            self.current_index -= 1
        else:
            self.notify("At first comparison", severity="warning", timeout=1)

    def action_save(self) -> None:
        """Save the current comparison result to disk."""
        result = self.result
        if not result:
            return

        try:
            self._save_result(result)
            result.saved = True
            status = self.query_one("#status-indicator", Label)
            status.update(f"[{SUCCESS_GREEN}]Comparison saved![/]")
            self.notify("Saved to ~/.config/tracecraft/comparison_results/")
        except Exception as e:
            logger.error(f"Failed to save comparison: {e}")
            self.notify(f"Failed to save: {e}", severity="error")

    def action_copy(self) -> None:
        """Copy the current result to clipboard."""
        result = self.result
        if not result:
            return

        try:
            import pyperclip

            pyperclip.copy(result.output)
            self.notify("Result copied to clipboard")
        except ImportError:
            self.notify("pyperclip not installed", severity="warning")
        except Exception as e:
            self.notify(f"Failed to copy: {e}", severity="error")

    def action_delete(self) -> None:
        """Delete the current comparison."""
        result = self.result
        if not result:
            return

        # Call the delete callback
        if self._on_delete:
            self._on_delete(result)

        # Remove from our list
        self._comparisons.remove(result)

        # Update display or close if no more comparisons
        if not self._comparisons:
            self.notify("All comparisons deleted", timeout=2)
            self.app.pop_screen()
        else:
            # Adjust index if needed
            if self.current_index >= len(self._comparisons):
                self.current_index = len(self._comparisons) - 1
            else:
                # Force update since index might be same
                self._update_display()

            status = self.query_one("#status-indicator", Label)
            status.update(f"[{DANGER_RED}]Comparison deleted[/]")
            self.notify("Comparison deleted", timeout=2)

    def _save_result(self, result: ComparisonResult) -> None:
        """Save a comparison result to a JSON file."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"comparison_{timestamp}_{result.id.hex[:8]}.json"
        filepath = RESULTS_DIR / filename

        # Build save data
        data = {
            "id": str(result.id),
            "created_at": result.created_at.isoformat(),
            "request": {
                "trace_a_id": str(result.request.trace_a_id),
                "trace_b_id": str(result.request.trace_b_id),
                "prompt_id": result.request.prompt_id,
                "model": result.request.model,
                "provider": result.request.provider,
            },
            "output": result.output,
            "tokens_used": result.tokens_used,
            "cost_usd": result.cost_usd,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved comparison to {filepath}")
