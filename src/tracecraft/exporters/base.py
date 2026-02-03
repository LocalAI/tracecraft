"""
Base exporter protocol.

Defines the interface that all exporters must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class BaseExporter(ABC):
    """
    Base class for all trace exporters.

    Exporters are responsible for outputting traces to various destinations
    (console, files, network endpoints, etc.).
    """

    @abstractmethod
    def export(self, run: AgentRun) -> None:
        """
        Export a completed agent run.

        Args:
            run: The AgentRun to export.
        """
        pass

    def close(self) -> None:  # noqa: B027
        """
        Clean up any resources held by the exporter.

        Override this method if your exporter needs to perform cleanup
        (e.g., closing file handles, flushing buffers).
        Not abstract because many exporters don't need cleanup.
        """
        pass

    def __enter__(self) -> BaseExporter:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit - ensures close is called."""
        self.close()
