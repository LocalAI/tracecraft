# Terminal UI

The TraceCraft Terminal UI (TUI) is a powerful, interactive trace explorer that runs right in your terminal. Analyze LLM traces, debug issues, compare performance, and understand your AI application's behavior - all without leaving the command line.

!!! success "Works with ANY OpenTelemetry Data"

    **You don't need TraceCraft instrumentation to use the TUI.** It reads standard
    OpenTelemetry trace formats, so you can use it with:

    - TraceCraft traces
    - OpenLLMetry traces
    - Any OTLP-exported traces (via JSONL/SQLite)
    - Jaeger exports
    - Custom OpenTelemetry instrumentation

---

## Why Use the TUI?

<div class="grid cards" markdown>

- :material-lightning-bolt:{ .lg .middle } **Instant Analysis**

    ---

    No browser, no cloud dashboard, no waiting. Launch and explore traces in milliseconds.

- :material-tree:{ .lg .middle } **Hierarchical View**

    ---

    See the complete call tree: agents → tools → LLM calls → sub-operations.

- :material-magnify:{ .lg .middle } **Powerful Search**

    ---

    Find traces by name, duration, status, token count, or any attribute.

- :material-compare:{ .lg .middle } **Side-by-Side Compare**

    ---

    Compare two traces to understand performance differences.

- :material-export:{ .lg .middle } **Export Anywhere**

    ---

    Export traces to JSON, HTML reports, or copy to clipboard.

- :material-lock:{ .lg .middle } **Fully Offline**

    ---

    All data stays local. No cloud uploads. Perfect for sensitive applications.

</div>

---

## Quick Start

### Installation

```bash
pip install "tracecraft[tui]"
```

### Launch

```bash
# From a JSONL file
tracecraft tui traces/tracecraft.jsonl

# From a SQLite database
tracecraft tui traces.db

# From a directory (auto-discovers trace files)
tracecraft tui traces/

# From any OTLP-compatible export
tracecraft tui my-otel-traces.jsonl
```

That's it! You're now exploring your traces.

---

## Interface Overview

When you launch the TUI, you'll see three main panels:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TraceCraft TUI v0.5.0                                         traces: 156   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                               ┃
┃  ┌─ TRACE LIST ──────────────────────────────────────────────────────────┐   ┃
┃  │  TRACE ID       NAME                    DURATION   STATUS   TOKENS    │   ┃
┃  │  ─────────────────────────────────────────────────────────────────── │   ┃
┃  │▸ a1b2c3...      research_agent          2.34s      ✓        4,521    │   ┃
┃  │  d4e5f6...      chat.completions        0.89s      ✓        1,247    │   ┃
┃  │  g7h8i9...      rag_query               1.56s      ✗        2,891    │   ┃
┃  │  j0k1l2...      summarize_docs          3.21s      ✓        8,432    │   ┃
┃  └───────────────────────────────────────────────────────────────────────┘   ┃
┃                                                                               ┃
┃  ┌─ SPAN TREE ───────────────────────────────────────────────────────────┐   ┃
┃  │  research_agent (2.34s)                                               │   ┃
┃  │  ├─ web_search (0.45s)                                                │   ┃
┃  │  │  └─ google_api_call (0.43s)                                        │   ┃
┃  │  ├─ process_results (0.12s)                                           │   ┃
┃  │  └─ chat.completions [gpt-4] (1.77s) ◀─────── Currently Selected     │   ┃
┃  │     ├─ Input: "Summarize these search results..."                     │   ┃
┃  │     ├─ Output: "Based on the search results..."                       │   ┃
┃  │     └─ Tokens: 1,247 (prompt: 892, completion: 355)                   │   ┃
┃  └───────────────────────────────────────────────────────────────────────┘   ┃
┃                                                                               ┃
┃  ┌─ DETAILS ─────────────────────────────────────────────────────────────┐   ┃
┃  │  Span: chat.completions                                               │   ┃
┃  │  ─────────────────────────────────────────────────────────────────── │   ┃
┃  │  Model:      gpt-4                                                    │   ┃
┃  │  Provider:   openai                                                   │   ┃
┃  │  Duration:   1.77s                                                    │   ┃
┃  │  Status:     Success                                                  │   ┃
┃  │                                                                       │   ┃
┃  │  ┌─ Input ────────────────────────────────────────────────────────┐  │   ┃
┃  │  │ Summarize these search results about climate change:           │  │   ┃
┃  │  │ 1. Global temperatures have risen 1.1°C since pre-industrial.. │  │   ┃
┃  │  │ 2. Arctic ice is melting at an unprecedented rate...           │  │   ┃
┃  │  └────────────────────────────────────────────────────────────────┘  │   ┃
┃  │                                                                       │   ┃
┃  │  ┌─ Output ───────────────────────────────────────────────────────┐  │   ┃
┃  │  │ Based on the search results, climate change is causing         │  │   ┃
┃  │  │ significant global impacts including rising temperatures...    │  │   ┃
┃  │  └────────────────────────────────────────────────────────────────┘  │   ┃
┃  └───────────────────────────────────────────────────────────────────────┘   ┃
┃                                                                               ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ [↑↓] Navigate  [Enter] Expand  [Tab] Switch Panel  [/] Search  [q] Quit      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### The Three Panels

| Panel | Purpose |
|-------|---------|
| **Trace List** | All traces in your data source, sorted by time. Shows duration, status, and token counts at a glance. |
| **Span Tree** | Hierarchical view of the selected trace. See how operations nest: agent → tool → LLM call. |
| **Details** | Deep dive into the selected span. View inputs, outputs, attributes, errors, and timing. |

---

## Keyboard Shortcuts

Master these shortcuts to navigate traces like a pro:

### Navigation

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move up/down in current panel |
| `←` / `→` | Collapse/expand tree nodes |
| `Tab` | Switch between panels |
| `Enter` | Expand selected item / View details |
| `Home` / `End` | Jump to first/last item |
| `PgUp` / `PgDn` | Page up/down |

### Search & Filter

| Key | Action |
|-----|--------|
| `/` | Open search dialog |
| `f` | Open filter panel |
| `Esc` | Clear search/filter |
| `n` / `N` | Next/previous search result |

### Actions

| Key | Action |
|-----|--------|
| `e` | Export current trace |
| `c` | Compare two traces |
| `r` | Refresh data |
| `y` | Copy span to clipboard |
| `?` | Show help |
| `q` | Quit |

---

## Features in Detail

### Trace List View

The trace list shows all traces at a glance:

```
┌─ TRACE LIST ─────────────────────────────────────────────────────────────────┐
│  TRACE ID       NAME                    DURATION   STATUS   TOKENS   TIME    │
│  ─────────────────────────────────────────────────────────────────────────── │
│▸ a1b2c3...      research_agent          2.34s      ✓        4,521   2m ago  │
│  d4e5f6...      chat.completions        0.89s      ✓        1,247   5m ago  │
│  g7h8i9...      rag_query               1.56s      ✗        2,891   8m ago  │
│  j0k1l2...      summarize_docs          3.21s      ✓        8,432   12m ago │
│  m3n4o5...      code_review_agent       5.67s      ✓       12,543   15m ago │
└──────────────────────────────────────────────────────────────────────────────┘
```

**What you see:**

- **Trace ID**: Unique identifier (truncated for display)
- **Name**: Root span name or agent name
- **Duration**: Total trace duration
- **Status**: ✓ Success, ✗ Error, ⚠ Warning
- **Tokens**: Total tokens used across all LLM calls
- **Time**: When the trace was recorded

---

### Span Tree View

The span tree shows the hierarchical structure of your trace:

```
┌─ SPAN TREE ──────────────────────────────────────────────────────────────────┐
│  research_agent (2.34s) ✓                                                    │
│  ├─ retrieve_documents (0.32s) ✓                                             │
│  │  ├─ vector_search (0.28s) ✓                                               │
│  │  └─ rerank_results (0.04s) ✓                                              │
│  ├─ chat.completions [gpt-4] (1.89s) ✓                                       │
│  │  └─ Tokens: 3,421 (prompt: 2,890, completion: 531)                        │
│  └─ format_response (0.13s) ✓                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Features:**

- **Expand/Collapse**: Use `←` `→` or `Enter` to expand/collapse nodes
- **Color Coding**: Different colors for agents (blue), tools (green), LLM calls (yellow), errors (red)
- **Inline Metrics**: See token counts, durations, and status inline
- **Error Highlighting**: Errors are highlighted in red with stack traces visible

---

### Detail Panel

The detail panel shows everything about the selected span:

```
┌─ DETAILS ────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  Span: chat.completions                                                      │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                              │
│  ┌─ Metadata ────────────────────────────────────────────────────────────┐  │
│  │  Model:       gpt-4                                                   │  │
│  │  Provider:    openai                                                  │  │
│  │  Temperature: 0.7                                                     │  │
│  │  Max Tokens:  1000                                                    │  │
│  │  Duration:    1.89s                                                   │  │
│  │  Status:      Success                                                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Token Usage ─────────────────────────────────────────────────────────┐  │
│  │  Prompt:      2,890 tokens ($0.0867)                                  │  │
│  │  Completion:    531 tokens ($0.0319)                                  │  │
│  │  Total:       3,421 tokens ($0.1186)                                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Input (Messages) ────────────────────────────────────────────────────┐  │
│  │  [system] You are a research assistant that provides accurate,       │  │
│  │           well-sourced information on any topic.                      │  │
│  │                                                                       │  │
│  │  [user] Based on these documents, what are the key findings about    │  │
│  │         renewable energy adoption in Europe?                          │  │
│  │                                                                       │  │
│  │         Document 1: European Solar Capacity Report 2024...            │  │
│  │         Document 2: Wind Energy Growth Analysis...                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─ Output ──────────────────────────────────────────────────────────────┐  │
│  │  Based on the provided documents, here are the key findings about    │  │
│  │  renewable energy adoption in Europe:                                 │  │
│  │                                                                       │  │
│  │  1. Solar capacity increased by 45% in 2024, with Germany and        │  │
│  │     Spain leading installations...                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**What you can see:**

- Complete input prompts and messages
- Full output/completion text
- Token counts with cost estimates
- Model parameters (temperature, max_tokens, etc.)
- Custom attributes
- Error messages and stack traces
- Timing breakdown

---

### Search & Filter

Press `/` to search or `f` to filter:

```
┌─ FILTER ─────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  Status:    [All ▼]  [ ] Success only  [ ] Errors only                       │
│                                                                              │
│  Duration:  Min: [____] ms    Max: [____] ms                                 │
│                                                                              │
│  Tokens:    Min: [____]       Max: [____]                                    │
│                                                                              │
│  Name:      [________________________]  (supports regex)                     │
│                                                                              │
│  Model:     [________________________]                                       │
│                                                                              │
│  Date:      From: [__________]    To: [__________]                           │
│                                                                              │
│                                      [Apply]  [Clear]  [Cancel]              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Filter Examples:**

- Find slow traces: Set `Duration Min: 2000` (>2 seconds)
- Find errors: Check `Errors only`
- Find specific model: Set `Model: gpt-4`
- Find by name pattern: Set `Name: research.*` (regex supported)

---

### Trace Comparison

Press `c` to compare two traces side-by-side:

```
┌─ COMPARE TRACES ─────────────────────────────────────────────────────────────┐
│                                                                              │
│     TRACE A (a1b2c3...)              │       TRACE B (d4e5f6...)             │
│  ────────────────────────────────────│────────────────────────────────────── │
│     Duration: 2.34s                  │       Duration: 4.56s (+95%)          │
│     Tokens:   4,521                  │       Tokens:   8,932 (+98%)          │
│     Status:   Success                │       Status:   Success               │
│                                      │                                       │
│     research_agent (2.34s)           │       research_agent (4.56s)          │
│     ├─ web_search (0.45s)            │       ├─ web_search (0.89s) ▲         │
│     ├─ process (0.12s)               │       ├─ process (0.15s)              │
│     └─ gpt-4 (1.77s)                 │       └─ gpt-4 (3.52s) ▲▲             │
│        Tokens: 1,247                 │          Tokens: 5,432 ▲▲             │
│                                      │                                       │
│  ────────────────────────────────────│────────────────────────────────────── │
│     ▲ = Slower    ▲▲ = Much Slower   │       ▼ = Faster    ▼▼ = Much Faster │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Great for:**

- A/B testing different prompts
- Comparing model performance (gpt-4 vs gpt-4-turbo)
- Understanding why some requests are slow
- Debugging regressions

---

### Export Options

Press `e` to export the current trace:

```
┌─ EXPORT ─────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  Export trace a1b2c3... to:                                                  │
│                                                                              │
│  [1] JSON file         trace_a1b2c3.json                                     │
│  [2] HTML report       trace_a1b2c3.html    (opens in browser)               │
│  [3] Clipboard         Copy as JSON                                          │
│  [4] JSONL append      Append to traces.jsonl                                │
│                                                                              │
│  Output directory: [./exports/___________________]                           │
│                                                                              │
│                                      [Export]  [Cancel]                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Using TUI with Non-TraceCraft Traces

!!! important "The TUI works with ANY OpenTelemetry data"

    You don't need to use TraceCraft instrumentation. The TUI reads standard
    OpenTelemetry trace formats.

### From OpenLLMetry / OpenTelemetry

If you're using OpenLLMetry or standard OpenTelemetry instrumentation:

```python
# Export your OTel traces to JSONL
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Your existing OTel setup exports to Jaeger, etc.
# Also export to JSONL for the TUI:
from tracecraft.exporters import JSONLExporter

tracer_provider.add_span_processor(
    BatchSpanProcessor(JSONLExporter("traces/my-traces.jsonl"))
)
```

Then view in the TUI:

```bash
tracecraft tui traces/my-traces.jsonl
```

### From Jaeger Export

Export traces from Jaeger and view them:

```bash
# Export from Jaeger API
curl "http://localhost:16686/api/traces?service=my-service" > jaeger-traces.json

# View in TUI (auto-converts Jaeger format)
tracecraft tui jaeger-traces.json
```

### From Any OTLP Collector

If you're running an OTLP collector, add a file exporter:

```yaml
# otel-collector-config.yaml
exporters:
  file:
    path: /var/traces/traces.jsonl

service:
  pipelines:
    traces:
      exporters: [file, jaeger]  # Export to both
```

Then view:

```bash
tracecraft tui /var/traces/traces.jsonl
```

---

## Configuration

### Environment Variables

```bash
# Default trace directory
export TRACECRAFT_TRACES_DIR=./traces

# Default format
export TRACECRAFT_TUI_FORMAT=jsonl

# Color theme (dark, light, auto)
export TRACECRAFT_TUI_THEME=dark
```

### Command Line Options

```bash
tracecraft tui [OPTIONS] [PATH]

Options:
  --format [jsonl|sqlite|auto]  Input format (default: auto-detect)
  --theme [dark|light]          Color theme
  --filter TEXT                 Pre-apply filter (e.g., "status:error")
  --watch                       Watch for new traces (live mode)
  --port INT                    HTTP server port for HTML export
  -h, --help                    Show help
```

### Live Mode

Watch for new traces in real-time:

```bash
tracecraft tui traces/ --watch
```

New traces appear automatically as they're written!

---

## Tips & Tricks

### Quick Debugging Workflow

1. Run your application with TraceCraft or any OTel instrumentation
2. `tracecraft tui traces/` to launch
3. Press `f` → Filter to `Errors only`
4. Press `Enter` on an error trace to see the full stack trace
5. Navigate the span tree to find which operation failed

### Finding Slow Traces

1. `tracecraft tui traces/`
2. Press `f` → Set `Duration Min: 2000` (2 seconds)
3. Compare slow vs fast traces with `c`

### Cost Analysis

The detail panel shows estimated costs per LLM call:

```
Token Usage:
  Prompt:      2,890 tokens ($0.0867)
  Completion:    531 tokens ($0.0319)
  Total:       3,421 tokens ($0.1186)
```

### Sharing Traces

Export to HTML for sharing with teammates:

1. Select trace → Press `e`
2. Choose `HTML report`
3. Open in browser or share the file

---

## Next Steps

- [Auto-Instrumentation](../integrations/auto-instrumentation.md) - Capture traces automatically
- [Exporters](exporters.md) - Configure where traces are stored
- [Configuration](configuration.md) - Full configuration reference
