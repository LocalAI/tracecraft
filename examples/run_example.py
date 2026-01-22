#!/usr/bin/env python3
"""Unified example runner for AgentTrace examples.

This utility helps discover, validate, and run AgentTrace examples.

Features:
    - List all available examples
    - Check dependencies before running
    - Run examples with proper environment
    - Filter by category
    - Verbose output mode

Usage:
    python run_example.py --list                              # List all examples
    python run_example.py 01-getting-started/01_hello_world.py  # Run example
    python run_example.py --check 06-evaluation/01_deepeval.py  # Check deps
    python run_example.py --list --category 04-production       # Filter by category
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent

# ANSI colors for terminal output
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def colorize(text: str, color: str) -> str:
    """Add ANSI color to text."""
    if not sys.stdout.isatty():
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def get_all_examples() -> list[Path]:
    """Find all example Python files."""
    examples = []
    for path in sorted(EXAMPLES_DIR.rglob("*.py")):
        # Skip utility files and __pycache__
        if path.name.startswith("_"):
            continue
        if "__pycache__" in str(path):
            continue
        if path.name == "run_example.py":
            continue
        # Skip files in service subdirectories (docker examples)
        if any(part in path.parts for part in ["gateway", "agent_service", "retrieval_service"]):
            continue
        examples.append(path)
    return examples


def get_example_metadata(path: Path) -> dict:
    """Extract metadata from example docstring.

    Parses the module docstring for:
    - Title (first line)
    - Description
    - Prerequisites
    - Environment Variables
    - External Services
    - Dependencies (extracted from imports)
    """
    metadata = {
        "title": path.stem,
        "description": "",
        "prerequisites": [],
        "env_vars": [],
        "services": [],
        "dependencies": [],
        "api_key_required": False,
    }

    try:
        content = path.read_text()

        # Parse the docstring
        tree = ast.parse(content)
        docstring = ast.get_docstring(tree)

        if docstring:
            lines = docstring.strip().split("\n")
            if lines:
                # First line is title
                metadata["title"] = lines[0].strip()

                # Parse sections
                current_section = "description"
                section_content: list[str] = []

                for line in lines[1:]:
                    line = line.strip()

                    # Check for section headers
                    if line.startswith("Prerequisites:"):
                        current_section = "prerequisites"
                        continue
                    elif line.startswith("Environment Variables:"):
                        current_section = "env_vars"
                        continue
                    elif line.startswith("External Services:"):
                        current_section = "services"
                        continue
                    elif line.startswith("Usage:"):
                        current_section = "usage"
                        continue
                    elif line.startswith("Expected Output:"):
                        current_section = "output"
                        continue

                    # Add content to current section
                    if line.startswith("- "):
                        item = line[2:].strip()
                        # Skip "None" entries
                        if item.lower() in ("none", "none required", "n/a"):
                            continue
                        if current_section == "prerequisites":
                            metadata["prerequisites"].append(item)
                        elif current_section == "env_vars":
                            metadata["env_vars"].append(item)
                        elif current_section == "services":
                            metadata["services"].append(item)
                    elif current_section == "description" and line:
                        section_content.append(line)

                metadata["description"] = " ".join(section_content)

        # Extract imports to detect dependencies
        dependencies = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    dependencies.add(module)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split(".")[0]
                    dependencies.add(module)

        # Map imports to pip packages
        pip_packages = {
            "langchain": "langchain",
            "langchain_openai": "langchain-openai",
            "langchain_community": "langchain-community",
            "langgraph": "langgraph",
            "llama_index": "llama-index-core",
            "pydantic_ai": "pydantic-ai",
            "openai": "openai",
            "deepeval": "deepeval",
            "ragas": "ragas",
            "mlflow": "mlflow",
            "httpx": "httpx",
        }

        for dep in dependencies:
            if dep in pip_packages:
                metadata["dependencies"].append(pip_packages[dep])

        # Check for API key usage
        api_key_patterns = [
            r"OPENAI_API_KEY",
            r"ANTHROPIC_API_KEY",
            r"GOOGLE_API_KEY",
            r"COHERE_API_KEY",
        ]
        for pattern in api_key_patterns:
            if re.search(pattern, content):
                metadata["api_key_required"] = True
                break

    except Exception as e:
        metadata["error"] = str(e)

    return metadata


def check_dependencies(example: Path) -> tuple[bool, list[str]]:
    """Check if all dependencies are installed.

    Returns:
        Tuple of (all_satisfied, list_of_missing)
    """
    metadata = get_example_metadata(example)
    missing = []

    for dep in metadata["dependencies"]:
        # Normalize package name
        normalized = dep.replace("-", "_").lower()
        spec = importlib.util.find_spec(normalized)
        if spec is None:
            missing.append(dep)

    return len(missing) == 0, missing


def run_example(example: Path, verbose: bool = False) -> int:
    """Run an example with proper environment.

    Returns:
        Exit code from the example
    """
    if not example.exists():
        # Try relative to examples dir
        example = EXAMPLES_DIR / example
        if not example.exists():
            print(colorize(f"Error: Example not found: {example}", "red"))
            return 1

    # Check dependencies first
    ok, missing = check_dependencies(example)
    if not ok:
        print(colorize("Missing dependencies:", "yellow"))
        for dep in missing:
            print(f"  - {dep}")
        print(f"\nInstall with: pip install {' '.join(missing)}")
        response = input("\nContinue anyway? [y/N] ")
        if response.lower() != "y":
            return 1

    # Get metadata for display
    metadata = get_example_metadata(example)

    print(colorize("=" * 60, "cyan"))
    print(colorize(f"Running: {metadata['title']}", "bold"))
    print(colorize("=" * 60, "cyan"))

    if verbose and metadata["description"]:
        print(f"\n{metadata['description']}\n")

    # Set up environment
    env = os.environ.copy()
    env["PYTHONPATH"] = str(EXAMPLES_DIR.parent / "src") + ":" + env.get("PYTHONPATH", "")

    # Run the example
    try:
        result = subprocess.run(
            [sys.executable, str(example)],
            env=env,
            cwd=str(example.parent),
        )
        return result.returncode
    except KeyboardInterrupt:
        print(colorize("\nInterrupted by user", "yellow"))
        return 130


def list_examples(category: str | None = None) -> None:
    """List available examples in table format."""
    examples = get_all_examples()

    if category:
        examples = [e for e in examples if category in str(e.relative_to(EXAMPLES_DIR))]

    if not examples:
        print(colorize("No examples found.", "yellow"))
        return

    # Group by category
    categories: dict[str, list[tuple[Path, dict]]] = {}
    for example in examples:
        rel_path = example.relative_to(EXAMPLES_DIR)
        parts = rel_path.parts
        cat = parts[0] if len(parts) > 1 else "root"

        if cat not in categories:
            categories[cat] = []

        metadata = get_example_metadata(example)
        categories[cat].append((example, metadata))

    # Print grouped examples
    print(colorize("\nAgentTrace Examples", "bold"))
    print(colorize("=" * 70, "cyan"))

    for cat in sorted(categories.keys()):
        print(colorize(f"\n{cat}/", "blue"))
        print("-" * 70)

        for example, metadata in categories[cat]:
            rel_path = example.relative_to(EXAMPLES_DIR)
            title = metadata.get("title", example.stem)[:40]

            # Status indicators
            indicators = []
            if metadata.get("api_key_required"):
                indicators.append(colorize("[API]", "yellow"))
            if metadata.get("services"):
                indicators.append(colorize("[SVC]", "cyan"))
            if metadata.get("dependencies"):
                ok, _ = check_dependencies(example)
                if not ok:
                    indicators.append(colorize("[DEPS]", "red"))

            indicator_str = " ".join(indicators)

            print(f"  {str(rel_path):<45} {title:<25} {indicator_str}")

    print(colorize("\n" + "=" * 70, "cyan"))
    print(f"Total: {len(examples)} examples in {len(categories)} categories")
    print("\nLegend:")
    print(f"  {colorize('[API]', 'yellow')} - Requires API key")
    print(f"  {colorize('[SVC]', 'cyan')} - Requires external service")
    print(f"  {colorize('[DEPS]', 'red')} - Missing dependencies")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run AgentTrace examples",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                              List all examples
  %(prog)s --list --category 04-production     List examples in category
  %(prog)s 01-getting-started/01_hello_world.py  Run specific example
  %(prog)s --check 06-evaluation/01_deepeval.py  Check dependencies
        """,
    )

    parser.add_argument(
        "example",
        nargs="?",
        help="Example path to run (relative to examples/)",
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available examples",
    )
    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Check dependencies for an example",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--category",
        help="Filter examples by category",
    )

    args = parser.parse_args()

    if args.list:
        list_examples(args.category)
    elif args.check and args.example:
        example_path = Path(args.example)
        if not example_path.is_absolute():
            example_path = EXAMPLES_DIR / example_path

        ok, missing = check_dependencies(example_path)
        if ok:
            print(colorize("All dependencies satisfied!", "green"))
        else:
            print(colorize("Missing dependencies:", "red"))
            for dep in missing:
                print(f"  - {dep}")
            print(f"\nInstall with: pip install {' '.join(missing)}")
            sys.exit(1)
    elif args.example:
        example_path = Path(args.example)
        if not example_path.is_absolute():
            example_path = EXAMPLES_DIR / example_path
        sys.exit(run_example(example_path, args.verbose))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
