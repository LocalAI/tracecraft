"""
HTML report exporter.

Generates self-contained HTML reports with embedded trace data.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agenttrace.exporters.base import BaseExporter

if TYPE_CHECKING:
    from agenttrace.core.models import AgentRun, Step


class HTMLExporter(BaseExporter):
    """
    Exports traces as self-contained HTML reports.

    The HTML report includes embedded CSS and JavaScript for
    interactive viewing without external dependencies.
    """

    def __init__(self, filepath: str | Path | None = None) -> None:
        """
        Initialize the HTML exporter.

        Args:
            filepath: Optional path for output file.
        """
        self.filepath = Path(filepath) if filepath else None

    def export(self, run: AgentRun) -> None:
        """
        Export an agent run as an HTML file.

        Args:
            run: The AgentRun to export.
        """
        html_content = self.render(run)

        if self.filepath:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.filepath.write_text(html_content, encoding="utf-8")

    def render(self, run: AgentRun) -> str:
        """
        Render an agent run as HTML string.

        Args:
            run: The AgentRun to render.

        Returns:
            HTML string.
        """
        trace_json = self._serialize_run(run)
        steps_html = self._render_steps(run.steps)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';">
    <title>AgentTrace - {html.escape(run.name)}</title>
    <style>
        {self._get_styles()}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html.escape(run.name)}</h1>
            {self._render_run_metadata(run)}
        </header>

        <section class="controls">
            <div class="search-box">
                <input type="text" id="search-input" placeholder="Search steps..." onkeyup="filterSteps()">
            </div>
            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all" onclick="filterByType('all')">All</button>
                <button class="filter-btn" data-filter="llm" onclick="filterByType('llm')">LLM</button>
                <button class="filter-btn" data-filter="tool" onclick="filterByType('tool')">Tool</button>
                <button class="filter-btn" data-filter="agent" onclick="filterByType('agent')">Agent</button>
                <button class="filter-btn" data-filter="retrieval" onclick="filterByType('retrieval')">Retrieval</button>
            </div>
            <div class="view-buttons">
                <button class="view-btn active" onclick="showView('tree')">Tree View</button>
                <button class="view-btn" onclick="showView('timeline')">Timeline</button>
            </div>
        </section>

        <section class="trace-view" id="tree-view">
            <h2>Trace Steps</h2>
            <div class="steps-tree">
                {steps_html}
            </div>
        </section>

        <section class="timeline-view" id="timeline-view" style="display:none;">
            <h2>Timeline</h2>
            <div id="timeline-container"></div>
        </section>

        <section class="json-view">
            <details>
                <summary>Raw JSON Data</summary>
                <pre><code>{html.escape(json.dumps(trace_json, indent=2))}</code></pre>
            </details>
        </section>
    </div>

    <script>
        const traceData = {self._safe_json_for_script(trace_json)};
        {self._get_script()}
    </script>
</body>
</html>"""

    def _serialize_run(self, run: AgentRun) -> dict[str, Any]:
        """Serialize run to JSON-safe dict."""
        data: dict[str, Any] = json.loads(run.model_dump_json())
        return data

    def _safe_json_for_script(self, data: dict[str, Any]) -> str:
        """Serialize JSON safely for embedding in script tags."""
        # Escape characters to prevent XSS:
        # - < and > prevent </script> injection
        # - & prevents HTML entity injection
        # - U+2028/U+2029 are line terminators that break JS string literals
        json_str = json.dumps(data)
        json_str = json_str.replace("&", "\\u0026")  # Must be first
        json_str = json_str.replace("<", "\\u003c")
        json_str = json_str.replace(">", "\\u003e")
        json_str = json_str.replace("\u2028", "\\u2028")  # Line separator
        json_str = json_str.replace("\u2029", "\\u2029")  # Paragraph separator
        return json_str

    def _render_run_metadata(self, run: AgentRun) -> str:
        """Render run metadata section."""
        parts = []

        if run.description:
            parts.append(f'<p class="description">{html.escape(run.description)}</p>')

        parts.append('<div class="metadata">')

        if run.duration_ms is not None:
            parts.append(f'<span class="duration">Duration: {run.duration_ms:.1f}ms</span>')

        if run.total_tokens:
            parts.append(f'<span class="tokens">Tokens: {run.total_tokens}</span>')

        if run.total_cost_usd:
            parts.append(f'<span class="cost">Cost: ${run.total_cost_usd:.4f}</span>')

        if run.error_count:
            parts.append(f'<span class="errors">Errors: {run.error_count}</span>')

        if run.tags:
            tags_html = " ".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in run.tags)
            parts.append(f'<div class="tags">{tags_html}</div>')

        parts.append("</div>")

        return "\n".join(parts)

    def _render_steps(self, steps: list[Step]) -> str:
        """Render steps as HTML tree."""
        if not steps:
            return '<p class="no-steps">No steps recorded</p>'

        parts = ['<ul class="step-list">']
        for step in steps:
            parts.append(self._render_step(step))
        parts.append("</ul>")

        return "\n".join(parts)

    def _render_step(self, step: Step) -> str:
        """Render a single step."""
        # step.type.value is from StepType enum - guaranteed safe lowercase
        # alphanumeric values (e.g., "agent", "llm", "tool"). No escaping needed
        # for CSS class names built from these values.
        step_type = step.type.value
        step_class = f"step step-{step_type}"

        if step.error:
            step_class += " step-error"

        parts = [f'<li class="{step_class}">']
        parts.append("<details open>")
        parts.append('<summary class="step-header" onclick="toggleStep(this)">')
        parts.append(f'<span class="step-type">{step_type.upper()}</span>')
        parts.append(f'<span class="step-name">{html.escape(step.name)}</span>')

        if step.duration_ms is not None:
            parts.append(f'<span class="step-duration">{step.duration_ms:.1f}ms</span>')

        parts.append("</summary>")

        # Step details
        parts.append('<div class="step-details">')

        # Model info
        if step.model_name:
            parts.append(f'<div class="model-info">Model: {html.escape(step.model_name)}</div>')

        # Token info
        if step.input_tokens is not None or step.output_tokens is not None:
            tokens_parts = []
            if step.input_tokens is not None:
                tokens_parts.append(f"Input: {step.input_tokens}")
            if step.output_tokens is not None:
                tokens_parts.append(f"Output: {step.output_tokens}")
            parts.append(f'<div class="token-info">Tokens: {", ".join(tokens_parts)}</div>')

        # Error info
        if step.error:
            parts.append('<div class="error-info">')
            parts.append(
                f'<span class="error-type">{html.escape(step.error_type or "Error")}</span>'
            )
            parts.append(f'<span class="error-message">{html.escape(step.error)}</span>')
            parts.append("</div>")

        # Inputs
        if step.inputs:
            parts.append('<details class="io-section">')
            parts.append("<summary>Inputs</summary>")
            parts.append(f"<pre>{html.escape(json.dumps(step.inputs, indent=2))}</pre>")
            parts.append("</details>")

        # Outputs
        if step.outputs:
            parts.append('<details class="io-section">')
            parts.append("<summary>Outputs</summary>")
            parts.append(f"<pre>{html.escape(json.dumps(step.outputs, indent=2))}</pre>")
            parts.append("</details>")

        parts.append("</div>")

        # Children
        if step.children:
            parts.append(self._render_steps(step.children))

        parts.append("</details>")
        parts.append("</li>")

        return "\n".join(parts)

    def _get_styles(self) -> str:
        """Get CSS styles."""
        return """
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        h1 { margin: 0 0 10px 0; color: #1a1a1a; }
        h2 { color: #444; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .description { color: #666; margin: 10px 0; }
        .metadata { display: flex; flex-wrap: wrap; gap: 15px; margin-top: 15px; }
        .metadata span { background: #f0f0f0; padding: 5px 10px; border-radius: 4px; font-size: 14px; }
        .errors { background: #ffe0e0 !important; color: #c00; }
        .tags { display: flex; gap: 5px; }
        .tag { background: #e0e7ff; color: #3730a3; padding: 3px 8px; border-radius: 3px; font-size: 12px; }

        .trace-view { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .step-list { list-style: none; padding-left: 20px; margin: 0; }
        .step { margin: 10px 0; }
        .step-header { cursor: pointer; padding: 10px; background: #f8f9fa; border-radius: 4px; display: flex; gap: 10px; align-items: center; }
        .step-header:hover { background: #e9ecef; }
        .step-type { font-weight: bold; padding: 2px 8px; border-radius: 3px; font-size: 12px; text-transform: uppercase; }
        .step-llm .step-type { background: #dbeafe; color: #1d4ed8; }
        .step-tool .step-type { background: #dcfce7; color: #166534; }
        .step-agent .step-type { background: #fef3c7; color: #92400e; }
        .step-retrieval .step-type { background: #f3e8ff; color: #7c3aed; }
        .step-workflow .step-type { background: #e0e7ff; color: #3730a3; }
        .step-error .step-header { background: #fef2f2; border-left: 3px solid #ef4444; }
        .step-name { flex-grow: 1; }
        .step-duration { color: #666; font-size: 13px; }

        .step-details { padding: 10px 15px; border-left: 2px solid #e5e7eb; margin-left: 10px; }
        .model-info, .token-info { font-size: 13px; color: #666; margin: 5px 0; }
        .error-info { background: #fef2f2; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .error-type { font-weight: bold; color: #b91c1c; }
        .error-message { display: block; margin-top: 5px; color: #7f1d1d; }

        .io-section { margin: 10px 0; }
        .io-section summary { cursor: pointer; color: #4b5563; font-size: 13px; }
        .io-section pre { background: #f8f9fa; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; }

        .json-view { background: #fff; padding: 20px; border-radius: 8px; }
        .json-view summary { cursor: pointer; font-weight: bold; }
        .json-view pre { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 4px; overflow-x: auto; }

        .no-steps { color: #666; font-style: italic; }
        details > summary { list-style: none; }
        details > summary::-webkit-details-marker { display: none; }

        /* Controls */
        .controls { background: #fff; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }
        .search-box input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; width: 250px; font-size: 14px; }
        .search-box input:focus { outline: none; border-color: #3b82f6; }
        .filter-buttons, .view-buttons { display: flex; gap: 5px; }
        .filter-btn, .view-btn { padding: 6px 12px; border: 1px solid #ddd; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; }
        .filter-btn:hover, .view-btn:hover { background: #f3f4f6; }
        .filter-btn.active, .view-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
        .step.hidden { display: none; }

        /* Timeline View */
        .timeline-view { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .timeline-container { position: relative; padding: 20px 0; }
        .timeline-bar { height: 30px; margin: 5px 0; border-radius: 4px; position: relative; cursor: pointer; transition: opacity 0.2s; }
        .timeline-bar:hover { opacity: 0.8; }
        .timeline-bar.type-llm { background: #dbeafe; border-left: 3px solid #1d4ed8; }
        .timeline-bar.type-tool { background: #dcfce7; border-left: 3px solid #166534; }
        .timeline-bar.type-agent { background: #fef3c7; border-left: 3px solid #92400e; }
        .timeline-bar.type-retrieval { background: #f3e8ff; border-left: 3px solid #7c3aed; }
        .timeline-bar.type-workflow { background: #e0e7ff; border-left: 3px solid #3730a3; }
        .timeline-bar.type-memory { background: #fce7f3; border-left: 3px solid #be185d; }
        .timeline-bar.has-error { border-right: 3px solid #ef4444; }
        .timeline-label { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: calc(100% - 20px); }
        .timeline-duration { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 11px; color: #666; }
        .timeline-axis { border-top: 1px solid #e5e7eb; margin-top: 10px; padding-top: 5px; display: flex; justify-content: space-between; font-size: 11px; color: #666; }
        """

    def _get_script(self) -> str:
        """Get JavaScript code."""
        return """
        // Search functionality
        function filterSteps() {
            const query = document.getElementById('search-input').value.toLowerCase();
            const steps = document.querySelectorAll('.step');
            steps.forEach(step => {
                const text = step.textContent.toLowerCase();
                step.classList.toggle('hidden', query && !text.includes(query));
            });
        }

        // Filter by type
        let currentFilter = 'all';
        function filterByType(type) {
            currentFilter = type;
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.filter === type);
            });
            const steps = document.querySelectorAll('.step');
            steps.forEach(step => {
                if (type === 'all') {
                    step.classList.remove('hidden');
                } else {
                    step.classList.toggle('hidden', !step.classList.contains('step-' + type));
                }
            });
        }

        // View switching
        function showView(view) {
            document.querySelectorAll('.view-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent.toLowerCase().includes(view));
            });
            document.getElementById('tree-view').style.display = view === 'tree' ? 'block' : 'none';
            document.getElementById('timeline-view').style.display = view === 'timeline' ? 'block' : 'none';
            if (view === 'timeline') {
                renderTimeline();
            }
        }

        // Timeline rendering
        function renderTimeline() {
            const container = document.getElementById('timeline-container');
            if (!traceData.steps || traceData.steps.length === 0) {
                container.innerHTML = '<p class="no-steps">No steps to display</p>';
                return;
            }

            // Flatten steps and calculate timing
            const flatSteps = [];
            function flattenSteps(steps, depth = 0) {
                steps.forEach(step => {
                    flatSteps.push({ ...step, depth });
                    if (step.children) flattenSteps(step.children, depth + 1);
                });
            }
            flattenSteps(traceData.steps);

            // Find time range
            const startTimes = flatSteps.map(s => new Date(s.start_time).getTime());
            const endTimes = flatSteps.map(s => s.end_time ? new Date(s.end_time).getTime() : Date.now());
            const minTime = Math.min(...startTimes);
            const maxTime = Math.max(...endTimes);
            const totalDuration = maxTime - minTime || 1;

            // Render bars
            let html = '<div class="timeline-container">';
            flatSteps.forEach(step => {
                const start = new Date(step.start_time).getTime();
                const end = step.end_time ? new Date(step.end_time).getTime() : maxTime;
                const left = ((start - minTime) / totalDuration) * 100;
                const width = Math.max(((end - start) / totalDuration) * 100, 1);
                const indent = step.depth * 15;
                const hasError = step.error ? 'has-error' : '';

                html += '<div class="timeline-bar type-' + step.type + ' ' + hasError + '" ' +
                        'style="margin-left:' + indent + 'px; left:' + left + '%; width:' + width + '%;">' +
                        '<span class="timeline-label">' + step.type.toUpperCase() + ': ' + step.name + '</span>' +
                        '<span class="timeline-duration">' + (step.duration_ms ? step.duration_ms.toFixed(1) + 'ms' : '') + '</span>' +
                        '</div>';
            });

            // Time axis
            html += '<div class="timeline-axis">';
            html += '<span>0ms</span>';
            html += '<span>' + (totalDuration / 1000).toFixed(2) + 's</span>';
            html += '</div>';
            html += '</div>';

            container.innerHTML = html;
        }

        // Expand/collapse all
        function expandAll() {
            document.querySelectorAll('.step-list details').forEach(d => d.open = true);
        }
        function collapseAll() {
            document.querySelectorAll('.step-list details').forEach(d => d.open = false);
        }

        // Initialize
        console.log('Trace data loaded:', traceData);
        """
