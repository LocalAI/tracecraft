# Quick Start

Get TraceCraft running in under 2 minutes with **zero code changes** to your existing application.

## The Fastest Path: Auto-Instrumentation

!!! success "No decorators. No code changes. Just trace."

    TraceCraft's auto-instrumentation automatically captures every LLM call in your application.
    You don't need to add decorators, modify function signatures, or change any code.

### Step 1: Install

```bash
pip install "tracecraft[auto,tui]"
```

### Step 2: Add One Line of Code

```python
import tracecraft

tracecraft.init(auto_instrument=True)

# That's it! Your existing code works unchanged.
```

### Step 3: Run Your App

```python
# Your existing code - NO CHANGES NEEDED
from openai import OpenAI

client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

Every LLM call is now automatically traced with:

- Model name and provider
- Input prompts and output completions
- Token counts (input, output, total)
- Latency and timing
- Streaming support
- Function/tool calls

### Step 4: Explore Your Traces

Launch the interactive terminal UI:

```bash
tracecraft tui traces/
```

You'll see a beautiful, interactive interface to explore all your traces:

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

---

## Complete Working Example

Here's a full example you can copy and run:

```python
# app.py
import tracecraft
from openai import OpenAI

# Initialize TraceCraft
tracecraft.init(auto_instrument=True)

# Your normal application code
client = OpenAI()

def ask_question(question: str) -> str:
    """Ask a question - automatically traced!"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

# Run it
if __name__ == "__main__":
    answer = ask_question("What is the capital of France?")
    print(answer)
```

Run it:

```bash
python app.py
```

Then explore your traces:

```bash
tracecraft tui traces/
```

---

## Auto-Instrumentation Supports

| SDK | What's Captured |
|-----|----------------|
| **OpenAI** | Chat completions, embeddings, streaming, function calls, token usage |
| **Anthropic** | Messages, streaming, tool use, token counts |
| **LangChain** | Chains, agents, tools, retrievers, LLM calls |
| **LlamaIndex** | Query engines, chat engines, agents, retrievers |

!!! tip "Works with frameworks too"

    Auto-instrumentation works alongside framework adapters. LangChain chains,
    LlamaIndex queries, and direct SDK calls are all captured automatically.

---

## What About Decorators?

!!! info "Decorators are optional"

    You only need decorators if you want to:

    - Add custom semantic meaning (e.g., mark a function as an "agent")
    - Capture custom inputs/outputs
    - Create hierarchical trace structures
    - Add custom attributes to spans

    **For most use cases, auto-instrumentation is sufficient.**

If you do want custom instrumentation, see [Custom Instrumentation](../user-guide/decorators.md).

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

---

## FAQ

??? question "Do I need to modify my existing code?"

    **No!** Auto-instrumentation patches the SDKs at runtime. Your existing
    code works unchanged. Just add the single initialization line.

??? question "What if I'm using LangChain or LlamaIndex?"

    Auto-instrumentation works with these frameworks too. You can also use
    the framework-specific adapters for richer context, but it's optional.

??? question "Can I use the TUI without TraceCraft instrumentation?"

    **Yes!** The TUI can read any OpenTelemetry-compatible trace data.
    See the [TUI Guide](../user-guide/tui.md) for details.

??? question "Where are traces stored?"

    By default, traces are saved to `traces/tracecraft.jsonl`. You can
    configure this with `tracecraft.init(jsonl_path="./my-traces/")`.
