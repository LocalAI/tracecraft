"""
OTLP HTTP Receiver Server.

Receives OTLP traces over HTTP and saves them to TraceCraft storage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tracecraft.core.models import AgentRun
    from tracecraft.receiver.importer import OTelImporter
    from tracecraft.storage.base import BaseTraceStore

logger = logging.getLogger(__name__)


class OTLPReceiverServer:
    """
    HTTP server that receives OTLP traces and saves them to storage.

    Supports both OTLP protobuf and JSON formats. Auto-detects schema dialect
    (OTel GenAI vs OpenInference) based on span attributes.

    Example:
        ```python
        from tracecraft.storage.sqlite import SQLiteTraceStore
        from tracecraft.receiver import OTLPReceiverServer

        store = SQLiteTraceStore("traces.db")
        server = OTLPReceiverServer(store, host="0.0.0.0", port=4318)

        # Run the server (blocking)
        server.run()

        # Or run in background
        server.start_background()
        # ... do other things ...
        server.stop()
        ```
    """

    def __init__(
        self,
        store: BaseTraceStore,
        host: str = "0.0.0.0",  # nosec B104 - intentional for receiver server
        port: int = 4318,
    ) -> None:
        """
        Initialize the receiver server.

        Args:
            store: Storage backend to save traces to.
            host: Host to bind to.
            port: Port to listen on.
        """
        self.store = store
        self.host = host
        self.port = port
        self._server: Any = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()  # Thread safety for state

        # Lazy import to avoid dependency issues
        self._app: Any = None

        # Cached importer instance (avoid creating on every request)
        self._importer: OTelImporter | None = None

    def _create_app(self) -> Any:
        """Create the Starlette application."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse, Response
        from starlette.routing import Route

        async def receive_traces(request: Any) -> Response:
            """Handle POST /v1/traces endpoint."""
            try:
                content_type = request.headers.get("content-type", "")

                if "application/x-protobuf" in content_type:
                    # Parse protobuf format
                    body = await request.body()
                    agent_runs = self._parse_protobuf(body)
                else:
                    # Parse JSON format
                    body = await request.body()
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError as e:
                        return JSONResponse(
                            {"error": f"Invalid JSON: {e}"},
                            status_code=400,
                        )
                    agent_runs = self._parse_json(data)

                # Save to storage
                saved_count = 0
                failed_count = 0
                for run in agent_runs:
                    try:
                        self.store.save(run)
                        saved_count += 1
                        logger.debug("Saved trace %s with %d steps", run.id, len(run.steps))
                    except Exception as e:
                        failed_count += 1
                        logger.error("Failed to save trace %s: %s", run.id, e)

                logger.info("Received %d traces, saved %d", len(agent_runs), saved_count)

                # Build response - indicate partial failure if some saves failed
                response_data: dict[str, Any] = {
                    "traces_received": len(agent_runs),
                    "traces_saved": saved_count,
                }

                if failed_count > 0:
                    response_data["status"] = "partial"
                    response_data["traces_failed"] = failed_count
                    # Use 207 Multi-Status for partial success
                    return JSONResponse(response_data, status_code=207)

                response_data["status"] = "ok"
                return JSONResponse(response_data, status_code=200)

            except Exception as e:
                logger.exception("Error processing traces")
                return JSONResponse(
                    {"error": str(e)},
                    status_code=500,
                )

        async def health_check(_request: Any) -> Response:
            """Handle GET /health endpoint."""
            return JSONResponse({"status": "healthy"}, status_code=200)

        routes = [
            Route("/v1/traces", receive_traces, methods=["POST"]),
            Route("/health", health_check, methods=["GET"]),
        ]

        return Starlette(routes=routes)

    def _get_importer(self) -> OTelImporter:
        """Get or create the cached importer instance."""
        if self._importer is None:
            from tracecraft.receiver.importer import OTelImporter

            self._importer = OTelImporter()
        return self._importer

    def _parse_protobuf(self, body: bytes) -> list[AgentRun]:
        """Parse OTLP protobuf format."""
        try:
            from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
                ExportTraceServiceRequest,
            )
        except ImportError as e:
            raise ImportError(
                "opentelemetry-proto is required for protobuf parsing. "
                "Install with: pip install 'tracecraft[receiver]'"
            ) from e

        request = ExportTraceServiceRequest()
        request.ParseFromString(body)

        return self._get_importer().import_resource_spans(list(request.resource_spans))

    def _parse_json(self, data: dict[str, Any]) -> list[AgentRun]:
        """Parse OTLP JSON format."""
        return self._get_importer().import_from_json(data)

    def run(self) -> None:
        """
        Run the server (blocking).

        This will block until the server is stopped.
        """
        import uvicorn

        if self._app is None:
            self._app = self._create_app()

        logger.info("Starting OTLP receiver on %s:%d", self.host, self.port)

        uvicorn.run(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )

    def start_background(self, timeout: float = 5.0) -> None:
        """
        Start the server in a background thread.

        Args:
            timeout: Maximum time to wait for server startup in seconds.

        Raises:
            RuntimeError: If server is already running or fails to start.
        """
        import uvicorn

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Server is already running")

            if self._app is None:
                self._app = self._create_app()

            self._stop_event.clear()

            def run_server() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                with self._lock:
                    self._loop = loop

                config = uvicorn.Config(
                    self._app,
                    host=self.host,
                    port=self.port,
                    log_level="warning",
                )
                server = uvicorn.Server(config)
                with self._lock:
                    self._server = server

                try:
                    loop.run_until_complete(server.serve())
                finally:
                    loop.close()

            self._thread = threading.Thread(target=run_server, daemon=True)
            self._thread.start()

        # Wait for server to start (outside lock to avoid deadlock)
        import time

        start_wait = time.monotonic()
        while time.monotonic() - start_wait < timeout:
            with self._lock:
                if self._server is not None and self._server.started:
                    logger.info("OTLP receiver started on %s:%d", self.host, self.port)
                    return
            time.sleep(0.1)

        # Timeout reached - cleanup and raise
        self.stop()
        raise RuntimeError(f"Server failed to start within {timeout} seconds")

    def stop(self) -> None:
        """Stop the background server."""
        with self._lock:
            if self._server is not None:
                self._server.should_exit = True
            thread = self._thread

        # Join thread outside lock to avoid deadlock
        if thread is not None:
            thread.join(timeout=5.0)

        with self._lock:
            self._server = None
            self._thread = None
            self._loop = None

        logger.info("OTLP receiver stopped")

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        with self._lock:
            return (
                self._thread is not None
                and self._thread.is_alive()
                and self._server is not None
                and self._server.started
            )

    @property
    def url(self) -> str:
        """Get the server URL."""
        return f"http://{self.host}:{self.port}"
