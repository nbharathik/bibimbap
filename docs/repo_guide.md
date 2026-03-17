# Repository Guide

This document explains how the current repository works internally and where the core pieces live.

## Purpose

BIBIMBAP is a benchmark framework for text-to-BIM agents. It runs prompt-based tasks against IFC models, records model/tool behavior, and evaluates results.

## High-Level Flow

1. `benchmark.py` loads benchmark config and prompt/test metadata.
2. It initializes the selected agent backend (`llm_agent_system`).
3. For each task/sample, it calls the agent and captures output, runtime metadata, and errors.
4. It evaluates output using task-specific tests.
5. It writes caches, edited IFC artifacts, and run metadata into `results/`.

## Core Architecture

- `benchmark.py`: orchestrates prompt loading, agent dispatch, evaluation, and cache persistence.
- `llm_agents/`: backend implementations.
- `llm_agents/runtime/runtime_core.py`: framework-agnostic runtime helpers.
- `llm_agents/runtime/runtime_langchain.py`: LangChain-specific parsing for output, tool calls, and token usage.
- `data/`: prompts, tests, structured schemas, and IFC assets.
- `scripts/`: post-processing and utility scripts (`analyze_results.py`, `eval_cache.py`, `download_data.py`).

## Repository Structure

- `configs/`: config templates and `.env.example`.
- `data/prompts/`: benchmark prompt CSV files.
- `data/tests/`: evaluation modules.
- `data/structured_outputs/`: structured output schema modules.
- `data/ifc/`: IFC files used by tasks.
- `results/`: generated benchmark runs.
- `docs/`: project documentation.

Runtime setup and command examples are documented in `README.md`.

## Config Contract

Required config keys include:
- `questions_csv`
- `num_samples`
- `model_name`
- `system_prompt`
- `llm_agent_system` (format `module:ClassName`)
- `paths`
- `results`

Provider is selected via `model_name`:
- `openai:<model>`
- `anthropic:<model>`
- `google_genai:<model>`

## Data Sync Behavior

If IFC data is hosted remotely, repository metadata is defined in `data/manifest.json` and synchronized via `scripts/download_data.py`.

## Results Format

Each run writes:
- `results/run_<timestamp>/config.json`
- `results/run_<timestamp>/cache_<model_suffix>.json`
- `results/run_<timestamp>/edited_ifc_<model_suffix>/...`

Each cache entry contains:
- `question_id`
- `prompt`
- `model`
- `ifc_file`
- `source_csv`
- `crud_operation`
- `results[]`

Each sample in `results[]` contains:
- `sample`
- `model_output`
- `tool_call_iterations`
- `metrics`
- `score`
- `input_tokens`
- `output_tokens`
- optional `error`
