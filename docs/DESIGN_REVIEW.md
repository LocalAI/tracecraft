# Design Review: Addressing Opinionated Decisions

This document analyzes the 10 most opinionated aspects of TraceCraft and provides recommendations on whether redesign is warranted, along with specific design proposals where applicable.

---

## Decision Framework

For each concern, I evaluate:

- **Legitimacy**: Is this a real problem or a theoretical concern?
- **Impact**: How many users would be affected?
- **Redesign Cost**: How much effort to fix?
- **Breaking Change**: Would this break existing users?
- **Verdict**: Keep, Modify, or Redesign

---

## 1. Global Singleton Runtime

### Current Design

```python
# Only way to use TraceCraft
tracecraft.init(config=config)
runtime = get_runtime()  # Returns global singleton
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Multi-tenant SaaS, testing, and modular codebases genuinely need isolated instances |
| Impact | **Medium** - Affects platform teams, not solo developers |
| Redesign Cost | **Medium** - Requires adding instance-based API alongside global |
| Breaking Change | **No** - Additive change |

### Verdict: **REDESIGN** - Add Instance-Based API

### Proposed Design

```python
# KEEP: Global convenience API (unchanged)
import tracecraft
tracecraft.init()

@trace_agent(name="my_agent")
def my_agent(): ...

# ADD: Explicit instance API for advanced users
from tracecraft import TraceCraftRuntime

# Create isolated runtime instances
runtime_tenant_a = TraceCraftRuntime(
    config=ConfigA(),
    exporters=[ExporterA()]
)
runtime_tenant_b = TraceCraftRuntime(
    config=ConfigB(),
    exporters=[ExporterB()]
)

# Use with explicit context
with runtime_tenant_a.trace_context() as ctx:
    # All traces in this block go to runtime_tenant_a
    result = my_agent()

# Or via dependency injection
@trace_agent(name="my_agent", runtime=runtime_tenant_a)
def my_agent(): ...
```

### Implementation Notes

- Global `init()` creates a default runtime stored in module state
- `TraceCraftRuntime` is a first-class, instantiable class
- Decorators accept optional `runtime` parameter; default to global
- Context managers allow scoped runtime selection
- Enables testing with isolated runtimes per test

---

## 2. Fixed Processor Pipeline Order

### Current Design

```python
# Hardcoded in runtime.py
processors = [
    TokenEnrichmentProcessor(),  # Always first
    RedactionProcessor(),        # Always second
    SamplingProcessor(),         # Always third
]
# No user control over ordering
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **Medium** - Some users want sampling before redaction for efficiency |
| Impact | **Low** - Most users don't think about processor order |
| Redesign Cost | **Low** - Simple configuration change |
| Breaking Change | **No** - Default behavior unchanged |

### Verdict: **MODIFY** - Make Order Configurable

### Proposed Design

```python
from tracecraft import TraceCraftConfig, ProcessorOrder

config = TraceCraftConfig()

# Option 1: Predefined strategies
config.processor_order = ProcessorOrder.EFFICIENCY  # Sample → Redact → Enrich
config.processor_order = ProcessorOrder.SAFETY      # Enrich → Redact → Sample (default)

# Option 2: Explicit ordering
config.processor_order = [
    "sampling",      # Sample first (skip work on dropped traces)
    "redaction",     # Redact survivors
    "enrichment",    # Enrich last
]

# Option 3: Insert custom processors
config.processors = [
    SamplingProcessor(rate=0.1),
    CustomAuditProcessor(),      # User's custom processor
    RedactionProcessor(),
    TokenEnrichmentProcessor(),
]
```

### Implementation Notes

- Default remains current order (safety-first)
- Predefined strategies cover common patterns
- Advanced users can specify exact order
- Custom processors can be inserted at any position
- Validate that required processors are present (warn if redaction missing)

---

## 3. Automatic Input Capture via Reflection

### Current Design

```python
@trace_agent(name="my_agent")
def my_agent(query: str, api_key: str, config: dict):
    # ALL parameters captured automatically
    # api_key appears in traces before redaction sees it
    ...
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Security risk; sensitive params captured before redaction |
| Impact | **High** - Affects anyone with sensitive function parameters |
| Redesign Cost | **Low** - Add exclude parameter to decorators |
| Breaking Change | **No** - Additive; default behavior unchanged |

### Verdict: **REDESIGN** - Add Input Exclusion

### Proposed Design

```python
# Option 1: Exclude specific parameters
@trace_agent(
    name="my_agent",
    exclude_inputs=["api_key", "credentials", "token"]
)
def my_agent(query: str, api_key: str, credentials: dict):
    ...
# Traces show: {"query": "...", "api_key": "[EXCLUDED]", "credentials": "[EXCLUDED]"}

# Option 2: Include only specific parameters (allowlist)
@trace_agent(
    name="my_agent",
    include_inputs=["query", "user_id"]  # Only these captured
)
def my_agent(query: str, api_key: str, user_id: str):
    ...

# Option 3: Parameter-level annotation (more Pythonic)
from tracecraft import Sensitive

@trace_agent(name="my_agent")
def my_agent(
    query: str,
    api_key: Annotated[str, Sensitive()],  # Never captured
    config: dict
):
    ...

# Option 4: Capture nothing by default, explicit opt-in
@trace_agent(name="my_agent", capture_inputs=False)
def my_agent(query: str, api_key: str):
    ...
```

### Recommended Approach

Implement **Option 1** (exclude_inputs) as it's:

- Backward compatible (default excludes nothing)
- Simple to understand
- Handles the common case (exclude a few sensitive params)

Also implement **Option 4** (capture_inputs=False) for maximum control.

### Implementation Notes

- Add `exclude_inputs: list[str] = []` to all trace decorators
- Add `capture_inputs: bool = True` for complete opt-out
- Excluded params show as `"[EXCLUDED]"` not omitted (preserves arity visibility)
- Consider adding common exclusions to config: `config.default_excluded_inputs = ["api_key", "token", "password"]`

---

## 4. Dual-Schema Dialect as Default

### Current Design

```python
# Default in schema/canonical.py
class SchemaDialect(Enum):
    OTEL_GENAI = "otel_genai"
    OPENINFERENCE = "openinference"
    BOTH = "both"  # DEFAULT - generates both attribute sets
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **Medium** - Payload bloat is real but rarely critical |
| Impact | **Low** - Most users don't notice attribute duplication |
| Redesign Cost | **Trivial** - Change default enum value |
| Breaking Change | **Minor** - Users relying on both dialects would need to opt-in |

### Verdict: **MODIFY** - Change Default to Single Dialect

### Proposed Design

```python
# New default: OTel GenAI (industry standard)
DEFAULT_SCHEMA_DIALECT = SchemaDialect.OTEL_GENAI

# Configuration
config = TraceCraftConfig()
config.schema_dialect = SchemaDialect.OTEL_GENAI      # Default
config.schema_dialect = SchemaDialect.OPENINFERENCE   # For Arize/Phoenix users
config.schema_dialect = SchemaDialect.BOTH            # Explicit opt-in for compatibility

# Auto-detection based on exporter (nice-to-have)
# If exporting to Phoenix → auto-select OpenInference
# If exporting to generic OTLP → auto-select OTel GenAI
```

### Implementation Notes

- Change default from `BOTH` to `OTEL_GENAI`
- Document dialect selection guidance:
  - Use `OTEL_GENAI` for: Jaeger, Tempo, Datadog, generic OTLP
  - Use `OPENINFERENCE` for: Arize Phoenix, OpenInference-native tools
  - Use `BOTH` for: Migration periods, multi-backend setups
- Consider auto-detection based on configured exporters

---

## 5. Console + JSONL Exporters Enabled by Default

### Current Design

```python
# In env_config.py
class EnvironmentSettings:
    console_enabled: bool = True   # Always on
    jsonl_enabled: bool = True     # Always on
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Breaks in read-only filesystems, noisy in production |
| Impact | **Medium** - Affects serverless/container deployments |
| Redesign Cost | **Low** - Environment-aware defaults |
| Breaking Change | **Minor** - Production users get quieter defaults |

### Verdict: **REDESIGN** - Environment-Aware Defaults

### Proposed Design

```python
# Smart defaults based on detected environment
def get_default_exporters() -> dict:
    env = detect_environment()

    if env == "development" or env == "test":
        return {
            "console_enabled": True,
            "jsonl_enabled": True,
        }
    elif env in ("staging", "production"):
        return {
            "console_enabled": False,  # Don't pollute logs
            "jsonl_enabled": False,    # Don't write to filesystem
        }
    else:
        # Unknown environment: safe defaults
        return {
            "console_enabled": False,
            "jsonl_enabled": False,
        }

def detect_environment() -> str:
    """Detect environment from various signals."""
    # 1. Explicit configuration
    if os.getenv("TRACECRAFT_ENVIRONMENT"):
        return os.getenv("TRACECRAFT_ENVIRONMENT")

    # 2. Common cloud indicators
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "production"
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        return "production"
    if os.getenv("CLOUD_RUN_JOB"):
        return "production"

    # 3. CI indicators
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS"):
        return "test"

    # 4. Default to development (local machine)
    return "development"
```

### Alternative: Explicit Mode Selection

```python
import tracecraft

# Quick local development (current behavior)
tracecraft.init(mode="local")  # Console + JSONL enabled

# Production mode
tracecraft.init(mode="production")  # Only configured exporters, no defaults

# Explicit (always works)
tracecraft.init(
    console=False,
    jsonl=False,
    exporters=[OTLPExporter(...)]
)
```

### Implementation Notes

- Add environment detection logic
- Default to quiet mode in detected production environments
- Keep `mode="local"` for explicit local debugging
- Document the detection logic so users understand behavior
- Always allow explicit override via config

---

## 6. Redaction Disabled by Default

### Current Design

```python
# In config.py
class RedactionConfig:
    enabled: bool = False  # Off by default
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Contradicts "governance built-in" promise; privacy risk |
| Impact | **High** - Users may leak PII without realizing |
| Redesign Cost | **Low** - Change default boolean |
| Breaking Change | **Medium** - Users relying on seeing full data would need to opt-out |

### Verdict: **REDESIGN** - Enable by Default with Development Bypass

### Proposed Design

```python
# New defaults
class RedactionConfig:
    enabled: bool = True  # ON by default (privacy-first)
    mode: RedactionMode = RedactionMode.MASK  # "[REDACTED]" replacement

# Development override for debugging
tracecraft.init(
    mode="development",  # Implies redaction disabled for debugging
)

# Or explicit
config = TraceCraftConfig()
config.redaction.enabled = False  # Explicit opt-out

# Production should require explicit disable
if environment == "production" and not config.redaction.enabled:
    warnings.warn(
        "PII redaction is disabled in production. "
        "Set TRACECRAFT_REDACTION_ENABLED=true or acknowledge with "
        "TRACECRAFT_ALLOW_UNREDACTED_PRODUCTION=true"
    )
```

### Implementation Notes

- Change default to `enabled=True`
- Add `mode="development"` that disables redaction + enables console/JSONL
- In production, warn if redaction explicitly disabled
- Document migration path for existing users
- Consider a `TRACECRAFT_UNSAFE_DISABLE_REDACTION=true` env var for explicit acknowledgment

---

## 7. Strict StepType Enum

### Current Design

```python
class StepType(str, Enum):
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    MEMORY = "memory"
    GUARDRAIL = "guardrail"
    EVALUATION = "evaluation"
    WORKFLOW = "workflow"
    ERROR = "error"
    # No extensibility
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **Low-Medium** - Edge case; most patterns fit existing types |
| Impact | **Low** - Advanced users only |
| Redesign Cost | **Medium** - Requires schema changes |
| Breaking Change | **No** - Additive |

### Verdict: **MINOR MODIFY** - Add CUSTOM Type with Subtype Field

### Proposed Design

```python
class StepType(str, Enum):
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    RETRIEVAL = "retrieval"
    MEMORY = "memory"
    GUARDRAIL = "guardrail"
    EVALUATION = "evaluation"
    WORKFLOW = "workflow"
    ERROR = "error"
    CUSTOM = "custom"  # NEW: escape hatch

class Step(BaseModel):
    step_type: StepType
    custom_type: str | None = None  # NEW: subtype for CUSTOM

    @model_validator(mode="after")
    def validate_custom_type(self):
        if self.step_type == StepType.CUSTOM and not self.custom_type:
            raise ValueError("custom_type required when step_type is CUSTOM")
        return self

# Usage
@trace_step(step_type=StepType.CUSTOM, custom_type="planner")
def planning_phase(): ...

@trace_step(step_type=StepType.CUSTOM, custom_type="router")
def route_request(): ...
```

### Alternative: Keep as-is with Documentation

The current enum covers most use cases. Could also just document:

- `AGENT` = any autonomous decision-making component
- `WORKFLOW` = orchestration, routing, planning
- `TOOL` = any function/action execution

### Recommendation

Add `CUSTOM` type for escape hatch, but don't over-engineer. Most users can map their concepts to existing types.

---

## 8. Thread-Local Context Model

### Current Design

```python
# In decorators.py
_current_run: ContextVar[AgentRun | None] = ContextVar("current_run", default=None)
_current_step: ContextVar[Step | None] = ContextVar("current_step", default=None)
_pending_parents: dict[str, str] = {}  # Global dict for parent tracking
MAX_STEP_DEPTH = 100  # Arbitrary limit
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Async context loss is a real problem |
| Impact | **Medium** - Affects async-heavy applications |
| Redesign Cost | **High** - Fundamental architecture change |
| Breaking Change | **Potentially** - Behavior changes in async code |

### Verdict: **MODIFY** - Improve Async Support, Don't Rewrite

### Proposed Design

Full redesign is too costly. Instead:

```python
# 1. Document limitations clearly
"""
Note: TraceCraft uses Python ContextVars for trace context propagation.
In async code, context is automatically propagated in most cases, but
may be lost when using:
- asyncio.create_task() without context copying
- run_in_executor() without explicit context
- Third-party async libraries that don't propagate context

Use the provided helpers for these cases.
"""

# 2. Provide async-aware helpers (already partially exist)
from tracecraft.contrib.async_helpers import (
    create_task_with_context,
    gather_with_context,
    run_in_executor_with_context,
)

# Instead of:
task = asyncio.create_task(my_coroutine())

# Use:
task = create_task_with_context(my_coroutine())

# 3. Add context snapshot/restore for manual cases
from tracecraft import capture_context, restore_context

ctx = capture_context()  # Snapshot current trace context

async def worker():
    with restore_context(ctx):  # Restore in new async context
        await do_work()

# 4. Remove arbitrary MAX_STEP_DEPTH or make configurable
config.max_step_depth = 100  # Default
config.max_step_depth = None  # Unlimited (warn about memory)
```

### Implementation Notes

- Don't attempt full async rewrite (too risky, too costly)
- Document known limitations prominently
- Provide helpers that "just work" for common async patterns
- Make `MAX_STEP_DEPTH` configurable with warning for unlimited
- Consider adding async-specific decorators: `@trace_agent_async`

---

## 9. Deep Copy in Redaction Processor

### Current Design

```python
# In processors/base.py
def process(self, run: AgentRun) -> AgentRun:
    run_copy = run.model_copy(deep=True)  # Always deep copy
    # ... redact run_copy ...
    return run_copy
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **Medium** - Real memory concern for large traces |
| Impact | **Low** - Only affects high-throughput systems with large traces |
| Redesign Cost | **Medium** - Requires careful mutation handling |
| Breaking Change | **No** - Optimization |

### Verdict: **MODIFY** - Lazy/Conditional Copying

### Proposed Design

```python
class RedactionProcessor(BaseProcessor):
    def __init__(self, config: RedactionConfig):
        self.config = config

    def process(self, run: AgentRun) -> AgentRun:
        # Skip entirely if disabled
        if not self.config.enabled:
            return run  # No copy needed

        # Check if redaction is actually needed
        if not self._needs_redaction(run):
            return run  # No copy needed

        # Only copy if we're actually going to modify
        run_copy = run.model_copy(deep=True)
        self._redact(run_copy)
        return run_copy

    def _needs_redaction(self, run: AgentRun) -> bool:
        """Quick scan to check if any redaction patterns match."""
        # Fast string scan without copying
        content = self._extract_redactable_content(run)
        return any(
            pattern.search(content)
            for pattern in self.patterns
        )
```

### Alternative: Copy-on-Write Wrapper

```python
class LazyRedactedRun:
    """Wrapper that only copies when mutation is needed."""
    def __init__(self, run: AgentRun):
        self._original = run
        self._copy = None

    def get_mutable(self) -> AgentRun:
        if self._copy is None:
            self._copy = self._original.model_copy(deep=True)
        return self._copy

    def get_result(self) -> AgentRun:
        return self._copy if self._copy else self._original
```

### Implementation Notes

- Add fast pre-scan to check if redaction needed
- Skip copy entirely when redaction disabled
- Consider copy-on-write for advanced optimization
- Benchmark to ensure optimization is worthwhile

---

## 10. Environment Name Validation

### Current Design

```python
# In env_config.py
class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"
    # Only these 4 allowed
```

### Assessment

| Criterion | Evaluation |
|-----------|------------|
| Legitimacy | **High** - Arbitrary restriction with no benefit |
| Impact | **Low** - Easy workaround (use "staging" for everything) |
| Redesign Cost | **Trivial** - Remove enum restriction |
| Breaking Change | **No** - Additive |

### Verdict: **REDESIGN** - Allow Arbitrary Strings

### Proposed Design

```python
# Remove enum, use string with suggestions
class EnvironmentSettings(BaseSettings):
    environment: str = "development"

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        known_environments = {
            "development", "staging", "production", "test",
            "local", "ci", "qa", "integration", "canary",
            "preview", "sandbox"
        }
        if v.lower() not in known_environments:
            # Warn but allow
            warnings.warn(
                f"Unknown environment '{v}'. Known environments: {known_environments}. "
                "Custom environments are allowed but may not have optimized defaults."
            )
        return v.lower()

# Usage
TRACECRAFT_ENVIRONMENT=canary  # Works!
TRACECRAFT_ENVIRONMENT=my-custom-env  # Works with warning
```

### Implementation Notes

- Change from Enum to str
- Keep list of "known" environments for smart defaults
- Warn on unknown environments (don't error)
- Document that custom environments get neutral defaults

---

## Summary: Redesign Decisions

| # | Aspect | Verdict | Priority | Effort |
|---|--------|---------|----------|--------|
| 1 | Global Singleton Runtime | **REDESIGN** | P1 | Medium |
| 2 | Fixed Processor Order | **MODIFY** | P2 | Low |
| 3 | Automatic Input Capture | **REDESIGN** | P1 | Low |
| 4 | Dual-Schema Default | **MODIFY** | P3 | Trivial |
| 5 | Console/JSONL Defaults | **REDESIGN** | P1 | Low |
| 6 | Redaction Disabled | **REDESIGN** | P1 | Low |
| 7 | Strict StepType Enum | **MINOR MODIFY** | P3 | Low |
| 8 | Thread-Local Context | **MODIFY** | P2 | Medium |
| 9 | Deep Copy Redaction | **MODIFY** | P3 | Medium |
| 10 | Environment Validation | **REDESIGN** | P2 | Trivial |

---

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 weeks)

High impact, low effort changes:

1. **Environment validation** - Remove enum restriction (trivial)
2. **Redaction default** - Enable by default (trivial, high impact)
3. **Input exclusion** - Add `exclude_inputs` parameter (low effort, high impact)
4. **Schema dialect default** - Change to `OTEL_GENAI` (trivial)

### Phase 2: Smart Defaults (2-3 weeks)

Environment-aware behavior:

5. **Console/JSONL defaults** - Environment detection (low-medium effort)
6. **Processor ordering** - Add configuration options (low effort)

### Phase 3: Architecture Improvements (4-6 weeks)

Larger changes for advanced users:

7. **Instance-based runtime** - Add alongside global API (medium effort)
8. **Async context helpers** - Document + provide utilities (medium effort)
9. **Lazy redaction copying** - Optimization (medium effort)

### Phase 4: Nice-to-Have (As needed)

Lower priority:

10. **Custom StepType** - Add CUSTOM type (low effort, low impact)

---

## Migration Notes

### For Existing Users

Most changes are additive or change defaults. Migration guide:

```python
# If you relied on seeing full unredacted data:
config.redaction.enabled = False  # Explicit opt-out

# If you relied on dual schema output:
config.schema_dialect = SchemaDialect.BOTH  # Explicit opt-in

# If you relied on console/JSONL in production:
tracecraft.init(console=True, jsonl=True)  # Explicit enable
```

### Deprecation Strategy

For breaking changes, use deprecation warnings for one minor version:

```python
import warnings

if config.schema_dialect is None:
    warnings.warn(
        "Default schema dialect changing from BOTH to OTEL_GENAI in v2.0. "
        "Set schema_dialect explicitly to suppress this warning.",
        DeprecationWarning
    )
```
