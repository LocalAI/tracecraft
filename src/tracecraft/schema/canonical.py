"""
Canonical internal schema definitions.

Provides the SchemaEngine that combines OTel GenAI and OpenInference mappers.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from tracecraft.schema.openinference import OpenInferenceMapper
from tracecraft.schema.otel_genai import OTelGenAIMapper

if TYPE_CHECKING:
    from tracecraft.core.models import Step


class SchemaDialect(Enum):
    """Schema dialect for attribute mapping."""

    OTEL_GENAI = "otel_genai"
    OPENINFERENCE = "openinference"
    BOTH = "both"


class SchemaEngine:
    """
    Engine for mapping Step attributes to standardized schemas.

    Supports OTel GenAI, OpenInference, or both dialects.

    Note: The default dialect is OTEL_GENAI as it aligns with the industry-standard
    OpenTelemetry semantic conventions. Use BOTH for maximum compatibility with
    legacy systems, or OPENINFERENCE for Arize Phoenix integration.
    """

    def __init__(self, dialect: SchemaDialect = SchemaDialect.OTEL_GENAI) -> None:
        """
        Initialize the schema engine.

        Args:
            dialect: Which schema dialect(s) to use. Defaults to OTEL_GENAI.
        """
        self.dialect = dialect
        self._otel_mapper = OTelGenAIMapper()
        self._openinference_mapper = OpenInferenceMapper()

    def map_step(self, step: Step) -> dict[str, Any]:
        """
        Map a Step to standardized attributes.

        Args:
            step: The Step to map.

        Returns:
            Dictionary of attributes according to the configured dialect(s).
        """
        attrs: dict[str, Any] = {}

        # Common attributes (always included)
        attrs["tracecraft.step.type"] = step.type.value
        attrs["tracecraft.step.name"] = step.name

        if step.error:
            attrs["error.message"] = step.error
        if step.error_type:
            attrs["error.type"] = step.error_type

        # Dialect-specific attributes
        if self.dialect in (SchemaDialect.OTEL_GENAI, SchemaDialect.BOTH):
            otel_attrs = self._otel_mapper.map_step(step)
            attrs.update(otel_attrs)

        if self.dialect in (SchemaDialect.OPENINFERENCE, SchemaDialect.BOTH):
            openinference_attrs = self._openinference_mapper.map_step(step)
            attrs.update(openinference_attrs)

        return attrs
