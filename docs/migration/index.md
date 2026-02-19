# Migration Guides

Moving from another LLM observability tool to TraceCraft is usually straightforward. TraceCraft
is vendor-neutral and supports all major export formats (OTLP, JSONL, HTML), so you can keep
your existing backend while switching the instrumentation layer.

Each guide covers the key differences, a side-by-side code comparison, a feature mapping table,
and a step-by-step migration checklist.

## Supported Migrations

<div class="grid cards" markdown>

- :material-swap-horizontal:{ .lg .middle } __From LangSmith__

    ---

    Replace LangSmith tracing with TraceCraft. Covers `@traceable` to `@trace_agent`
    conversion, callback handler setup, and OTLP export as an alternative to the
    LangSmith cloud.

    [:octicons-arrow-right-24: Migrate from LangSmith](from-langsmith.md)

- :material-swap-horizontal:{ .lg .middle } __From Langfuse__

    ---

    Replace Langfuse SDK calls with TraceCraft decorators and context managers. Covers
    observation mapping, dataset export, and self-hosted alternatives.

    [:octicons-arrow-right-24: Migrate from Langfuse](from-langfuse.md)

- :material-swap-horizontal:{ .lg .middle } __From OpenLLMetry__

    ---

    Replace OpenLLMetry instrumentation with TraceCraft. Covers span mapping, workflow
    decorators, and reusing your existing OTLP collector configuration.

    [:octicons-arrow-right-24: Migrate from OpenLLMetry](from-openllmetry.md)

</div>

## Why Migrate to TraceCraft?

| Feature | LangSmith | Langfuse | OpenLLMetry | TraceCraft |
|---------|:---------:|:--------:|:-----------:|:----------:|
| Vendor-neutral export | No | Partial | Yes | Yes |
| Works fully offline | No | Self-host | Yes | Yes |
| Per-trace pricing | Yes | Yes | No | No |
| Multi-framework support | LangChain | Any | Any | Any |
| Built-in PII redaction | No | No | No | Yes |
| Terminal UI | No | No | No | Yes |

## Migration Strategy

Regardless of which tool you are migrating from, the process follows the same pattern:

1. __Install TraceCraft__ alongside your existing tool (no need to remove it first).
2. __Initialize the runtime__ at application startup with your chosen exporters.
3. __Replace instrumentation__ one module at a time - decorators, callback handlers, or
   context managers depending on your integration point.
4. __Verify traces__ appear correctly in the console or TUI before switching exporters.
5. __Remove the old SDK__ once all modules have been migrated and verified.

!!! tip "Zero-Downtime Migration"
    Because TraceCraft can export to the same OTLP backend as your current tool, you can run
    both side by side during the transition. Simply point both SDKs at the same collector and
    compare the output before fully cutting over.

## Next Steps

Choose the guide that matches your current tool:

- [From LangSmith](from-langsmith.md)
- [From Langfuse](from-langfuse.md)
- [From OpenLLMetry](from-openllmetry.md)
