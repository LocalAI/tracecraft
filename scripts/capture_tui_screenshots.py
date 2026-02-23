#!/usr/bin/env python3
"""
Capture TUI screenshots for documentation.

Usage:
    uv run python scripts/capture_tui_screenshots.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TRACES_DIR = Path(__file__).parent.parent / "traces"
OUTPUT_DIR = Path(__file__).parent.parent / "docs/assets/screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRACE_FILE = str(TRACES_DIR / "agenttrace.jsonl")
DB_FILE = str(TRACES_DIR / "receiver_demo.db")


async def capture_main_view() -> None:
    """Capture the main TUI view - trace list."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)
        path = str(OUTPUT_DIR / "tui-main-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_waterfall_view() -> None:
    """Capture the TUI with waterfall showing a multi-step agent trace."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        # Find trace with most steps (most interesting)
        best_trace = None
        best_count = 0
        for run in app._runs:
            count = len(run.steps)
            if count > best_count:
                best_count = count
                best_trace = run

        if best_trace:
            app._current_run = best_trace
            app._expand_waterfall(best_trace)
            app._update_detail_panels()
            await pilot.pause(0.5)

        path = str(OUTPUT_DIR / "tui-waterfall-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_input_view() -> None:
    """Capture the TUI showing input/prompt content."""
    from textual.pilot import Pilot

    from tracecraft.core.models import StepType
    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.io_viewer import IOViewer

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        if app._runs:
            trace = app._runs[0]
            app._current_run = trace
            app._show_waterfall_for_trace(trace)

            llm_step = None

            def find_llm(steps: list) -> None:
                nonlocal llm_step
                for step in steps:
                    if step.type == StepType.LLM and llm_step is None:
                        llm_step = step
                    if step.children:
                        find_llm(step.children)

            find_llm(trace.steps)

            if llm_step:
                app._current_step = llm_step
                app._update_detail_panels()
                io_viewer = app.query_one("#io-viewer", IOViewer)
                io_viewer.set_mode(IOViewer.MODE_INPUT)

            await pilot.pause(0.4)

        path = str(OUTPUT_DIR / "tui-input-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_output_view() -> None:
    """Capture the TUI showing output/completion content."""
    from textual.pilot import Pilot

    from tracecraft.core.models import StepType
    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.io_viewer import IOViewer

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        if app._runs:
            trace = app._runs[0]
            app._current_run = trace
            app._show_waterfall_for_trace(trace)

            llm_step = None

            def find_llm(steps: list) -> None:
                nonlocal llm_step
                for step in steps:
                    if step.type == StepType.LLM and llm_step is None:
                        llm_step = step
                    if step.children:
                        find_llm(step.children)

            find_llm(trace.steps)

            if llm_step:
                app._current_step = llm_step
                app._update_detail_panels()
                io_viewer = app.query_one("#io-viewer", IOViewer)
                io_viewer.set_mode(IOViewer.MODE_OUTPUT)

            await pilot.pause(0.4)

        path = str(OUTPUT_DIR / "tui-output-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_attributes_view() -> None:
    """Capture the TUI showing attributes/detail."""
    from textual.pilot import Pilot

    from tracecraft.core.models import StepType
    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.io_viewer import IOViewer

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        if app._runs:
            trace = app._runs[0]
            app._current_run = trace
            app._show_waterfall_for_trace(trace)

            llm_step = None

            def find_llm(steps: list) -> None:
                nonlocal llm_step
                for step in steps:
                    if step.type == StepType.LLM and llm_step is None:
                        llm_step = step
                    if step.children:
                        find_llm(step.children)

            find_llm(trace.steps)

            if llm_step:
                app._current_step = llm_step
                app._update_detail_panels()
                io_viewer = app.query_one("#io-viewer", IOViewer)
                io_viewer.set_mode(IOViewer.MODE_DETAIL)

            await pilot.pause(0.4)

        path = str(OUTPUT_DIR / "tui-attributes-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_filter_active() -> None:
    """Capture the TUI with filter bar active and text typed."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.filter_bar import FilterBar

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        # Focus filter and type something
        filter_bar = app.query_one("#filter-bar", FilterBar)
        filter_bar.focus_input()
        await pilot.pause(0.2)
        # Type a filter query
        await pilot.press("a", "g", "e", "n", "t")
        await pilot.pause(0.3)

        path = str(OUTPUT_DIR / "tui-filter-active.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_error_filter() -> None:
    """Capture the TUI with error filter active - shows only error traces."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp
    from tracecraft.tui.widgets.filter_bar import FilterBar

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        # Toggle the errors-only filter
        filter_bar = app.query_one("#filter-bar", FilterBar)
        # Simulate toggling the errors filter by calling the event directly
        from tracecraft.storage.base import TraceQuery
        from tracecraft.tui.widgets.trace_table import TraceTable

        # Filter to show only error traces
        query = TraceQuery(has_error=True)
        if app._loader:
            filtered = app._loader.query_traces(query)
            table = app.query_one("#trace-table", TraceTable)
            table.show_traces(filtered, is_filtered=True)
            filter_bar.update_result_count(len(filtered), app._loader.count())
            await pilot.pause(0.3)

        path = str(OUTPUT_DIR / "tui-errors-only.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_db_main_view() -> None:
    """Capture the main TUI view from SQLite database - shows project/session columns."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    db_path = Path(DB_FILE)
    if not db_path.exists():
        print(f"  SKIP: {DB_FILE} not found")
        return

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)
        path = str(OUTPUT_DIR / "tui-db-main-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=f"sqlite://{DB_FILE}")
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_db_detail_view() -> None:
    """Capture SQLite DB view with a trace selected - shows rich metadata."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    db_path = Path(DB_FILE)
    if not db_path.exists():
        print(f"  SKIP: {DB_FILE} not found")
        return

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        if app._runs:
            trace = app._runs[0]
            app._current_run = trace
            app._show_waterfall_for_trace(trace)
            app._update_detail_panels()
            await pilot.pause(0.4)

        path = str(OUTPUT_DIR / "tui-db-detail-view.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=f"sqlite://{DB_FILE}")
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_notes_editor() -> None:
    """Capture the notes editor modal."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    db_path = Path(DB_FILE)
    if not db_path.exists():
        print(f"  SKIP notes editor: {DB_FILE} not found (notes require SQLite)")
        return

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)

        if app._runs:
            trace = app._runs[0]
            app._current_run = trace
            app._show_waterfall_for_trace(trace)
            await pilot.pause(0.3)
            # Open notes editor
            app.action_edit_notes()
            await pilot.pause(0.4)

        path = str(OUTPUT_DIR / "tui-notes-editor.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=f"sqlite://{DB_FILE}")
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def capture_help_screen() -> None:
    """Capture the help screen."""
    from textual.pilot import Pilot

    from tracecraft.tui.app import TraceCraftApp

    async def auto_pilot(pilot: Pilot) -> None:
        app = pilot.app
        await pilot.pause(0.8)
        # Open help screen
        app.action_help()
        await pilot.pause(0.3)

        path = str(OUTPUT_DIR / "tui-help-screen.svg")
        app.save_screenshot(path)
        print(f"  Saved: {path}")
        app.exit()

    app = TraceCraftApp(trace_source=TRACE_FILE)
    await app.run_async(headless=True, size=(200, 50), auto_pilot=auto_pilot)


async def main() -> None:
    """Capture all TUI screenshots."""
    print(f"Capturing TUI screenshots from: {TRACE_FILE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    captures = [
        ("Main view (trace list)", capture_main_view),
        ("Waterfall view", capture_waterfall_view),
        ("Input/Prompt view", capture_input_view),
        ("Output/Completion view", capture_output_view),
        ("Attributes view", capture_attributes_view),
        ("Filter bar active", capture_filter_active),
        ("Errors-only filter", capture_error_filter),
        ("DB main view", capture_db_main_view),
        ("DB detail view", capture_db_detail_view),
        ("Notes editor", capture_notes_editor),
        ("Help screen", capture_help_screen),
    ]

    for name, fn in captures:
        print(f"Capturing: {name}...")
        try:
            await fn()
        except Exception as e:
            import traceback

            print(f"  ERROR: {e}")
            traceback.print_exc()
        print()

    # List captured files
    screenshots = list(OUTPUT_DIR.glob("*.svg"))
    print(f"\nCaptured {len(screenshots)} screenshots:")
    for s in sorted(screenshots):
        size = s.stat().st_size
        print(f"  {s.name} ({size:,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
