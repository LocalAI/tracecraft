# Frequently Asked Questions

Find answers to the most common questions about TraceCraft. If your question is not covered here,
open an issue on [GitHub](https://github.com/LocalAI/tracecraft/issues).

---

## Getting Started

??? question "What is TraceCraft?"
    TraceCraft is a vendor-neutral observability SDK for LLM applications. You instrument your
    code once with TraceCraft decorators or context managers, and then export traces to any
    backend: console, local JSONL files, OTLP-compatible platforms (Jaeger, Honeycomb, Grafana
    Tempo, etc.), MLflow, or static HTML reports.

    TraceCraft captures the full hierarchy of an agent run - agent calls, LLM requests, tool
    invocations, retrieval operations, and more - without locking you into any vendor's
    proprietary format.

??? question "Which Python version does TraceCraft require?"
    TraceCraft requires **Python 3.11 or later**. It uses modern Python features including
    `X | Y` union syntax, built-in generics (`list[str]`, `dict[str, Any]`), and
    `datetime.now(UTC)`.

    ```bash
    python --version  # Must be 3.11+
    pip install tracecraft
    ```

??? question "Which LLM frameworks does TraceCraft support?"
    TraceCraft ships adapters for the most widely used frameworks:

    | Framework | Package Extra | How to Enable |
    |-----------|--------------|---------------|
    | LangChain | `tracecraft[langchain]` | `TraceCraftCallbackHandler` |
    | LlamaIndex | `tracecraft[llamaindex]` | `TraceCraftSpanHandler` |
    | PydanticAI | `tracecraft[pydantic-ai]` | `TraceCraftSpanProcessor` |
    | Claude SDK | `tracecraft[claude-sdk]` | `ClaudeTraceCraftr` |
    | OpenAI (auto) | `tracecraft[auto]` | `init(auto_instrument=True)` |
    | Anthropic (auto) | `tracecraft[auto]` | `init(auto_instrument=True)` |

    For frameworks not listed here, you can use the `@trace_agent`, `@trace_tool`,
    `@trace_llm`, and `@trace_retrieval` decorators directly, or wrap calls in a
    `with tracecraft.step(...)` context manager.

??? question "Can I use TraceCraft without any LLM framework?"
    Yes. The decorator API and context manager work with any Python code, regardless of which
    LLM SDK you use.

    ```python
    import tracecraft
    from tracecraft import trace_agent, trace_tool, trace_llm

    tracecraft.init(console=True)

    @trace_agent(name="my_agent")
    async def my_agent(prompt: str) -> str:
        result = await call_llm(prompt)
        return result

    @trace_llm(name="gpt4_call", model="gpt-4o", provider="openai")
    async def call_llm(prompt: str) -> str:
        # Call any LLM SDK here
        ...
    ```

??? question "Does TraceCraft require an external service to work?"
    No. By default `tracecraft.init()` writes traces to the console and optionally to a local
    JSONL file. No network connection or cloud account is needed for development.

    External services (OTLP collectors, MLflow, cloud platforms) are optional and only required
    when you configure the corresponding exporter.

    ```python
    # Fully offline - no external services needed
    tracecraft.init(console=True, jsonl=True)
    ```

---

## Configuration

??? question "How do I configure TraceCraft differently for development and production?"
    Use environment variables so the same code runs correctly in both environments:

    ```python title="app.py"
    import os
    import tracecraft

    tracecraft.init(
        service_name=os.getenv("SERVICE_NAME", "my-agent"),
        console=os.getenv("ENV", "development") == "development",
        jsonl=os.getenv("ENV", "development") == "development",
        otlp_endpoint=os.getenv("OTLP_ENDPOINT"),  # None in dev = disabled
        sampling_rate=float(os.getenv("TRACECRAFT_SAMPLING_RATE", "1.0")),
        enable_pii_redaction=os.getenv("ENV") == "production",
    )
    ```

    ```bash title=".env.development"
    ENV=development
    SERVICE_NAME=my-agent-dev
    TRACECRAFT_SAMPLING_RATE=1.0
    ```

    ```bash title=".env.production"
    ENV=production
    SERVICE_NAME=my-agent
    OTLP_ENDPOINT=https://otlp.example.com:4317
    TRACECRAFT_SAMPLING_RATE=0.1
    ```

??? question "What environment variables does TraceCraft read?"
    TraceCraft respects the following environment variables:

    | Variable | Description | Default |
    |----------|-------------|---------|
    | `TRACECRAFT_SERVICE_NAME` | Service name tag | `"tracecraft"` |
    | `TRACECRAFT_SAMPLING_RATE` | Trace sampling rate (0.0-1.0) | `1.0` |
    | `TRACECRAFT_REDACTION_ENABLED` | Enable PII redaction | `"false"` |
    | `OTLP_ENDPOINT` | OTLP gRPC endpoint | None |
    | `OTEL_SERVICE_NAME` | OTel-standard service name override | None |

    You can also pass all options directly to `tracecraft.init()` as keyword arguments.
    Explicit arguments take precedence over environment variables.

??? question "How do I set up PII redaction?"
    Enable the built-in redaction processor in `tracecraft.init()`:

    ```python
    import tracecraft

    tracecraft.init(
        enable_pii_redaction=True,  # Masks emails, phone numbers, credit cards by default
    )
    ```

    To add custom patterns or change the redaction mode:

    ```python
    from tracecraft.processors.redaction import RedactionProcessor, RedactionMode

    redaction = RedactionProcessor(
        mode=RedactionMode.MASK,          # Replace with [REDACTED]
        custom_patterns=[
            (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),       # Social Security Numbers
            (r"\b[A-Z]{2}\d{6}\b", "[PASSPORT]"),        # Passport numbers
        ],
    )

    tracecraft.init(processors=[redaction])
    ```

    !!! warning "Redact before exporting"
        Always use `ProcessorOrder.SAFETY` (the default) so redaction runs before sampling.
        This guarantees that no PII reaches any exporter, even on sampled-out traces that
        are later kept by an error or slow-trace rule.

??? question "What is the difference between SAFETY and EFFICIENCY processor order?"
    The processor order controls whether redaction or sampling runs first in the pipeline.

    **SAFETY (default):** Redact first, then sample.

    - All traces are redacted before any export decision is made.
    - Guarantees that no PII can leak through any code path.
    - Slightly higher CPU cost because redaction runs on 100% of traces.

    **EFFICIENCY:** Sample first, then redact.

    - Traces that are sampled out are never redacted (they are dropped without processing).
    - Lower CPU cost in high-throughput scenarios.
    - Only use this if your traces never contain PII, or if you are comfortable that sampled-out
      traces are discarded without inspection.

    ```python
    from tracecraft.core.config import ProcessorOrder

    # Default - safe for PII-sensitive workloads
    tracecraft.init(processor_order=ProcessorOrder.SAFETY)

    # High-throughput, non-PII workloads
    tracecraft.init(processor_order=ProcessorOrder.EFFICIENCY)
    ```

---

## Integrations

??? question "How do I enable tracing for a LangChain chain?"
    Install the LangChain extra and attach the callback handler:

    ```bash
    pip install "tracecraft[langchain]"
    ```

    ```python
    import tracecraft
    from tracecraft.adapters.langchain import TraceCraftCallbackHandler

    tracecraft.init(console=True)
    handler = TraceCraftCallbackHandler()

    # Pass the handler at invocation time
    result = chain.invoke(
        {"query": "What is TraceCraft?"},
        config={"callbacks": [handler]},
    )
    ```

    The handler automatically creates a Step for every chain, LLM call, and tool invocation
    in the LangChain execution graph.

??? question "How do I enable tracing for LlamaIndex?"
    Install the LlamaIndex extra and set a global span handler before creating any index or
    query engine:

    ```bash
    pip install "tracecraft[llamaindex]"
    ```

    ```python
    import tracecraft
    from tracecraft.adapters.llamaindex import TraceCraftSpanHandler
    import llama_index.core

    tracecraft.init(console=True)

    # Must be set before creating indexes or query engines
    llama_index.core.global_handler = TraceCraftSpanHandler()

    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine()
    response = query_engine.query("What is RAG?")
    ```

??? question "What is auto-instrumentation and how do I enable it?"
    Auto-instrumentation patches the OpenAI and Anthropic Python SDKs at import time so that
    every API call is automatically traced without adding decorators to your code.

    ```bash
    pip install "tracecraft[auto]"
    ```

    ```python
    import tracecraft

    # Pass auto_instrument=True (or a list of providers) to init()
    tracecraft.init(console=True, auto_instrument=True)

    import openai  # All calls to openai are now traced automatically
    ```

    !!! important "Import order matters"
        Call `tracecraft.init(auto_instrument=True)` before importing `openai` or `anthropic`.
        If those modules are already imported, the patches will not take effect. See
        [Auto-Instrumentation](integrations/auto-instrumentation.md) for details.

??? question "How do I receive traces from an existing OpenTelemetry setup?"
    Use the OTLP receiver to accept traces from any OTLP-compatible source and convert them
    into TraceCraft steps:

    ```bash
    pip install "tracecraft[receiver]"
    ```

    ```python
    from tracecraft.otel import setup_exporter

    tracer = setup_exporter(
        endpoint="http://localhost:4318",
        service_name="my-agent",
        instrument=["openai"],  # SDK names to auto-instrument
    )
    ```

    This is useful when you have an existing OTel pipeline and want to add TraceCraft's TUI,
    PII redaction, or JSONL export without changing your instrumentation code.

??? question "Does TraceCraft work with async code?"
    Yes. All TraceCraft decorators support both synchronous and asynchronous functions.
    Context variables (`contextvars`) propagate correctly across `await` boundaries within
    a single async task.

    ```python
    @trace_agent(name="async_agent")
    async def async_agent(prompt: str) -> str:
        result = await async_llm_call(prompt)
        return result

    @trace_llm(name="llm_call", model="gpt-4o", provider="openai")
    async def async_llm_call(prompt: str) -> str:
        ...
    ```

    When using `asyncio.gather()` to run multiple agents concurrently, each task maintains its
    own context. See [Multi-Tenancy](user-guide/multi-tenancy.md) for patterns that involve
    concurrent runs with separate `AgentRun` contexts.

---

## Exporters

??? question "What export backends does TraceCraft support?"
    TraceCraft ships five built-in exporters:

    | Exporter | Class | Use Case |
    |----------|-------|----------|
    | Console | `ConsoleExporter` | Development, debugging |
    | JSONL | `JSONLExporter` | Local storage, TUI, offline analysis |
    | OTLP | `OTLPExporter` | Jaeger, Honeycomb, Grafana Tempo, Datadog |
    | MLflow | `MLflowExporter` | Experiment tracking, dataset creation |
    | HTML | `HTMLExporter` | Shareable standalone trace reports |

    Enable them via `tracecraft.init()` shorthand flags or by passing exporter instances:

    ```python
    # Shorthand flags
    tracecraft.init(console=True, jsonl=True)

    # Explicit exporter instances (for custom configuration)
    from tracecraft.exporters import OTLPExporter, JSONLExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(endpoint="http://jaeger:4317"),
            JSONLExporter(filepath="traces/run.jsonl"),
        ]
    )
    ```

??? question "Can I send traces to multiple backends at the same time?"
    Yes. Pass a list of exporter instances to `tracecraft.init()`. All exporters run
    concurrently for each completed trace.

    ```python
    from tracecraft.exporters import OTLPExporter, JSONLExporter, HTMLExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(endpoint="http://jaeger:4317"),      # Live dashboards
            JSONLExporter(filepath="traces/archive.jsonl"),   # Local archive
            HTMLExporter(output_dir="reports/"),              # Shareable reports
        ]
    )
    ```

??? question "How do I write a custom exporter?"
    Subclass `BaseExporter` and implement the `export` method:

    ```python
    from tracecraft.exporters.base import BaseExporter
    from tracecraft.core.models import AgentRun

    class MyExporter(BaseExporter):
        """Send traces to a custom backend."""

        def export(self, run: AgentRun) -> None:
            """Export a completed AgentRun.

            Args:
                run: The completed agent run containing all steps.
            """
            payload = {
                "run_id": run.run_id,
                "name": run.name,
                "steps": [s.name for s in run.steps],
            }
            my_backend.send(payload)

    tracecraft.init(exporters=[MyExporter()])
    ```

??? question "My traces are not appearing anywhere - what should I check?"
    Work through this checklist:

    1. **Is `tracecraft.init()` called before any decorated functions?** The runtime must be
       initialized before decorators execute.
    2. **Is at least one exporter enabled?** `tracecraft.init()` with no arguments uses the
       console exporter by default. If you passed `console=False` and no other exporter, traces
       are silently dropped.
    3. **Is the sampling rate above zero?** A `sampling_rate=0.0` drops all traces.
    4. **Are your functions actually being called?** Add a `print()` inside the function to
       confirm execution.
    5. **Check for export errors:** `get_runtime().export_errors` will be non-zero if an
       exporter is failing silently.

    ```python
    import tracecraft

    tracecraft.init(console=True)  # Add console exporter to see output

    runtime = tracecraft.get_runtime()
    print("Export errors:", runtime.export_errors)
    ```

---

## Troubleshooting

??? question "I get ModuleNotFoundError when importing a TraceCraft adapter. What is wrong?"
    Most adapters and exporters are optional dependencies grouped into extras. Install the
    extra that matches the adapter you want:

    ```bash
    pip install "tracecraft[langchain]"      # LangChain adapter
    pip install "tracecraft[llamaindex]"     # LlamaIndex adapter
    pip install "tracecraft[pydantic-ai]"    # PydanticAI adapter
    pip install "tracecraft[claude-sdk]"     # Claude SDK adapter
    pip install "tracecraft[otlp]"           # OTLP exporter
    pip install "tracecraft[mlflow]"         # MLflow exporter
    pip install "tracecraft[auto]"           # Auto-instrumentation
    pip install "tracecraft[all]"            # Everything
    ```

    The base `pip install tracecraft` only installs the core package with the console and
    JSONL exporters.

??? question "Child spans are missing - my trace shows only the top-level step."
    This usually means the context variable that carries the current `AgentRun` is not
    propagating into the child function. Common causes:

    - **Threads:** `contextvars.Context` does not automatically copy into new threads.
      Use `contextvars.copy_context().run(fn)` to propagate context manually.
    - **ProcessPoolExecutor:** Sub-processes do not inherit context. Avoid tracing across
      process boundaries.
    - **Framework callbacks:** Some frameworks invoke callbacks in a different execution
      context. Use the framework-specific adapter instead of plain decorators.

    For async code, context propagates automatically across `await` calls within the same
    task. Use `asyncio.gather()` with care - each task gets a copy of the context at the
    point it is created, so nested calls within a task will appear correctly, but steps
    started in separate tasks will appear as separate roots unless you use
    `runtime.run()` context managers.

??? question "Auto-instrumentation is not capturing my OpenAI calls."
    The most common cause is import order. `tracecraft.init(auto_instrument=True)` must be
    called before `import openai` or `import anthropic`:

    ```python
    # Correct order
    import tracecraft

    tracecraft.init(console=True, auto_instrument=True)  # Patch SDKs before importing them

    import openai            # Now the patch is in place
    ```

    If the modules are imported at the top of a different file that loads first, move
    `tracecraft.init(auto_instrument=True)` to the very start of your application entry point.

??? question "How do I enable debug logging for TraceCraft itself?"
    Set the `tracecraft` logger to `DEBUG` level:

    ```python
    import logging

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("tracecraft").setLevel(logging.DEBUG)

    import tracecraft
    tracecraft.init(console=True)
    ```

    Debug output shows exporter calls, processor decisions, and context variable state.
    This is the fastest way to identify why traces are being dropped or not exported.

---

## Performance

??? question "How much overhead does TraceCraft add?"
    The overhead depends on your configuration:

    | Configuration | Typical Overhead | Max Throughput |
    |---------------|-----------------|----------------|
    | 100% sampling, console + JSONL | ~5-10 ms/trace | ~1 K traces/s |
    | 10% sampling, OTLP only | ~1-2 ms/trace | ~10 K traces/s |
    | 1% sampling, async batch export | <0.5 ms/trace | ~50 K+ traces/s |

    For most LLM applications the network latency of the LLM API call (hundreds of
    milliseconds) far exceeds TraceCraft's instrumentation overhead.

    See [High Throughput](deployment/high-throughput.md) for tuning guidance.

??? question "TraceCraft is using a lot of memory. What can I do?"
    High memory usage is almost always caused by a large in-memory export queue. Reduce it
    by lowering the batch size and queue limit on the async exporter:

    ```python
    from tracecraft.exporters import AsyncBatchExporter, OTLPExporter

    exporter = AsyncBatchExporter(
        exporter=OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
        batch_size=50,         # Flush more frequently
        max_queue_size=500,    # Limit the in-memory queue
    )

    tracecraft.init(
        sampling_rate=0.05,    # Sample less
        exporters=[exporter],
    )
    ```

    Also consider lowering `sampling_rate` to reduce the number of traces being queued.

??? question "What sampling strategies are available?"
    TraceCraft supports three sampling strategies via `SamplingProcessor`:

    ```python
    from tracecraft.processors.sampling import SamplingProcessor

    # 1. Uniform random sampling
    sampler = SamplingProcessor(rate=0.1)  # Keep 10% of all traces

    # 2. Always keep errors and slow traces, sample the rest
    sampler = SamplingProcessor(
        rate=0.05,
        always_keep_errors=True,
        always_keep_slow=True,
        slow_threshold_ms=3000,
    )

    # 3. Head-based sampling via init() shorthand
    tracecraft.init(
        sampling_rate=0.1,
        always_keep_errors=True,
    )
    ```

    For tail-based sampling (decide after the trace completes), use `always_keep_errors=True`
    combined with a low base rate - errors are evaluated after the run completes, so they are
    never dropped even when the base rate would exclude them.

---

## Production

??? question "How do I deploy TraceCraft on Kubernetes?"
    The recommended pattern is to run an OpenTelemetry Collector as a DaemonSet or sidecar
    and point TraceCraft's OTLP exporter at it. This decouples your application from the
    observability backend.

    ```yaml title="tracecraft-config.yaml"
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: tracecraft-config
    data:
      SERVICE_NAME: "my-agent"
      OTLP_ENDPOINT: "http://otel-collector:4317"
      TRACECRAFT_SAMPLING_RATE: "0.1"
    ```

    See the complete [Kubernetes Deployment](deployment/kubernetes.md) guide for Helm
    values, resource limits, and HPA configuration.

??? question "How does TraceCraft integrate with cloud-managed AI platforms?"
    TraceCraft ships contrib helpers for AWS, Azure, and GCP that handle credential
    resolution and platform-specific export targets:

    - **AWS AgentCore:** See [AWS AgentCore](deployment/aws-agentcore.md) for IAM role setup
      and CloudWatch export.
    - **Azure AI Foundry:** See [Azure AI Foundry](deployment/azure-foundry.md) for
      managed identity and Azure Monitor export.
    - **GCP Vertex AI:** See [GCP Vertex Agent](deployment/gcp-vertex-agent.md) for
      Workload Identity and Cloud Trace export.

    All three platforms support OTLP export, so you can also use the standard
    `OTLPExporter` with the platform's managed collector endpoint.

??? question "How do I persist traces so they survive application restarts?"
    Use the JSONL exporter (flat file) or configure a SQLite storage backend:

    ```python
    # Option 1: JSONL file (portable, human-readable)
    tracecraft.init(
        jsonl=True,
        jsonl_path="/var/data/traces/",  # Mount a persistent volume here
    )
    ```

    ```python
    # Option 2: SQLite (queryable, used by the TUI)
    from tracecraft.storage.sqlite import SQLiteTraceStore

    store = SQLiteTraceStore(db_path="/var/data/traces/tracecraft.db")
    tracecraft.init(storage=store)
    ```

    Then explore persisted traces with the Terminal UI:

    ```bash
    tracecraft ui /var/data/traces/tracecraft.jsonl
    # or
    tracecraft ui /var/data/traces/tracecraft.db
    ```
