# BIM Benchmark

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment**: Create a `.env` file in the root directory and add API keys (e.g., `OPENAI_API_KEY=...`). Example - `configs/.env.example`

3. **Configure the benchmark**: Update `configs/benchmark.config.json`
   - Example configuration - `configs/benchmark.config.example.json`

4. **Run the benchmark**:
   ```bash
   python llm_agent.py --config configs/benchmark.config.json --force-subprocess
   ```

5. **Analyze results**:
   ```bash
    python analyze_results.py --latest
    ```