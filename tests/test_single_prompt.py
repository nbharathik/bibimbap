"""
Test the LLM agent with a single simple prompt.

Usage:
    python tests/test_single_prompt.py --config configs/benchmark.config.example.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmark import load_config, resolve_path, load_agent_class


# ── Structured output format ──────────────────────────────────────────────
class TestOutput(BaseModel):
    name: str = Field(description="The Name of the element")


# ── Test data ─────────────────────────────────────────────────────────────
IFC_FILE = "basic_tasks.ifc"
PROMPT = "What is the Name of the floor with GlobalId 11kJIqz$n2Jf_DfJV1SCVP?"
EXPECTED_NAME = "Floor:Generic 300mm:1601598"


def run(config_path: str | None = None):
    if config_path is None:
        config_path = str(REPO_ROOT / "configs" / "benchmark.config.example.json")

    config = load_config(Path(config_path))
    ifc_dir = resolve_path(REPO_ROOT, config["paths"]["ifc_dir"])
    ifc_path = str((ifc_dir / IFC_FILE).resolve())

    # init agent
    AgentClass = load_agent_class(config["llm_agent_system"], REPO_ROOT)
    agent = AgentClass(
        system_prompt=config.get("system_prompt"),
        model_name=config.get("model_name"),
        agent_config=config.get("agent", {}),
    )

    print(f"Agent:    {AgentClass.__name__}")
    print(f"Model:    {config.get('model_name', '')}")
    print(f"IFC:      {ifc_path}")
    print(f"Prompt:   {PROMPT}")
    print()

    # run agent with structured output
    print("Running agent...")
    answer = agent.invoke(prompt=PROMPT, ifc_path=ifc_path, output_format=TestOutput)

    # extract name from structured output
    if hasattr(answer, "model_dump"):
        answer_dict = answer.model_dump()
    elif hasattr(answer, "__dict__"):
        answer_dict = answer.__dict__
    else:
        answer_dict = {"name": str(answer)}

    got_name = answer_dict.get("name", "")
    print(f"Got:      {got_name}")
    print(f"Expected: {EXPECTED_NAME}")
    print()

    passed = got_name == EXPECTED_NAME
    print("PASS" if passed else "FAIL")

    # save results (same format as benchmark.py cache)
    results_dir = REPO_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    run_dir = results_dir / f"test_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # save config
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))

    result = {
        "0": {
            "question_id": 0,
            "prompt": PROMPT,
            "model": config.get("model_name", ""),
            "ifc_file": IFC_FILE,
            "source_csv": "test_single_prompt",
            "crud_operation": "retrieve",
            "results": [
                {
                    "sample": 1,
                    "model_output": answer_dict,
                    "tool_call_iterations": getattr(agent, "tool_call_iterations", []) or [],
                    "metrics": {"passed": passed, "expected": EXPECTED_NAME, "got": got_name},
                    "score": 1.0 if passed else 0.0,
                    "input_tokens": getattr(agent, "input_tokens", 0) or 0,
                    "output_tokens": getattr(agent, "output_tokens", 0) or 0,
                }
            ],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    }

    model_suffix = config.get("model_name", "unknown").split(":")[-1] or "unknown"
    cache_path = run_dir / f"cache_{model_suffix}.json"
    cache_path.write_text(json.dumps(result, indent=2, default=str))
    print(f"Results saved to: {cache_path}")

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ok = run(args.config)
    sys.exit(0 if ok else 1)
