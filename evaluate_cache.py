import argparse
import json
from pathlib import Path
import importlib
import pandas as pd

def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)

def resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def main() -> None:
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(description="Evaluate cached LLM outputs.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="Run directory containing cache_*.json and config.json.",
    )
    parser.add_argument(
        "--cache",
        default="",
        help="Path to cache file. If omitted, uses latest cache in results dir.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute metrics even if they already exist.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    run_dir = Path(args.run_dir).resolve() if args.run_dir else None

    if run_dir:
        config_path = run_dir / "config.json"
    else:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = (Path.cwd() / config_path).resolve()

    config = load_config(config_path)

    base_dir = repo_root
    paths_config = config["paths"]
    ifc_dir = resolve_path(base_dir, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    results_dir = resolve_path(base_dir, paths_config["results_dir"])

    questions_val = config["questions_csv"]
    f_list = questions_val if isinstance(questions_val, list) else [questions_val]
    questions_list = []
    for f in f_list:
        csv_path = resolve_path(base_dir, f)
        df = pd.read_csv(csv_path)
        questions_list.append(df)
    questions = pd.concat(questions_list, ignore_index=True)

    if args.cache:
        cache_path = Path(args.cache)
        if not cache_path.is_absolute():
            cache_path = (Path.cwd() / cache_path).resolve()
    elif run_dir:
        cache_path = None
        for candidate in sorted(run_dir.glob("cache_*.json"), reverse=True):
            cache_path = candidate
            break
    else:
        cache_path = None
        for candidate in sorted(results_dir.rglob("cache_*.json"), reverse=True):
            cache_path = candidate
            break

    if cache_path is None or not cache_path.exists():
        raise SystemExit("Cache file not found. Provide --cache.")

    run_dir = cache_path.parent
    output_cache_path = cache_path.with_name(f"{cache_path.stem}_test{cache_path.suffix}")

    with cache_path.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)

    updated = 0
    missing_edited = 0
    skipped_invalid_output = 0
    for question_id, cache_object in cache.items():
        results = cache_object.get("results", [])
        ifc_file = cache_object.get("ifc_file")
        if not ifc_file:
            continue
        ifc_path = ifc_dir / ifc_file
        crud_operation = (cache_object.get("crud_operation") or "").lower()

        question_index = int(cache_object.get("question_id", question_id))
        if question_index < 0 or question_index >= len(questions):
            continue
        question_row = questions.iloc[question_index]
        test_name = question_row.get("test")

        question_scores = []
        for sample_obj in results:
            if not args.force and sample_obj.get("metrics") is not None and sample_obj.get("score") is not None:
                continue

            prompt = cache_object.get("prompt", "")
            if not prompt:
                continue

            # Resolve edited IFC path from model output cache
            # The edited IFC path is stored indirectly in the model output; use the same naming
            # convention as the LLM run: edited_ifc_<model_suffix>/<question_id>/<ifc_stem>_<sample-1>.ifc
            model_name = cache_object.get("model", "")
            model_suffix = model_name.split(":")[-1] if model_name else ""
            edited_ifc_path = None
            if crud_operation != "retrieve":
                edited_dir = run_dir / f"edited_ifc_{model_suffix}" / str(cache_object.get("question_id"))
                if not edited_dir.exists():
                    missing_edited += 1
                    continue

                sample_index = int(sample_obj.get("sample", 1)) - 1
                candidates = sorted(edited_dir.glob(f"*_{sample_index}.ifc"))
                if not candidates:
                    candidates = sorted(edited_dir.glob("*.ifc"))
                if not candidates:
                    missing_edited += 1
                    continue
                edited_ifc_path = candidates[0]
            else:
                edited_ifc_path = ifc_path

            if not test_name:
                continue

            test_path = f"{tests_module}.{test_name}"
            try:
                test = importlib.import_module(test_path)
                model_output = sample_obj.get("model_output")
                if sample_obj.get("error"):
                    print(
                        f"Skipping test for question {question_id}, sample {sample_obj.get('sample')}: "
                        "sample has error"
                    )
                    skipped_invalid_output += 1
                    metrics = {}
                elif model_output is None:
                    print(
                        f"Skipping test for question {question_id}, sample {sample_obj.get('sample')}: "
                        "model_output is None"
                    )
                    skipped_invalid_output += 1
                    metrics = {}
                else:
                    if isinstance(model_output, str):
                        if model_output.startswith("ERROR_OR_RECURSION_LIMIT_OF_25_EXCEEDED"):
                            print(
                                f"Skipping test for question {question_id}, sample {sample_obj.get('sample')}: "
                                "model_output is error placeholder"
                            )
                            skipped_invalid_output += 1
                            metrics = {}
                            model_output = None
                        try:
                            model_output = json.loads(model_output)
                        except Exception:
                            pass
                    if model_output is None:
                        metrics = {}
                    else:
                        try:
                            metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)
                        except Exception as exc:
                            print(
                                f"Error executing test for question {question_id}, sample {sample_obj.get('sample')}: {exc}"
                            )
                            metrics = {}
            except Exception as exc:
                print(f"Error executing test for question {question_id}, sample {sample_obj.get('sample')}: {exc}")
                metrics = {}

            sample_obj["metrics"] = metrics
            sample_obj["score"] = sum(metrics.values()) / len(metrics) if metrics else 0
            question_scores.append(sample_obj["score"])
            updated += 1

        if question_scores:
            avg_score = sum(question_scores) / len(question_scores)
            print(f"Question {question_index}: score {avg_score:.3f}")

    if updated:
        with output_cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)

    print(f"Updated {updated} sample(s) in cache: {output_cache_path}")
    if missing_edited:
        print(f"Skipped {missing_edited} sample(s) due to missing edited IFC files.")
    if skipped_invalid_output:
        print(f"Skipped {skipped_invalid_output} sample(s) due to invalid model_output.")


if __name__ == "__main__":
    main()
