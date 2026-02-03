"""
CLI entry point for Trace Craft commands.

Provides commands for viewing, validating, and exporting traces.
"""

from __future__ import annotations

import json
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

from tracecraft.core.models import AgentRun, Step, StepType

# Create the main app
app = typer.Typer(
    name="tracecraft",
    help="Trace Craft CLI - View and manage LLM observability traces",
    add_completion=False,
)

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
def ui(
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
    """
    Launch the interactive terminal UI.

    Examples:
        # JSONL file
        tracecraft ui traces/tracecraft.jsonl

        # SQLite database
        tracecraft ui traces.db
        tracecraft ui sqlite:///path/to/traces.db

        # MLflow (default tracking URI)
        tracecraft ui mlflow:my_experiment

        # MLflow (specific server)
        tracecraft ui mlflow://localhost:5000/production_traces

        # Watch for new traces
        tracecraft ui traces.jsonl --watch

        # Use production environment config
        tracecraft ui --env production
    """
    try:
        from tracecraft.tui import run_tui
    except ImportError:
        console.print(
            "[red]Error: TUI dependencies not installed.[/red]\n"
            "Install with: pip install tracecraft[tui]"
        )
        raise typer.Exit(1) from None

    # If env specified, use storage from that environment's config
    effective_source = source
    if env and not source:
        try:
            from tracecraft.core.env_config import load_config

            config = load_config(env=env)
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
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load env config: {e}[/yellow]")

    run_tui(source=effective_source, watch=watch)


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


# ============================================================================
# Evaluation Subcommands
# ============================================================================

eval_app = typer.Typer(
    name="eval",
    help="Evaluation management - create, run, and view evaluations",
)
app.add_typer(eval_app)


def _get_sqlite_store(source: str) -> SQLiteTraceStore:
    """Get SQLite store from source string."""
    from tracecraft.storage.sqlite import SQLiteTraceStore

    # Handle various source formats
    if source.endswith(".db"):
        return SQLiteTraceStore(source)
    elif source.startswith("sqlite://"):
        path = source.replace("sqlite://", "")
        return SQLiteTraceStore(path)
    else:
        console.print(f"[red]Error: Evaluations require SQLite storage. Got: {source}[/red]")
        console.print("Use a .db file or sqlite:// URI")
        raise typer.Exit(1)


@eval_app.command("list")
def eval_list(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    project_id: Annotated[
        str | None, typer.Option("--project", "-p", help="Filter by project")
    ] = None,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table, json")
    ] = "table",
) -> None:
    """List evaluation sets."""
    store = _get_sqlite_store(source)

    eval_sets = store.list_evaluation_sets(project_id=project_id)

    if not eval_sets:
        console.print("[yellow]No evaluation sets found[/yellow]")
        return

    if format_type == "json":
        console.print(json.dumps(eval_sets, indent=2, default=str))
        return

    # Table format
    table = Table(title=f"Evaluation Sets ({len(eval_sets)})")
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Cases", justify="right")
    table.add_column("Threshold", justify="right")
    table.add_column("Last Run")
    table.add_column("Pass Rate", justify="right")

    for eval_set in eval_sets:
        set_id = str(eval_set.get("id", ""))[:8]
        name = eval_set.get("name", "Unknown")
        case_count = str(eval_set.get("case_count", 0))
        threshold = f"{eval_set.get('pass_rate_threshold', 0.8) * 100:.0f}%"

        # Latest run info
        latest_run = eval_set.get("latest_run")
        if latest_run:
            status = latest_run.get("status", "pending")
            pass_rate = latest_run.get("overall_pass_rate")
            if pass_rate is not None:
                pct = pass_rate * 100
                if latest_run.get("passed"):
                    pass_rate_str = f"[green]{pct:.0f}%[/green]"
                else:
                    pass_rate_str = f"[red]{pct:.0f}%[/red]"
            else:
                pass_rate_str = "-"
            last_run = status.upper()
        else:
            last_run = "-"
            pass_rate_str = "-"

        table.add_row(name, set_id, case_count, threshold, last_run, pass_rate_str)

    console.print(table)


@eval_app.command("show")
def eval_show(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    set_id: Annotated[str, typer.Argument(help="Evaluation set ID or name")],
    cases: Annotated[bool, typer.Option("--cases", "-c", help="Include cases")] = False,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table, json")
    ] = "table",
) -> None:
    """Show evaluation set details."""
    store = _get_sqlite_store(source)

    # Try to find by ID or name
    eval_set = store.get_evaluation_set(set_id)
    if not eval_set:
        # Try by name
        all_sets = store.list_evaluation_sets()
        for s in all_sets:
            if s.get("name") == set_id:
                eval_set = store.get_evaluation_set(s["id"])
                break

    if not eval_set:
        console.print(f"[red]Error: Evaluation set not found: {set_id}[/red]")
        raise typer.Exit(1)

    # Get cases if requested
    eval_cases = []
    if cases:
        eval_cases = store.get_evaluation_cases(eval_set["id"])

    if format_type == "json":
        output = {**eval_set}
        if cases:
            output["cases"] = eval_cases
        console.print(json.dumps(output, indent=2, default=str))
        return

    # Table format - set info
    console.print(f"[bold]Evaluation Set: {eval_set.get('name')}[/bold]")
    console.print()

    info_table = Table(show_header=False)
    info_table.add_column("Key", style="cyan")
    info_table.add_column("Value")

    info_table.add_row("ID", str(eval_set.get("id", ""))[:8])
    info_table.add_row("Description", eval_set.get("description") or "-")
    info_table.add_row("Default Threshold", f"{eval_set.get('default_threshold', 0.7) * 100:.0f}%")
    info_table.add_row(
        "Pass Rate Threshold", f"{eval_set.get('pass_rate_threshold', 0.8) * 100:.0f}%"
    )

    # Metrics
    metrics = eval_set.get("metrics", [])
    if metrics:
        metric_strs = [f"{m.get('name')}:{m.get('framework')}" for m in metrics]
        info_table.add_row("Metrics", ", ".join(metric_strs))

    info_table.add_row("Case Count", str(eval_set.get("case_count", len(eval_cases))))

    console.print(info_table)

    # Show cases if requested
    if cases and eval_cases:
        console.print()
        console.print("[bold]Cases:[/bold]")

        cases_table = Table()
        cases_table.add_column("Name", style="cyan")
        cases_table.add_column("Input", max_width=40)
        cases_table.add_column("Expected", max_width=40)
        cases_table.add_column("Source")

        for case in eval_cases:
            name = case.get("name", "Unknown")
            input_str = json.dumps(case.get("input", {}))[:40]
            expected = case.get("expected_output")
            expected_str = json.dumps(expected)[:40] if expected else "-"
            source_trace = (
                str(case.get("source_trace_id", ""))[:8] if case.get("source_trace_id") else "-"
            )

            cases_table.add_row(name, input_str, expected_str, source_trace)

        console.print(cases_table)


@eval_app.command("create")
def eval_create(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    name: Annotated[str, typer.Option("--name", "-n", help="Evaluation set name")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Description")] = None,
    metric: Annotated[
        list[str] | None,
        typer.Option("--metric", "-m", help="Metric in format name:framework:threshold"),
    ] = None,
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="Default threshold")] = 0.7,
    pass_rate: Annotated[
        float, typer.Option("--pass-rate", "-p", help="Pass rate threshold")
    ] = 0.8,
) -> None:
    """
    Create a new evaluation set.

    Examples:
        # Create with built-in metric
        tracecraft eval create traces.db --name "quality-check" --metric "exact_match:builtin:1.0"

        # Create with DeepEval metrics
        tracecraft eval create traces.db --name "rag-eval" \\
            --metric "faithfulness:deepeval:0.8" \\
            --metric "answer_relevancy:deepeval:0.7"
    """
    if not name:
        console.print("[red]Error: --name is required[/red]")
        raise typer.Exit(1)

    store = _get_sqlite_store(source)

    # Parse metrics
    metrics = []
    if metric:
        for m in metric:
            parts = m.split(":")
            if len(parts) < 2:
                console.print(
                    f"[red]Error: Invalid metric format '{m}'. Use name:framework[:threshold][/red]"
                )
                raise typer.Exit(1)

            metric_name = parts[0]
            framework = parts[1]
            metric_threshold = float(parts[2]) if len(parts) > 2 else threshold

            metrics.append(
                {
                    "name": metric_name,
                    "framework": framework,
                    "metric_type": metric_name,
                    "threshold": metric_threshold,
                }
            )

    # Default to exact_match if no metrics specified
    if not metrics:
        metrics.append(
            {
                "name": "exact_match",
                "framework": "builtin",
                "metric_type": "exact_match",
                "threshold": threshold,
            }
        )

    try:
        set_id = store.create_evaluation_set(
            name=name,
            description=description,
            metrics=metrics,
            default_threshold=threshold,
            pass_rate_threshold=pass_rate,
        )
        console.print(f"[green]Created evaluation set: {name}[/green]")
        console.print(f"[dim]ID: {set_id}[/dim]")
    except Exception as e:
        console.print(f"[red]Error creating evaluation set: {e}[/red]")
        raise typer.Exit(1) from None


@eval_app.command("add-case")
def eval_add_case(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    set_name: Annotated[str, typer.Option("--set", "-s", help="Evaluation set name or ID")] = None,
    name: Annotated[str, typer.Option("--name", "-n", help="Case name")] = None,
    input_str: Annotated[str | None, typer.Option("--input", "-i", help="Input JSON")] = None,
    expected: Annotated[
        str | None, typer.Option("--expected", "-e", help="Expected output JSON")
    ] = None,
    from_trace: Annotated[
        str | None, typer.Option("--from-trace", help="Create case from trace ID")
    ] = None,
    from_step: Annotated[
        str | None, typer.Option("--from-step", help="Create case from step ID")
    ] = None,
) -> None:
    """
    Add a case to an evaluation set.

    Examples:
        # Add manual case
        tracecraft eval add-case traces.db --set quality-check \\
            --name "test-1" --input '{"prompt": "2+2=?"}' --expected '{"answer": "4"}'

        # Add case from trace
        tracecraft eval add-case traces.db --set quality-check \\
            --from-trace abc123 --name "production-case-1"
    """
    if not set_name:
        console.print("[red]Error: --set is required[/red]")
        raise typer.Exit(1)

    if not name:
        console.print("[red]Error: --name is required[/red]")
        raise typer.Exit(1)

    store = _get_sqlite_store(source)

    # Find eval set
    eval_set = store.get_evaluation_set(set_name)
    if not eval_set:
        all_sets = store.list_evaluation_sets()
        for s in all_sets:
            if s.get("name") == set_name:
                eval_set = store.get_evaluation_set(s["id"])
                break

    if not eval_set:
        console.print(f"[red]Error: Evaluation set not found: {set_name}[/red]")
        raise typer.Exit(1)

    try:
        if from_trace:
            # Create from trace
            case_id = store.create_case_from_trace(
                set_id=eval_set["id"],
                trace_id=from_trace,
                step_id=from_step,
                name=name,
            )
            console.print(f"[green]Added case from trace: {name}[/green]")
        else:
            # Manual case
            if not input_str:
                console.print("[red]Error: --input is required for manual cases[/red]")
                raise typer.Exit(1)

            try:
                input_data = json.loads(input_str)
            except json.JSONDecodeError:
                console.print("[red]Error: Invalid JSON in --input[/red]")
                raise typer.Exit(1) from None

            expected_data = None
            if expected:
                try:
                    expected_data = json.loads(expected)
                except json.JSONDecodeError:
                    console.print("[red]Error: Invalid JSON in --expected[/red]")
                    raise typer.Exit(1) from None

            case_id = store.add_evaluation_case(
                set_id=eval_set["id"],
                name=name,
                input_data=input_data,
                expected_output=expected_data,
            )
            console.print(f"[green]Added case: {name}[/green]")

        console.print(f"[dim]ID: {case_id}[/dim]")

    except Exception as e:
        console.print(f"[red]Error adding case: {e}[/red]")
        raise typer.Exit(1) from None


@eval_app.command("from-traces")
def eval_from_traces(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    name: Annotated[str, typer.Option("--name", "-n", help="Evaluation set name")] = None,
    filter_str: Annotated[
        str | None, typer.Option("--filter", "-f", help="Filter traces (name:pattern)")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max traces to include")] = 10,
    metric: Annotated[
        list[str] | None,
        typer.Option("--metric", "-m", help="Metric in format name:framework:threshold"),
    ] = None,
) -> None:
    """
    Create an evaluation set from existing traces.

    Examples:
        # Create from recent traces
        tracecraft eval from-traces traces.db --name "production-baseline" --limit 50

        # Create with filter
        tracecraft eval from-traces traces.db --name "agent-cases" \\
            --filter "name:customer_support" --limit 20
    """
    if not name:
        console.print("[red]Error: --name is required[/red]")
        raise typer.Exit(1)

    store = _get_sqlite_store(source)

    # Build query
    from tracecraft.storage.base import TraceQuery

    query_kwargs = {"limit": limit}
    if filter_str and ":" in filter_str:
        key, value = filter_str.split(":", 1)
        if key == "name":
            query_kwargs["name_contains"] = value

    query = TraceQuery(**query_kwargs)
    traces = store.query_traces(query)

    if not traces:
        console.print("[yellow]No traces found matching filter[/yellow]")
        raise typer.Exit(0)

    # Parse metrics
    metrics = []
    if metric:
        for m in metric:
            parts = m.split(":")
            if len(parts) < 2:
                console.print(f"[red]Error: Invalid metric format '{m}'[/red]")
                raise typer.Exit(1)

            metrics.append(
                {
                    "name": parts[0],
                    "framework": parts[1],
                    "metric_type": parts[0],
                    "threshold": float(parts[2]) if len(parts) > 2 else 0.7,
                }
            )

    if not metrics:
        metrics.append(
            {
                "name": "exact_match",
                "framework": "builtin",
                "metric_type": "exact_match",
                "threshold": 1.0,
            }
        )

    try:
        # Create eval set
        set_id = store.create_evaluation_set(
            name=name,
            metrics=metrics,
        )

        # Add cases from traces
        for trace in traces:
            store.create_case_from_trace(
                set_id=set_id,
                trace_id=str(trace.id),
                name=f"trace-{str(trace.id)[:8]}",
            )

        console.print(f"[green]Created evaluation set: {name}[/green]")
        console.print(f"[dim]ID: {set_id}[/dim]")
        console.print(f"[dim]Added {len(traces)} cases from traces[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


@eval_app.command("run")
def eval_run(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    set_id: Annotated[str, typer.Argument(help="Evaluation set ID or name")],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed progress")
    ] = False,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table, json")
    ] = "table",
) -> None:
    """
    Run an evaluation set.

    Examples:
        tracecraft eval run traces.db quality-check --verbose
    """
    import asyncio

    store = _get_sqlite_store(source)

    # Find eval set
    eval_set = store.get_evaluation_set(set_id)
    if not eval_set:
        all_sets = store.list_evaluation_sets()
        for s in all_sets:
            if s.get("name") == set_id:
                eval_set = store.get_evaluation_set(s["id"])
                break

    if not eval_set:
        console.print(f"[red]Error: Evaluation set not found: {set_id}[/red]")
        raise typer.Exit(1)

    # Get cases
    cases = store.get_evaluation_cases(eval_set["id"])
    if not cases:
        console.print("[yellow]No cases in this evaluation set[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold]Running: {eval_set.get('name')}[/bold]")
    console.print(f"[dim]Cases: {len(cases)}[/dim]")
    console.print()

    try:
        from tracecraft.evaluation import EvaluationRunner, EvaluationSet, ProgressInfo

        # Build eval set model
        eval_set_data = {
            "id": eval_set["id"],
            "name": eval_set["name"],
            "metrics": eval_set.get("metrics", []),
            "default_threshold": eval_set.get("default_threshold", 0.7),
            "pass_rate_threshold": eval_set.get("pass_rate_threshold", 0.8),
            "cases": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "input": c["input"],
                    "expected_output": c.get("expected_output"),
                    "retrieval_context": c.get("retrieval_context", []),
                }
                for c in cases
            ],
        }

        eval_set_model = EvaluationSet.model_validate(eval_set_data)

        # Progress callback
        def on_progress(info: ProgressInfo) -> None:
            if verbose:
                msg = f"[{info.completed_cases}/{info.total_cases}]"
                if info.current_case:
                    msg += f" {info.current_case}"
                if info.current_metric:
                    msg += f" ({info.current_metric})"
                console.print(msg, end="\r")

        # Run evaluation
        runner = EvaluationRunner(store=store)

        async def run_eval():
            return await runner.run(eval_set_model, on_progress=on_progress)

        result = asyncio.run(run_eval())

        if verbose:
            console.print()  # Clear progress line
            console.print()

        if format_type == "json":
            output = {
                "run_id": str(result.run_id),
                "status": result.status.value,
                "total_cases": result.total_cases,
                "passed_cases": result.passed_cases,
                "failed_cases": result.failed_cases,
                "pass_rate": result.pass_rate,
                "overall_passed": result.overall_passed,
                "duration_ms": result.duration_ms,
            }
            console.print(json.dumps(output, indent=2))
            return

        # Results table
        console.print("[bold]Results:[/bold]")
        results_table = Table(show_header=False)
        results_table.add_column("Metric", style="cyan")
        results_table.add_column("Value")

        results_table.add_row("Total Cases", str(result.total_cases))
        results_table.add_row("Passed", f"[green]{result.passed_cases}[/green]")
        results_table.add_row("Failed", f"[red]{result.failed_cases}[/red]")

        pass_rate_pct = result.pass_rate * 100 if result.pass_rate else 0
        if result.overall_passed:
            results_table.add_row("Pass Rate", f"[green]{pass_rate_pct:.0f}%[/green]")
            results_table.add_row("Result", "[bold green]PASSED[/bold green]")
        else:
            results_table.add_row("Pass Rate", f"[red]{pass_rate_pct:.0f}%[/red]")
            results_table.add_row("Result", "[bold red]FAILED[/bold red]")

        if result.duration_ms:
            results_table.add_row("Duration", f"{result.duration_ms:.0f}ms")

        console.print(results_table)
        console.print()
        console.print(f"[dim]Run ID: {result.run_id}[/dim]")

    except ImportError as e:
        console.print(f"[red]Error: Missing dependency - {e}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error running evaluation: {e}[/red]")
        raise typer.Exit(1) from None


@eval_app.command("results")
def eval_results(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    run_id: Annotated[str | None, typer.Option("--run-id", "-r", help="Specific run ID")] = None,
    set_name: Annotated[str | None, typer.Option("--set", "-s", help="Eval set name or ID")] = None,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table, json")
    ] = "table",
) -> None:
    """
    View evaluation results.

    Examples:
        # View results for specific run
        tracecraft eval results traces.db --run-id abc123

        # View latest results for a set
        tracecraft eval results traces.db --set quality-check
    """
    store = _get_sqlite_store(source)

    # Find run
    if run_id:
        run = store.get_evaluation_run(run_id)
        if not run:
            console.print(f"[red]Error: Run not found: {run_id}[/red]")
            raise typer.Exit(1)
    elif set_name:
        # Find eval set first
        eval_set = store.get_evaluation_set(set_name)
        if not eval_set:
            all_sets = store.list_evaluation_sets()
            for s in all_sets:
                if s.get("name") == set_name:
                    eval_set = store.get_evaluation_set(s["id"])
                    break

        if not eval_set:
            console.print(f"[red]Error: Evaluation set not found: {set_name}[/red]")
            raise typer.Exit(1)

        # Get latest run
        runs = store.list_evaluation_runs(set_id=eval_set["id"])
        if not runs:
            console.print("[yellow]No runs found for this evaluation set[/yellow]")
            raise typer.Exit(0)

        run = runs[0]  # Most recent
    else:
        # Show all recent runs
        runs = store.list_evaluation_runs()
        if not runs:
            console.print("[yellow]No evaluation runs found[/yellow]")
            raise typer.Exit(0)

        if format_type == "json":
            console.print(json.dumps(runs, indent=2, default=str))
            return

        table = Table(title="Recent Evaluation Runs")
        table.add_column("Run ID", style="dim")
        table.add_column("Set")
        table.add_column("Status")
        table.add_column("Passed", justify="right")
        table.add_column("Failed", justify="right")
        table.add_column("Pass Rate", justify="right")
        table.add_column("Time")

        for r in runs[:20]:
            rid = str(r.get("id", ""))[:8]
            set_id_short = str(r.get("evaluation_set_id", ""))[:8]
            status = r.get("status", "pending").upper()
            passed = str(r.get("passed_cases", 0))
            failed = str(r.get("failed_cases", 0))
            pr = r.get("overall_pass_rate")
            pass_rate_str = f"{pr * 100:.0f}%" if pr is not None else "-"
            started = r.get("started_at", "")[:19] if r.get("started_at") else "-"

            if r.get("passed"):
                pass_rate_str = f"[green]{pass_rate_str}[/green]"
            elif r.get("passed") is False:
                pass_rate_str = f"[red]{pass_rate_str}[/red]"

            table.add_row(rid, set_id_short, status, passed, failed, pass_rate_str, started)

        console.print(table)
        return

    # Show detailed results for specific run
    results = store.get_evaluation_results(run["id"])

    if format_type == "json":
        output = {
            "run": run,
            "results": results,
        }
        console.print(json.dumps(output, indent=2, default=str))
        return

    console.print(f"[bold]Evaluation Run: {str(run.get('id', ''))[:8]}[/bold]")
    console.print()

    # Summary
    summary_table = Table(show_header=False)
    summary_table.add_column("Key", style="cyan")
    summary_table.add_column("Value")

    summary_table.add_row("Status", run.get("status", "pending").upper())
    summary_table.add_row("Total", str(run.get("total_cases", 0)))
    summary_table.add_row("Passed", f"[green]{run.get('passed_cases', 0)}[/green]")
    summary_table.add_row("Failed", f"[red]{run.get('failed_cases', 0)}[/red]")

    pr = run.get("overall_pass_rate")
    if pr is not None:
        if run.get("passed"):
            summary_table.add_row("Pass Rate", f"[green]{pr * 100:.0f}%[/green]")
        else:
            summary_table.add_row("Pass Rate", f"[red]{pr * 100:.0f}%[/red]")

    console.print(summary_table)

    # Per-case results
    if results:
        console.print()
        console.print("[bold]Case Results:[/bold]")

        cases_table = Table()
        cases_table.add_column("Case", style="cyan")
        cases_table.add_column("Score", justify="right")
        cases_table.add_column("Result")
        cases_table.add_column("Error")

        for r in results:
            case_id = str(r.get("evaluation_case_id", ""))[:8]
            score = r.get("overall_score")
            score_str = f"{score:.2f}" if score is not None else "-"
            passed = r.get("passed", False)
            result_str = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            error = r.get("error", "") or "-"
            if len(error) > 30:
                error = error[:30] + "..."

            cases_table.add_row(case_id, score_str, result_str, error)

        console.print(cases_table)


@eval_app.command("export")
def eval_export(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    set_id: Annotated[str, typer.Argument(help="Evaluation set ID or name")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path")] = None,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format: json, yaml")
    ] = "json",
) -> None:
    """
    Export an evaluation set.

    Examples:
        tracecraft eval export traces.db quality-check -o eval-set.json
        tracecraft eval export traces.db quality-check --format yaml -o eval-set.yaml
    """
    store = _get_sqlite_store(source)

    # Find eval set
    eval_set = store.get_evaluation_set(set_id)
    if not eval_set:
        all_sets = store.list_evaluation_sets()
        for s in all_sets:
            if s.get("name") == set_id:
                eval_set = store.get_evaluation_set(s["id"])
                break

    if not eval_set:
        console.print(f"[red]Error: Evaluation set not found: {set_id}[/red]")
        raise typer.Exit(1)

    # Get cases
    cases = store.get_evaluation_cases(eval_set["id"])

    # Build export data
    export_data = {
        "name": eval_set.get("name"),
        "description": eval_set.get("description"),
        "metrics": eval_set.get("metrics", []),
        "default_threshold": eval_set.get("default_threshold", 0.7),
        "pass_rate_threshold": eval_set.get("pass_rate_threshold", 0.8),
        "cases": [
            {
                "name": c.get("name"),
                "input": c.get("input"),
                "expected_output": c.get("expected_output"),
                "retrieval_context": c.get("retrieval_context", []),
            }
            for c in cases
        ],
    }

    if format_type == "yaml":
        try:
            import yaml

            content = yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
        except ImportError:
            console.print(
                "[red]Error: PyYAML not installed. Install with: pip install pyyaml[/red]"
            )
            raise typer.Exit(1) from None
    else:
        content = json.dumps(export_data, indent=2, default=str)

    if output:
        output.write_text(content)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(content)


@eval_app.command("delete")
def eval_delete(
    source: Annotated[str, typer.Argument(help="SQLite database path")],
    set_id: Annotated[str, typer.Argument(help="Evaluation set ID or name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete an evaluation set."""
    store = _get_sqlite_store(source)

    # Find eval set
    eval_set = store.get_evaluation_set(set_id)
    if not eval_set:
        all_sets = store.list_evaluation_sets()
        for s in all_sets:
            if s.get("name") == set_id:
                eval_set = store.get_evaluation_set(s["id"])
                break

    if not eval_set:
        console.print(f"[red]Error: Evaluation set not found: {set_id}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete evaluation set '{eval_set.get('name')}'?")
        if not confirm:
            raise typer.Exit(0)

    try:
        store.delete_evaluation_set(eval_set["id"])
        console.print(f"[green]Deleted: {eval_set.get('name')}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
