# BIM Benchmark

Run an LLM + MCP benchmark over IFC tasks.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set API keys in `.env` (for example: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
3. Review `benchmark.config.json` for model, MCP server, and path settings.
4. Run the benchmark:
   ```bash
   python mcp-client.py
   ```
   Or provide a custom config:
   ```bash
   python mcp-client.py --config path\to\benchmark.config.json
   ```

## Results & Caching

- **Results Folder**: A new directory `results/run_YYYY-MM-DD_HH-MM-SS/` is created for each run.
  - Contains `cache_<model>.json` (the results).
  - Contains `edited_ifc/` (saved models).
  - Contains `config.json` (snapshot of configuration used).
- **Caching**: 
  - To use previous results (avoid re-running successful queries), set `"cache_source": "path/to/old/cache.json"` in `benchmark.config.json`.
  - To force a fresh run, set `"cache_source": null`.

## Git Ignore

- The `results/` folder is ignored by default to avoid bloating the repository.
- `venv/` and `.env` are also ignored.
