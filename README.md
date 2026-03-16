# BIBIMBAP: A Benchmark for Instructional BIM-Based Automated Programming

We introduce BIBIMBAP, a Text-to-BIM benchmark with 100 curated tasks spanning the full set of CRUD operations and organized into spatial, geometric, topological, numeric, and conceptual understanding tasks. Each task provides a natural-language prompt, a reference IFC model, structured expected outputs, and executable test scripts to enable reproducible, automated evaluation.

![Figure of the Benchmark Architecture](/figures/benchmark-architecture.svg "Benchmark Architecture")



# Run the Benchmark

This repository supports running the benchmark through an inference system in `inference/`. The runner is `inference_benchmark.py`.

## Quick start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**: Create a `.env` file <ins>in the root directory</ins> and add API keys (e.g., `OPENAI_API_KEY=...`). Example - `configs/.env.example`

3. **Configure your inference system** in a config JSON file.
   - You can use a predefined inference system or create your own.
   - To create a custom system, see [Custom Inference System Manual](CUSTOM_SYSTEM_MANUAL.md).
   - **Note**: The inference class must implement `invoke(prompt, ifc_path, output_format)`
4. **Run the benchmark**:
   ```bash
   python inference_benchmark.py --config configs/your-config.json
   ```
   Optional flags:
   - `--run_name`: Suffix for the run folder.
   - `--resume_run`: Resume from an existing run directory.
   - `--only_llm`: Skip evaluation and only run inference.

## Example: OpenAI code agent

Use the provided config:

```bash
python inference_benchmark.py --config configs/benchmark.config.openai_code_agent.json
```

## Config fields

Required fields:
- `questions_csv`: CSV file(s) with benchmark questions.
- `num_samples`: Number of samples per question.
- `model_name`: Name of the LLM to use. This is used to name the result directories and can be accessed within an inference system.
- `system_prompt`: System prompt passed to your inference system.
- `inference_system`: Inference class to use. Format: `module_or_file:ClassName`
  - Short form resolves inside `inference/`, so `custom:CustomTextToBIM` loads `inference/custom.py`.

## Inference systems

### `openai_code_agent:OpenAICodeAgent`
Runs a tool-calling agent with an embedded `execute_ifc_code` tool. The tool executes ifcopenshell code.

### `openai-mcp:OpenAIMCP`
Connects to an MCP server and uses its tools to solve the task. The IFC is preloaded when possible via the `load_ifc_file` tool.


## Analyze results
The benchmark writes results to `results/run_<timestamp>/`. Edited IFC files are stored as well.

To analyze the latest experiment run, execute:
```bash
python analyze_results.py --latest
```

Optional flags:
- `paths`: One or more run directories or cache JSON files.
- `--latest`: Analyze the most recent run (default if no path provided).
- `--dir`: Analyze a specific run directory.
- `--cache`: Analyze a specific cache JSON file or directory (overrides run dir selection).
- `--output-dir`: Write analysis outputs to a custom directory.
- `--semantic-splits`: Split questions into semantic categories by counts.
