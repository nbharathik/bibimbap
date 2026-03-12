# Run Inference Benchmark

This repository now supports running the benchmark through an inference system in `inference/`. The runner is `inference_benchmark.py`.

## Quick start

1. Configure your inference system in a config JSON file.
2. Run the benchmark:
   ```bash
   python inference_benchmark.py --config configs/your-config.json
   ```

## Example: OpenAI code agent

Use the provided config:

```bash
python inference_benchmark.py --config configs/benchmark.config.openai_code_agent.json
```

## Config fields

Required fields:
- `questions_csv`: CSV file(s) with benchmark questions.
- `num_samples`: Number of samples per question.
- `system_prompt`: System prompt passed to your inference system.
- `inference_system`: Inference class to use. Format: `module_or_file:ClassName`
  - Short form resolves inside `inference/`, so `custom:CustomTextToBIM` loads `inference/custom.py`.

Standard benchmark fields:
- `model_name`: Used only for naming output folders and cache files.
- `paths.ifc_dir`, `paths.tests_module`, `paths.structured_outputs_module`, `paths.results_dir`
- `results.cache_filename_template`, `results.edited_ifc_dir_template`

## Inference systems

### `openai_code_agent:OpenAICodeAgent`
Runs a tool-calling agent with an embedded `execute_ifc_code` tool (ported from `llm_agent.py`). The tool executes ifcopenshell code against the IFC file.

### `openai-mcp:CustomTextToBIM`
Connects to an MCP server and uses its tools to solve the task. The IFC is preloaded when possible via the `load_ifc_file` tool.

## Notes

- The inference class must implement `invoke(prompt, ifc_path, output_format)`.
- The runner writes results to `results/run_<timestamp>/`.
- Use `--only-llm` to skip evaluation and just generate outputs.
