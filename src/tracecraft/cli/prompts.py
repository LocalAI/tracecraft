"""
CLI commands for managing comparison prompts.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tracecraft.comparison.prompts import PromptManager

app = typer.Typer(
    name="prompts",
    help="Manage comparison prompts for trace analysis",
    add_completion=False,
)

console = Console()


@app.command("list")
def list_prompts() -> None:
    """List all available comparison prompts."""
    manager = PromptManager()
    prompts = manager.list_prompts()

    if not prompts:
        console.print("[yellow]No prompts available[/yellow]")
        return

    table = Table(title="Comparison Prompts")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Type", style="dim")

    for p in prompts:
        table.add_row(
            p.id,
            p.name,
            p.description or "-",
            "[blue]builtin[/blue]" if p.is_builtin else "[green]custom[/green]",
        )

    console.print(table)


@app.command("show")
def show_prompt(
    prompt_id: Annotated[str, typer.Argument(help="Prompt ID to show")],
) -> None:
    """Show details of a comparison prompt."""
    manager = PromptManager()
    prompt = manager.get_prompt(prompt_id)

    if not prompt:
        console.print(f"[red]Prompt not found: {prompt_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]{prompt.name}[/bold cyan] ({prompt.id})")
    console.print(f"Type: {'builtin' if prompt.is_builtin else 'custom'}")

    if prompt.description:
        console.print(f"Description: {prompt.description}")

    console.print()
    console.print("[bold]Template:[/bold]")
    console.print(prompt.template)


@app.command("add")
def add_prompt(
    name: Annotated[str, typer.Argument(help="Name for the new prompt")],
    template: Annotated[
        str,
        typer.Option(
            "--template", "-t", help="Prompt template with {trace_a} and {trace_b} placeholders"
        ),
    ],
    description: Annotated[
        str,
        typer.Option("--description", "-d", help="Description of what the prompt does"),
    ] = "",
) -> None:
    """
    Add a custom comparison prompt.

    The template should contain {trace_a} and {trace_b} placeholders
    that will be replaced with the trace data when comparing.

    Example:
        tracecraft prompts add "My Prompt" -t "Compare {trace_a} with {trace_b}"
    """
    manager = PromptManager()

    # Validate template has required placeholders
    if "{trace_a}" not in template or "{trace_b}" not in template:
        console.print(
            "[red]Error: Template must contain {trace_a} and {trace_b} placeholders[/red]"
        )
        raise typer.Exit(1)

    try:
        prompt = manager.add_prompt(name, template, description)
        console.print(f"[green]Added prompt: {prompt.id}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding prompt: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("remove")
def remove_prompt(
    prompt_id: Annotated[str, typer.Argument(help="Prompt ID to remove")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Remove without confirmation"),
    ] = False,
) -> None:
    """
    Remove a custom comparison prompt.

    Builtin prompts cannot be removed.
    """
    manager = PromptManager()
    prompt = manager.get_prompt(prompt_id)

    if not prompt:
        console.print(f"[red]Prompt not found: {prompt_id}[/red]")
        raise typer.Exit(1)

    if prompt.is_builtin:
        console.print(f"[red]Cannot remove builtin prompt: {prompt_id}[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove prompt '{prompt.name}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    if manager.remove_prompt(prompt_id):
        console.print(f"[green]Removed prompt: {prompt_id}[/green]")
    else:
        console.print(f"[red]Failed to remove prompt: {prompt_id}[/red]")
        raise typer.Exit(1)


@app.command("import")
def import_prompt(
    file_path: Annotated[str, typer.Argument(help="Path to prompt file (.txt)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Name for the prompt")],
    description: Annotated[
        str,
        typer.Option("--description", "-d", help="Description"),
    ] = "",
) -> None:
    """
    Import a prompt from a text file.

    The file should contain the prompt template with {trace_a} and {trace_b}
    placeholders.
    """
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(1)

    try:
        template = path.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(1) from None

    # Validate template
    if "{trace_a}" not in template or "{trace_b}" not in template:
        console.print(
            "[red]Error: Template must contain {trace_a} and {trace_b} placeholders[/red]"
        )
        raise typer.Exit(1)

    manager = PromptManager()
    try:
        prompt = manager.add_prompt(name, template, description)
        console.print(f"[green]Imported prompt: {prompt.id}[/green]")
    except Exception as e:
        console.print(f"[red]Error importing prompt: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("export")
def export_prompt(
    prompt_id: Annotated[str, typer.Argument(help="Prompt ID to export")],
    output: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
) -> None:
    """Export a prompt template to a file."""
    from pathlib import Path

    manager = PromptManager()
    prompt = manager.get_prompt(prompt_id)

    if not prompt:
        console.print(f"[red]Prompt not found: {prompt_id}[/red]")
        raise typer.Exit(1)

    if output:
        path = Path(output)
        path.write_text(prompt.template, encoding="utf-8")
        console.print(f"[green]Exported to: {output}[/green]")
    else:
        # Print to stdout
        console.print(prompt.template)
