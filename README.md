# BIM Benchmark

## Quick Start

1.  **Install**:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Environment**: Add your keys to a `.env` file (e.g., `OPENAI_API_KEY=...`).
3.  **Run**:
    ```bash
    python mcp-client.py
    ```

## Usage

### Run Benchmark
Executes tasks defined in `data/questions.csv`.
```bash
python mcp-client.py --config configs/benchmark.config.json
```
