# Troubleshooting

This guide covers the most common problems encountered when installing, configuring, or running
TraceCraft. Each issue includes the root cause and a concrete solution.

If your problem is not listed here, check the [FAQ](faq.md) or open an issue on
[GitHub](https://github.com/LocalAI/tracecraft/issues).

---

## Installation Issues

### ModuleNotFoundError for an adapter or exporter

**Problem**

```
ModuleNotFoundError: No module named 'tracecraft.adapters.langchain'
```

**Cause**

TraceCraft uses optional dependency groups (extras) to keep the base package lightweight.
Adapters and some exporters are not installed unless you request them explicitly.

**Solution**

Install the extra that provides the module you need:

```bash
pip install "tracecraft[langchain]"      # LangChain adapter
pip install "tracecraft[llamaindex]"     # LlamaIndex adapter
pip install "tracecraft[pydantic-ai]"    # PydanticAI adapter
pip install "tracecraft[claude-sdk]"     # Claude SDK adapter
pip install "tracecraft[otlp]"           # OTLP exporter
pip install "tracecraft[mlflow]"         # MLflow exporter
pip install "tracecraft[receiver]"       # OpenTelemetry receiver
pip install "tracecraft[auto]"           # Auto-instrumentation
pip install "tracecraft[all]"            # All extras
```

**Prevention**

Add the required extra to your `pyproject.toml` or `requirements.txt` so it is always
installed in every environment:

```toml title="pyproject.toml"
[project]
dependencies = [
    "tracecraft[langchain,otlp]",
]
```

---

### OpenTelemetry version conflict

**Problem**

```
ImportError: cannot import name 'SpanExporter' from 'opentelemetry.sdk.trace.export'
AttributeError: module 'opentelemetry.trace' has no attribute 'use_span'
```

**Cause**

TraceCraft targets the OpenTelemetry Python SDK `>=1.20`. An older version installed by
another package in your environment is taking precedence.

**Solution**

Pin or upgrade to a compatible version:

```bash
pip install "opentelemetry-sdk>=1.20" "opentelemetry-api>=1.20"
pip install --upgrade "tracecraft[otlp]"
```

Check for conflicting packages:

```bash
pip show opentelemetry-sdk opentelemetry-api
pip list | grep opentelemetry
```

If a framework dependency forces an older version, use a virtual environment or a
dependency resolver override:

```toml title="pyproject.toml"
[tool.uv.override-dependencies]
opentelemetry-sdk = ">=1.20"
```

**Prevention**

Use a lockfile (`uv.lock`, `requirements.txt` from `pip-compile`) and run dependency
audits (`pip check`) in CI to catch version conflicts early.

---

### Platform-specific build failures on Apple Silicon or Windows

**Problem**

```
error: Failed building wheel for grpcio
error: Microsoft Visual C++ 14.0 or greater is required
```

**Cause**

The `grpcio` package (required by `tracecraft[otlp]`) has native extensions that must be
compiled if a pre-built wheel is not available for your platform and Python version.

**Solution**

=== "macOS (Apple Silicon)"

    Install the Xcode command-line tools and use a recent pip that can fetch pre-built wheels:

    ```bash
    xcode-select --install
    pip install --upgrade pip
    pip install "tracecraft[otlp]"
    ```

    If wheels are still unavailable, install `grpcio` with system OpenSSL:

    ```bash
    GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 pip install grpcio
    ```

=== "Windows"

    Install the Visual C++ Build Tools from the
    [Microsoft Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
    page, then retry:

    ```bat
    pip install --upgrade pip
    pip install "tracecraft[otlp]"
    ```

=== "Linux (Alpine/musl)"

    Install build dependencies first, then install the package:

    ```bash
    apk add --no-cache gcc musl-dev python3-dev
    pip install "tracecraft[otlp]"
    ```

**Prevention**

Pin `grpcio` to a version for which pre-built wheels exist for your target platforms.
Check [PyPI](https://pypi.org/project/grpcio/#files) for available wheels before
upgrading.

---

## Traces Not Appearing

### No output to the console

**Problem**

Your decorated functions run without errors, but nothing appears in the terminal.

**Cause**

The console exporter is not enabled, or `tracecraft.init()` was not called before the
decorated functions ran.

**Solution**

Ensure `tracecraft.init()` is called at application startup, before any decorated
function is invoked:

```python
import tracecraft

# Must be called before any @trace_* decorated function executes
tracecraft.init(console=True)

@tracecraft.trace_agent(name="my_agent")
def my_agent(prompt: str) -> str:
    ...

my_agent("Hello")  # Trace now appears in the console
```

Inspect the active configuration to confirm the console exporter is active:

```python
runtime = tracecraft.get_runtime()
print(runtime.config)
```

**Prevention**

Call `tracecraft.init()` as early as possible - typically the first statement after
standard library imports in your entry point module.

---

### OTLP backend is not receiving traces

**Problem**

Your application runs and `tracecraft.init()` succeeds, but the OTLP backend (Jaeger,
Grafana Tempo, etc.) shows no traces.

**Cause**

Common causes include a wrong endpoint URL, missing TLS configuration, a firewall
blocking the collector port, or the backend process not yet running.

**Solution**

1. Verify the endpoint is reachable from the application host:

    ```bash
    # HTTP/Protobuf endpoint
    curl -v http://localhost:4318/v1/traces

    # gRPC endpoint - check the port is open
    nc -zv localhost 4317
    ```

2. Enable debug logging to see what TraceCraft is attempting to send:

    ```python
    import logging
    logging.getLogger("tracecraft").setLevel(logging.DEBUG)
    ```

3. Review the exporter configuration and confirm `insecure=True` for local testing:

    ```python
    from tracecraft.exporters import OTLPExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(
                endpoint="http://localhost:4317",
                insecure=True,
            )
        ]
    )
    ```

4. Add a JSONL fallback exporter so traces are not lost while debugging:

    ```python
    from tracecraft.exporters import OTLPExporter, JSONLExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(endpoint="http://localhost:4317"),
            JSONLExporter(filepath="debug-traces.jsonl"),
        ]
    )
    ```

**Prevention**

Add a health check in your startup code that verifies the OTLP endpoint is reachable
before the application begins serving requests.

---

### TUI shows no traces after running the OTLP receiver

**Problem**

You configured the OTel receiver (`tracecraft.otel.setup_exporter`) and ran your
application, but `tracecraft tui` shows an empty trace list.

**Cause**

The receiver writes traces to a JSONL file or SQLite database. The TUI must be pointed
at the same file path that the receiver is writing to.

**Solution**

Check the receiver configuration for the output path and pass that same path to the TUI:

```python title="app.py"
from tracecraft.otel import setup_exporter

tracer = setup_exporter(
    endpoint="http://localhost:4318",
    service_name="my-agent",
    output_path="traces/receiver.jsonl",  # Note this path
)
```

```bash
tracecraft tui traces/receiver.jsonl   # Use the same path
```

If no `output_path` was specified, check the default path documented in `setup_exporter`:

```python
from tracecraft.otel import setup_exporter
help(setup_exporter)
```

**Prevention**

Always specify an explicit `output_path` in `setup_exporter` so the path is unambiguous
in both your application code and your TUI launch command.

---

### Trace hierarchy is flat - child steps are missing

**Problem**

The TUI shows the top-level agent step, but LLM calls, tool invocations, and retrieval
steps that happen inside it are missing or appear as separate root traces.

**Cause**

The `contextvars.ContextVar` that carries the current `AgentRun` and parent `Step` is
not propagating into the child execution context. This happens when:

- Child functions run in separate **threads** (`ThreadPoolExecutor`).
- Child functions run in separate **processes** (`ProcessPoolExecutor`).
- Framework callbacks are invoked in a different context (use the framework-specific
  adapter instead of plain decorators).
- Steps are started in `asyncio` tasks that were created before the parent step opened.

**Solution**

For threads, copy the context explicitly before submitting work:

```python
import contextvars
from concurrent.futures import ThreadPoolExecutor

ctx = contextvars.copy_context()

with ThreadPoolExecutor() as pool:
    future = pool.submit(ctx.run, my_traced_function, arg)
```

For async tasks, create them inside a traced function so they inherit its context:

```python
@trace_agent(name="coordinator")
async def coordinator(tasks: list[str]) -> list[str]:
    # Tasks created here inherit the coordinator's context
    return await asyncio.gather(*[worker(t) for t in tasks])

@trace_tool(name="worker")
async def worker(task: str) -> str:
    ...
```

For framework integrations, always use the TraceCraft adapter:

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()
result = chain.invoke(input, config={"callbacks": [handler]})
```

**Prevention**

Use the framework-specific adapters for LangChain, LlamaIndex, and PydanticAI. For
custom threading code, always propagate context with `contextvars.copy_context().run()`.

---

## Integration Problems

### LangChain callbacks are not firing

**Problem**

You attached `TraceCraftCallbackHandler` to a chain, but the handler methods are never
called and no steps appear in the trace.

**Cause**

The handler must be passed as part of the `config` dictionary at invocation time. Adding
it only to a component at construction time does not guarantee it propagates to all steps
in the chain.

**Solution**

Pass the handler inside `config` at `.invoke()` time:

```python
from tracecraft.adapters.langchain import TraceCraftCallbackHandler

handler = TraceCraftCallbackHandler()

# Correct: config is forwarded to every step in the chain
result = chain.invoke(
    {"input": "Hello"},
    config={"callbacks": [handler]},
)
```

The same applies to `.ainvoke()`, `.stream()`, and `.astream()`.

**Prevention**

Always pass `config={"callbacks": [handler]}` at the top-level invocation. Consult the
LangChain documentation to verify that the specific component you are using forwards the
`config` dict to its children.

---

### Auto-instrumentation patches are not applied

**Problem**

After calling `tracecraft.init(auto_instrument=True)`, OpenAI or Anthropic API calls do
not appear in traces.

**Cause**

The `openai` (or `anthropic`) module was already imported before `tracecraft.init()` was
called. The patch cannot be applied retroactively to a module that is already loaded.

**Solution**

Restructure your entry point so patching happens before any other imports:

```python title="main.py"
# 1. Initialize the runtime and patch SDKs in one step
import tracecraft
tracecraft.init(console=True, auto_instrument=True)

# 2. Now import the rest of the application
import openai
from my_app import run_agent

run_agent()
```

If `openai` is imported at module level in many files, create a dedicated
`instrumentation.py` that is imported first in `main.py`.

**Prevention**

Treat `tracecraft.init(auto_instrument=True)` like logging setup - it must be the
very first line of your application entry point, before any application code is
imported.

---

### Duplicate spans appearing in traces

**Problem**

Each LLM call appears twice in the trace - once from a `@trace_llm` decorator and once
from the auto-instrumentation or an adapter.

**Cause**

Both a `@trace_llm` decorator on a wrapper function and auto-instrumentation are active,
so the same underlying API call is captured by two separate mechanisms.

**Solution**

Choose one instrumentation strategy per code path:

```python
# Option A: Use @trace_llm decorator, disable auto_instrument for that SDK
@trace_llm(name="gpt4_call", model="gpt-4o", provider="openai")
async def call_gpt4(prompt: str) -> str:
    response = await client.chat.completions.create(...)
    return response.choices[0].message.content


# Option B: Use auto-instrumentation, remove the decorator
async def call_gpt4(prompt: str) -> str:
    response = await client.chat.completions.create(...)  # Captured automatically
    return response.choices[0].message.content
```

To enable auto-instrumentation for one SDK only:

```python
import tracecraft

tracecraft.init(auto_instrument=["anthropic"])  # Only Anthropic, not OpenAI
```

**Prevention**

Document which instrumentation strategy is used for each SDK in your codebase. Avoid
mixing decorators and auto-instrumentation for the same API.

---

### Steps appear with the wrong StepType

**Problem**

Retrieval operations appear as `TOOL` steps, or agent orchestration appears as `LLM`
steps in the TUI.

**Cause**

The wrong decorator was applied, or a framework adapter mapped a callback to a different
type than expected.

**Solution**

Use the decorator that matches the semantic role of the function:

```python
from tracecraft import trace_agent, trace_tool, trace_llm, trace_retrieval

# Orchestration / decision-making
@trace_agent(name="planner")
async def planner(goal: str) -> list[str]: ...

# External tool calls
@trace_tool(name="web_search")
async def web_search(query: str) -> list[str]: ...

# LLM API calls
@trace_llm(name="summarizer", model="gpt-4o", provider="openai")
async def summarize(text: str) -> str: ...

# Vector search / document retrieval
@trace_retrieval(name="vector_search")
async def vector_search(query: str) -> list[str]: ...
```

To set a type that does not have a dedicated decorator, use the `step()` context manager:

```python
from tracecraft import step
from tracecraft.core.models import StepType

with step("quality_check", type=StepType.EVALUATION) as s:
    result = run_evaluator(output, expected)
    s.outputs["score"] = result.score
```

**Prevention**

Review [Core Concepts](getting-started/concepts.md) for the definition of each
`StepType` and the decorator that corresponds to it.

---

## Performance Issues

### High memory usage

**Problem**

Application memory grows steadily over time when processing many agent tasks.

**Cause**

The export queue is filling up faster than it is being flushed. This occurs when the
OTLP backend is slow or unreachable, causing in-memory batches to accumulate.

**Solution**

Reduce the queue size limit and flush more frequently:

```python
import os
from tracecraft.exporters import AsyncBatchExporter, OTLPExporter

exporter = AsyncBatchExporter(
    exporter=OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
    batch_size=50,           # Flush more often
    max_queue_size=200,      # Drop oldest traces when the queue is full
    flush_interval_ms=2000,  # Flush every 2 seconds
)

tracecraft.init(
    sampling_rate=0.05,
    exporters=[exporter],
)
```

Monitor queue health:

```python
runtime = tracecraft.get_runtime()
print("Export errors:", runtime.export_errors)
print("Traces dropped:", runtime.traces_dropped)
```

**Prevention**

Always set `max_queue_size` explicitly so the queue cannot grow unbounded. Match
`sampling_rate` to your backend's ingestion capacity.

---

### Slow application startup

**Problem**

Application startup is noticeably slower after adding `tracecraft.init()`.

**Cause**

Importing optional extras, particularly `grpcio` for the OTLP exporter, can add
100-300 ms to import time because of native extension loading.

**Solution**

Defer `tracecraft.init()` until after the application framework has finished its own
startup, or use only the built-in exporters (console, JSONL) which have no native
dependencies:

```python
# Fast startup: no native extensions
tracecraft.init(
    jsonl=True,
    jsonl_path="/tmp/traces/",
    console=False,
)
```

Measure import overhead before and after adding extras:

```bash
python -X importtime -c "import tracecraft" 2>&1 | grep tracecraft
```

**Prevention**

Install only the extras you use. Avoid `tracecraft[all]` in production images where
startup time is critical.

---

### High CPU usage from PII redaction

**Problem**

CPU usage spikes significantly when `enable_pii_redaction=True` is set alongside a high
sampling rate.

**Cause**

`RedactionProcessor` runs regex patterns against every string value in every trace
attribute. At 100% sampling with many patterns, this scales linearly with trace volume.

**Solution**

Switch to `ProcessorOrder.EFFICIENCY` so redaction only runs on traces that survive
sampling, and reduce the number of custom patterns:

```python
from tracecraft.core.config import ProcessorOrder

tracecraft.init(
    enable_pii_redaction=True,
    processor_order=ProcessorOrder.EFFICIENCY,  # Sample first, then redact
    sampling_rate=0.1,
)
```

!!! warning "Security trade-off"
    `EFFICIENCY` mode skips redaction on traces that are sampled out. Only use it when
    sampled-out traces are discarded immediately and never written to any persistent
    storage.

Limit which step attributes are scanned by specifying `redact_keys`:

```python
from tracecraft.processors.redaction import RedactionProcessor

redaction = RedactionProcessor(
    redact_keys=["inputs", "outputs"],  # Only scan these step attributes
)
tracecraft.init(processors=[redaction])
```

**Prevention**

Profile redaction overhead in a load test before enabling it in production. Start with
the built-in patterns and add custom patterns one at a time.

---

## Export Failures

### Connection refused when exporting to OTLP

**Problem**

```
grpc._channel._InactiveRpcError: StatusCode.UNAVAILABLE
Connection refused: localhost:4317
```

**Cause**

The OTLP collector or backend is not running, or the application is attempting to connect
before the collector is ready.

**Solution**

1. Confirm the collector is listening:

    ```bash
    nc -zv localhost 4317        # gRPC port
    nc -zv localhost 4318        # HTTP port
    ```

2. Add retry logic with exponential backoff:

    ```python
    from tracecraft.exporters import RetryingExporter, OTLPExporter

    exporter = RetryingExporter(
        exporter=OTLPExporter(endpoint="http://localhost:4317"),
        max_retries=5,
        backoff_factor=2.0,  # Waits: 1s, 2s, 4s, 8s, 16s
    )

    tracecraft.init(exporters=[exporter])
    ```

3. Add a JSONL fallback so no traces are lost during the outage:

    ```python
    from tracecraft.exporters import RetryingExporter, OTLPExporter, JSONLExporter

    tracecraft.init(
        exporters=[
            RetryingExporter(
                exporter=OTLPExporter(endpoint="http://localhost:4317"),
                max_retries=3,
            ),
            JSONLExporter(filepath="/var/log/traces/fallback.jsonl"),
        ]
    )
    ```

**Prevention**

In Docker Compose or Kubernetes, use a health check or `depends_on` condition so the
application does not start until the collector reports healthy.

---

### TLS handshake errors

**Problem**

```
ssl.SSLCertVerificationError: certificate verify failed
grpc._channel._InactiveRpcError: StatusCode.UNAVAILABLE: failed to connect to all addresses
```

**Cause**

The OTLP exporter is connecting to a TLS-enabled endpoint but the certificate is
self-signed, expired, or the system CA bundle does not include the signing authority.

**Solution**

=== "Update the system CA bundle"

    If the backend has a valid certificate from a public CA, update your CA bundle:

    ```bash
    pip install --upgrade certifi
    ```

=== "Specify a custom CA bundle"

    ```python
    from tracecraft.exporters import OTLPExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(
                endpoint="https://otlp.example.com:4317",
                certificate_file="/etc/ssl/certs/my-ca.pem",
            )
        ]
    )
    ```

=== "Disable TLS for internal networks only"

    !!! danger "Not for production"
        Only disable TLS on private internal networks. Never disable TLS verification in
        a production environment exposed to the internet.

    ```python
    from tracecraft.exporters import OTLPExporter

    tracecraft.init(
        exporters=[
            OTLPExporter(
                endpoint="http://internal-collector:4317",
                insecure=True,
            )
        ]
    )
    ```

**Prevention**

Use certificates from a trusted CA in production. Automate certificate renewal with
Let's Encrypt or your cloud provider's managed certificate service.

---

### Traces lost on application crash

**Problem**

When the application is forcefully terminated (SIGKILL, OOM kill), the last batch of
traces in the export queue is lost.

**Cause**

`AsyncBatchExporter` holds pending traces in memory and flushes on a timer or when the
batch is full. A hard kill signal does not allow the exporter time to flush.

**Solution**

Register a shutdown hook to flush all pending traces before the process exits:

```python
import atexit
import signal
import tracecraft

tracecraft.init(otlp_endpoint=os.getenv("OTLP_ENDPOINT"))


def _flush_traces(signum=None, frame=None) -> None:
    """Flush all pending traces before the process exits."""
    runtime = tracecraft.get_runtime()
    runtime.shutdown(timeout=5.0)


atexit.register(_flush_traces)
signal.signal(signal.SIGTERM, _flush_traces)
```

Add a JSONL fallback that is written synchronously per trace, so it survives a crash:

```python
from tracecraft.exporters import OTLPExporter, JSONLExporter

tracecraft.init(
    exporters=[
        OTLPExporter(endpoint=os.getenv("OTLP_ENDPOINT")),
        JSONLExporter(filepath="/var/log/traces/wal.jsonl"),  # Written immediately
    ]
)
```

The JSONL file can be replayed later with the TUI or a custom script.

**Prevention**

Handle `SIGTERM` gracefully in all production services. In Kubernetes, set
`terminationGracePeriodSeconds` long enough for the exporter to flush (10-30 seconds
is sufficient for most batch sizes).
