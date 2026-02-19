# Getting Help

TraceCraft is maintained by an open-source community. This page describes the best way to get help, report problems, and contribute ideas depending on your situation.

---

## Quick Help Resources

Before opening an issue or starting a discussion, the answer may already exist:

<div class="grid cards" markdown>

- :material-frequently-asked-questions:{ .lg .middle } **FAQ**

    ---

    Answers to common setup and usage questions

    [:octicons-arrow-right-24: Troubleshooting Guide](user-guide/tui.md)

- :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    Step-by-step documentation for all features

    [:octicons-arrow-right-24: User Guide](user-guide/index.md)

- :material-api:{ .lg .middle } **API Reference**

    ---

    Complete reference for all classes and functions

    [:octicons-arrow-right-24: API Reference](api/index.md)

- :material-text-search:{ .lg .middle } **Search the Docs**

    ---

    Use the search bar at the top of any page (keyboard shortcut: ++slash++)

    [:octicons-arrow-right-24: Home](index.md)

</div>

### Search Tips

- Use specific class or function names: `TraceCraftRuntime`, `RedactionProcessor`, `trace_llm`
- Search for error messages verbatim (without line numbers or paths)
- Check the [Glossary](glossary.md) if a term is unfamiliar
- Look at the [Changelog](changelog.md) if behavior changed after an upgrade

---

## Community Support (GitHub Discussions)

**GitHub Discussions** is the right place for questions, general feedback, and sharing what you have built.

[:octicons-mark-github-16: Open a Discussion](https://github.com/LocalAI/tracecraft/discussions){ .md-button }

### When to Use Discussions

- You have a question about how to use a feature
- You want to know the recommended approach for a use case
- You have a feature idea you want to explore before opening a formal request
- You want to share a project that uses TraceCraft
- You are unsure whether something is a bug or intentional behavior

### Discussion Categories

| Category | Use For |
|---|---|
| **Q&A** | Questions about installation, usage, and configuration |
| **Ideas** | Feature proposals, enhancement suggestions |
| **Show and Tell** | Projects, integrations, and examples built with TraceCraft |
| **General** | Everything else |

### How to Ask an Effective Question

A well-formed question gets a faster, more useful answer. Include the following:

**1. Your environment**

```
TraceCraft version: 0.x.y  (tracecraft --version)
Python version:    3.11.x  (python --version)
OS:                macOS 14, Ubuntu 22.04, Windows 11, etc.
Installation:      pip / uv / conda / source
Framework:         LangChain 0.x, LlamaIndex 0.x, plain Python, etc.
```

**2. What you are trying to do**

Describe your goal in one or two sentences. Explain the context if it is not obvious.

**3. What you have tried**

Include the relevant code, configuration, and any steps you have already taken to debug the issue.

```python
import tracecraft
from tracecraft import trace_agent

tracecraft.init(console=True)

@trace_agent(name="my_agent")
def agent(query: str) -> str:
    # Minimal example that reproduces the problem
    ...
```

**4. What you expected vs. what happened**

Be specific. "It doesn't work" is hard to act on. "The console output shows nothing after calling `tracecraft.init(console=True)`" is actionable.

**5. Error messages**

Paste the full traceback, not just the last line.

!!! tip "Minimal Reproduction"
    The single most effective way to get a quick answer is to provide the smallest possible code example that reproduces the issue. Trim your code to just what is needed; this also often reveals the root cause yourself.

---

## Bug Reports (GitHub Issues)

Use **GitHub Issues** when you have confirmed that TraceCraft behaves incorrectly: crashes, wrong output, silent failures, or behavior that contradicts the documentation.

[:octicons-mark-github-16: Open an Issue](https://github.com/LocalAI/tracecraft/issues/new/choose){ .md-button .md-button--primary }

### Before Opening an Issue

- [ ] Search [existing issues](https://github.com/LocalAI/tracecraft/issues) to check for duplicates
- [ ] Check the [Changelog](changelog.md) to see if the bug was already fixed in a newer version
- [ ] Reproduce the issue on the latest release: `pip install --upgrade tracecraft`
- [ ] Try to reduce the reproduction to minimal code (no unrelated dependencies)

### Bug Report Template

Copy and fill in this template when opening an issue:

```markdown
## Bug Description

A clear, concise description of what the bug is.

## Environment

- TraceCraft version: (output of `tracecraft --version` or `python -c "import tracecraft; print(tracecraft.__version__)"`)
- Python version: (output of `python --version`)
- OS: (e.g., macOS 14.5, Ubuntu 22.04, Windows 11)
- Installation method: (pip, uv, conda, from source)
- Relevant extras installed: (e.g., `tracecraft[langchain,tui]`)

## Steps to Reproduce

1. Install TraceCraft with `pip install tracecraft`
2. Run the following code:

```python
import tracecraft

# Minimal code that reproduces the issue
tracecraft.init(console=True)
```

3. Observe the output

## Expected Behavior

What you expected to happen.

## Actual Behavior

What actually happened. Include any unexpected output or missing output.

## Error Message / Stack Trace

```
Paste the full traceback here. Do not truncate it.
```

## Minimal Reproduction Code

```python
# The smallest possible complete script that reproduces the issue.
# It should be runnable as-is (with TraceCraft installed).
import tracecraft

tracecraft.init()
# ...
```

## Additional Context

Anything else that might be relevant: integrations used, deployment environment,
whether the issue is intermittent, links to related issues or discussions.

```

!!! warning "Before Submitting"
    Make sure your reproduction code does not contain real API keys, credentials, or personal data. Replace them with placeholder strings like `"sk-..."` or `os.environ["OPENAI_API_KEY"]`.

### Issue Labels

After you open an issue, maintainers will apply labels to categorize and prioritize it. You do not need to set labels yourself.

| Label | Meaning |
|---|---|
| `bug` | Confirmed defect in TraceCraft |
| `needs-reproduction` | Cannot reproduce without more information |
| `good first issue` | Suitable for first-time contributors |
| `help wanted` | Community contributions welcome |
| `wontfix` | Out of scope or working as intended |

---

## Feature Requests

New feature ideas are best started as a **GitHub Discussion** in the **Ideas** category. This allows the community to weigh in before a formal issue is created, which reduces the chance of duplicating work or building something in the wrong direction.

[:octicons-mark-github-16: Post an Idea](https://github.com/LocalAI/tracecraft/discussions/new?category=ideas){ .md-button }

### Feature Request Template

```markdown
## Use Case

Describe the problem or workflow gap this feature would address.
Focus on the "why" rather than jumping straight to the solution.

Example: "When running high-volume production agents, I have no way to know
which specific prompt templates are causing high token costs across runs."

## Proposed Solution

Describe what you would like TraceCraft to do. Be as specific as you can
about the interface, behavior, and configuration.

Example: "A `PromptTemplateProcessor` that extracts named template variables
from Step inputs and records them as indexed attributes, enabling grouping
and aggregation in the TUI."

## Alternatives Considered

What other approaches have you considered or tried?
Why do they fall short of your needs?

## Additional Context

Mockups, links to similar features in other tools, related issues or discussions.
```

!!! note "If Your Idea Gets Traction"
    Once a discussion has community support and clear scope, a maintainer will convert it to a GitHub Issue and add it to the project roadmap.

---

## Security Issues

!!! danger "Do Not Report Security Issues Publicly"
    If you discover a security vulnerability - including authentication bypasses, data exposure, or dependency vulnerabilities - **do not open a public GitHub Issue or Discussion**.

    Public disclosure before a fix is available puts all TraceCraft users at risk.

### Responsible Disclosure Process

1. **Email** the security team at `security@tracecraft.dev` with the subject line `[Security] Brief description`.
2. Include a description of the vulnerability, reproduction steps, and the potential impact.
3. We will acknowledge receipt within **2 business days**.
4. We will provide an initial assessment and expected fix timeline within **7 business days**.
5. We will coordinate a disclosure date with you once a fix is ready.
6. You will be credited in the security advisory unless you prefer to remain anonymous.

### What to Include in a Security Report

- Affected TraceCraft version(s)
- Description of the vulnerability and its potential impact
- Step-by-step reproduction instructions
- Any proof-of-concept code (shared privately)
- Suggested fix or mitigation, if you have one

We follow [responsible disclosure](https://en.wikipedia.org/wiki/Coordinated_vulnerability_disclosure) and ask reporters to do the same. We will not take legal action against good-faith reporters who follow this process.

---

## Contributing

If you want to fix a bug yourself, add a feature, or improve the documentation, contributions are welcome.

[:octicons-arrow-right-24: Read the Contributing Guide](contributing.md){ .md-button }

### Quick Summary

1. **Fork** the repository on GitHub
2. **Set up** your development environment:

   ```bash
   git clone https://github.com/YOUR_USERNAME/tracecraft.git
   cd tracecraft
   uv sync --all-extras
   uv run pre-commit install
   ```

3. **Create a branch** with a descriptive name:

   ```bash
   git checkout -b fix/sampling-rate-off-by-one
   git checkout -b feat/prometheus-exporter
   git checkout -b docs/glossary-additions
   ```

4. **Make your changes**, add tests, and update documentation
5. **Verify everything passes**:

   ```bash
   uv run pytest
   uv run ruff check src tests
   uv run mypy src
   uv run mkdocs build --strict
   ```

6. **Open a pull request** against the `main` branch

!!! tip "Start Small"
    First-time contributors often find it easiest to start with documentation improvements, test additions, or issues labeled `good first issue`. These changes are lower-risk and still genuinely useful.

---

## Response Time Expectations

TraceCraft is a community-maintained open-source project. Response times are best-effort and depend on maintainer availability.

| Channel | Typical Response |
|---|---|
| GitHub Discussions | 1-5 business days |
| GitHub Issues (bugs) | 2-7 business days |
| Pull Requests | 5-10 business days for initial review |
| Security Reports | 2 business days for acknowledgement |

If your issue is urgent, adding a clear description of the business impact helps maintainers prioritize.
