# Quick Start

Get TraceCraft running in under 2 minutes.

## Step 1 — Zero code changes (absolute simplest)

!!! success "No decorators. No code changes. Just point and trace."

    If your app already emits OTLP traces (via OpenLLMetry, LangChain, LlamaIndex, DSPy,
    or the standard OTel SDK), TraceCraft can receive them with no modifications to your app.

**Install:**

```bash
pip install "tracecraft[receiver,tui]"
```

**Start the receiver and TUI:**

```bash
tracecraft serve --tui
```

**Run your existing app, unchanged:**

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python your_app.py
```

Traces stream live into the TUI as they arrive. Works with any OTLP-compatible app —
OpenLLMetry, LangChain, LlamaIndex, DSPy, or the standard OpenTelemetry SDK.

---

## Step 2 — Config file (one line of code)

If your app does not already emit OTLP traces, create a config file and add a single
`tracecraft.init()` call before your LLM imports. TraceCraft's auto-instrumentation
patches the SDKs at runtime and streams traces to the TUI.

**Create `.tracecraft/config.yaml` in your project root:**

```yaml
# .tracecraft/config.yaml
default:
  exporters:
    receiver: true
  instrumentation:
    auto_instrument: true
```

**Add one line before your LLM imports:**

```python
import tracecraft
tracecraft.init()   # reads .tracecraft/config.yaml automatically

# Your existing code below — no other changes needed
from openai import OpenAI
client = OpenAI()
```

**Start the TUI and run your app:**

```bash
tracecraft serve --tui && python your_app.py
```

Auto-instrumentation captures:

| SDK | What's Captured |
|-----|----------------|
| **OpenAI** | Chat completions, embeddings, streaming, function calls, token usage |
| **Anthropic** | Messages, streaming, tool use, token counts |
| **LangChain** | Chains, agents, tools, retrievers, LLM calls |
| **LlamaIndex** | Query engines, chat engines, agents, retrievers |

---

## Step 3 — SDK instrumentation (optional, richer spans)

Decorators let you add custom semantic meaning, structured inputs/outputs, and hierarchical
spans beyond what auto-instrumentation captures automatically.

```python
import tracecraft
from tracecraft import trace_agent, trace_tool

tracecraft.init()

@trace_agent(name="assistant")
async def assistant(message: str) -> str:
    result = await search(message)
    return result

@trace_tool(name="search")
async def search(query: str) -> str:
    ...
```

For the full decorator API, context managers, custom attributes, and pipeline configuration,
see the [SDK Guide](../user-guide/).

---

## Explore your traces

Once your app is running and the TUI is open, you will see a live trace list:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  TraceCraft TUI                                              traces: 47  ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃  TRACE ID         NAME                 DURATION    STATUS    TOKENS      ┃
┃  ─────────────────────────────────────────────────────────────────────── ┃
┃▸ abc123...        chat.completions     245ms       ✓         1,247       ┃
┃  def456...        chat.completions     189ms       ✓         892         ┃
┃  ghi789...        embeddings           67ms        ✓         512         ┃
┃  jkl012...        chat.completions     1.2s        ✓         3,891       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  [↑↓] Navigate  [Enter] Expand  [/] Search  [f] Filter  [q] Quit
```

You can also open a previously saved trace file:

```bash
tracecraft tui
```

See the [Terminal UI Guide](../user-guide/tui.md) for the full list of keyboard shortcuts,
filters, and comparison views.

---

## FAQ

??? question "Do I need to modify my existing code?"

    **No, for Path 1.** If your app already emits OTLP traces, just set the
    `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable and run as-is.

    **One line, for Path 2.** If your app calls OpenAI or Anthropic directly without
    existing OTel instrumentation, add `tracecraft.init()` before your LLM imports and
    TraceCraft auto-instruments the SDKs for you.

??? question "What if I'm using LangChain or LlamaIndex?"

    Both work with Path 1 (OTLP env var) and Path 2 (auto-instrumentation). Framework-specific
    adapters are also available for richer context — see the
    [Integrations](../integrations/) page.

??? question "Can I use the TUI without TraceCraft instrumentation?"

    **Yes.** The TUI accepts any OpenTelemetry-compatible trace data over OTLP.
    See the [TUI Guide](../user-guide/tui.md) for details.

??? question "Where are traces stored?"

    With `tracecraft serve --tui`, traces are stored in a local SQLite database managed
    by the receiver process. With `jsonl=True`, traces are saved to
    `traces/tracecraft.jsonl` (configurable via `jsonl_path`).

??? question "Can I configure this from a file instead of code?"

    Yes. Create `.tracecraft/config.yaml` in your project root. All `tracecraft.init()`
    keyword arguments are supported as config file keys. See the
    [Configuration Guide](../user-guide/configuration.md) for the full schema.

---

## Next Steps

<div class="grid cards" markdown>

- :material-monitor:{ .lg .middle } **Terminal UI**

    ---

    Deep dive into the interactive trace explorer

    [:octicons-arrow-right-24: Terminal UI Guide](../user-guide/tui.md)

- :material-auto-fix:{ .lg .middle } **Auto-Instrumentation**

    ---

    Learn about all auto-instrumentation options

    [:octicons-arrow-right-24: Auto-Instrumentation](../integrations/auto-instrumentation.md)

- :material-code-tags:{ .lg .middle } **Custom Instrumentation**

    ---

    Add decorators for custom tracing (optional)

    [:octicons-arrow-right-24: Decorators](../user-guide/decorators.md)

- :material-export:{ .lg .middle } **Export Options**

    ---

    Send traces to Jaeger, Datadog, Grafana, etc.

    [:octicons-arrow-right-24: Exporters](../user-guide/exporters.md)

</div>
