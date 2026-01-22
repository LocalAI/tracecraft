Comprehensive Architectural Specification and Implementation Strategy for AgentTrace Telemetry Abstraction Layer (TAL)

1. Introduction: The Crisis of Observability in Agentic Systems
The emergence of autonomous agentic frameworks—principally LangChain, LlamaIndex, and PydanticAI—has precipitated a fundamental shift in software architecture, transitioning from deterministic, procedural execution to non-deterministic, probabilistic reasoning loops. This paradigm shift has exposed severe deficiencies in traditional Application Performance Monitoring (APM) and observability standards. While OpenTelemetry (OTel) has established itself as the ubiquitous transport protocol for distributed tracing, its standard semantic conventions, designed primarily for HTTP-based microservices, fail to capture the cognitive nuances of agentic behaviors such as multi-step reasoning, tool selection, retrieval-augmented generation (RAG), and self-reflection.
The AgentTrace Telemetry Abstraction Layer (TAL) is proposed as a necessary infrastructure component to bridge this gap. It functions not merely as a passive logger but as an active, intelligent middleware that intercepts, normalizes, governs, and semanticizes the execution flow of AI agents. The complexity of this undertaking is compounded by the fragmentation of the ecosystem: distinct frameworks employ radically different internal event models—LangChain utilizes a callback system, LlamaIndex employs a hierarchical event dispatcher, and PydanticAI integrates natively with OpenTelemetry but through an opinionated lens (Logfire). Furthermore, the standardization landscape is in flux, characterized by a schism between the official, albeit nascent, OpenTelemetry Semantic Conventions for Generative AI and the industry-led OpenInference standard, which offers richer, albeit non-standard, attribute schemas.
This report provides an exhaustive, implementation-grade blueprint for the AgentTrace TAL. It dissects the architectural requirements for building a robust runtime capable of handling asynchronous context propagation in Python, specifies the precise adaptation logic required for major agent frameworks, defines a unified semantic schema that satisfies competing standards, and details the construction of governance engines and local debugging tools. The objective is to define a system that provides developers with "Flight Recorder" fidelity—the ability to replay, inspect, and debug the cognitive trajectory of an agent—while ensuring enterprise-grade governance and compatibility with the broader observability ecosystem.
2. The Observability Landscape and Standardization Challenges
Constructing a Telemetry Abstraction Layer requires a rigorous analysis of the underlying standards upon which it builds. The TAL must serve as a Rosetta Stone, translating framework-specific vernacular into a universal observability language. However, the definition of that "universal language" is currently a subject of active contention and development within the industry.
2.1 The Schism: OpenTelemetry GenAI vs. OpenInference
Two primary specifications compete to define how Generative AI operations should be represented in telemetry data: the official OpenTelemetry Semantic Conventions and the OpenInference standard developed by Arize AI.
The OpenTelemetry Semantic Conventions for Generative AI represent the official effort to standardize LLM telemetry within the CNCF ecosystem. As of 2025, these conventions are in a "Development" status, implying that breaking changes are possible and stability guarantees are not yet met.1 The specification focuses heavily on the request-response model typical of API interactions. It defines span names such as chat and generate_content, and attributes are strictly namespaced under gen_ai.* (e.g., gen_ai.usage.input_tokens, gen_ai.response.model).2 A critical limitation identified in the research is the deprecation of content-bearing attributes like gen_ai.prompt and gen_ai.completion in favor of event-based logging, which, while technically cleaner for privacy, complicates the immediate debugging experience for developers who expect to see inputs and outputs directly on the span.4
Conversely, OpenInference has emerged as a pragmatic, implementation-first standard, driven by the needs of AI engineers rather than protocol purists. It extends the semantic richness of traces to include concepts native to agents, such as "Tools" and "Retrievers," rather than treating everything as a generic dependency call. OpenInference uses a flatter, more direct attribute schema, prioritizing developer utility with keys like input.value, output.value, and tool.name.5 Crucially, OpenInference defines specific semantic conventions for RAG, including retrieval.documents (containing content, scores, and metadata IDs), which OpenTelemetry generic conventions currently lack.6
Implications for TAL Architecture: The TAL cannot simply choose one standard over the other. Choosing OpenTelemetry ensures long-term infrastructure compatibility but sacrifices immediate debugging fidelity and RAG observability. Choosing OpenInference provides rich debugging features but risks vendor lock-in or non-compliance with strict OTel collectors. Therefore, the TAL must implement a Polyglot Schema Strategy, actively populating attributes from both standards simultaneously where non-conflicting, and providing configuration options to prioritize one namespace over the other during export. This "Dual-Dialect" approach ensures that a trace generated by AgentTrace TAL is valid in a strict Jaeger instance while simultaneously lighting up rich features in AI-specific backends like Arize Phoenix or Langfuse.
2.2 Framework Fragmentation
Beyond the output standards, the input sources—the agent frameworks—exhibit profound architectural differences that the TAL must abstract away.
LangChain: Operates on a CallbackHandler architecture. Instrumentation relies on hooks like on_chain_start, on_llm_start, and on_tool_end. This model is event-driven and somewhat disconnected from the execution context, requiring the instrumentation layer to manually maintain the stack of active spans to correctly associate children with parents.7
LlamaIndex: Utilizes a more sophisticated instrumentation module (introduced in v0.10.x) centered around a Dispatcher pattern. It explicitly distinguishes between Events (point-in-time occurrences) and Spans (durational operations). This architecture is cleaner but requires the TAL to implement distinct SpanHandler and EventHandler classes to capture the full fidelity of the execution.9
PydanticAI: Represents a modern approach where observability is a first-class citizen, built directly on OpenTelemetry via the Logfire library. Here, the challenge is not adding instrumentation, but intercepting and governing it. The TAL must inject itself as the TracerProvider to capture spans that the framework emits natively, ensuring that governance policies (like redaction) are applied before the data leaves the process.11
3. Runtime Architecture Implementation
The Runtime is the heart of the TAL. It is responsible for managing the lifecycle of traces, generating unique identifiers, propagating context across asynchronous boundaries, and maintaining the integrity of the trace graph.
3.1 Context Propagation in Asynchronous Python
The most formidable technical challenge in instrumenting Python-based agents is maintaining the trace context (the linkage between a parent span and a child span) across asynchronous execution boundaries. Agents frequently utilize asyncio.gather for parallel tool execution or offload heavy tasks (like embedding generation) to thread pools. Without rigorous context management, traces become fragmented, appearing as disjointed root spans rather than a cohesive graph.
3.1.1 The ContextVars Foundation
OpenTelemetry for Python relies on the contextvars module to manage active spans.12 A ContextVar is a mechanism that stores state local to an asynchronous task, similar to how threading.local stores state for a thread. The TAL must define a global ContextVar, typically named current_context, which holds the OTel Context object.
However, standard contextvars usage is insufficient for all agentic patterns. While asyncio.create_task (and by extension gather) automatically copies the context to the new task in Python 3.7+, this automatic propagation breaks down when interacting with concurrent.futures.ThreadPoolExecutor, which is often used by vector database clients to perform blocking I/O without freezing the event loop.
3.1.2 Implementing a Context-Aware Executor
To solve the "broken trace" problem in RAG pipelines, the TAL Runtime must implement and enforce the use of a Context-Aware Executor. This component wraps the standard executor and manually copies the context into the worker thread.

Python

import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor

class TALContextExecutor(ThreadPoolExecutor):
    """
    A ThreadPoolExecutor that propagates the OpenTelemetry context
    to the worker threads, ensuring traces remain connected.
    """
    def submit(self, fn, *args, **kwargs):
        # Capture the context from the calling thread
        context = contextvars.copy_context()
        # Define a wrapper that runs the function inside the captured context
        def wrapper(*args,**kwargs):
            return context.run(fn, *args, **kwargs)

        return super().submit(wrapper, *args, **kwargs)

The TAL must provide this executor as a utility and, where possible, patch the agent framework's default executor to use this implementation. This ensures that when LlamaIndex offloads an embedding request to a thread, the resulting HTTP span is correctly linked as a child of the retrieval span.12
3.2 ID Generation and The Root Span Problem
In distributed systems, a trace ID is typically generated at the edge (e.g., a load balancer or ingress controller). In agentic systems, the "trace" often originates internally within a background worker or a CLI script.
3.2.1 Deterministic vs. Random IDs
While OTel defaults to random 128-bit Trace IDs, the TAL should support Deterministic Session Binding. For debugging purposes, it is highly advantageous to link a trace to a semantic session_id or conversation_id.
The TAL Runtime should allow the injection of a custom IdGenerator.15 This generator can create Trace IDs that are statistically unique but deterministically derived from a session identifier if one is provided. This allows a developer to query a backend for trace_id="session-12345..." rather than hunting for a random hex string.
Implementation Detail:
The IdGenerator must subclass opentelemetry.sdk.trace.id_generator.IdGenerator and implement generate_trace_id() and generate_span_id(). The implementation must ensure 64-bit randomness in the lower bits to satisfy W3C Trace Context requirements for sampling, while potentially encoding session metadata in the upper bits.15
3.2.2 Handling Orphaned Spans
A common pattern in agents is "Fire and Forget" background tasks (e.g., memory reflection steps). These tasks often start after the main HTTP request has returned, causing them to detach from the trace.
The TAL Runtime must implement a Session Context Store. When a user request initiates an agent, the TAL creates a Session object. Even if the main thread completes, the Session remains active. Any background task spawned by the agent must look up this Session and attach itself to the Session's active trace ID. This transforms the concept of a "Trace" from a strict request-response lifecycle to a "Session Lifecycle," which is far more appropriate for long-running agents.
3.3 The Polyglot Schema Engine
To address the standards conflict identified in Section 2.1, the TAL Runtime must implement a Schema Normalization Engine that runs at span creation time.
Mechanism:
When an adapter requests a new span (e.g., runtime.start_span(name="tool_call", inputs=...)), the engine does not simply pass these arguments to OTel. Instead, it expands them into a superset of attributes.
Schema Mapping Table:

Concept
TAL Internal Representation
OpenTelemetry GenAI Attribute
OpenInference Attribute
Model Name
model.name
gen_ai.request.model
llm.model_name
Input Data
input.payload
Deprecated / Event-based
input.value
Output Data
output.payload
Deprecated / Event-based
output.value
Token Cost
usage.input
gen_ai.usage.input_tokens
llm.token_count.prompt
Tool Name
tool.name
gen_ai.operation.name
tool.name
System
system.provider
gen_ai.system
llm.system

Conflict Resolution Strategy:
The runtime logic is additive.

Python

def start_span(self, name, **kwargs):
    attributes = {}
    if "model" in kwargs:
        attributes["gen_ai.request.model"] = kwargs["model"]
        attributes["llm.model_name"] = kwargs["model"]

    if "input" in kwargs:
        # OpenInference uses input.value
        attributes["input.value"] = str(kwargs["input"])
        # OTel prefers we don't put PII in attributes, but for local debug we must.
        # We flag this for the Governance engine to potentially redact later.
        attributes["_governance.sensitive"] = True

    return self.tracer.start_as_current_span(name, attributes=attributes)

This approach ensures that the "Input Value" is present for local debugging (via OpenInference keys) but can be stripped by the Governance engine before upstream export if strict OTel compliance is required.
4. Framework-Specific Adapter Implementation
The TAL must provide specialized adapters for the major frameworks. These adapters act as the translation layer, converting framework-specific events into the TAL's internal Polyglot Schema.
4.1 LlamaIndex Adapter
LlamaIndex's architecture is event-driven and hierarchical, utilizing a Dispatcher system that is highly amenable to instrumentation.
4.1.1 The SpanHandler Implementation
The core integration point is the BaseSpanHandler class.10 The TAL adapter must subclass this to intercept span lifecycle events.
class_name: Must return a unique identifier, e.g., AgentTraceSpanHandler.
new_span: This method is called when a span starts. The adapter must:
Extract id_and map it to OTel's Span ID.
Parse bound_args to extract function inputs. Since LlamaIndex passes raw Python objects (like QueryBundle or Node), the adapter must perform Object Serialization. It should extract text content from Node objects and query strings from QueryBundle objects to populate input.value.
prepare_to_exit_span: Called upon successful completion. The adapter captures the return value. If the return value is a Response object, it must extract the response.source_nodes to populate the retrieval.documents attribute, adhering to the OpenInference RAG specification.6
prepare_to_drop_span: This hook is critical for error tracking. It provides the exception object. The adapter must call span.record_exception(err) and set the span status to StatusCode.ERROR.
4.1.2 Dispatcher Registration
To ensure full coverage, the adapter must attach itself to the root dispatcher.

Python

import llama_index.core.instrumentation as instrument
from agenttrace.adapters.llamaindex import AgentTraceSpanHandler

def instrument_llamaindex():
    dispatcher = instrument.get_dispatcher("llama_index.core.instrumentation.root_dispatcher")
    handler = AgentTraceSpanHandler()
    dispatcher.add_span_handler(handler)

This registration should be idempotent to prevent duplicate span handling if the user calls the instrumentation function multiple times.9
4.2 LangChain Adapter
LangChain's architecture is callback-based. While it offers a Tracer interface, the BaseCallbackHandler is the most reliable integration point for synchronous and asynchronous event capture.
4.2.1 The Sync/Async Dual Implementation
LangChain separates synchronous and asynchronous callbacks (e.g., on_chain_start vs. on_chain_start (async)). The TAL adapter must implement both versions for every event type to ensure no events are missed in mixed-mode applications.7
Mapping Logic:
on_chain_start / on_agent_start: Initiates a span with kind=INTERNAL. If the chain class name suggests an agent (e.g., AgentExecutor), the span should be tagged as openinference.span.kind=AGENT.
on_llm_start: Initiates a span with kind=CLIENT. This is the point to capture gen_ai.request.model and gen_ai.system (provider).
on_tool_start: Initiates a span with kind=INTERNAL (or TOOL in OpenInference semantics). Captures tool.name and input arguments.
on_retriever_end: This is a critical hook for RAG observability. The payload contains a list of Document objects. The adapter must transform this list into the JSON structure required by retrieval.documents (content, score, metadata).6
4.2.2 The Stack Management Challenge
Unlike LlamaIndex, LangChain's callback interface does not always explicitly pass the parent run ID in a way that aligns with OTel's context. The adapter must maintain a thread-local (or context-local) Run Stack.
Push: On start, push the new OTel span onto the stack.
Pop: On end or error, pop the span and finish it.
Parenting: When starting a span, peek at the stack to find the parent. This manual management is necessary because LangChain's internal execution graph does not map 1:1 to OTel's ContextVars based propagation in all scenarios.
4.3 PydanticAI Integration
PydanticAI is unique as it instruments itself using OpenTelemetry natively via Logfire.11 The TAL's role here is not adaptation but Interception.
4.3.1 Provider Injection
PydanticAI allows for the configuration of a custom TracerProvider. The TAL must provide a utility to swap the default Logfire provider with the TAL provider.

Python

from opentelemetry import trace
from agenttrace.runtime import TALTracerProvider

def instrument_pydantic_ai():
    # Instantiate the TAL provider with our processors (Redaction, Buffering)
    provider = TALTracerProvider()

    # Set as the global default, which PydanticAI will pick up
    trace.set_tracer_provider(provider)

    # PydanticAI uses the global tracer by default unless configured otherwise

This approach ensures that PydanticAI's spans flow through the TAL's governance and debugging pipelines.11
4.3.2 Attribute Enrichment
Since the TAL does not control the creation of PydanticAI spans (the framework does), it cannot force the Polyglot Schema at creation time. Instead, the TAL must use a SpanProcessor to enrich these spans just before export. The processor inspects the PydanticAI-native attributes and injects the corresponding OpenInference/OTel GenAI attributes to ensure consistency with traces from other frameworks.
5. Governance Engine Implementation
The Governance Engine is a differentiator for the AgentTrace TAL. It moves observability from passive monitoring to active policy enforcement. This is implemented via a chain of SpanProcessors.
5.1 PII Redaction Processor
Redaction must occur in-memory, ensuring sensitive data never reaches the network layer or the local debug file.
Architecture:
The RedactionProcessor must implement the SpanProcessor interface and hook into the on_end(span) method. Since ReadableSpan attributes are immutable in some OTel implementations, the processor may need to construct a new dictionary of attributes and replace the span's internal attribute storage.17
Scrubbing Logic:
Targeted Keys: The processor should only scan attributes known to contain user content: input.value, output.value, gen_ai.prompt, message.content. Scanning system attributes (like latencies) is wasteful.
Regex Patterns: Implement a library of high-performance compiled regexes for SSNs, Credit Cards, API Keys (sk-[a-zA-Z0-9]+), and Email addresses.
Allowlist Mode: For high-security environments, the governance engine should support an "Allowlist Only" mode. If enabled, any attribute key not explicitly in the allowed_keys configuration is dropped entirely. This is a "Fail-Closed" security model.19
Hash-Based Redaction: Instead of replacing sensitive values with ***, the TAL should offer an option to replace them with Hash(value). This allows analysts to see that the same user input caused an error multiple times without knowing what the input was (Cardinality Analysis).
5.2 The "Kill Switch" and Cost Control
Governance also implies resource control. The TAL must track token usage in real-time.
Implementation:
This cannot be done in a SpanProcessor (which is reactive/async). It requires a Synchronous Hook within the adapters.
Token Counting: On new_span (LlamaIndex) or on_llm_start (LangChain), the adapter extracts the input text.
Estimation: Use a fast, approximate tokenizer (like tiktoken) to estimate cost.
Budget Check: Check a thread-safe SessionBudget counter.
Intervention: If current_usage + estimated_cost > limit, the adapter raises a GovernanceException immediately.
Effect: This aborts the framework's execution flow before the API call is made to the LLM provider, effectively acting as a circuit breaker for run-away agents.
6. Local Debugging and "Flight Recorder" Tools
Developers require immediate feedback loops. The "Flight Recorder" feature allows developers to see traces locally without spinning up a complex Docker-based observability stack (Jaeger, Zipkin, Collector).
6.1 The Buffering Span Processor
To show a complete trace locally, the TAL must capture spans until the operation completes.
Implementation:
Data Structure: A thread-safe deque (double-ended queue) is used to buffer completed spans.20
Trigger: The buffer is not flushed based on time, but on the completion of a Root Span.
Tail Sampling for Local Debug: The processor can be configured to FlushOnCondition.
ALWAYS: Dump every trace to disk (noisy).
ON_ERROR: Only dump traces where root_span.status == ERROR. This is highly effective for debugging flaky agents without wading through successful logs.21
6.2 Standalone HTML Report Generator
The specific requirement for local debugging is a standalone HTML file that acts as a "Trace Player."
Why D3.js?
While Playwright's trace viewer is powerful, it requires a Node.js runtime to generate traces. A D3.js implementation allows the TAL (Python) to generate the report by simply replacing a string placeholder in an HTML template. D3.js is lightweight, capable of rendering collapsible trees (essential for deep agent traces), and runs entirely in the browser.22
Technical Specification for Report Generation:
Tree Construction: The buffered flat list of spans must be converted into a hierarchical JSON tree.
Find the span with parent_id == None (Root).
Recursively find all spans where parent_id == current_span.context.span_id.
Compute exclusive_duration (Total duration - duration of children) for each node to highlight bottlenecks.
JSON Embedding:
Python

# Python Generator Logic

tree_data = construct_tree(buffer)
json_payload = json.dumps(tree_data)

with open("templates/report.html", "r") as f:
    template = f.read()

# Injection: The template contains <script>const TRACE_DATA = {{ DATA_PLACEHOLDER }};</script>

html_out = template.replace("{{ DATA_PLACEHOLDER }}", json_payload)

with open("agent_trace.html", "w") as f:
    f.write(html_out)

Visualization Features:
Timeline View: A Gantt chart visualization using D3 to show parallel execution (common in asyncio.gather tool calls).
Data Inspection: Clicking a node opens a side panel displaying input.value and output.value (attributes populated by the Polyglot Schema).
Search: A Javascript-based client-side search to find spans containing specific text or error codes.
6.3 The CLI Tool
To streamline the developer experience, the TAL should include a CLI entry point.
agenttrace run script.py: Runs the python script with the TAL instrumentation auto-injected.
agenttrace view last: Opens the most recently generated HTML report in the default browser.
7. Deployment Topologies
The TAL is designed to support flexible deployment models ranging from local development to scaled production Kubernetes environments.
7.1 Local / Notebook Topology
Configuration: export AGENTTRACE_MODE=LOCAL
Components: Adapters + Buffering Processor + HTML Exporter.
Output: Local .html files or console output.
Use Case: Rapid prototyping in Jupyter notebooks or local IDE debugging.
7.2 Production / Sidecar Topology
Configuration: export AGENTTRACE_MODE=PRODUCTION
Components: Adapters + Redaction Processor + OTLP Exporter.
Output: Protocol Buffers over gRPC to an OpenTelemetry Collector.
Mechanism: The OTLP exporter is configured to send data to localhost:4317 (Collector running as a sidecar) or a remote endpoint (Langfuse/Arize/Honeycomb).
Benefit: Offloads the network overhead and retries to the Collector. The TAL process remains lightweight.
7.3 Hybrid Topology (Sampling)
In high-volume production, tracing every agent step is cost-prohibitive.
Head Sampling: The TAL Runtime configures the OTel TraceIdRatioBased sampler to record only 1% of sessions.
Tail Sampling: The TAL sends all traces to a local Collector sidecar, which is configured with a tail_sampling processor to forward only traces that contain errors or high latency, dropping the rest.21
8. Conclusion and Future Outlook
The AgentTrace Telemetry Abstraction Layer represents a critical piece of infrastructure for the maturing AI engineering stack. By strictly decoupling the application logic from the observability implementation, it solves the fragmentation problem inherent in the current ecosystem.
The proposed architecture specifically addresses the nuances of agentic systems:
Context-Aware Runtime: Solves the broken trace problem in asynchronous RAG pipelines via custom executors and contextvars management.
Polyglot Schema: Bridges the gap between the rigid OTel standard and the rich OpenInference standard, ensuring compatibility without sacrificing fidelity.
Active Governance: Moves beyond logging to enforcement, providing redaction and cost control at the runtime level.
Local "Flight Recorder": Democratizes observability for developers by providing zero-dependency visualization tools.
As the OpenTelemetry Semantic Conventions for GenAI mature and stabilize, the TAL's internal mapping logic can be updated without breaking changes to the application code, effectively "future-proofing" the agent implementation. This architecture transforms observability from a passive debugging utility into a strategic asset for reliability and governance in autonomous systems.
9. Appendix: Reference Data Tables
9.1 Semantic Attribute Mapping Reference
Domain
Attribute Key
Type
Description
OTel Mapping
OpenInference Mapping
LLM
model.name
String
The name of the model invoked
gen_ai.request.model
llm.model_name
LLM
model.provider
String
The vendor (OpenAI, Anthropic)
gen_ai.system
llm.provider
LLM
gen_ai.usage.input_tokens
Int
Count of prompt tokens
gen_ai.usage.input_tokens
llm.token_count.prompt
LLM
gen_ai.usage.output_tokens
Int
Count of completion tokens
gen_ai.usage.output_tokens
llm.token_count.completion
Chain
input.value
String
Input to the chain/agent
Event Payload
input.value
Chain
output.value
String
Final output of the chain
Event Payload
output.value
RAG
retrieval.documents
JSON
List of retrieved chunks
N/A
retrieval.documents
Tool
tool.name
String
Name of the tool function
gen_ai.operation.name
tool.name
Tool
tool.parameters
JSON
Arguments passed to tool
N/A
tool.parameters
Error
error.type
String
Class name of exception
error.type
error.type

9.2 Adapter Capabilities Matrix
Feature
LlamaIndex Adapter
LangChain Adapter
PydanticAI Interceptor
Integration Point
BaseSpanHandler
BaseCallbackHandler
TracerProvider
Async Support
Native (Dispatcher)
Requires Dual Handlers
Native (OTel)
RAG Observability
High (Nodes)
Medium (Documents)
N/A (Model focused)
Input Capture
via bound_args
via on_chain_start
via Span Attributes
Governance Hook
Sync handle check
Sync callback check
Pre-export Processor

9.3 Governance Regex Pattern Examples
Entity
Pattern (Python Regex)
Action
Email
[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+
Mask e***@***.com
API Key (OpenAI)
sk-[a-zA-Z0-9]{48}
Redact ``
IPv4 Address
\b(?:\d{1,3}\.){3}\d{1,3}\b
Hash SHA256(IP)
Credit Card
\b(?:\d[ -]*?){13,16}\b
Redact ``

Works cited
Semantic conventions for generative AI systems - OpenTelemetry, accessed January 19, 2026, <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
Semantic Conventions for GenAI agent and framework spans - OpenTelemetry, accessed January 19, 2026, <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/>
Semantic conventions for generative client AI spans - OpenTelemetry, accessed January 19, 2026, <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/>
Gen AI | OpenTelemetry, accessed January 19, 2026, <https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/>
Spans - Arize AX Docs, accessed January 19, 2026, <https://arize.com/docs/ax/observe/tracing/spans>
Semantic Conventions | openinference - GitHub Pages, accessed January 19, 2026, <https://arize-ai.github.io/openinference/spec/semantic_conventions.html>
BaseCallbackHandler - LangChain.js, accessed January 19, 2026, <https://v03.api.js.langchain.com/classes/_langchain_core.callbacks_base.BaseCallbackHandler.html>
langchain.callbacks.base.BaseCallbackHandler, accessed January 19, 2026, <https://sj-langchain.readthedocs.io/en/latest/callbacks/langchain.callbacks.base.BaseCallbackHandler.html>
Instrumentation | LlamaIndex Python Documentation, accessed January 19, 2026, <https://developers.llamaindex.ai/python/framework/module_guides/observability/instrumentation/>
Span handlers - LlamaIndex, accessed January 19, 2026, <https://developers.llamaindex.ai/python/framework-api-reference/instrumentation/span_handlers/>
Debugging & Monitoring with Pydantic Logfire - Pydantic AI, accessed January 19, 2026, <https://ai.pydantic.dev/logfire/>
asyncio context propagation in Python 3.5/3.6 · Issue #71 · open-telemetry/opentelemetry-python - GitHub, accessed January 19, 2026, <https://github.com/open-telemetry/opentelemetry-python/issues/71>
Is OpenTelemetry in Python safe to use with Async? - Stack Overflow, accessed January 19, 2026, <https://stackoverflow.com/questions/77410600/is-opentelemetry-in-python-safe-to-use-with-async>
Context Propagation in Asynchronous and Multithreaded Backends | Leapcell, accessed January 19, 2026, <https://leapcell.io/blog/context-propagation-in-asynchronous-and-multithreaded-backends>
opentelemetry.sdk.trace.id_generator, accessed January 19, 2026, <https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.id_generator.html>
Integrate Logfire, accessed January 19, 2026, <https://logfire.pydantic.dev/docs/guides/onboarding-checklist/integrate/>
opentelemetry-collector-contrib/processor/attributesprocessor/README.md at main - GitHub, accessed January 19, 2026, <https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/attributesprocessor/README.md>
Python : Opentelemetry - Filtering PII Data from Logs - Reddit, accessed January 19, 2026, <https://www.reddit.com/r/OpenTelemetry/comments/1ececxi/python_opentelemetry_filtering_pii_data_from_logs/>
Mastering the OpenTelemetry Redaction Processor - Dash0, accessed January 19, 2026, <https://www.dash0.com/guides/opentelemetry-redaction-processor>
opentelemetry.sdk.trace package, accessed January 19, 2026, <https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.html>
Tail-based sampling - OpenTelemetry, accessed January 19, 2026, <https://opentelemetry.io/docs/languages/dotnet/traces/tail-based-sampling/>
D3.js tree diagram generated from external (JSON) data - GitHub Gist, accessed January 19, 2026, <https://gist.github.com/d3noob/8329447>
Create an interactive tree structure from json using D3 | Javascript - YouTube, accessed January 19, 2026, <https://www.youtube.com/watch?v=szc4KlykGl0>
Tail Sampling with OpenTelemetry: Why it's useful, how to do it, and what to consider, accessed January 19, 2026, <https://opentelemetry.io/blog/2022/tail-sampling/>
