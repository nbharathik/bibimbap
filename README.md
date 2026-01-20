# BIM Benchmark

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**: Create a `.env` file in the root directory and add API keys (e.g., `OPENAI_API_KEY=...`). Example - `configs/.env.example`

3. **Configure the benchmark**: Update `configs/benchmark.config.json`
   - Use the [benchmark-v1](https://github.com/Show2Instruct/ifc-bonsai-mcp/tree/benchmark-v1) branch of the MCP server.
   - Example configuration - `configs/benchmark.config.example.json`

4. **Run the benchmark**:
   ```bash
   python mcp-client.py --config configs/benchmark.config.json
   ```
## Vision Benchmark
Change to the `image-benchmark` branch to run the vision benchmark.
1. **Configure the benchmark**: Update `image_benchmark.config.example.json`
2. **Run the benchmark**:
   ```bash
   python image_benchmark.py
   ```
