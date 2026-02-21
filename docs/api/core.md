# Core API

Core functionality of Trace Craft.

## Module: tracecraft.core

::: tracecraft.core.runtime
    options:
      show_root_heading: true
      show_source: true

::: tracecraft.core.models
    options:
      show_root_heading: true
      show_source: false

::: tracecraft.core.config
    options:
      show_root_heading: true
      show_source: false

## Classes

### TraceCraftRuntime

Main runtime for managing traces.

```python
from tracecraft import TraceCraftRuntime, TraceCraftConfig

config = TraceCraftConfig(service_name="my-service")
runtime = TraceCraftRuntime(config=config)

# Create a run
with runtime.run("my_run"):
    # Your traced code
    pass
```

### AgentRun

Represents a complete trace.

### Step

Represents a single span in a trace.

### StepType

Enumeration of step types:

- `AGENT` - Agent orchestration
- `TOOL` - Tool execution
- `LLM` - LLM API call
- `RETRIEVAL` - Retrieval operation
- `WORKFLOW` - General workflow step

## Functions

### init()

Initialize Trace Craft with configuration. Returns the global `TraceCraftRuntime` singleton (subsequent calls return the same instance).

**Signature:**

```python
tracecraft.init(
    # Service identity
    service_name: str | None = None,        # shown in TUI + OTLP; reads from config / TRACECRAFT_SERVICE_NAME

    # Built-in exporters
    console: bool | None = None,            # pretty-print to terminal
    jsonl: bool | None = None,              # write to JSONL file
    jsonl_path: str | None = None,          # JSONL output path

    # TUI receiver shorthand
    receiver: bool | str | None = None,     # True → http://localhost:4318; str → custom URL

    # Auto-instrumentation
    auto_instrument: bool | list[str] | None = None,  # True / ["openai", "anthropic"] / False

    # Custom exporters added alongside built-ins
    exporters: list[BaseExporter] | None = None,

    # Storage backend override ("none" disables local storage)
    storage: str | None = None,
) -> TraceCraftRuntime
```

Settings are resolved in this order (highest priority wins):

1. Explicit parameters passed to `init()`
2. `.tracecraft/config.yaml` (project root or `~`)
3. `TRACECRAFT_*` environment variables
4. Built-in defaults

**Examples:**

```python
import tracecraft

# Live TUI — stream traces as they happen
runtime = tracecraft.init(
    auto_instrument=True,
    receiver=True,
    service_name="my-agent",
)

# File-based — write to JSONL, open TUI separately
runtime = tracecraft.init(
    auto_instrument=True,
    jsonl=True,
    service_name="my-agent",
)

# Custom receiver URL
runtime = tracecraft.init(
    receiver="http://remote-host:4318",
    service_name="my-agent",
)

# Custom exporter + receiver together
from tracecraft.exporters.otlp import OTLPExporter

runtime = tracecraft.init(
    receiver=True,
    exporters=[OTLPExporter(endpoint="http://jaeger:4317")],
    console=False,
)
```

### get_runtime()

Get the current global runtime.

```python
from tracecraft import get_runtime

runtime = get_runtime()
```

## Next Steps

- [Decorators API](decorators.md)
- [Configuration API](configuration.md)
- [User Guide](../user-guide/index.md)
