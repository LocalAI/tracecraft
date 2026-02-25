"""
CLI entry point for Trace Craft commands.

Provides commands for viewing, validating, and exporting traces.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from tracecraft.storage.sqlite import SQLiteTraceStore

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from tracecraft.cli.prompts import app as prompts_app
from tracecraft.core.models import AgentRun, Step, StepType

# Create the main app
app = typer.Typer(
    name="tracecraft",
    help="Trace Craft CLI - View and manage LLM observability traces",
    add_completion=False,
)

# Register subcommand groups
app.add_typer(prompts_app, name="prompts")

console = Console()

# Step type icons for display
STEP_ICONS = {
    StepType.AGENT: "[blue]🤖[/blue]",
    StepType.LLM: "[green]💬[/green]",
    StepType.TOOL: "[yellow]🔧[/yellow]",
    StepType.RETRIEVAL: "[cyan]📚[/cyan]",
    StepType.MEMORY: "[magenta]🧠[/magenta]",
    StepType.GUARDRAIL: "[red]🛡️[/red]",
    StepType.EVALUATION: "[cyan]📊[/cyan]",
    StepType.WORKFLOW: "[white]⚙️[/white]",
    StepType.ERROR: "[red]❌[/red]",
}


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print("tracecraft version 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Trace Craft CLI - View and manage LLM observability traces."""
    pass


def load_runs_from_file(file_path: Path) -> list[AgentRun]:
    """Load AgentRun objects from a JSONL file."""
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    runs: list[AgentRun] = []
    try:
        with file_path.open() as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    run = AgentRun.model_validate(data)
                    runs.append(run)
                except json.JSONDecodeError as e:
                    console.print(f"[red]Error: Invalid JSON on line {line_num}: {e}[/red]")
                    raise typer.Exit(1) from e
                except ValidationError as e:
                    console.print(f"[red]Error: Invalid trace data on line {line_num}: {e}[/red]")
                    raise typer.Exit(1) from e
    except PermissionError:
        console.print(f"[red]Error: Permission denied reading {file_path}[/red]")
        raise typer.Exit(1) from None

    return runs


def build_step_tree(tree: Tree, steps: list[Step], depth: int = 0) -> None:
    """Recursively build a tree of steps."""
    for step in steps:
        icon = STEP_ICONS.get(step.type, "")
        duration = f" ({step.duration_ms:.1f}ms)" if step.duration_ms else ""
        tokens = ""
        if step.input_tokens or step.output_tokens:
            tokens = f" [dim]tokens: {step.input_tokens or 0}/{step.output_tokens or 0}[/dim]"

        label = f"{icon} {step.name}{duration}{tokens}"
        if step.error:
            label += f" [red]Error: {step.error}[/red]"

        branch = tree.add(label)

        if step.children:
            build_step_tree(branch, step.children, depth + 1)


@app.command()
def view(
    file_path: Annotated[Path, typer.Argument(help="Path to JSONL trace file")],
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
    run_index: Annotated[
        int | None, typer.Option("--run", "-r", help="Show specific run by index (0-based)")
    ] = None,
) -> None:
    """View traces from a JSONL file."""
    runs = load_runs_from_file(file_path)

    if not runs:
        console.print("[yellow]No traces found in file[/yellow]")
        raise typer.Exit(0)

    # Filter to specific run if requested
    if run_index is not None:
        if run_index < 0 or run_index >= len(runs):
            console.print(
                f"[red]Error: Run index {run_index} out of range (0-{len(runs) - 1})[/red]"
            )
            raise typer.Exit(1)
        runs = [runs[run_index]]

    # JSON output mode
    if json_output:
        if len(runs) == 1:
            console.print(runs[0].model_dump_json(indent=2))
        else:
            console.print(json.dumps([r.model_dump() for r in runs], indent=2, default=str))
        return

    # Tree output mode
    for i, run in enumerate(runs):
        duration = f" ({run.duration_ms:.1f}ms)" if run.duration_ms else ""
        tokens = f" [dim]total tokens: {run.total_tokens}[/dim]" if run.total_tokens else ""

        tree = Tree(f"[bold]{run.name}[/bold]{duration}{tokens}")

        if run.steps:
            build_step_tree(tree, run.steps)

        console.print(tree)
        if i < len(runs) - 1:
            console.print()


@app.command()
def info() -> None:
    """Show Trace Craft configuration and info."""
    console.print("[bold]Trace Craft Info[/bold]")
    console.print()

    table = Table(show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Version", "0.1.0")
    table.add_row("Python", sys.version.split()[0])

    # List available exporters
    exporters = ["Console (built-in)", "JSONL (built-in)", "HTML (built-in)"]
    table.add_row("Exporters", ", ".join(exporters))

    # List available adapters
    adapters = ["LangChain", "LlamaIndex", "PydanticAI"]
    table.add_row("Adapters", ", ".join(adapters))

    console.print(table)


@app.command()
def stats(
    file_path: Annotated[Path, typer.Argument(help="Path to JSONL trace file")],
) -> None:
    """Show statistics for traces in a file."""
    runs = load_runs_from_file(file_path)

    if not runs:
        console.print("[yellow]No traces found in file[/yellow]")
        raise typer.Exit(0)

    console.print("[bold]Trace Statistics[/bold]")
    console.print()

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total runs", str(len(runs)))

    total_tokens = sum(r.total_tokens for r in runs)
    table.add_row("Total tokens", str(total_tokens))

    durations = [r.duration_ms for r in runs if r.duration_ms]
    if durations:
        avg_duration = sum(durations) / len(durations)
        table.add_row("Avg duration (ms)", f"{avg_duration:.1f}")
        table.add_row("Min duration (ms)", f"{min(durations):.1f}")
        table.add_row("Max duration (ms)", f"{max(durations):.1f}")

    total_steps = sum(len(r.steps) for r in runs)
    table.add_row("Total steps", str(total_steps))

    error_count = sum(r.error_count for r in runs)
    table.add_row("Total errors", str(error_count))

    console.print(table)


@app.command()
def export(
    file_path: Annotated[Path, typer.Argument(help="Path to JSONL trace file")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format (html)")
    ] = "html",
) -> None:
    """Export traces to different formats."""
    runs = load_runs_from_file(file_path)

    if not runs:
        console.print("[yellow]No traces found in file[/yellow]")
        raise typer.Exit(0)

    if format_type == "html":
        from tracecraft.exporters.html import HTMLExporter

        exporter = HTMLExporter()

        # Render first run as HTML
        html_content = exporter.render(runs[0])

        if output:
            output.write_text(html_content)
            console.print(f"[green]Exported to {output}[/green]")
        else:
            console.print(html_content)
    else:
        console.print(f"[red]Error: Unknown format '{format_type}'. Supported: html[/red]")
        raise typer.Exit(1)


@app.command()
def tui(
    source: Annotated[
        str | None,
        typer.Argument(
            help="Trace source: file.jsonl, file.db, sqlite:///path, mlflow://host/exp, mlflow:exp"
        ),
    ] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch for new traces")] = False,
    env: Annotated[
        str | None,
        typer.Option("--env", "-e", help="Use storage from environment config"),
    ] = None,
    filter_str: Annotated[str | None, typer.Option("--filter", "-f", help="Initial filter")] = None,
    serve_flag: Annotated[
        bool, typer.Option("--serve", "-S", help="Start OTLP receiver on :4318 before opening TUI")
    ] = False,
) -> None:
    """
    Launch the interactive terminal UI.

    With no arguments, reads storage location from .tracecraft/config.yaml (defaults to
    traces/tracecraft.db if no config is found).

    Examples:
        # Open TUI from config-specified storage (or default SQLite)
        tracecraft tui

        # Start OTLP receiver on :4318 and open TUI
        tracecraft tui --serve

        # JSONL file
        tracecraft tui traces/tracecraft.jsonl

        # SQLite database
        tracecraft tui traces.db
        tracecraft tui sqlite:///path/to/traces.db

        # MLflow (default tracking URI)
        tracecraft tui mlflow:my_experiment

        # MLflow (specific server)
        tracecraft tui mlflow://localhost:5000/production_traces

        # Watch for new traces
        tracecraft tui traces.jsonl --watch

        # Use production environment config
        tracecraft tui --env production
    """
    try:
        from tracecraft.tui import run_tui
    except ImportError:
        console.print(
            "[red]Error: TUI dependencies not installed.[/red]\n"
            "Install with: pip install tracecraft[tui]"
        )
        raise typer.Exit(1) from None

    # Resolve effective source from config when neither source nor env is explicitly given
    effective_source = source
    if not source:
        try:
            from tracecraft.core.env_config import load_config

            config = load_config(env=env)  # env=None → auto-detect
            settings = config.get_settings()

            if settings.storage.type == "sqlite" and settings.storage.sqlite_path:
                effective_source = f"sqlite://{settings.storage.sqlite_path}"
            elif settings.storage.type == "mlflow":
                if settings.storage.mlflow_tracking_uri:
                    exp = settings.storage.mlflow_experiment_name or "tracecraft"
                    effective_source = f"mlflow://{settings.storage.mlflow_tracking_uri.replace('http://', '')}/{exp}"
                else:
                    exp = settings.storage.mlflow_experiment_name or "tracecraft"
                    effective_source = f"mlflow:{exp}"
            elif settings.storage.type == "jsonl" and settings.storage.jsonl_path:
                effective_source = settings.storage.jsonl_path
            elif settings.storage.type == "xray":
                region = settings.storage.xray_region or "us-east-1"
                svc = settings.storage.xray_service_name or ""
                effective_source = f"xray://{region}/{svc}"
            elif settings.storage.type == "cloudtrace":
                project = settings.storage.cloudtrace_project_id or os.environ.get(
                    "GOOGLE_CLOUD_PROJECT", ""
                )
                svc = settings.storage.cloudtrace_service_name or ""
                effective_source = f"cloudtrace://{project}/{svc}"
            elif settings.storage.type == "azuremonitor":
                workspace = settings.storage.azuremonitor_workspace_id or os.environ.get(
                    "AZURE_MONITOR_WORKSPACE_ID", ""
                )
                svc = settings.storage.azuremonitor_service_name or ""
                effective_source = f"azuremonitor://{workspace}/{svc}"
            elif settings.storage.type == "datadog":
                site = settings.storage.datadog_site or "us1"
                svc = settings.storage.datadog_service or ""
                effective_source = f"datadog://{site}/{svc}"
            else:
                effective_source = "sqlite://traces/tracecraft.db"
        except Exception:
            effective_source = "sqlite://traces/tracecraft.db"

    if serve_flag:
        try:
            from tracecraft.receiver import OTLPReceiverServer
        except ImportError:
            console.print(
                "[red]Error: Receiver dependencies not installed.[/red]\n"
                "Install with: pip install tracecraft[receiver]"
            )
            raise typer.Exit(1) from None

        storage_path = Path("traces/tracecraft.db")
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        from tracecraft.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore(storage_path)
        tui_source = f"sqlite://{storage_path}"

        server = OTLPReceiverServer(store=store, host="0.0.0.0", port=4318)  # nosec B104
        console.print("[dim]Starting OTLP receiver on :4318 with TUI...[/dim]")
        server.start_background()
        try:
            run_tui(source=tui_source, watch=True)
        finally:
            server.stop()
    else:
        run_tui(source=effective_source, watch=watch)


@app.command(name="ui", hidden=True)
def ui_alias(
    source: Annotated[
        str | None,
        typer.Argument(
            help="Trace source: file.jsonl, file.db, sqlite:///path, mlflow://host/exp, mlflow:exp"
        ),
    ] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch for new traces")] = False,
    env: Annotated[
        str | None,
        typer.Option("--env", "-e", help="Use storage from environment config"),
    ] = None,
    filter_str: Annotated[str | None, typer.Option("--filter", "-f", help="Initial filter")] = None,
) -> None:
    """Deprecated alias for 'tracecraft tui'. Use 'tracecraft tui' instead."""
    tui(source=source, watch=watch, env=env, filter_str=filter_str, serve_flag=False)


@app.command()
def serve(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on")] = 4318,
    host: Annotated[str, typer.Option("--host", "-H", help="Host to bind to")] = "0.0.0.0",  # nosec B104 - intentional for receiver server
    storage: Annotated[
        str,
        typer.Option("--storage", "-s", help="Storage path (SQLite or JSONL)"),
    ] = "traces/tracecraft.db",
    tui: Annotated[
        bool,
        typer.Option("--tui", "-t", help="Launch TUI alongside receiver"),
    ] = False,
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Watch for new traces in TUI"),
    ] = True,
) -> None:
    """
    Start OTLP receiver server, optionally with TUI.

    Receives traces from OTLP-instrumented applications and saves them to storage.
    The TUI can then display them in real-time with --watch mode.

    Examples:
        # Start receiver only
        tracecraft serve

        # Start receiver with TUI
        tracecraft serve --tui

        # Custom port and storage
        tracecraft serve --port 4317 --storage my_traces.db

        # Use JSONL storage
        tracecraft serve --storage traces.jsonl
    """
    try:
        from tracecraft.receiver import OTLPReceiverServer
    except ImportError:
        console.print(
            "[red]Error: Receiver dependencies not installed.[/red]\n"
            "Install with: pip install tracecraft[receiver]"
        )
        raise typer.Exit(1) from None

    # Create storage based on file extension
    storage_path = Path(storage)

    # Ensure parent directory exists
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    if storage_path.suffix == ".db" or storage_path.suffix == ".sqlite":
        from tracecraft.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore(storage_path)
        source = f"sqlite://{storage_path}"
    else:
        from tracecraft.storage.jsonl import JSONLTraceStore

        store = JSONLTraceStore(storage_path)
        source = str(storage_path)

    # Create receiver server
    server = OTLPReceiverServer(store=store, host=host, port=port)

    console.print("[bold green]TraceCraft Receiver[/bold green]")
    console.print(f"  Listening on: http://{host}:{port}")
    console.print(f"  Storage: {storage_path}")
    console.print()
    console.print("[dim]Send traces with:[/dim]")
    console.print(f"  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:{port}")
    console.print()

    if tui:
        try:
            from tracecraft.tui import run_tui
        except ImportError:
            console.print(
                "[yellow]Warning: TUI dependencies not installed. Running receiver only.[/yellow]\n"
                "Install with: pip install tracecraft[tui]"
            )
            server.run()
            return

        # Start receiver in background, TUI in foreground
        console.print("[dim]Starting TUI with receiver in background...[/dim]")
        server.start_background()

        try:
            run_tui(source=source, watch=watch)
        finally:
            server.stop()
    else:
        # Run receiver in foreground (blocking)
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        try:
            server.run()
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def receive(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to listen on")] = 4318,
    host: Annotated[str, typer.Option("--host", "-H", help="Host to bind to")] = "0.0.0.0",  # nosec B104 - intentional for receiver server
    storage: Annotated[
        str,
        typer.Option("--storage", "-s", help="Storage path (SQLite or JSONL)"),
    ] = "traces/tracecraft.db",
) -> None:
    """
    Start OTLP receiver server (headless).

    Alias for 'tracecraft serve' without TUI option.
    Use 'tracecraft serve --tui' to run receiver with interactive UI.

    Examples:
        # Start receiver
        tracecraft receive

        # Custom port
        tracecraft receive --port 4317
    """
    try:
        from tracecraft.receiver import OTLPReceiverServer
    except ImportError:
        console.print(
            "[red]Error: Receiver dependencies not installed.[/red]\n"
            "Install with: pip install tracecraft[receiver]"
        )
        raise typer.Exit(1) from None

    storage_path = Path(storage)

    # Ensure parent directory exists
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    if storage_path.suffix == ".db" or storage_path.suffix == ".sqlite":
        from tracecraft.storage.sqlite import SQLiteTraceStore

        store = SQLiteTraceStore(storage_path)
    else:
        from tracecraft.storage.jsonl import JSONLTraceStore

        store = JSONLTraceStore(storage_path)

    server = OTLPReceiverServer(store=store, host=host, port=port)

    console.print("[bold green]TraceCraft Receiver[/bold green]")
    console.print(f"  Listening on: http://{host}:{port}")
    console.print(f"  Storage: {storage_path}")
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    try:
        server.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def query(
    source: Annotated[str, typer.Argument(help="Trace source (file, sqlite, mlflow)")],
    sql: Annotated[str | None, typer.Option("--sql", help="Raw SQL query (SQLite only)")] = None,
    mlflow_filter: Annotated[
        str | None, typer.Option("--mlflow-filter", help="MLflow filter DSL")
    ] = None,
    has_error: Annotated[
        bool | None, typer.Option("--error/--no-error", help="Filter by error status")
    ] = None,
    min_cost: Annotated[float | None, typer.Option("--min-cost", help="Minimum cost USD")] = None,
    max_cost: Annotated[float | None, typer.Option("--max-cost", help="Maximum cost USD")] = None,
    min_duration: Annotated[
        float | None, typer.Option("--min-duration", help="Minimum duration ms")
    ] = None,
    name_contains: Annotated[
        str | None, typer.Option("--name", "-n", help="Filter by name (substring)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 10,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table, json, csv")
    ] = "table",
) -> None:
    """
    Query traces from storage.

    Examples:
        # Find expensive traces
        tracecraft query traces.db --min-cost 0.10

        # Find errors
        tracecraft query mlflow:my_experiment --error

        # Raw SQL (SQLite only)
        tracecraft query traces.db --sql "SELECT name, total_cost_usd FROM traces ORDER BY total_cost_usd DESC LIMIT 5"

        # MLflow filter DSL
        tracecraft query mlflow:production --mlflow-filter "metrics.duration_ms > 5000"
    """
    from tracecraft.storage.base import TraceQuery
    from tracecraft.tui.data.loader import TraceLoader

    try:
        loader = TraceLoader.from_source(source)
    except Exception as e:
        console.print(f"[red]Error loading source: {e}[/red]")
        raise typer.Exit(1) from None

    # Handle raw SQL for SQLite
    if sql:
        from tracecraft.storage.sqlite import SQLiteTraceStore

        if not isinstance(loader.store, SQLiteTraceStore):
            console.print("[red]Error: --sql only supported for SQLite sources[/red]")
            raise typer.Exit(1)

        results = loader.store.execute_sql(sql)
        _output_results(results, format_type)
        return

    # Handle MLflow filter DSL
    if mlflow_filter:
        from tracecraft.storage.mlflow import MLflowTraceStore

        if not isinstance(loader.store, MLflowTraceStore):
            console.print("[red]Error: --mlflow-filter only supported for MLflow sources[/red]")
            raise typer.Exit(1)

        traces = loader.store.search(mlflow_filter)
        _output_traces(traces[:limit], format_type)
        return

    # Standard query
    trace_query = TraceQuery(
        has_error=has_error,
        min_cost_usd=min_cost,
        max_cost_usd=max_cost,
        min_duration_ms=min_duration,
        name_contains=name_contains,
        limit=limit,
    )
    traces = loader.query_traces(trace_query)
    _output_traces(traces, format_type)


def _output_traces(traces: list[AgentRun], format_type: str) -> None:
    """Output traces in specified format."""
    if not traces:
        console.print("[yellow]No traces found[/yellow]")
        return

    if format_type == "json":
        for trace in traces:
            console.print(trace.model_dump_json())
    elif format_type == "csv":
        console.print("id,name,duration_ms,total_cost_usd,error_count,start_time")
        for trace in traces:
            console.print(
                f"{trace.id},{trace.name},{trace.duration_ms or 0},"
                f"{trace.total_cost_usd},{trace.error_count},{trace.start_time.isoformat()}"
            )
    else:
        # Table format
        table = Table(title=f"Traces ({len(traces)} results)")
        table.add_column("Name", style="cyan")
        table.add_column("Duration", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Time")

        for trace in traces:
            duration = f"{trace.duration_ms:.0f}ms" if trace.duration_ms else "-"
            cost = f"${trace.total_cost_usd:.4f}" if trace.total_cost_usd else "-"
            tokens = str(trace.total_tokens) if trace.total_tokens else "-"
            errors = str(trace.error_count) if trace.error_count else "0"
            time_str = trace.start_time.strftime("%Y-%m-%d %H:%M")

            # Color errors red
            if trace.error_count > 0:
                errors = f"[red]{errors}[/red]"

            table.add_row(trace.name, duration, cost, tokens, errors, time_str)

        console.print(table)


def _output_results(results: list[dict], format_type: str) -> None:
    """Output raw SQL results."""
    if not results:
        console.print("[yellow]No results[/yellow]")
        return

    if format_type == "json":
        console.print(json.dumps(results, indent=2, default=str))
    elif format_type == "csv":
        keys = list(results[0].keys())
        console.print(",".join(keys))
        for row in results:
            console.print(",".join(str(row.get(k, "")) for k in keys))
    else:
        table = Table()
        for key in results[0].keys():
            table.add_column(key)

        for row in results:
            table.add_row(*[str(v) if v is not None else "-" for v in row.values()])

        console.print(table)


@app.command()
def playground(
    file_path: Annotated[Path, typer.Argument(help="Path to JSONL trace file")],
    trace_id: Annotated[str, typer.Option("--trace-id", "-t", help="Trace ID to replay")],
    step_id: Annotated[
        str | None, typer.Option("--step-id", "-s", help="Step ID to replay")
    ] = None,
    step_name: Annotated[
        str | None, typer.Option("--step-name", "-n", help="Step name to replay")
    ] = None,
    modified_prompt: Annotated[
        str | None, typer.Option("--prompt", "-p", help="Modified system prompt")
    ] = None,
    compare: Annotated[
        bool, typer.Option("--compare", "-c", help="Compare original vs modified output")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
) -> None:
    """Replay an LLM step from a trace file."""
    import asyncio

    if step_id is None and step_name is None:
        console.print("[red]Error: Either --step-id or --step-name is required[/red]")
        raise typer.Exit(1)

    if compare and modified_prompt is None:
        console.print("[red]Error: --prompt is required when using --compare[/red]")
        raise typer.Exit(1)

    try:
        if compare:
            from tracecraft.playground import compare_prompts

            result = asyncio.run(
                compare_prompts(
                    trace_id=trace_id,
                    step_id=step_id,
                    step_name=step_name,
                    trace_source=file_path,
                    modified_prompt=modified_prompt,
                )
            )

            if json_output:
                console.print(json.dumps(result.to_dict(), indent=2))
            else:
                console.print("[bold]Original Output:[/bold]")
                console.print(result.original_output[:500])
                if len(result.original_output) > 500:
                    console.print(f"... ({len(result.original_output)} chars total)")
                console.print()
                console.print("[bold]Modified Output:[/bold]")
                console.print(result.modified_output[:500])
                if len(result.modified_output) > 500:
                    console.print(f"... ({len(result.modified_output)} chars total)")
                console.print()
                console.print(f"[dim]Similarity: {result.similarity:.1%}[/dim]")
                console.print(
                    f"[dim]Tokens: {result.modified_result.total_tokens}, "
                    f"Duration: {result.modified_result.duration_ms:.0f}ms[/dim]"
                )
        else:
            from tracecraft.playground import replay_step

            result = asyncio.run(
                replay_step(
                    trace_id=trace_id,
                    step_id=step_id,
                    step_name=step_name,
                    trace_source=file_path,
                    modified_prompt=modified_prompt,
                )
            )

            if result.error:
                console.print(f"[red]Error: {result.error}[/red]")
                raise typer.Exit(1)

            if json_output:
                console.print(
                    json.dumps(
                        {
                            "output": result.output,
                            "model": result.model,
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                            "duration_ms": result.duration_ms,
                        },
                        indent=2,
                    )
                )
            else:
                console.print("[bold]Output:[/bold]")
                console.print(result.output)
                console.print()
                console.print(
                    f"[dim]Model: {result.model}, "
                    f"Tokens: {result.total_tokens}, "
                    f"Duration: {result.duration_ms:.0f}ms[/dim]"
                )

    except ImportError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Install required package: pip install openai anthropic")
        raise typer.Exit(1) from None
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


@app.command()
def validate(
    file_path: Annotated[Path, typer.Argument(help="Path to JSONL trace file")],
) -> None:
    """Validate a trace file."""
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    errors: list[str] = []
    valid_count = 0

    try:
        with file_path.open() as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    AgentRun.model_validate(data)
                    valid_count += 1
                except json.JSONDecodeError as e:
                    errors.append(f"Line {line_num}: Invalid JSON - {e}")
                except ValidationError as e:
                    errors.append(f"Line {line_num}: Invalid trace data - {e}")
    except PermissionError:
        console.print(f"[red]Error: Permission denied reading {file_path}[/red]")
        raise typer.Exit(1) from None

    if errors:
        console.print(f"[red]Validation failed with {len(errors)} error(s):[/red]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[green]Valid: {valid_count} trace(s) validated successfully[/green]")


if __name__ == "__main__":
    app()
