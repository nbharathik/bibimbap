# Agent Guide

This document explains how to extend the benchmark by creating a new agent backend.

## Agent Contract

Agents are loaded via `llm_agent_system` (`module:ClassName`) and must implement:

`invoke(prompt, ifc_path, output_format)`

Agents should populate these runtime fields for better benchmarking and debugging:
- `input_tokens`
- `output_tokens`
- `tool_call_iterations`
- `last_error`
- `last_recursion_error`

These fields are recommended, but not strictly required for the run to complete. The benchmark can fall back to defaults (for example `0`, `[]`, or `None`) if an agent does not set them.

## Create a New Agent

1. Create a new module in `llm_agents/`.
2. Inherit from `BaseLLMAgent`.
3. Implement `invoke(prompt, ifc_path, output_format)`.
4. Prefer setting runtime fields (`input_tokens`, `output_tokens`, `tool_call_iterations`) during execution.
5. Register the class in config using `llm_agent_system`.

Example config snippet:

```json
{
  "llm_agent_system": "llm_agents.my_agent:MyAgent"
}
```

## Provider Selection

The provider is inferred from `model_name`:
- `openai:<model>`
- `anthropic:<model>`
- `google_genai:<model>`

## Runtime Helpers

Use these modules to keep implementations consistent:
- `llm_agents/runtime/runtime_core.py` for framework-agnostic helpers.
- `llm_agents/runtime/runtime_langchain.py` for LangChain-specific parsing behavior.

## Validation Checklist

Before running large benchmarks, verify:
- The class path in `llm_agent_system` imports correctly.
- `invoke` handles `prompt`, `ifc_path`, and `output_format`.
- Token and tool-call fields are set for each invocation (recommended for analysis quality).
- Errors are surfaced through `last_error` / `last_recursion_error` (recommended for easier debugging).
- A small benchmark run completes and writes expected outputs under `results/`.
