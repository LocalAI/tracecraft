"""
TraceCraft OTLP Receiver.

Receives traces from external OTLP sources and converts them to TraceCraft format.
"""

from __future__ import annotations

from tracecraft.receiver.importer import OTelImporter
from tracecraft.receiver.server import OTLPReceiverServer

__all__ = [
    "OTelImporter",
    "OTLPReceiverServer",
]
