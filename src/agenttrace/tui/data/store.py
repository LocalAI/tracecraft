"""
In-memory trace store for the TUI.

Loads and manages traces from JSONL files for display in the TUI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agenttrace.core.models import AgentRun

logger = logging.getLogger(__name__)


class TraceStore:
    """
    Manages trace data for the TUI.

    Loads traces from JSONL files and provides access methods
    for the UI components.
    """

    def __init__(self) -> None:
        """Initialize the trace store."""
        self._runs: list[AgentRun] = []
        self._source_path: Path | None = None
        self._last_position: int = 0
        self._last_modified: float = 0.0

    @property
    def runs(self) -> list[AgentRun]:
        """Get all loaded runs."""
        return self._runs

    @property
    def run_count(self) -> int:
        """Get the number of loaded runs."""
        return len(self._runs)

    def get_run(self, run_id: str) -> AgentRun | None:
        """Get a specific run by ID."""
        for run in self._runs:
            if str(run.id) == run_id:
                return run
        return None

    async def load_from_source(self, source: str) -> None:
        """
        Load traces from a source.

        Args:
            source: Path to JSONL file or directory containing JSONL files.
        """
        path = Path(source)

        if path.is_file():
            await self._load_from_file(path)
        elif path.is_dir():
            await self._load_from_directory(path)
        else:
            logger.warning("Source not found: %s", source)

    async def _load_from_file(self, path: Path) -> None:
        """Load traces from a single JSONL file."""
        self._source_path = path

        if not path.exists():
            logger.warning("File not found: %s", path)
            return

        try:
            self._last_modified = path.stat().st_mtime
            with path.open() as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            run = self._parse_run(data)
                            if run:
                                self._runs.append(run)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON line in %s", path)
                self._last_position = f.tell()
        except Exception:
            logger.exception("Failed to load traces from %s", path)

    async def _load_from_directory(self, path: Path) -> None:
        """Load traces from all JSONL files in a directory."""
        for jsonl_file in sorted(path.glob("*.jsonl")):
            await self._load_from_file(jsonl_file)

    def _parse_run(self, data: dict[str, Any]) -> AgentRun | None:
        """Parse a run from JSON data."""
        try:
            return AgentRun.model_validate(data)
        except Exception:
            logger.warning("Failed to parse run data")
            return None

    async def check_for_updates(self) -> bool:
        """
        Check for new traces in the source file.

        Returns:
            True if new traces were loaded.
        """
        if self._source_path is None or not self._source_path.exists():
            return False

        current_mtime = self._source_path.stat().st_mtime
        if current_mtime <= self._last_modified:
            return False

        # File was modified, read new content
        new_runs: list[AgentRun] = []
        try:
            with self._source_path.open() as f:
                f.seek(self._last_position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            run = self._parse_run(data)
                            if run:
                                new_runs.append(run)
                        except json.JSONDecodeError:
                            pass
                self._last_position = f.tell()
            self._last_modified = current_mtime
        except Exception:
            logger.exception("Failed to read updates from %s", self._source_path)
            return False

        if new_runs:
            self._runs.extend(new_runs)
            return True
        return False

    def filter_runs(
        self,
        name_filter: str | None = None,
        has_error: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AgentRun]:
        """
        Filter runs by various criteria.

        Args:
            name_filter: Filter by run name (substring match).
            has_error: Filter by error status.
            since: Filter runs after this time.
            until: Filter runs before this time.

        Returns:
            Filtered list of runs.
        """
        result = self._runs

        if name_filter:
            name_lower = name_filter.lower()
            result = [r for r in result if name_lower in r.name.lower()]

        if has_error is not None:
            if has_error:
                result = [r for r in result if r.error or r.error_count > 0]
            else:
                result = [r for r in result if not r.error and r.error_count == 0]

        if since:
            result = [r for r in result if r.start_time >= since]

        if until:
            result = [r for r in result if r.start_time <= until]

        return result

    def get_statistics(self) -> dict[str, Any]:
        """
        Get aggregate statistics for all runs.

        Returns:
            Dictionary with statistics.
        """
        if not self._runs:
            return {
                "total_runs": 0,
                "total_steps": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "error_count": 0,
                "avg_duration_ms": 0.0,
            }

        total_steps = sum(len(r.steps) for r in self._runs)
        total_tokens = sum(r.total_tokens for r in self._runs)
        total_cost = sum(r.total_cost_usd for r in self._runs)
        error_count = sum(1 for r in self._runs if r.error or r.error_count > 0)

        durations = [r.duration_ms for r in self._runs if r.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "total_runs": len(self._runs),
            "total_steps": total_steps,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "error_count": error_count,
            "avg_duration_ms": avg_duration,
        }

    def clear(self) -> None:
        """Clear all loaded traces."""
        self._runs.clear()
        self._last_position = 0
        self._last_modified = 0.0
