"""
TALRuntime for managing trace state.

The runtime manages exporters, run lifecycle, processors, storage, and global state.
"""

from __future__ import annotations

import atexit
import logging
import threading
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from agenttrace.core.context import set_current_run
from agenttrace.core.models import AgentRun

if TYPE_CHECKING:
    from agenttrace.core.config import AgentTraceConfig
    from agenttrace.core.env_config import StorageConfig
    from agenttrace.exporters.base import BaseExporter
    from agenttrace.processors.base import BaseProcessor
    from agenttrace.storage.base import BaseTraceStore

logger = logging.getLogger(__name__)

# Global singleton with thread lock
_runtime: TALRuntime | None = None
_runtime_lock = threading.Lock()

# Default path constant
DEFAULT_JSONL_PATH = Path("traces/agenttrace.jsonl")


class TALRuntime:
    """
    The main runtime for managing AgentTrace.

    Manages exporters, coordinates run lifecycle, processors, storage, and provides
    the main API for tracing.
    """

    def __init__(
        self,
        console: bool = True,
        jsonl: bool = True,
        jsonl_path: str | Path | None = None,
        console_file: TextIO | None = None,
        console_verbose: bool = False,
        exporters: list[BaseExporter] | None = None,
        config: AgentTraceConfig | None = None,
        storage: BaseTraceStore | None = None,
    ) -> None:
        """
        Initialize the TALRuntime.

        Args:
            console: Enable console exporter (default: True).
            jsonl: Enable JSONL exporter (default: True).
            jsonl_path: Custom path for JSONL file.
            console_file: Custom file for console output.
            console_verbose: Enable verbose console output.
            exporters: Additional custom exporters.
            config: Configuration object for processors and settings.
            storage: Optional storage backend for persisting traces.
        """
        self._exporters: dict[str, BaseExporter] = {}
        self._custom_exporters: list[BaseExporter] = exporters or []
        self._processors: list[BaseProcessor] = []
        self._storage: BaseTraceStore | None = storage
        self._export_lock = threading.Lock()
        self._config = config

        # Setup processors from config
        if config is not None:
            self._setup_processors(config)

        # Setup default exporters
        if console:
            from agenttrace.exporters.console import ConsoleExporter

            self._exporters["console"] = ConsoleExporter(
                file=console_file,
                verbose=console_verbose,
            )

        if jsonl:
            from agenttrace.exporters.jsonl import JSONLExporter

            path = jsonl_path or DEFAULT_JSONL_PATH
            self._exporters["jsonl"] = JSONLExporter(path)

    def _setup_processors(self, config: AgentTraceConfig) -> None:
        """
        Initialize processor pipeline from configuration.

        Processor order depends on config.processor_order:
        - SAFETY: Enrichment → Redaction → Sampling (default)
        - EFFICIENCY: Sampling → Redaction → Enrichment

        Args:
            config: The AgentTraceConfig to use.
        """
        from agenttrace.core.config import ProcessorOrder
        from agenttrace.processors.base import (
            EnrichmentProcessorAdapter,
            RedactionProcessorAdapter,
            SamplingProcessorAdapter,
        )
        from agenttrace.processors.enrichment import TokenEnrichmentProcessor
        from agenttrace.processors.redaction import RedactionProcessor
        from agenttrace.processors.sampling import SamplingProcessor

        # Create processors
        enrichment = EnrichmentProcessorAdapter(TokenEnrichmentProcessor())

        redaction = None
        if config.redaction.enabled:
            redaction = RedactionProcessorAdapter(
                RedactionProcessor(
                    mode=config.redaction.mode,
                    allowlist=config.redaction.allowlist,
                    allowlist_patterns=config.redaction.allowlist_patterns,
                )
            )

        sampling = None
        if (
            config.sampling.rate < 1.0
            or config.sampling.always_keep_errors
            or config.sampling.always_keep_slow
        ):
            sampling = SamplingProcessorAdapter(
                SamplingProcessor(
                    default_rate=config.sampling.rate,
                    always_keep_errors=config.sampling.always_keep_errors,
                    always_keep_slow=config.sampling.always_keep_slow,
                    slow_threshold_ms=config.sampling.slow_threshold_ms,
                )
            )

        # Apply processor order
        if config.processor_order == ProcessorOrder.EFFICIENCY:
            # EFFICIENCY: Sample → Redact → Enrich
            # Samples first to reduce processing overhead
            if sampling:
                self._processors.append(sampling)
            if redaction:
                self._processors.append(redaction)
            self._processors.append(enrichment)
        else:
            # SAFETY (default): Enrich → Redact → Sample
            # Ensures redaction happens before any data leaves
            self._processors.append(enrichment)
            if redaction:
                self._processors.append(redaction)
            if sampling:
                self._processors.append(sampling)

    def has_exporter(self, name: str) -> bool:
        """Check if an exporter is registered."""
        return name in self._exporters

    @property
    def storage(self) -> BaseTraceStore | None:
        """Get the storage backend."""
        return self._storage

    def export(self, run: AgentRun) -> None:
        """
        Export a run through all registered exporters and save to storage.

        Before exporting, applies the processor pipeline (enrichment,
        redaction, sampling) to the run. If a processor filters out
        the run (e.g., sampling), the run is not exported.

        Exceptions from individual exporters are caught and logged,
        ensuring all exporters have a chance to run.

        Args:
            run: The AgentRun to export.
        """
        # Skip if run shouldn't be exported
        if not run.should_export:
            return

        # Apply processor pipeline
        processed_run: AgentRun | None = run
        for processor in self._processors:
            try:
                processed_run = processor.process(processed_run)
                if processed_run is None:
                    # Processor filtered out the run (e.g., sampling)
                    logger.debug(
                        "Run '%s' filtered out by processor '%s'",
                        run.name,
                        processor.name,
                    )
                    return
            except Exception:
                logger.exception(
                    "Processor '%s' failed on run '%s'",
                    processor.name,
                    run.name,
                )
                # Continue with unprocessed run if processor fails
                processed_run = run

        with self._export_lock:
            # Save to storage if configured
            if self._storage is not None:
                try:
                    self._storage.save(processed_run)
                except Exception:
                    logger.exception("Storage failed to save run '%s'", run.name)

            # Export through built-in exporters
            for name, exporter in self._exporters.items():
                try:
                    exporter.export(processed_run)
                except Exception:
                    logger.exception("Exporter '%s' failed to export run '%s'", name, run.name)

            # Export through custom exporters
            for i, exporter in enumerate(self._custom_exporters):
                try:
                    exporter.export(processed_run)
                except Exception:
                    logger.exception(
                        "Custom exporter %d (%s) failed to export run '%s'",
                        i,
                        type(exporter).__name__,
                        run.name,
                    )

    def start_run(
        self,
        name: str,
        description: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        input: Any = None,
    ) -> AgentRun:
        """
        Start a new agent run.

        Args:
            name: Name of the agent/run.
            description: Optional description.
            session_id: Optional session identifier.
            user_id: Optional user identifier.
            tags: Optional list of tags.
            input: Input to the agent.

        Returns:
            The created AgentRun.
        """
        run = AgentRun(
            name=name,
            description=description,
            start_time=datetime.now(UTC),
            session_id=session_id,
            user_id=user_id,
            tags=tags or [],
            input=input,
        )
        set_current_run(run)
        return run

    def end_run(
        self,
        run: AgentRun,
        output: Any = None,
        error: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """
        End and export an agent run.

        Args:
            run: The run to end.
            output: Output from the agent.
            error: Error message if run failed.
            error_type: Error type name if run failed.
        """
        run.end_time = datetime.now(UTC)
        run.duration_ms = (run.end_time - run.start_time).total_seconds() * 1000
        run.output = output

        # Set error info if provided
        if error:
            run.error = error
            run.error_type = error_type

        # Aggregate metrics
        self._aggregate_metrics(run)

        # Export
        self.export(run)

        # Clear context
        set_current_run(None)

    def _aggregate_metrics(self, run: AgentRun) -> None:
        """
        Aggregate metrics from all steps in a run.

        Uses iterative traversal to avoid stack overflow on deeply nested traces.
        """
        total_tokens = 0
        total_cost = 0.0
        error_count = 0

        # Use iterative traversal with explicit stack
        stack = list(run.steps)
        while stack:
            step = stack.pop()
            if step.input_tokens:
                total_tokens += step.input_tokens
            if step.output_tokens:
                total_tokens += step.output_tokens
            if step.cost_usd:
                total_cost += step.cost_usd
            if step.error:
                error_count += 1
            # Add children to stack for processing
            stack.extend(step.children)

        run.total_tokens = total_tokens
        run.total_cost_usd = total_cost
        run.error_count = error_count

    @contextmanager
    def run(
        self,
        name: str,
        description: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        input: Any = None,
    ) -> Generator[AgentRun, None, None]:
        """
        Context manager for managing a run's lifecycle.

        Args:
            name: Name of the agent/run.
            description: Optional description.
            session_id: Optional session identifier.
            user_id: Optional user identifier.
            tags: Optional list of tags.
            input: Input to the agent.

        Yields:
            The created AgentRun.

        Example:
            with runtime.run("my_agent") as run:
                # Do work
                pass
        """
        run = self.start_run(
            name=name,
            description=description,
            session_id=session_id,
            user_id=user_id,
            tags=tags,
            input=input,
        )
        try:
            yield run
            self.end_run(run)
        except BaseException as e:
            # Capture all exceptions including GeneratorExit, KeyboardInterrupt
            self.end_run(run, error=str(e), error_type=type(e).__name__)
            raise

    @contextmanager
    def trace_context(self) -> Generator[TALRuntime, None, None]:
        """
        Context manager for scoping this runtime to the current context.

        When used, decorators will use this runtime instead of the global one.
        This is useful for multi-tenant scenarios or isolated testing.

        Yields:
            This runtime instance.

        Example:
            runtime_a = TALRuntime(config=config_a)
            runtime_b = TALRuntime(config=config_b)

            with runtime_a.trace_context():
                # All @trace_agent decorators use runtime_a
                my_agent()

            with runtime_b.trace_context():
                # All @trace_agent decorators use runtime_b
                my_agent()
        """
        from agenttrace.core.context import (
            reset_current_runtime,
            set_current_runtime,
        )

        token = set_current_runtime(self)
        try:
            yield self
        finally:
            reset_current_runtime(token)

    @asynccontextmanager
    async def run_async(
        self,
        name: str,
        description: str | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        input: Any = None,
    ) -> AsyncGenerator[AgentRun, None]:
        """
        Async context manager for managing a run's lifecycle.

        Identical to run() but for async code paths. Properly handles
        async exception handling and context cleanup.

        Args:
            name: Name of the agent/run.
            description: Optional description.
            session_id: Optional session identifier.
            user_id: Optional user identifier.
            tags: Optional list of tags.
            input: Input to the agent.

        Yields:
            The created AgentRun.

        Example:
            async with runtime.run_async("my_agent") as run:
                result = await process_async()
        """
        run = self.start_run(
            name=name,
            description=description,
            session_id=session_id,
            user_id=user_id,
            tags=tags,
            input=input,
        )
        try:
            yield run
            self.end_run(run)
        except BaseException as e:
            # Capture all exceptions including GeneratorExit, KeyboardInterrupt
            self.end_run(run, error=str(e), error_type=type(e).__name__)
            raise

    def shutdown(self) -> None:
        """
        Shutdown the runtime and close all exporters and storage.

        Ensures all exporters and storage are closed even if some fail.
        Thread-safe: protects both exporter closing and global state.
        """
        global _runtime

        # Use export_lock to prevent concurrent export during shutdown
        with self._export_lock:
            # Close storage
            if self._storage is not None:
                try:
                    self._storage.close()
                except Exception:
                    logger.exception("Failed to close storage")
                self._storage = None

            # Close built-in exporters
            for name, exporter in list(self._exporters.items()):
                try:
                    exporter.close()
                except Exception:
                    logger.exception("Failed to close exporter '%s'", name)

            # Close custom exporters
            for i, exporter in enumerate(list(self._custom_exporters)):
                try:
                    exporter.close()
                except Exception:
                    logger.exception(
                        "Failed to close custom exporter %d (%s)",
                        i,
                        type(exporter).__name__,
                    )

            self._exporters.clear()
            self._custom_exporters.clear()

        with _runtime_lock:
            if _runtime is self:
                _runtime = None


def _atexit_shutdown() -> None:
    """Shutdown handler called on process exit."""
    global _runtime
    if _runtime is not None:
        try:
            _runtime.shutdown()
        except Exception:
            logger.exception("Error during atexit shutdown")


# Register atexit handler
atexit.register(_atexit_shutdown)


def init(
    console: bool | None = None,
    jsonl: bool | None = None,
    jsonl_path: str | Path | None = None,
    console_file: TextIO | None = None,
    console_verbose: bool = False,
    exporters: list[BaseExporter] | None = None,
    config: AgentTraceConfig | None = None,
    # Environment configuration
    env: str | None = None,
    config_path: str | Path | None = None,
    # Mode for smart defaults
    mode: str | None = None,
    # Storage configuration
    storage: str | BaseTraceStore | None = None,
    # Convenience parameters that override config
    redaction_enabled: bool | None = None,
    sampling_rate: float | None = None,
) -> TALRuntime:
    """
    Initialize the AgentTrace runtime.

    This is the main entry point for configuring AgentTrace. By default,
    it enables both console and JSONL exporters for local-first debugging,
    unless running in a detected production environment.

    Configuration precedence:
    1. Explicit parameters to init()
    2. Mode-based defaults (if mode is specified)
    3. Environment-aware defaults (auto-detected or from env parameter)
    4. Environment-specific config from config file (.agenttrace/config.yaml)
    5. Default config

    Thread-safe: Multiple calls from different threads will return the
    same runtime instance.

    Args:
        console: Enable console exporter. If None, uses environment-aware defaults.
        jsonl: Enable JSONL exporter. If None, uses environment-aware defaults.
        jsonl_path: Custom path for JSONL file.
        console_file: Custom file for console output.
        console_verbose: Enable verbose console output.
        exporters: Additional custom exporters.
        config: Configuration object for processors and settings.
        env: Environment name (development, staging, production, test).
            If None, auto-detects from environment variables.
        config_path: Path to config file.
        mode: Mode for smart defaults. Options:
            - "local": Force local development defaults (console=True, jsonl=True)
            - "production": Force production defaults (console=False, jsonl=False)
            - "auto" or None: Auto-detect from environment (default)
        storage: Storage backend. Can be:
            - None: Use env config or no storage
            - str: "sqlite:///path.db", "mlflow:experiment", "path/to/file.jsonl"
            - BaseTraceStore: Custom storage instance
        redaction_enabled: Enable PII redaction (overrides config).
        sampling_rate: Sampling rate 0.0-1.0 (overrides config).

    Returns:
        The TALRuntime instance.

    Example:
        import agenttrace

        # Simple usage (auto-detects environment)
        agenttrace.init()

        # Force local development mode
        agenttrace.init(mode="local")

        # Force production mode (disables console/jsonl)
        agenttrace.init(mode="production")

        # Explicit environment
        agenttrace.init(env="production")

        # With SQLite storage
        agenttrace.init(storage="sqlite:///traces.db")

        @agenttrace.trace_agent(name="my_agent")
        def my_agent(query: str):
            return process(query)
    """
    global _runtime

    with _runtime_lock:
        if _runtime is None:
            # Load environment config
            from agenttrace.core.env_config import (
                detect_environment,
                get_environment_defaults,
            )
            from agenttrace.core.env_config import (
                load_config as load_env_config,
            )
            from agenttrace.core.env_config import (
                set_config as set_env_config,
            )

            # Detect or use provided environment
            detected_env = env if env is not None else detect_environment()
            logger.debug("Detected environment: %s", detected_env)

            env_config = load_env_config(config_path=config_path, env=detected_env)
            set_env_config(env_config)
            settings = env_config.get_settings()

            # Load processor config from env if not provided
            if config is None:
                from agenttrace.core.config import load_config_from_env

                config = load_config_from_env()

            # Apply env config processor settings
            if settings.processors.redaction_enabled:
                config.redaction.enabled = True
            if settings.processors.sampling_enabled:
                config.sampling.rate = settings.processors.sampling_rate

            # Apply convenience overrides
            if redaction_enabled is not None:
                config.redaction.enabled = redaction_enabled
            if sampling_rate is not None:
                config.sampling.rate = sampling_rate

            # Determine console/jsonl settings based on mode or environment
            if mode == "local":
                # Force local development defaults
                env_defaults = {"console": True, "jsonl": True}
            elif mode == "production":
                # Force production defaults
                env_defaults = {"console": False, "jsonl": False}
            else:
                # Auto mode: use environment-aware defaults
                env_defaults = get_environment_defaults(detected_env)

            # Apply settings with precedence: explicit params > mode defaults > env config
            use_console = (
                console
                if console is not None
                else (
                    settings.exporters.console
                    if settings.exporters.console != env_defaults["console"]
                    else env_defaults["console"]
                )
            )
            use_jsonl = (
                jsonl
                if jsonl is not None
                else (
                    settings.exporters.jsonl
                    if settings.exporters.jsonl != env_defaults["jsonl"]
                    else env_defaults["jsonl"]
                )
            )
            effective_jsonl_path = jsonl_path or settings.exporters.jsonl_path or DEFAULT_JSONL_PATH

            # Initialize storage backend
            storage_backend = _init_storage(storage, settings.storage)

            _runtime = TALRuntime(
                console=use_console,
                jsonl=use_jsonl,
                jsonl_path=effective_jsonl_path,
                console_file=console_file,
                console_verbose=console_verbose,
                exporters=exporters,
                config=config,
                storage=storage_backend,
            )
        # Return inside lock to prevent race condition
        return _runtime


def _init_storage(
    storage_arg: str | BaseTraceStore | None,
    storage_config: StorageConfig,
) -> BaseTraceStore | None:
    """
    Initialize storage backend from argument or config.

    Args:
        storage_arg: Explicit storage argument from init().
        storage_config: Storage config from environment settings.

    Returns:
        Storage backend or None.
    """
    # If explicit storage provided, use it
    if storage_arg is not None:
        if isinstance(storage_arg, str):
            return _parse_storage_string(storage_arg)
        return storage_arg

    # Use config
    if storage_config.type == "none":
        return None
    elif storage_config.type == "sqlite" and storage_config.sqlite_path:
        from agenttrace.storage.sqlite import SQLiteTraceStore

        return SQLiteTraceStore(
            storage_config.sqlite_path,
            wal_mode=storage_config.sqlite_wal_mode,
        )
    elif storage_config.type == "mlflow":
        from agenttrace.storage.mlflow import MLflowTraceStore

        return MLflowTraceStore(
            tracking_uri=storage_config.mlflow_tracking_uri,
            experiment_name=storage_config.mlflow_experiment_name,
        )
    elif storage_config.type == "jsonl" and storage_config.jsonl_path:
        from agenttrace.storage.jsonl import JSONLTraceStore

        return JSONLTraceStore(storage_config.jsonl_path)

    return None


def _parse_storage_string(storage: str) -> BaseTraceStore | None:
    """Parse storage string into a storage backend."""
    if storage.startswith("sqlite://"):
        path = storage.replace("sqlite://", "")
        from agenttrace.storage.sqlite import SQLiteTraceStore

        return SQLiteTraceStore(path)
    elif storage.startswith("mlflow://"):
        from urllib.parse import urlparse

        parsed = urlparse(storage)
        tracking_uri = f"http://{parsed.netloc}"
        experiment_name = parsed.path.lstrip("/") or None

        from agenttrace.storage.mlflow import MLflowTraceStore

        return MLflowTraceStore(
            tracking_uri=tracking_uri,
            experiment_name=experiment_name,
        )
    elif storage.startswith("mlflow:"):
        experiment_name = storage.replace("mlflow:", "")
        from agenttrace.storage.mlflow import MLflowTraceStore

        return MLflowTraceStore(experiment_name=experiment_name)
    elif storage.endswith(".jsonl"):
        from agenttrace.storage.jsonl import JSONLTraceStore

        return JSONLTraceStore(storage)
    elif storage.endswith(".db") or storage.endswith(".sqlite"):
        from agenttrace.storage.sqlite import SQLiteTraceStore

        return SQLiteTraceStore(storage)
    elif storage == "none":
        return None
    else:
        # Default to JSONL
        from agenttrace.storage.jsonl import JSONLTraceStore

        return JSONLTraceStore(storage)


def get_runtime() -> TALRuntime | None:
    """Get the current runtime instance (thread-safe)."""
    with _runtime_lock:
        return _runtime
