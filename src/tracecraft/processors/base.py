"""
Base processor protocol for trace processing.

Defines the interface that all processors must implement. Processors
are applied in a pipeline before export to modify, enrich, or filter traces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun


class BaseProcessor(ABC):
    """
    Base class for all trace processors.

    Processors are applied in a pipeline before traces are exported.
    They can modify traces (e.g., redaction, enrichment) or filter
    them out entirely (e.g., sampling).

    The pipeline order is typically:
    1. Enrichment (add token counts, costs)
    2. Redaction (remove PII)
    3. Sampling (decide whether to export)
    """

    @abstractmethod
    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Process an agent run.

        Args:
            run: The AgentRun to process.

        Returns:
            The processed AgentRun, or None to filter it out.
            Returning None will prevent the run from being exported.
        """
        pass

    @property
    def name(self) -> str:
        """Get the processor name (defaults to class name)."""
        return self.__class__.__name__


class RedactionProcessorAdapter(BaseProcessor):
    """
    Adapter to make RedactionProcessor conform to BaseProcessor protocol.

    Wraps the existing RedactionProcessor to work in the processor pipeline.
    """

    def __init__(self, redaction_processor: object) -> None:
        """
        Initialize the adapter.

        Args:
            redaction_processor: The RedactionProcessor instance to wrap.
        """
        self._processor = redaction_processor

    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Apply redaction to the run.

        Creates a deep copy of the run and applies redaction to all
        inputs and outputs in the run and its steps.

        Args:
            run: The AgentRun to process.

        Returns:
            The redacted AgentRun.
        """
        # Create a deep copy to avoid mutating the original
        redacted_run = deepcopy(run)

        # Redact inputs/outputs at run level
        if redacted_run.input is not None and isinstance(redacted_run.input, dict):
            redacted_run.input = self._processor.redact_dict(redacted_run.input)
        elif isinstance(redacted_run.input, str):
            redacted_run.input = self._processor.redact_text(redacted_run.input)

        if redacted_run.output is not None and isinstance(redacted_run.output, dict):
            redacted_run.output = self._processor.redact_dict(redacted_run.output)
        elif isinstance(redacted_run.output, str):
            redacted_run.output = self._processor.redact_text(redacted_run.output)

        # Recursively redact steps
        self._redact_steps(redacted_run.steps)

        return redacted_run

    def _redact_steps(self, steps: list) -> None:
        """Recursively redact step inputs and outputs."""
        for step in steps:
            # Redact inputs
            if step.inputs:
                step.inputs = self._processor.redact_dict(step.inputs)

            # Redact outputs
            if step.outputs:
                step.outputs = self._processor.redact_dict(step.outputs)

            # Recursively process children
            if step.children:
                self._redact_steps(step.children)


class SamplingProcessorAdapter(BaseProcessor):
    """
    Adapter to make SamplingProcessor conform to BaseProcessor protocol.

    Wraps the existing SamplingProcessor to work in the processor pipeline.
    """

    def __init__(self, sampling_processor: object) -> None:
        """
        Initialize the adapter.

        Args:
            sampling_processor: The SamplingProcessor instance to wrap.
        """
        self._processor = sampling_processor

    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Apply sampling decision to the run.

        Args:
            run: The AgentRun to process.

        Returns:
            The run if it should be kept, None if it should be dropped.
        """
        should_keep, reason = self._processor.should_sample(run)

        # Update the run with sampling decision
        run.should_export = should_keep
        run.sample_reason = reason

        if not should_keep:
            return None

        return run


class EnrichmentProcessorAdapter(BaseProcessor):
    """
    Adapter to make TokenEnrichmentProcessor conform to BaseProcessor protocol.

    Wraps the existing TokenEnrichmentProcessor to work in the processor pipeline.
    """

    def __init__(self, enrichment_processor: object) -> None:
        """
        Initialize the adapter.

        Args:
            enrichment_processor: The TokenEnrichmentProcessor instance to wrap.
        """
        self._processor = enrichment_processor

    def process(self, run: AgentRun) -> AgentRun | None:
        """
        Apply token enrichment to the run.

        Enriches all LLM steps with token counts and cost estimates.

        Args:
            run: The AgentRun to process.

        Returns:
            The enriched AgentRun.
        """
        # Recursively enrich steps
        self._enrich_steps(run.steps)

        return run

    def _enrich_steps(self, steps: list) -> None:
        """Recursively enrich step token counts and costs."""
        for step in steps:
            self._processor.enrich_step(step)

            # Recursively process children
            if step.children:
                self._enrich_steps(step.children)
