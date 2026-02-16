#!/usr/bin/env python3
"""OTLP Receiver Demo - Receive traces from external applications.

This example demonstrates the OTLP receiver that allows TraceCraft to
receive traces from any OpenTelemetry-instrumented application.

It also demonstrates the Project and Session features:
- Creates a "Receiver Examples" project (reuses if exists)
- Creates a unique session for each script execution
- All incoming traces are automatically assigned to the project/session

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

import atexit
import logging
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

from tracecraft.receiver.server import OTLPReceiverServer
from tracecraft.storage.sqlite import SQLiteTraceStore

# Enable logging to see incoming traces
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


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

    # Show existing trace count
    initial_count = store.count()
    if initial_count > 0:
        print(f"Existing traces in database: {initial_count}")

    # Setup project (reuse if exists)
    project_name = "Receiver Examples"
    existing_project = store.get_project_by_name(project_name)
    if existing_project:
        project_id = existing_project["id"]
        print(f"Using existing project: {project_name}")
    else:
        project_id = store.create_project(
            name=project_name,
            description="Traces received from OTLP receiver examples",
        )
        print(f"Created project: {project_name}")

    # Create unique session for this execution
    session_name = f"demo-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    session_id = store.create_session(
        name=session_name,
        project_id=project_id,
        description="OTLP receiver demo run",
    )
    print(f"Created session: {session_name}")

    # Create receiver server with project/session context
    # All incoming traces will be automatically assigned to this project and session
    server = OTLPReceiverServer(
        store=store,
        host="127.0.0.1",
        port=4318,
        project_id=project_id,
        session_id=session_id,
    )

    # Track initial count for summary
    start_count = initial_count

    # Handle Ctrl+C gracefully - show summary and close properly
    def signal_handler(sig: int, frame: object) -> None:
        print("\n\nShutting down receiver...")
        # Show summary of traces received
        final_count = store.count()
        new_traces = final_count - start_count
        print(f"Traces received this session: {new_traces}")
        print(f"Total traces in database: {final_count}")
        # Close database connection to ensure writes are flushed
        store.close()
        print("Database closed.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Also ensure cleanup on normal exit
    def cleanup() -> None:
        store.close()

    atexit.register(cleanup)

    print(f"\nReceiver URL: {server.url}")
    print("\nEndpoints:")
    print(f"  POST {server.url}/v1/traces  - Receive OTLP traces")
    print(f"  GET  {server.url}/health     - Health check")
    print("\nAll traces will be assigned to:")
    print(f"  Project: {project_name}")
    print(f"  Session: {session_name}")
    print("\nWaiting for traces... (Ctrl+C to stop)")
    print("-" * 60)

    # Run the server (blocking)
    server.run()


if __name__ == "__main__":
    main()
