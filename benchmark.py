import argparse
import importlib
import importlib.machinery
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def load_config(config_path: Path) -> dict:
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        raise SystemExit(
            f"Config file not found: {config_path}. Create it or pass --config."
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in config file: {config_path}. {exc}")


def resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_agent_class(spec: str, base_dir: Path):
    """
    Load an agent class from:
      - "module.path:ClassName"
      - "relative/or/abs/path.py:ClassName"
    """
    if ":" not in spec:
        raise SystemExit(
            "Config field 'llm_agent_system' must be of the form "
            "'module.path:ClassName' or 'file.py:ClassName'."
        )

    module_or_file, class_name = spec.split(":", 1)
    module_or_file = module_or_file.strip()
    class_name = class_name.strip()

    if not class_name:
        raise SystemExit("llm_agent_system missing class name after ':'.")

    # Allow short spec like "custom:CustomAgent" to resolve inside llm_agents.
    if (
        not Path(module_or_file).is_absolute()
        and not Path(module_or_file).exists()
        and not module_or_file.startswith("llm_agents.")
        and "/" not in module_or_file
        and "\\" not in module_or_file
    ):
        module_name = module_or_file[:-3] if module_or_file.endswith(".py") else module_or_file
        module_or_file = f"llm_agents.{module_name}"

    candidate_path = resolve_path(base_dir, module_or_file)
    if module_or_file.endswith(".py") or candidate_path.exists():
        if not candidate_path.exists():
            raise SystemExit(f"Agent file not found: {candidate_path}")
        package_dir = str(candidate_path.parent)
        repo_dir = str(base_dir)
        if package_dir not in sys.path:
            sys.path.insert(0, package_dir)
        if repo_dir not in sys.path:
            sys.path.insert(0, repo_dir)
        module_name = f"_llm_agent_{candidate_path.stem}"
        loader = importlib.machinery.SourceFileLoader(module_name, str(candidate_path))
        spec_obj = importlib.util.spec_from_loader(module_name, loader)
        if spec_obj is None or spec_obj.loader is None:
            raise SystemExit(f"Failed to load module from file: {candidate_path}")
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
    else:
        module = importlib.import_module(module_or_file)

    if not hasattr(module, class_name):
        raise SystemExit(f"Class '{class_name}' not found in '{module_or_file}'.")
    return getattr(module, class_name)


def model_suffix(model_name: str) -> str:
    return model_name.split(":")[-1] if model_name else "unknown"


def main() -> None:
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.example.json"
    parser = argparse.ArgumentParser(description="Run the BIBIMBAP benchmark.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    parser.add_argument(
        "--only-llm",
        action="store_true",
        help="Skip evaluation and only run the LLM agent pipeline.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)
    evaluate = not args.only_llm

    if "inference_system" in config:
        raise SystemExit(
            "Config key 'inference_system' is no longer supported. "
            "Use 'llm_agent_system' instead."
        )

    questions_val = config["questions_csv"]
    f_list = questions_val if isinstance(questions_val, list) else [questions_val]
    if not f_list:
        raise SystemExit("Config 'questions_csv' must be a path or a non-empty list of paths.")

    questions_list = []
    for f in f_list:
        csv_path = resolve_path(repo_root, f)
        df = pd.read_csv(csv_path)
        df["source_csv"] = Path(f).name
        questions_list.append(df)
    questions = pd.concat(questions_list, ignore_index=True)

    num_samples = int(config["num_samples"])
    model_name = config.get("model_name", "")

    paths_config = config["paths"]
    ifc_dir = resolve_path(repo_root, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    structured_outputs_module = paths_config["structured_outputs_module"]
    results_dir = resolve_path(repo_root, paths_config["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)

    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = results_dir / f"run_{run_timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Result for this run will be stored in: {run_dir}")

    with (run_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    results_config = config["results"]
    model_suffix_value = model_suffix(model_name)

    cache_filename = results_config["cache_filename_template"].format(
        model_suffix=model_suffix_value
    )
    cache_path = run_dir / cache_filename

    edited_ifc_dirname = results_config["edited_ifc_dir_template"].format(
        model_suffix=model_suffix_value
    )
    edited_ifc_directory = run_dir / edited_ifc_dirname
    edited_ifc_directory.mkdir(parents=True, exist_ok=True)

    llm_agent_spec = config.get("llm_agent_system", "").strip()
    if not llm_agent_spec:
        raise SystemExit(
            "Config must include 'llm_agent_system', e.g. "
            "'llm_agents.code_execution_agent:CodeExecutionAgent'."
        )

    AgentClass = load_agent_class(llm_agent_spec, repo_root)
    try:
        agent = AgentClass(
            system_prompt=config.get("system_prompt"),
            model_name=config.get("model_name"),
            agent_config=config.get("agent", {}),
        )
    except Exception as exc:
        raise SystemExit(
            f"Failed to initialize agent '{llm_agent_spec}' for model '{model_name}': {exc}"
        ) from exc

    cache = {}

    for index, row in questions.iterrows():
        print(f"Processing question {int(str(index)) + 1} of {len(questions)}...")
        question_id = int(str(index))

        if str(question_id) in cache:
            print("Question already in cache. Using cached result.")
            print(cache[str(question_id)])
            continue

        prompt = row["question"]
        if pd.isna(prompt):
            print("Empty prompt. Skipping.")
            continue

        test_path = f"{tests_module}.{row['test']}"
        ifc_path = ifc_dir / row["ifc-file"]

        structured_output_cell = row.get("structured-output")
        structured_output_name = (
            str(structured_output_cell).strip()
            if structured_output_cell is not None and not pd.isna(structured_output_cell)
            else ""
        )
        if structured_output_name:
            structured_output = f"{structured_outputs_module}.{structured_output_name}"
            output_object = importlib.import_module(structured_output).ModelOutput
        else:
            output_object = None

        crud_value = ""
        if not pd.isna(row.get("CRUD")):
            crud_value = str(row["CRUD"]).strip().lower()
        is_retrieve = crud_value == "retrieve"

        edited_question_directory: Path | None = None
        if not is_retrieve:
            edited_question_directory = edited_ifc_directory / str(question_id)
            edited_question_directory.mkdir(parents=True, exist_ok=True)

        sample_results = []
        for sample in range(num_samples):
            if is_retrieve:
                edited_ifc_path = ifc_path
            else:
                ifc_stem = Path(row["ifc-file"]).stem
                edited_ifc_path = edited_question_directory / f"{ifc_stem}_{sample}.ifc"
                edited_ifc_path.write_bytes(ifc_path.read_bytes())

            try:
                model_output = agent.invoke(
                    prompt=str(prompt),
                    ifc_path=str(edited_ifc_path.resolve()),
                    output_format=output_object,
                )
            except Exception as exc:
                print(f"Error in question {question_id}, sample {sample}: {exc}")
                sample_results.append(
                    {
                        "sample": sample + 1,
                        "model_output": "ERROR_INFERENCE_EXCEPTION",
                        "tool_call_iterations": getattr(agent, "tool_call_iterations", [])
                        or [],
                        "metrics": {},
                        "score": 0,
                        "input_tokens": getattr(agent, "input_tokens", 0) or 0,
                        "output_tokens": getattr(agent, "output_tokens", 0) or 0,
                        "error": str(exc),
                    }
                )
                continue

            if output_object and hasattr(model_output, "model_dump"):
                model_output = model_output.model_dump()
            elif output_object and hasattr(model_output, "__dict__"):
                model_output = model_output.__dict__

            metrics = None
            score = None
            if evaluate:
                test = importlib.import_module(test_path)
                try:
                    metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)
                except Exception as exc:
                    print(
                        f"Error executing test for question {question_id}, sample {sample}: {exc}"
                    )
                    metrics = {}
                score = sum(metrics.values()) / len(metrics) if metrics else 0

            input_tokens = getattr(agent, "input_tokens", None) or 0
            output_tokens = getattr(agent, "output_tokens", None) or 0
            tool_call_iterations = getattr(agent, "tool_call_iterations", None) or []
            sample_results.append(
                {
                    "sample": sample + 1,
                    "model_output": model_output,
                    "tool_call_iterations": tool_call_iterations,
                    "metrics": metrics,
                    "score": score,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            )

        cache_object = {
            "question_id": question_id,
            "prompt": prompt,
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "source_csv": row.get("source_csv", "unknown"),
            "crud_operation": crud_value,
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }

        cache[str(question_id)] = cache_object
        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)


if __name__ == "__main__":
    main()
