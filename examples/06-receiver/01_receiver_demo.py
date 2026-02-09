#!/usr/bin/env python3
"""OTLP Receiver Demo - Receive traces from external applications.

This example demonstrates the OTLP receiver that allows TraceCraft to
receive traces from any OpenTelemetry-instrumented application.

Prerequisites:
    - TraceCraft with receiver extras: pip install 'tracecraft[receiver]'

Usage:
    # Terminal 1: Start the receiver
    python examples/06-receiver/01_receiver_demo.py

    # Terminal 2: Run the sender (after receiver is running)
    python examples/06-receiver/02_send_traces.py

    # Or use the TUI directly:
    tracecraft serve --tui

Expected Output:
    - Receiver starts on http://localhost:4318
    - Traces appear in the SQLite database
    - View with: tracecraft ui sqlite://traces/receiver_demo.db
"""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from tracecraft.receiver.server import OTLPReceiverServer
from tracecraft.storage.sqlite import SQLiteTraceStore


def main() -> None:
    """Run the receiver demo."""
    print("=" * 60)
    print("TraceCraft OTLP Receiver Demo")
    print("=" * 60)

    # Create storage directory
    storage_path = Path("traces/receiver_demo.db")
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize storage
    store = SQLiteTraceStore(storage_path)
    print(f"\nStorage: {storage_path}")

    # Create receiver server
    server = OTLPReceiverServer(
        store=store,
        host="127.0.0.1",
        port=4318,
    )

    # Handle Ctrl+C gracefully
    def signal_handler(sig: int, frame: object) -> None:
        print("\n\nShutting down receiver...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"\nReceiver URL: {server.url}")
    print("\nEndpoints:")
    print(f"  POST {server.url}/v1/traces  - Receive OTLP traces")
    print(f"  GET  {server.url}/health     - Health check")
    print("\nWaiting for traces... (Ctrl+C to stop)")
    print("-" * 60)

    # Run the server (blocking)
    server.run()


if __name__ == "__main__":
    main()
