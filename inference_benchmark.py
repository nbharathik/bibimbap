import argparse
import importlib
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, TypedDict

import pandas as pd
import inspect


class State(TypedDict):
    prompt: str
    structured_output: object
    ifc_file_path: str
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_call_iterations: List[dict]
    filtered_tools: list


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


def model_suffix(model_name: str) -> str:
    return model_name.split(":")[-1] if model_name else "unknown"


def load_inference_class(spec: str, base_dir: Path):
    """
    Load a TextToBIM class from either:
      - "module.path:ClassName"
      - "relative/or/abs/path.py:ClassName"
    """
    if ":" not in spec:
        raise SystemExit(
            "Config field 'inference_system' must be of the form "
            "'module.path:ClassName' or 'file.py:ClassName'."
        )

    module_or_file, class_name = spec.split(":", 1)
    module_or_file = module_or_file.strip()
    class_name = class_name.strip()

    if not class_name:
        raise SystemExit("inference_system missing class name after ':'.")

    # Allow short spec like "custom:MyClass" or "custom.py:MyClass" to resolve inside inference/
    if (
        not Path(module_or_file).is_absolute()
        and not Path(module_or_file).exists()
        and not module_or_file.startswith("inference.")
        and "/" not in module_or_file
        and "\\" not in module_or_file
    ):
        if not module_or_file.endswith(".py"):
            module_or_file = f"{module_or_file}.py"
        module_or_file = str((Path("inference") / module_or_file).as_posix())

    candidate_path = resolve_path(base_dir, module_or_file)
    if module_or_file.endswith(".py") or candidate_path.exists():
        if not candidate_path.exists():
            raise SystemExit(f"Inference file not found: {candidate_path}")
        inference_dir = str(candidate_path.parent)
        repo_dir = str(base_dir)
        if inference_dir not in sys.path:
            sys.path.insert(0, inference_dir)
        if repo_dir not in sys.path:
            sys.path.insert(0, repo_dir)
        module_name = f"_inference_{candidate_path.stem}"
        loader = importlib.machinery.SourceFileLoader(module_name, str(candidate_path))
        spec_obj = importlib.util.spec_from_loader(module_name, loader)
        if spec_obj is None or spec_obj.loader is None:
            raise SystemExit(f"Failed to load module from file: {candidate_path}")
        module = importlib.util.module_from_spec(spec_obj)
        spec_obj.loader.exec_module(module)
    else:
        module = importlib.import_module(module_or_file)

    if not hasattr(module, class_name):
        raise SystemExit(
            f"Class '{class_name}' not found in '{module_or_file}'."
        )
    return getattr(module, class_name)


def main() -> None:
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(
        description="Run the IFC benchmark using an inference system from inference/."
    )
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    parser.add_argument(
        "--run-name",
        "--run_name",
        default="",
        help="Suffix for new run folder.",
    )
    parser.add_argument(
        "--resume-run",
        "--resume_run",
        default="",
        help="Resume from existing run directory.",
    )
    parser.add_argument(
        "--only-llm",
        "--only_llm",
        action="store_true",
        help="Skip evaluation and only run the inference pipeline.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)
    evaluate = not args.only_llm

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

    num_samples = config["num_samples"]
    model_name = config.get("model_name", "")

    paths_config = config["paths"]
    ifc_dir = resolve_path(repo_root, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    structured_outputs_module = paths_config["structured_outputs_module"]
    results_dir = resolve_path(repo_root, paths_config["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)

    resume_run = (args.resume_run or "").strip()
    if resume_run:
        run_dir = Path(resume_run).expanduser().resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"Resuming run in: {run_dir}")
        cfg_out = run_dir / "config.json"
        if not cfg_out.exists():
            with cfg_out.open("w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
    else:
        run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_name = (args.run_name or "").strip()
        if run_name:
            safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in run_name)
            run_dir = results_dir / f"run_{run_timestamp}_{safe}"
        else:
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

    inference_spec = config.get("inference_system", "").strip()
    if not inference_spec:
        raise SystemExit(
            "Config must include 'inference_system', e.g. "
            "'custom:CustomTextToBIM' or 'openai-mcp.py:CustomTextToBIM'."
        )

    InferenceClass = load_inference_class(inference_spec, repo_root)
    inference = InferenceClass(
        system_prompt=config.get("system_prompt"),
        model_name=config.get("model_name"),
    )

    cache: dict = {}
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as cache_file:
                cache = json.load(cache_file)
            print(f"Loaded existing cache from: {cache_path}")
            print(f"Cache contains {len(cache)} entries.")
        except Exception as exc:
            print(f"Warning: Failed to load existing cache {cache_path}: {exc}")
            print("Starting with empty cache.")

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
                model_output = inference.invoke(
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
                        "tool_call_iterations": [],
                        "metrics": {},
                        "score": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "error": str(exc),
                    }
                )
                continue

            if output_object and hasattr(model_output, "__dict__"):
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

            input_tokens = getattr(inference, "input_tokens", None) or 0
            output_tokens = getattr(inference, "output_tokens", None) or 0
            sample_results.append(
                {
                    "sample": sample + 1,
                    "model_output": model_output,
                    "tool_call_iterations": [],
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
