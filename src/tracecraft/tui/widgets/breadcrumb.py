"""
Breadcrumb navigation widget for TraceCraft TUI.

Shows the current navigation path and allows quick jumps back.
NOIR SIGNAL theme styling.
"""

from __future__ import annotations

from typing import Any

try:
    from textual.app import ComposeResult
    from textual.containers import Horizontal
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widgets import Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

    # Stub class for when Textual isn't installed
    class Static:  # type: ignore[no-redef]
        pass

    class Horizontal:  # type: ignore[no-redef]
        pass

    class Message:  # type: ignore[no-redef]
        pass

    def reactive(default: Any, **_kwargs: Any) -> Any:  # type: ignore[misc]
        return default

    ComposeResult = Any  # type: ignore[misc,assignment]


# Import theme constants
try:
    from tracecraft.tui.theme import (
        BORDER,
        INFO_BLUE,
        SURFACE,
        TEXT_MUTED,
        TEXT_PRIMARY,
    )
except ImportError:
    # Fallback if theme not available
    SURFACE = "#1a1a2e"
    TEXT_PRIMARY = "#e8e6e3"
    TEXT_MUTED = "#6b6b6b"
    INFO_BLUE = "#6cb2eb"
    BORDER = "#3d3d5c"


class BreadcrumbSegment(Static if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """A clickable breadcrumb segment."""

    class Clicked(Message):
        """Message sent when a segment is clicked."""

        def __init__(self, index: int, data: dict[str, Any]) -> None:
            """Initialize the message.

            Args:
                index: The segment index in the breadcrumb path.
                data: The segment data for navigation.
            """
            super().__init__()
            self.index = index
            self.data = data

    DEFAULT_CSS = f"""
    BreadcrumbSegment {{
        height: 1;
        width: auto;
        color: {TEXT_MUTED};
    }}

    BreadcrumbSegment:hover {{
        color: {INFO_BLUE};
        text-style: underline;
    }}

    BreadcrumbSegment.current {{
        color: {TEXT_PRIMARY};
        text-style: bold;
    }}

    BreadcrumbSegment.current:hover {{
        color: {TEXT_PRIMARY};
        text-style: bold;
    }}
    """

    def __init__(
        self, label: str, index: int, data: dict[str, Any], is_current: bool = False, **kwargs: Any
    ) -> None:
        """Initialize the segment.

        Args:
            label: Display label for this segment.
            index: Index in the breadcrumb path.
            data: Navigation data.
            is_current: Whether this is the current (last) segment.
        """
        if TEXTUAL_AVAILABLE:
            super().__init__(label, **kwargs)
        self._index = index
        self._data = data
        self._is_current = is_current

    def on_mount(self) -> None:
        """Apply current class if needed."""
        if self._is_current:
            self.add_class("current")

    def on_click(self) -> None:
        """Handle click - post message to parent."""
        if not self._is_current:
            self.post_message(self.Clicked(self._index, self._data))


class BreadcrumbSeparator(Static if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """Separator between breadcrumb segments."""

    DEFAULT_CSS = f"""
    BreadcrumbSeparator {{
        height: 1;
        width: 3;
        color: {TEXT_MUTED};
        text-align: center;
    }}
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize separator."""
        if TEXTUAL_AVAILABLE:
            super().__init__(" › ", **kwargs)


class Breadcrumb(Horizontal if TEXTUAL_AVAILABLE else object):  # type: ignore[misc]
    """
    Breadcrumb navigation widget showing the current path.

    Supports push/pop operations for navigating through hierarchy.
    Each segment stores label and associated data for navigation.
    Segments are clickable to navigate back.
    """

    class SegmentClicked(Message):
        """Message sent when a breadcrumb segment is clicked."""

        def __init__(self, index: int, data: dict[str, Any]) -> None:
            """Initialize the message.

            Args:
                index: The segment index that was clicked.
                data: The navigation data for that segment.
            """
            super().__init__()
            self.index = index
            self.data = data

    DEFAULT_CSS = f"""
    Breadcrumb {{
        height: 1;
        padding: 0 1;
        background: {SURFACE};
        border-bottom: solid {BORDER};
    }}
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize breadcrumb widget."""
        if TEXTUAL_AVAILABLE:
            super().__init__(**kwargs)
        self._path: list[dict[str, Any]] = []

    @property
    def path(self) -> list[dict[str, Any]]:
        """Get the current path."""
        return self._path

    @path.setter
    def path(self, value: list[dict[str, Any]]) -> None:
        """Set the path."""
        self._path = list(value) if value else []
        self._refresh_segments()

    def push(self, label: str, data: dict[str, Any]) -> None:
        """
        Add a segment to the breadcrumb path.

        Args:
            label: Display label for this segment.
            data: Navigation data (type, id, etc.).
        """
        self._path = self._path + [{"label": label, "data": data}]
        self._refresh_segments()

    def pop(self) -> dict[str, Any] | None:
        """
        Remove and return the last segment.

        Returns:
            The removed segment, or None if empty.
        """
        if self._path:
            last = self._path[-1]
            self._path = self._path[:-1]
            self._refresh_segments()
            return last
        return None

    def clear(self) -> None:
        """Clear the breadcrumb path."""
        self._path = []
        self._refresh_segments()

    def _refresh_segments(self) -> None:
        """Refresh the displayed segments."""
        if not TEXTUAL_AVAILABLE or not hasattr(self, "query"):
            return

        # Remove all existing children
        try:
            self.remove_children()
        except Exception:
            return

        # Add new segments
        for i, segment in enumerate(self._path):
            is_current = i == len(self._path) - 1
            seg_widget = BreadcrumbSegment(
                label=segment["label"],
                index=i,
                data=segment.get("data", {}),
                is_current=is_current,
            )
            self.mount(seg_widget)

            # Add separator after non-last segments
            if not is_current:
                self.mount(BreadcrumbSeparator())

    def on_breadcrumb_segment_clicked(self, event: BreadcrumbSegment.Clicked) -> None:
        """Handle segment click - navigate to that segment."""
        # Pop segments after the clicked one
        self.pop_to(event.index)
        # Post message for app to handle navigation
        self.post_message(self.SegmentClicked(event.index, event.data))

    def get_segment(self, index: int) -> dict[str, Any] | None:
        """
        Get a specific segment by index.

        Args:
            index: The segment index.

        Returns:
            The segment dict, or None if out of bounds.
        """
        if 0 <= index < len(self._path):
            return self._path[index]
        return None

    def pop_to(self, index: int) -> list[dict[str, Any]]:
        """
        Pop all segments after the given index.

        Args:
            index: The index to pop to (this segment will be kept).

        Returns:
            List of removed segments.
        """
        if index < 0 or index >= len(self._path):
            return []

        removed = self._path[index + 1 :]
        self._path = self._path[: index + 1]
        self._refresh_segments()
        return removed

    def __len__(self) -> int:
        """Return the number of segments in the path."""
        return len(self._path)
