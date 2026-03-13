"""Re-evaluate cached LLM outputs by re-running benchmark tests.

Usage:
  - Point to a run directory that contains `config.json` and `cache_*.json`,
    or pass `--cache` directly to a cache file.
  - The script resolves IFC inputs and edited IFCs, recomputes metrics/scores,
    and writes a new cache JSON (never overwrites the input cache).

Args:
  run_dir (positional): Run directory containing `cache_*.json` and `config.json`.
  --run-dir: Same as positional run_dir (overrides if both are set).
  --cache: Path to a cache JSON file with multiple JSON files are there in run-dir
  --output: Path to write the updated cache JSON.
  --output-suffix: Suffix for output cache name when --output is not set (default: retest).
  --only-missing: Recompute metrics only when metrics/score are missing.
  --force: Alias for recomputing all samples (default behavior).

Examples:
  python scripts/eval_cache.py path/to/results/run_..
  python scripts/eval_cache.py --run-dir path/to/results/run_..
  python scripts/eval_cache.py --cache path/to/cache_foo.json
  python scripts/eval_cache.py --cache path/to/cache_foo.json --output cache_x_test.json
  python scripts/eval_cache.py --cache path/to/cache_foo.json --only-missing
"""

import argparse
import ast
import importlib
import inspect
import json
from pathlib import Path
import textwrap

import pandas as pd


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def model_suffix(model_name: str) -> str:
    return model_name.split(":")[-1] if model_name else ""


def _extract_metric_keys_from_test(test_module) -> list[str]:
    func = getattr(test_module, "execute_test", None)
    if func is None:
        return []
    try:
        source = inspect.getsource(func)
    except Exception:
        return []
    try:
        tree = ast.parse(textwrap.dedent(source))
    except Exception:
        return []

    def extract_keys(dict_node: ast.Dict) -> list[str]:
        keys: list[str] = []
        for key in dict_node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
            elif isinstance(key, ast.Str):
                keys.append(key.s)
        return keys

    class MetricsVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.keys: list[str] = []

        def visit_Assign(self, node: ast.Assign) -> None:
            if self.keys:
                return
            if isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "metrics":
                        self.keys = extract_keys(node.value)
                        return
            self.generic_visit(node)

        def visit_Return(self, node: ast.Return) -> None:
            if self.keys:
                return
            if isinstance(node.value, ast.Dict):
                self.keys = extract_keys(node.value)
            self.generic_visit(node)

    visitor = MetricsVisitor()
    visitor.visit(tree)
    return visitor.keys


def default_metrics_from_test(test_module) -> dict:
    keys = _extract_metric_keys_from_test(test_module)
    return {key: False for key in keys} if keys else {}


def execute_test_with_fallback(test_module, ifc_path: Path, edited_ifc_path: Path, model_output):
    try:
        metrics = test_module.execute_test(ifc_path, edited_ifc_path, model_output)
        if isinstance(metrics, dict):
            return metrics, ""
        return {}, "invalid_metrics"
    except Exception as exc:
        return default_metrics_from_test(test_module), str(exc)


def load_questions(config: dict, base_dir: Path) -> pd.DataFrame:
    questions_val = config.get("questions_csv")
    f_list = questions_val if isinstance(questions_val, list) else [questions_val]
    if not f_list:
        raise SystemExit("Config 'questions_csv' must be a path or a non-empty list of paths.")

    questions_list = []
    for f in f_list:
        if not f:
            continue
        csv_path = resolve_path(base_dir, f)
        df = pd.read_csv(csv_path)
        df["source_csv"] = Path(f).name
        questions_list.append(df)

    if not questions_list:
        raise SystemExit("No question CSV files found to load.")

    return pd.concat(questions_list, ignore_index=True)


def find_latest_run_dir(results_dir: Path) -> Path | None:
    run_dirs = [path for path in results_dir.glob("run_*") if path.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda path: path.stat().st_mtime)


def find_cache_in_run_dir(run_dir: Path, config: dict) -> Path | None:
    results_config = config.get("results", {})
    template = results_config.get("cache_filename_template")
    model_name = config.get("model_name", "")
    suffix = model_suffix(model_name)
    if template and suffix:
        candidate = run_dir / template.format(model_suffix=suffix)
        if candidate.exists():
            return candidate

    candidates = sorted(run_dir.glob("cache_*.json"))
    if not candidates:
        return None

    def rank(path: Path) -> tuple[int, int, str]:
        stem = path.stem
        penalty = 0
        for token in ("_test", "_retest", "_eval", "_recompute", "_metrics"):
            penalty += stem.count(token)
        return (penalty, len(stem), path.name)

    return min(candidates, key=rank)


def resolve_output_cache_path(
    cache_path: Path, output_path_arg: str | None, output_suffix: str
) -> Path:
    if output_path_arg:
        output_path = Path(output_path_arg)
        if not output_path.is_absolute():
            output_path = (cache_path.parent / output_path).resolve()
    else:
        suffix = output_suffix.strip()
        if suffix:
            output_name = f"{cache_path.stem}_{suffix}{cache_path.suffix}"
        else:
            output_name = f"{cache_path.stem}{cache_path.suffix}"
        output_path = cache_path.with_name(output_name)

    if output_path.resolve() == cache_path.resolve():
        raise SystemExit(
            "Output cache path is the same as input. Use --output or --output-suffix."
        )

    if output_path.exists():
        counter = 2
        while True:
            candidate = output_path.with_name(
                f"{output_path.stem}_{counter}{output_path.suffix}"
            )
            if not candidate.exists():
                output_path = candidate
                break
            counter += 1

    return output_path


def resolve_edited_ifc_root(run_dir: Path, config: dict, cache: dict) -> Path | None:
    results_config = config.get("results", {})
    template = results_config.get("edited_ifc_dir_template")
    model_name = config.get("model_name", "") or ""
    if not model_name:
        for cache_object in cache.values():
            model_name = cache_object.get("model", "")
            if model_name:
                break
    suffix = model_suffix(model_name)
    if template and suffix:
        candidate = run_dir / template.format(model_suffix=suffix)
        if candidate.exists():
            return candidate

    edited_dirs = sorted(
        [path for path in run_dir.glob("edited_ifc_*") if path.is_dir()]
    )
    if len(edited_dirs) == 1:
        return edited_dirs[0]
    return None


def resolve_edited_question_dir(
    run_dir: Path, edited_root: Path | None, question_id: int
) -> Path | None:
    if edited_root:
        candidate = edited_root / str(question_id)
        if candidate.exists():
            return candidate

    for root in run_dir.glob("edited_ifc_*"):
        if not root.is_dir():
            continue
        candidate = root / str(question_id)
        if candidate.exists():
            return candidate
    return None


def select_edited_ifc_path(
    edited_dir: Path, ifc_file: str | None, sample_index: int
) -> Path | None:
    if ifc_file:
        expected = edited_dir / f"{Path(ifc_file).stem}_{sample_index}.ifc"
        if expected.exists():
            return expected

    candidates = sorted(edited_dir.glob(f"*_{sample_index}.ifc"))
    if candidates:
        return candidates[0]

    candidates = sorted(edited_dir.glob("*.ifc"))
    if candidates:
        return candidates[0]
    return None


def prepare_model_output(sample_obj: dict) -> tuple[object | None, str]:
    model_output = sample_obj.get("model_output")
    if model_output is None:
        return None, "missing_output"

    if isinstance(model_output, str):
        if model_output.startswith(
            (
                "ERROR_OR_RECURSION_LIMIT_OF_25_EXCEEDED",
                "ERROR_OR_RECURSION_LIMIT_OR_TOOL_FATAL",
            )
        ):
            return model_output, "error_placeholder"
        try:
            model_output = json.loads(model_output)
        except Exception:
            pass

    return model_output, ""


def main() -> None:
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(description="Re-evaluate cached LLM outputs.")
    parser.add_argument(
        "run_dir",
        nargs="?",
        help="Run directory containing cache_*.json and config.json.",
    )
    parser.add_argument(
        "--run-dir",
        dest="run_dir_override",
        default="",
        help="Run directory containing cache_*.json and config.json.",
    )
    parser.add_argument(
        "--cache",
        default="",
        help="Path to cache JSON file to re-evaluate.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Path to write the updated cache JSON.",
    )
    parser.add_argument(
        "--output-suffix",
        default="retest",
        help="Suffix for output cache name when --output is not set.",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only recompute metrics if metrics/score are missing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Alias for recompute all samples (default behavior).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    run_dir_arg = args.run_dir_override or args.run_dir
    run_dir = Path(run_dir_arg).resolve() if run_dir_arg else None

    config_path = default_config
    if run_dir:
        candidate = run_dir / "config.json"
        if candidate.exists():
            config_path = candidate
    config = load_config(config_path)

    base_dir = repo_root
    paths_config = config["paths"]
    results_dir = resolve_path(base_dir, paths_config["results_dir"])

    cache_path = None
    if args.cache:
        cache_path = Path(args.cache)
        if not cache_path.is_absolute():
            base = run_dir if run_dir else Path.cwd()
            cache_path = (base / cache_path).resolve()
        if not cache_path.exists():
            raise SystemExit(f"Cache file not found: {cache_path}")
    else:
        if run_dir is None:
            run_dir = find_latest_run_dir(results_dir)
            if run_dir is None:
                raise SystemExit("No run directory found. Provide --run-dir or --cache.")

        cache_path = find_cache_in_run_dir(run_dir, config)
        if cache_path is None or not cache_path.exists():
            raise SystemExit(f"Cache file not found in run directory: {run_dir}")

    if run_dir is None:
        run_dir = cache_path.parent

    run_config_path = run_dir / "config.json"
    if run_config_path.exists() and run_config_path.resolve() != config_path.resolve():
        config_path = run_config_path
        config = load_config(config_path)
        paths_config = config["paths"]
        results_dir = resolve_path(base_dir, paths_config["results_dir"])
        if not args.cache:
            cache_path = find_cache_in_run_dir(run_dir, config)
            if cache_path is None or not cache_path.exists():
                raise SystemExit(f"Cache file not found in run directory: {run_dir}")

    ifc_dir = resolve_path(base_dir, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    questions = load_questions(config, base_dir)

    output_cache_path = resolve_output_cache_path(
        cache_path, args.output or None, args.output_suffix
    )

    with cache_path.open("r", encoding="utf-8") as cache_file:
        cache = json.load(cache_file)

    if not isinstance(cache, dict):
        raise SystemExit("Cache file format not recognized; expected a JSON object.")

    edited_ifc_root = resolve_edited_ifc_root(run_dir, config, cache)
    only_missing = args.only_missing
    if args.force:
        only_missing = False

    updated = 0
    missing_edited = 0
    missing_ifc = 0
    missing_test = 0
    skipped_invalid_output = 0
    skipped_existing = 0
    skipped_bad_question = 0

    print(f"Input cache: {cache_path}")
    print(f"Output cache: {output_cache_path}")

    for question_key, cache_object in cache.items():
        results = cache_object.get("results", [])
        if not isinstance(results, list):
            continue

        question_id_raw = cache_object.get("question_id", question_key)
        try:
            question_index = int(question_id_raw)
        except Exception:
            skipped_bad_question += len(results)
            continue

        if question_index < 0 or question_index >= len(questions):
            skipped_bad_question += len(results)
            continue

        question_row = questions.iloc[question_index]
        source_csv = cache_object.get("source_csv")
        if not source_csv:
            source_cell = question_row.get("source_csv")
            if source_cell is not None and not pd.isna(source_cell):
                source_csv = str(source_cell).strip()
        if source_csv is not None:
            cache_object["source_csv"] = source_csv

        test_name = question_row.get("test")
        if test_name is None or pd.isna(test_name) or not str(test_name).strip():
            missing_test += len(results)
            continue
        test_name = str(test_name).strip()

        test_path = f"{tests_module}.{test_name}"
        try:
            test = importlib.import_module(test_path)
        except Exception as exc:
            print(f"Error importing test {test_path} for question {question_index}: {exc}")
            missing_test += len(results)
            continue

        ifc_file = cache_object.get("ifc_file")
        if not ifc_file:
            ifc_file = question_row.get("ifc-file")
            if ifc_file is None or pd.isna(ifc_file) or not str(ifc_file).strip():
                missing_ifc += len(results)
                continue
            ifc_file = str(ifc_file).strip()

        ifc_path = Path(ifc_file)
        if not ifc_path.is_absolute():
            ifc_path = (ifc_dir / ifc_path).resolve()

        if not ifc_path.exists():
            missing_ifc += len(results)
            continue

        crud_operation = (cache_object.get("crud_operation") or "").strip()
        if not crud_operation:
            crud_cell = question_row.get("CRUD")
            if crud_cell is not None and not pd.isna(crud_cell):
                crud_operation = str(crud_cell).strip()
        crud_operation = crud_operation.lower()
        cache_object["crud_operation"] = crud_operation

        question_scores = []
        for sample_obj in results:
            if only_missing:
                existing_metrics = sample_obj.get("metrics")
                existing_score = sample_obj.get("score")
                has_metrics = existing_metrics is not None and (
                    not isinstance(existing_metrics, dict) or existing_metrics
                )
                if has_metrics and existing_score is not None:
                    skipped_existing += 1
                    continue

            edited_ifc_path = ifc_path
            if crud_operation != "retrieve":
                edited_dir = resolve_edited_question_dir(
                    run_dir, edited_ifc_root, question_index
                )
                if edited_dir is None:
                    missing_edited += 1
                    continue

                sample_index = sample_obj.get("sample", 1)
                try:
                    sample_index = int(sample_index) - 1
                except Exception:
                    sample_index = 0

                edited_ifc_path = select_edited_ifc_path(
                    edited_dir, str(ifc_file) if ifc_file else None, sample_index
                )
                if edited_ifc_path is None or not edited_ifc_path.exists():
                    missing_edited += 1
                    continue

            model_output, output_reason = prepare_model_output(sample_obj)
            if model_output is None:
                skipped_invalid_output += 1
                metrics = {}
            else:
                metrics, test_error = execute_test_with_fallback(
                    test, ifc_path, edited_ifc_path, model_output
                )
                if test_error:
                    print(
                        "Error executing test for question "
                        f"{question_index}, sample {sample_obj.get('sample')}: {test_error} "
                        f"(model_output={output_reason or 'ok'})"
                    )

            score = sum(metrics.values()) / len(metrics) if metrics else 0
            sample_obj["metrics"] = metrics
            sample_obj["score"] = score
            question_scores.append(score)
            updated += 1

        if question_scores:
            avg_score = sum(question_scores) / len(question_scores)
            print(f"Question {question_index}: score {avg_score:.3f}")

    with output_cache_path.open("w", encoding="utf-8") as cache_file:
        json.dump(cache, cache_file)

    print(f"Updated {updated} sample(s) in cache: {output_cache_path}")
    if skipped_existing:
        print(f"Skipped {skipped_existing} sample(s) with existing metrics/score.")
    if missing_ifc:
        print(f"Skipped {missing_ifc} sample(s) due to missing IFC files.")
    if missing_edited:
        print(f"Skipped {missing_edited} sample(s) due to missing edited IFC files.")
    if missing_test:
        print(f"Skipped {missing_test} sample(s) due to missing tests.")
    if skipped_invalid_output:
        print(f"Skipped {skipped_invalid_output} sample(s) due to invalid model_output.")
    if skipped_bad_question:
        print(f"Skipped {skipped_bad_question} sample(s) due to invalid question IDs.")


if __name__ == "__main__":
    main()
