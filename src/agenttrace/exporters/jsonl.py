"""
JSONL file exporter.

Exports agent traces as JSON Lines format for easy storage and analysis.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from agenttrace.exporters.base import BaseExporter

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun


class JSONLExporter(BaseExporter):
    """
    Exports traces as JSON Lines format to a file.

    Each line contains a complete JSON representation of an AgentRun.
    Useful for log aggregation, analysis, and debugging.

    Can be used as a context manager to ensure proper cleanup:
        with JSONLExporter("traces.jsonl") as exporter:
            exporter.export(run)
    """

    def __init__(self, filepath: str | Path) -> None:
        """
        Initialize the JSONL exporter.

        Args:
            filepath: Path to the output file. Parent directories will be
                     created if they don't exist.
        """
        self.filepath = Path(filepath)
        self._file: TextIO | None = None
        self._lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Create parent directories if they don't exist."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def _get_file(self) -> TextIO:
        """Get or create the file handle (lazy initialization)."""
        if self._file is None:
            self._file = open(self.filepath, "a", encoding="utf-8")  # noqa: SIM115
        return self._file

    def export(self, run: AgentRun) -> None:
        """
        Export an agent run as a JSON line.

        Thread-safe - uses lock to protect file writes.

        Args:
            run: The AgentRun to export.
        """
        with self._lock:
            file = self._get_file()
            # Use Pydantic's JSON serialization for proper datetime handling
            json_str = run.model_dump_json()
            file.write(json_str + "\n")
            file.flush()

    def close(self) -> None:
        """Close the file handle."""
        with self._lock:
            if self._file is not None:
                try:
                    self._file.close()
                finally:
                    # Ensure _file is set to None even if close() raises
                    self._file = None

    def __enter__(self) -> JSONLExporter:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager and close file handle."""
        self.close()
