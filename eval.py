import argparse
import csv
import importlib
import json
import re
import sys
from pathlib import Path


def load_config(config_path: Path) -> dict:
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"Config file not found: {config_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in config file: {config_path}. {exc}")


def resolve_path(base_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_questions(questions_value, base_dir: Path) -> list[dict]:
    paths = questions_value if isinstance(questions_value, list) else [questions_value]
    rows: list[dict] = []
    for path_value in paths:
        if not path_value:
            continue
        csv_path = resolve_path(base_dir, path_value)
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows.extend(list(reader))
    return rows


def model_suffix(model_name: str) -> str:
    return model_name.split(":")[-1]


def find_cache_file(run_dir: Path, cache_path: str | None) -> Path:
    if cache_path:
        return Path(cache_path).expanduser().resolve()
    cache_files = sorted(run_dir.glob("cache_*.json"))
    if not cache_files:
        raise SystemExit(f"No cache_*.json found in run dir: {run_dir}")
    if len(cache_files) > 1:
        print(f"Warning: multiple cache files found, using {cache_files[0].name}")
    return cache_files[0]


def find_edited_ifc_dir(run_dir: Path, config: dict) -> Path:
    results_cfg = config.get("results") or {}
    template = results_cfg.get("edited_ifc_dir_template")
    model_name = config.get("model_name") or ""
    if template and model_name:
        candidate = run_dir / template.format(model_suffix=model_suffix(model_name))
        if candidate.exists():
            return candidate

    candidates = [p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("edited_ifc_")]
    if candidates:
        return sorted(candidates)[0]
    raise SystemExit(f"No edited_ifc_* directory found in: {run_dir}")


def score_metrics(metrics: dict) -> float:
    if not metrics:
        return 0.0
    try:
        return sum(float(v) for v in metrics.values()) / len(metrics)
    except Exception:
        return 0.0


ERROR_OUTPUT_PREFIXES = (
    "ERROR_OR_RECURSION_LIMIT_OF_25_EXCEEDED",
    "ERROR_OR_RECURSION_LIMIT_OR_TOOL_FATAL",
)
ERROR_OUTPUT_SENTINEL = object()

NUMERIC_VALUE_KEYS = {
    "volume",
    "area",
    "length",
    "distance",
    "number",
    "count",
    "height",
    "width",
    "depth",
    "radius",
    "diameter",
}


def _parse_first_number(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[\.,]\d+)?", text)
    if not match:
        return None

    raw = match.group(0)

    if "," in raw and "." in raw:
        last_comma = raw.rfind(",")
        last_dot = raw.rfind(".")
        if last_comma > last_dot:
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except ValueError:
        return None


def _coerce_numeric_fields(model_output: dict) -> dict:
    normalized = dict(model_output)
    for key in NUMERIC_VALUE_KEYS:
        if key not in normalized:
            continue
        value = normalized[key]
        if isinstance(value, (int, float)):
            continue
        if isinstance(value, str):
            parsed = _parse_first_number(value)
            if parsed is not None:
                normalized[key] = parsed
    return normalized


def normalize_model_output(raw: object) -> object | None:
    if raw is None:
        return None

    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped.startswith(ERROR_OUTPUT_PREFIXES):
            return ERROR_OUTPUT_SENTINEL
        try:
            parsed = json.loads(stripped)
        except Exception:
            return raw
        return normalize_model_output(parsed)

    if isinstance(raw, dict):
        return _coerce_numeric_fields(raw)

    if isinstance(raw, list):
        normalized = []
        for item in raw:
            if isinstance(item, dict):
                normalized.append(_coerce_numeric_fields(item))
            else:
                normalized.append(item)
        return normalized

    return raw


def false_metrics_for_sample(sample: object, test_mod: object) -> dict:
    if isinstance(sample, dict):
        existing = sample.get("metrics")
        if isinstance(existing, dict) and existing:
            return {key: False for key in existing.keys()}

    for attr in ("DEFAULT_METRICS", "METRICS_TEMPLATE"):
        template = getattr(test_mod, attr, None)
        if isinstance(template, dict) and template:
            return {key: False for key in template.keys()}

    return {"right_answer": False}


def parse_crud_set(crud_arg: str) -> set[str]:
    return {c.strip().lower() for c in crud_arg.split(",") if c.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-evaluate cached results using updated tests."
    )
    parser.add_argument("run_dir", help="Path to a run result directory")
    parser.add_argument(
        "--config",
        help="Path to config JSON (default: <run_dir>/config.json)",
    )
    parser.add_argument(
        "--cache",
        help="Path to cache JSON (default: cache_*.json in run dir)",
    )
    parser.add_argument(
        "--output",
        help="Output cache JSON path (default: overwrite cache with .bak backup)",
    )
    parser.add_argument(
        "--crud",
        default="create,update,delete",
        help="Comma-separated CRUD types to re-evaluate (default: create,update,delete)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-question errors and missing file warnings",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")

    config_path = Path(args.config).expanduser().resolve() if args.config else run_dir / "config.json"
    config = load_config(config_path)

    repo_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(repo_root))

    questions = load_questions(config.get("questions_csv"), repo_root)
    if not questions:
        raise SystemExit("No questions loaded from config.")

    cache_path = find_cache_file(run_dir, args.cache)
    with cache_path.open("r", encoding="utf-8") as f:
        cache = json.load(f)

    ifc_dir = resolve_path(repo_root, config["paths"]["ifc_dir"])
    tests_module = config["paths"]["tests_module"]
    edited_ifc_dir = find_edited_ifc_dir(run_dir, config)

    crud_targets = parse_crud_set(args.crud)
    test_cache: dict[str, object] = {}

    question_count = 0
    sample_count = 0
    error_count = 0
    skipped_count = 0

    for qid_str, q_data in cache.items():
        try:
            qid = int(qid_str)
        except ValueError:
            if args.verbose:
                print(f"Skipping non-integer question id: {qid_str}")
            skipped_count += 1
            continue

        if qid < 0 or qid >= len(questions):
            if args.verbose:
                print(f"Question id out of range: {qid}")
            skipped_count += 1
            continue

        row = questions[qid]
        prompt = (row.get("question") or "").strip()
        if not prompt:
            skipped_count += 1
            continue

        crud = (row.get("CRUD") or "").strip().lower()
        if crud not in crud_targets:
            skipped_count += 1
            continue

        test_name = (row.get("test") or "").strip()
        if not test_name:
            if args.verbose:
                print(f"Missing test name for question id {qid}")
            skipped_count += 1
            continue

        ifc_file = (row.get("ifc-file") or "").strip()
        if not ifc_file:
            if args.verbose:
                print(f"Missing IFC filename for question id {qid}")
            skipped_count += 1
            continue

        ifc_path = ifc_dir / ifc_file
        if not ifc_path.exists() and args.verbose:
            print(f"IFC file missing for question id {qid}: {ifc_path}")

        test_path = f"{tests_module}.{test_name}"
        if test_path in test_cache:
            test_mod = test_cache[test_path]
        else:
            try:
                test_mod = importlib.import_module(test_path)
            except Exception as exc:
                if args.verbose:
                    print(f"Failed to import {test_path}: {exc}")
                error_count += 1
                continue
            test_cache[test_path] = test_mod

        results = q_data.get("results") or []
        if not isinstance(results, list):
            if args.verbose:
                print(f"Invalid results format for question id {qid}")
            error_count += 1
            continue

        question_count += 1
        for idx, sample in enumerate(results):
            sample_num = sample.get("sample", idx + 1)
            try:
                sample_idx = int(sample_num) - 1
            except Exception:
                sample_idx = idx

            edited_ifc_path = ifc_path
            if crud in {"create", "update", "delete"}:
                edited_ifc_path = (
                    edited_ifc_dir
                    / str(qid)
                    / f"{Path(ifc_file).stem}_{sample_idx}.ifc"
                )

            if not edited_ifc_path.exists():
                if args.verbose:
                    print(f"Edited IFC missing: {edited_ifc_path}")
                error_count += 1
                metrics = {}
            else:
                model_output = normalize_model_output(sample.get("model_output"))
                if model_output is ERROR_OUTPUT_SENTINEL:
                    if args.verbose:
                        print(
                            f"Error placeholder qid={qid} sample={sample_num}: "
                            "running test with model_output=None"
                        )
                    try:
                        metrics = test_mod.execute_test(
                            str(ifc_path), str(edited_ifc_path), None
                        )
                    except Exception as exc:
                        if args.verbose:
                            print(f"Test error qid={qid} sample={sample_num}: {exc}")
                        metrics = false_metrics_for_sample(sample, test_mod)
                        error_count += 1
                elif model_output is None:
                    if args.verbose:
                        print(
                            f"Invalid model_output qid={qid} sample={sample_num}: "
                            "setting metrics to false"
                        )
                    metrics = false_metrics_for_sample(sample, test_mod)
                    error_count += 1
                else:
                    try:
                        metrics = test_mod.execute_test(
                            str(ifc_path), str(edited_ifc_path), model_output
                        )
                    except Exception as exc:
                        if args.verbose:
                            print(f"Test error qid={qid} sample={sample_num}: {exc}")
                        metrics = false_metrics_for_sample(sample, test_mod)
                        error_count += 1

            sample["metrics"] = metrics
            sample["score"] = score_metrics(metrics)
            sample_count += 1

    output_path = Path(args.output).expanduser().resolve() if args.output else cache_path
    if output_path == cache_path and not args.output:
        backup_path = cache_path.with_suffix(cache_path.suffix + ".bak")
        cache_path.replace(backup_path)
        if args.verbose:
            print(f"Backed up original cache to: {backup_path}")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

    print(f"Questions re-evaluated: {question_count}")
    print(f"Samples re-evaluated: {sample_count}")
    print(f"Skipped entries: {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Updated cache: {output_path}")


if __name__ == "__main__":
    main()
