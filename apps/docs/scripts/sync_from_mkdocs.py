#!/usr/bin/env python3
"""Sync documentation from MkDocs (docs/) to Nextra (apps/docs/pages/).

This script converts MkDocs Material markdown syntax to Nextra MDX format,
enabling a single source of truth for documentation while supporting both
documentation systems.

Usage:
    python scripts/sync_from_mkdocs.py [--dry-run] [--verbose] [--file PATH]

The script handles these conversions:
- `??? question "title"` -> `<Details>` component
- `!!! note/warning/tip` -> `<Callout>` component
- `=== "Tab"` -> `<Tabs>` component
- Code block titles -> Comments above code blocks
- MkDocs grid cards -> Nextra `<Cards>` components
- Internal link path adjustments
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import NamedTuple


class ConversionResult(NamedTuple):
    """Result of converting a single file."""

    source: Path
    destination: Path
    success: bool
    imports_needed: set[str]
    error: str | None = None


# Mapping from MkDocs admonition types to Nextra Callout types
ADMONITION_TYPE_MAP = {
    "note": "info",
    "info": "info",
    "tip": "info",
    "hint": "info",
    "success": "info",
    "question": "info",
    "warning": "warning",
    "caution": "warning",
    "attention": "warning",
    "danger": "error",
    "error": "error",
    "bug": "error",
    "failure": "error",
    "example": "default",
    "quote": "default",
    "abstract": "default",
    "summary": "default",
    "tldr": "default",
}


class MkDocsToNextraConverter:
    """Converts MkDocs Material markdown to Nextra MDX format."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.imports_needed: set[str] = set()

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"  {message}")

    def convert(self, content: str) -> str:
        """Convert MkDocs markdown content to Nextra MDX format."""
        self.imports_needed = set()

        # Order matters - process complex patterns first
        content = self._convert_collapsible_admonitions(content)
        content = self._convert_admonitions(content)
        content = self._convert_tabs(content)
        content = self._convert_code_titles(content)
        content = self._convert_grid_cards(content)
        content = self._convert_internal_links(content)
        content = self._cleanup_mkdocs_specific(content)

        # Add imports at the top
        content = self._add_imports(content)

        return content

    def _convert_collapsible_admonitions(self, content: str) -> str:
        """Convert MkDocs collapsible admonitions (???) to <Details> components."""
        # Ensure content ends with newline for consistent matching
        if not content.endswith("\n"):
            content += "\n"

        # Pattern: ??? type "title"
        #     content (indented by 4 spaces)
        # Match indented lines or blank lines, until we hit a non-indented non-blank line
        pattern = r'^\?\?\?(\+)?\s+(\w+)\s+"([^"]+)"\n((?:    .*\n|\s*\n)*)'

        def replace_collapsible(match: re.Match) -> str:
            is_open = match.group(1) == "+"
            _admon_type = match.group(2)  # noqa: F841 - captured for potential future use
            title = match.group(3)
            body = match.group(4)

            # Remove 4-space indentation from body
            body_lines = []
            for line in body.split("\n"):
                if line.startswith("    "):
                    body_lines.append(line[4:])
                elif line.strip() == "":
                    body_lines.append("")
                else:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()

            self.imports_needed.add("Details")
            self.log(f"Converting collapsible admonition: {title}")

            open_attr = " open" if is_open else ""
            return f'<Details summary="{title}"{open_attr}>\n{body}\n</Details>\n\n'

        return re.sub(pattern, replace_collapsible, content, flags=re.MULTILINE)

    def _convert_admonitions(self, content: str) -> str:
        """Convert MkDocs admonitions (!!!) to <Callout> components."""
        # Ensure content ends with newline for consistent matching
        if not content.endswith("\n"):
            content += "\n"

        # Pattern: !!! type "optional title"
        #     content (indented by 4 spaces)
        # Match indented lines or blank lines
        pattern = r'^!!!\s+(\w+)(?:\s+"([^"]+)")?\n((?:    .*\n|\s*\n)*)'

        def replace_admonition(match: re.Match) -> str:
            admon_type = match.group(1).lower()
            title = match.group(2)
            body = match.group(3)

            # Remove 4-space indentation from body
            body_lines = []
            for line in body.split("\n"):
                if line.startswith("    "):
                    body_lines.append(line[4:])
                elif line.strip() == "":
                    body_lines.append("")
                else:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()

            callout_type = ADMONITION_TYPE_MAP.get(admon_type, "default")
            self.imports_needed.add("Callout")
            self.log(f"Converting admonition: {admon_type} -> {callout_type}")

            if title:
                return f'<Callout type="{callout_type}" title="{title}">\n{body}\n</Callout>\n\n'
            else:
                return f'<Callout type="{callout_type}">\n{body}\n</Callout>\n\n'

        return re.sub(pattern, replace_admonition, content, flags=re.MULTILINE)

    def _convert_tabs(self, content: str) -> str:
        """Convert MkDocs tabs (===) to <Tabs> components."""
        # Ensure content ends with newline for consistent matching
        if not content.endswith("\n"):
            content += "\n"

        # Find tab groups - consecutive === blocks
        # A tab group is: === "name"\n followed by indented content, repeated
        # We need to match multiple consecutive tabs as a single group
        tab_group_pattern = (
            r'(^===\s+"[^"]+"\n(?:    .*\n|\s*\n)*(?:^===\s+"[^"]+"\n(?:    .*\n|\s*\n)*)*)'
        )

        def replace_tab_group(match: re.Match) -> str:
            tab_content = match.group(1)

            # Extract individual tabs
            # Each tab starts with === "name" and includes all following indented lines
            tab_pattern = r'^===\s+"([^"]+)"\n((?:    .*\n|\s*\n)*)'
            tabs = re.findall(tab_pattern, tab_content, re.MULTILINE)

            if not tabs:
                return tab_content

            self.imports_needed.add("Tabs")
            self.log(f"Converting tab group with {len(tabs)} tabs")

            # Build Nextra Tabs component
            tab_names = [tab[0] for tab in tabs]
            items_str = ", ".join(f"'{name}'" for name in tab_names)

            result = f"<Tabs items={{[{items_str}]}}>\n"
            for _name, body in tabs:
                # Remove 4-space indentation and strip
                body_lines = []
                for line in body.split("\n"):
                    if line.startswith("    "):
                        body_lines.append(line[4:])
                    elif line.strip() == "":
                        body_lines.append("")
                    else:
                        body_lines.append(line)
                body = "\n".join(body_lines).strip()
                result += f"<Tabs.Tab>\n{body}\n</Tabs.Tab>\n"
            result += "</Tabs>\n\n"

            return result

        return re.sub(tab_group_pattern, replace_tab_group, content, flags=re.MULTILINE)

    def _convert_code_titles(self, content: str) -> str:
        """Convert code block titles from MkDocs format to comments."""
        # Pattern: ```language title="filename"
        pattern = r'```(\w+)\s+title="([^"]+)"'

        def replace_code_title(match: re.Match) -> str:
            language = match.group(1)
            title = match.group(2)
            self.log(f"Converting code title: {title}")
            # Add filename as a comment above the code block
            return f"{{/* {title} */}}\n```{language}"

        return re.sub(pattern, replace_code_title, content)

    def _convert_grid_cards(self, content: str) -> str:
        """Convert MkDocs Material grid cards to Nextra Cards components."""
        # Pattern for MkDocs grid cards (HTML-based)
        # <div class="grid cards" markdown>
        # -   :icon: **Title**
        #     ---
        #     Description
        #     [:octicons-arrow-right-24: Link Text](url)
        # </div>

        # Also handle the simpler markdown link-based cards
        # - :icon: [**Title**](url) - Description

        # For now, handle the common case of card grids
        grid_pattern = r'<div class="grid cards"[^>]*>\s*(.*?)\s*</div>'

        def replace_grid(match: re.Match) -> str:
            grid_content = match.group(1)
            self.imports_needed.add("Cards")
            self.imports_needed.add("Card")

            # Try to parse card items
            # Pattern: -   :icon: **Title**\n    ---\n    Description\n    [:...: Text](url)
            card_pattern = r"-\s+:[\w-]+:\s+\*\*([^*]+)\*\*\s*\n\s+---\s*\n\s+([^\n]+)\s*\n\s+\[:[^\]]+:\s+[^\]]+\]\(([^)]+)\)"
            cards = re.findall(card_pattern, grid_content)

            if not cards:
                # Try simpler pattern
                card_pattern = r"-\s+\[([^\]]+)\]\(([^)]+)\)\s*[:-]?\s*(.+)?"
                cards = re.findall(card_pattern, grid_content)
                if cards:
                    cards = [(c[0].replace("**", ""), c[2] or "", c[1]) for c in cards]

            if not cards:
                self.log("Could not parse grid cards, keeping original")
                return match.group(0)

            self.log(f"Converting grid with {len(cards)} cards")

            result = "<Cards>\n"
            for title, description, href in cards:
                title = title.strip()
                description = description.strip()
                href = self._convert_link_path(href)
                result += f'  <Card title="{title}" href="{href}">\n    {description}\n  </Card>\n'
            result += "</Cards>\n"

            return result

        content = re.sub(grid_pattern, replace_grid, content, flags=re.DOTALL)

        return content

    def _convert_internal_links(self, content: str) -> str:
        """Convert internal documentation links to Nextra paths."""
        # Convert .md extensions to no extension (Nextra routing)
        content = re.sub(
            r"\]\(([^)]+)\.md\)", lambda m: f"]({self._convert_link_path(m.group(1))})", content
        )

        # Convert relative paths that go up directories
        # ../integrations/langchain.md -> /integrations/langchain
        content = re.sub(
            r"\]\(\.\./([^)]+)\)",
            lambda m: f"](/{m.group(1).replace('.md', '')})",
            content,
        )

        return content

    def _convert_link_path(self, path: str) -> str:
        """Convert a single link path from MkDocs to Nextra format."""
        # Remove .md extension
        path = re.sub(r"\.md$", "", path)

        # Handle relative paths
        if path.startswith("../"):
            path = "/" + path.replace("../", "")

        # Ensure leading slash for absolute paths
        if not path.startswith("/") and not path.startswith("http") and not path.startswith("#"):
            path = "/" + path

        return path

    def _cleanup_mkdocs_specific(self, content: str) -> str:
        """Remove or convert MkDocs-specific syntax that doesn't have a Nextra equivalent."""
        # Remove [TOC] markers
        content = re.sub(r"^\[TOC\]\s*$", "", content, flags=re.MULTILINE)

        # Remove mkdocs-material specific attributes like {: .grid }
        content = re.sub(r"\{:\s*[^}]+\}", "", content)

        # Convert horizontal rules (--- is valid in both, but clean up extras)
        content = re.sub(r"\n---+\n", "\n---\n", content)

        return content

    def _add_imports(self, content: str) -> str:
        """Add necessary imports at the top of the file."""
        if not self.imports_needed:
            return content

        imports = []

        # Nextra built-in components
        nextra_components = {"Tabs", "Callout", "Steps", "FileTree"}
        nextra_imports = self.imports_needed & nextra_components
        if nextra_imports:
            imports.append(
                f"import {{ {', '.join(sorted(nextra_imports))} }} from 'nextra/components'"
            )

        # Custom components
        custom_components = {"Cards", "Card", "Details"}
        custom_imports = self.imports_needed & custom_components
        if custom_imports:
            imports.append(f"import {{ {', '.join(sorted(custom_imports))} }} from '@/components'")

        if imports:
            import_block = "\n".join(imports) + "\n\n"
            return import_block + content

        return content


def get_destination_path(source: Path, docs_root: Path, pages_root: Path) -> Path:
    """Calculate the destination path for a source file."""
    relative = source.relative_to(docs_root)
    # Change extension from .md to .mdx
    dest = pages_root / relative.with_suffix(".mdx")
    return dest


def get_meta_entries_for_dir(pages_dir: Path) -> dict[str, str]:
    """Generate _meta.ts entries for files in a directory."""
    entries = {}

    for mdx_file in sorted(pages_dir.glob("*.mdx")):
        name = mdx_file.stem
        # Convert kebab-case to Title Case
        title = "Overview" if name == "index" else name.replace("-", " ").title()
        entries[name] = title

    return entries


def update_meta_file(pages_dir: Path, new_entries: dict[str, str], verbose: bool = False) -> None:
    """Update or create _meta.ts file with new entries."""
    meta_file = pages_dir / "_meta.ts"

    existing_entries: dict[str, str] = {}

    # Parse existing _meta.ts if it exists
    if meta_file.exists():
        content = meta_file.read_text()
        # Simple regex to extract key-value pairs
        pattern = r"['\"]?([\w-]+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern, content):
            existing_entries[match.group(1)] = match.group(2)

    # Merge entries (new entries take precedence for new files, keep existing titles)
    merged = existing_entries.copy()
    for key, value in new_entries.items():
        if key not in merged:
            merged[key] = value
            if verbose:
                print(f"    Adding to _meta.ts: {key} = {value}")

    # Generate new _meta.ts content
    lines = ["export default {"]
    for key, value in merged.items():
        # Use quotes for keys with hyphens
        if "-" in key:
            lines.append(f"  '{key}': '{value}',")
        else:
            lines.append(f"  {key}: '{value}',")
    lines.append("}")

    meta_file.write_text("\n".join(lines) + "\n")


def sync_docs(
    docs_root: Path,
    pages_root: Path,
    dry_run: bool = False,
    verbose: bool = False,
    single_file: Path | None = None,
) -> list[ConversionResult]:
    """Sync documentation from MkDocs to Nextra format.

    Args:
        docs_root: Path to the MkDocs docs/ directory
        pages_root: Path to the Nextra pages/ directory
        dry_run: If True, don't write files, just show what would be done
        verbose: If True, print detailed progress
        single_file: If provided, only sync this specific file

    Returns:
        List of ConversionResult objects describing what was done
    """
    results: list[ConversionResult] = []
    converter = MkDocsToNextraConverter(verbose=verbose)

    # Directories to skip (they may have different structure in Nextra)
    skip_dirs = {"overrides", "stylesheets", "javascripts"}

    # Files to skip
    skip_files = {"CNAME"}

    # Get list of files to process
    if single_file:
        if single_file.exists():
            md_files = [single_file]
        else:
            print(f"Error: File not found: {single_file}")
            return results
    else:
        md_files = list(docs_root.rglob("*.md"))

    # Track which directories have new files
    updated_dirs: set[Path] = set()

    for source in md_files:
        # Skip files in excluded directories
        if any(skip_dir in source.parts for skip_dir in skip_dirs):
            continue

        # Skip excluded files
        if source.name in skip_files:
            continue

        dest = get_destination_path(source, docs_root, pages_root)

        if verbose:
            print(f"Processing: {source.relative_to(docs_root)}")

        try:
            # Read source content
            content = source.read_text(encoding="utf-8")

            # Convert to Nextra format
            converted = converter.convert(content)

            if dry_run:
                print(f"Would write: {dest}")
                if verbose and converter.imports_needed:
                    print(f"  Imports needed: {converter.imports_needed}")
            else:
                # Ensure destination directory exists
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Write converted content
                dest.write_text(converted, encoding="utf-8")

                if verbose:
                    print(f"  Wrote: {dest}")

                # Track this directory for _meta.ts updates
                updated_dirs.add(dest.parent)

            results.append(
                ConversionResult(
                    source=source,
                    destination=dest,
                    success=True,
                    imports_needed=converter.imports_needed.copy(),
                )
            )

        except Exception as e:
            print(f"Error processing {source}: {e}")
            results.append(
                ConversionResult(
                    source=source,
                    destination=dest,
                    success=False,
                    imports_needed=set(),
                    error=str(e),
                )
            )

    # Update _meta.ts files for directories with new content
    if not dry_run:
        for pages_dir in updated_dirs:
            if verbose:
                print(f"Updating _meta.ts in: {pages_dir}")
            new_entries = get_meta_entries_for_dir(pages_dir)
            update_meta_file(pages_dir, new_entries, verbose=verbose)

    return results


def main() -> None:
    """Main entry point for the sync script."""
    parser = argparse.ArgumentParser(
        description="Sync documentation from MkDocs to Nextra format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed progress information",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Sync only a specific file",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=None,
        help="Path to MkDocs docs/ directory (default: auto-detect)",
    )
    parser.add_argument(
        "--pages-root",
        type=Path,
        default=None,
        help="Path to Nextra pages/ directory (default: auto-detect)",
    )

    args = parser.parse_args()

    # Auto-detect paths if not provided
    script_dir = Path(__file__).parent
    apps_docs_dir = script_dir.parent  # apps/docs/
    project_root = apps_docs_dir.parent.parent  # project root

    docs_root = args.docs_root or (project_root / "docs")
    pages_root = args.pages_root or (apps_docs_dir / "pages")

    if not docs_root.exists():
        print(f"Error: MkDocs docs directory not found: {docs_root}")
        return

    if not pages_root.exists():
        print(f"Error: Nextra pages directory not found: {pages_root}")
        return

    print(f"Syncing from: {docs_root}")
    print(f"Syncing to: {pages_root}")

    if args.dry_run:
        print("DRY RUN - no changes will be made")

    print()

    results = sync_docs(
        docs_root=docs_root,
        pages_root=pages_root,
        dry_run=args.dry_run,
        verbose=args.verbose,
        single_file=args.file,
    )

    # Print summary
    successful = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)

    print()
    print(f"Processed {len(results)} files: {successful} successful, {failed} failed")

    if failed > 0:
        print("\nFailed files:")
        for r in results:
            if not r.success:
                print(f"  {r.source}: {r.error}")


if __name__ == "__main__":
    main()
