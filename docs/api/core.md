# Core API

Core functionality of TraceCraft.

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

Initialize TraceCraft with configuration.

```python
import tracecraft

runtime = tracecraft.init(
    service_name="my-service",
    console=True,
    jsonl=True,
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
