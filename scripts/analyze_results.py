"""Analyze benchmark results and write summary CSV/TXT reports.

Usage:
  python scripts/analyze_results.py [path_to_run_dir_or_cache_file ...]
  python scripts/analyze_results.py --latest
  python scripts/analyze_results.py --dir results/run_x
  python scripts/analyze_results.py --semantic-splits 20 20 20 20 20

How it works:
  Loads cache JSON files, expands per-sample rows, aggregates metrics, and writes detailed CSV + summary text outputs.

Args:
  paths: run directories or cache JSON files (can pass multiple)
  --dir: specific run directory to analyze
  --latest: analyze the latest run in results/
  --output-dir: override output directory for reports
  --semantic-splits: separate questions into semantic categories by counts
  --cache: specific cache JSON file or directory to analyze (overrides run dir selection)
"""

import argparse
import json
from pathlib import Path

import pandas as pd

DEFAULT_SEMANTIC_SPLITS = [20, 20, 20, 20, 20]
DEFAULT_SEMANTIC_LABELS = ["basic", "geometry", "topology", "numeric", "conceptual"]


# Cache discovery helpers
def get_latest_run_dir(results_base_dir: Path) -> Path | None:
    run_dirs = [path for path in results_base_dir.glob("run_*") if path.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda path: path.stat().st_mtime)


def pick_cache_file(run_dir: Path) -> Path | None:
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


def load_cache(cache_path: Path) -> dict:
    with cache_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Cache file format not recognized: {cache_path}")
    return data


def infer_run_id(cache_path: Path) -> str:
    parent = cache_path.parent
    if parent.name.startswith("run_"):
        return parent.name
    return cache_path.stem


# Formatting helpers
def safe_mean(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


# Cache parsing helpers
def collect_rows(cache_data: dict, run_id: str, cache_path: Path | None = None) -> tuple[list[dict], list[dict], list[dict], set[str]]:
    rows = []
    metric_rows = []
    tool_rows = []
    models: set[str] = set()

    for key, q_data in cache_data.items():
        question_id_raw = q_data.get("question_id", key)
        try:
            question_id = int(question_id_raw)
        except Exception:
            question_id = question_id_raw

        prompt = q_data.get("prompt", "") or ""
        model_name = q_data.get("model", "") or ""
        if model_name:
            models.add(model_name)

        source_csv = q_data.get("source_csv") or "unknown"
        crud_op = q_data.get("crud_operation") or None

        results = q_data.get("results", [])
        if not isinstance(results, list):
            continue

        for sample in results:
            sample_id_raw = sample.get("sample", "")
            try:
                sample_id = int(sample_id_raw)
            except Exception:
                sample_id = sample_id_raw

            metrics = sample.get("metrics")
            if not isinstance(metrics, dict):
                metrics = {}

            score = sample.get("score")
            if score is None and metrics:
                score = sum(metrics.values()) / len(metrics)

            tool_call_iterations = sample.get("tool_call_iterations", []) or []
            tool_names = []
            tool_call_count = 0
            for iteration in tool_call_iterations:
                calls = iteration.get("tool_calls", []) or []
                for call in calls:
                    name = call.get("name", "unknown")
                    tool_names.append(name)
                    tool_call_count += 1
                    tool_rows.append(
                        {
                            "Run ID": run_id,
                            "Tool Name": name,
                        }
                    )

            model_output = sample.get("model_output", "")
            is_error = bool(sample.get("error"))
            if isinstance(model_output, str) and "ERROR" in model_output:
                is_error = True

            # Infer CRUD from the source CSV file when missing.
            if (not crud_op or crud_op == "unknown") and isinstance(source_csv, str) and source_csv:
                try:
                    inferred = None
                    if isinstance(question_id, int):
                        inferred = None
                        def find_csv_path(name: str) -> Path | None:
                            candidate = Path(name)
                            if candidate.exists():
                                return candidate
                            cwd_candidate = Path.cwd() / name
                            if cwd_candidate.exists():
                                return cwd_candidate
                            data_candidate = Path("data") / name
                            if data_candidate.exists():
                                return data_candidate
                            if cache_path:
                                cp_candidate = Path(cache_path).parent / name
                                if cp_candidate.exists():
                                    return cp_candidate
                            for p in Path.cwd().rglob(name):
                                return p
                            return None

                        csv_path = find_csv_path(source_csv)
                        if csv_path and csv_path.exists():
                            try:
                                df_q = pd.read_csv(csv_path)
                                cols = {c.lower(): c for c in df_q.columns}
                                for key in ("crud", "crud_operation"):
                                    if key in cols:
                                        colname = cols[key]
                                        if 0 <= question_id < len(df_q):
                                            val = df_q.iloc[question_id][colname]
                                            if pd.notna(val):
                                                inferred = str(val).strip()
                                        break
                            except Exception:
                                inferred = None
                    if inferred:
                        crud_val = inferred
                    else:
                        crud_val = crud_op if crud_op is not None else "unknown"
                except Exception:
                    crud_val = crud_op if crud_op is not None else "unknown"
            else:
                crud_val = crud_op if crud_op is not None else "unknown"

            rows.append(
                {
                    "Run ID": run_id,
                    "Model": model_name,
                    "Question ID": question_id,
                    "Sample": sample_id,
                    "Prompt": prompt,
                    "Source CSV": source_csv,
                    "CRUD Operation": crud_val,
                    "Score": score,
                    "Metrics": json.dumps(metrics),
                    "Tool Calls": tool_call_count,
                    "Tools Used": ", ".join(sorted(set(tool_names))) if tool_names else "none",
                    "Input Tokens": sample.get("input_tokens", 0) or 0,
                    "Output Tokens": sample.get("output_tokens", 0) or 0,
                    "Error": is_error,
                    "_metrics_raw": metrics,
                }
            )

            for metric_name, metric_value in metrics.items():
                metric_rows.append(
                    {
                        "Run ID": run_id,
                        "Question ID": question_id,
                        "Sample": sample_id,
                        "Source CSV": source_csv,
                        "CRUD Operation": crud_op,
                        "Metric": metric_name,
                        "Value": metric_value,
                    }
                )

    return rows, metric_rows, tool_rows, models


# Summaries and aggregations
def summarize_groups(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    work = df.copy()
    work["Score_num"] = pd.to_numeric(work["Score"], errors="coerce")
    work["Pass"] = work["Score_num"].apply(
        lambda x: 1 if x == 1 else (pd.NA if pd.isna(x) else 0)
    )
    work["Error_num"] = work["Error"].astype(int)
    work["Tool Calls_num"] = pd.to_numeric(work["Tool Calls"], errors="coerce").fillna(0)
    work["Input Tokens_num"] = pd.to_numeric(work["Input Tokens"], errors="coerce").fillna(0)
    work["Output Tokens_num"] = pd.to_numeric(work["Output Tokens"], errors="coerce").fillna(0)

    summary = (
        work.groupby(group_cols, dropna=False)
        .agg(
            Prompts=("Question ID", "nunique"),
            Samples=("Sample", "count"),
            Avg_Score=("Score_num", "mean"),
            Pass_Rate=("Pass", "mean"),
            Error_Rate=("Error_num", "mean"),
            Avg_Tool_Calls=("Tool Calls_num", "mean"),
            Avg_Input_Tokens=("Input Tokens_num", "mean"),
            Avg_Output_Tokens=("Output Tokens_num", "mean"),
        )
        .reset_index()
    )

    return summary


def summarize_metrics(df_metrics: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    work = df_metrics.copy()
    work["Value_num"] = pd.to_numeric(work["Value"], errors="coerce")
    work = work.dropna(subset=["Value_num"])
    summary = (
        work.groupby(group_cols + ["Metric"], dropna=False)
        .agg(Count=("Value_num", "count"), Mean=("Value_num", "mean"))
        .reset_index()
    )
    return summary


def assign_semantic_categories(
    df_samples: pd.DataFrame, splits: list[int], labels: list[str] | None = None
) -> pd.Series:
    question_ids = df_samples["Question ID"]
    ids_series = question_ids.dropna()
    if ids_series.empty:
        return pd.Series(["unknown"] * len(df_samples), index=df_samples.index)

    ids_numeric = pd.to_numeric(ids_series, errors="coerce")
    if ids_numeric.notna().all():
        unique_ids = (
            pd.DataFrame({"id": ids_series, "num": ids_numeric})
            .drop_duplicates(subset="id")
            .sort_values("num")
        )
        ordered_ids = unique_ids["id"].tolist()
    else:
        ordered_ids = ids_series.drop_duplicates().tolist()

    mapping: dict[object, str] = {}
    start = 0
    category_index = 1
    labels = labels or []
    for size in splits:
        end = start + size
        category_name = (
            labels[category_index - 1]
            if category_index - 1 < len(labels)
            else f"Category {category_index}"
        )
        for qid in ordered_ids[start:end]:
            mapping[qid] = category_name
        start = end
        category_index += 1

    if start < len(ordered_ids):
        category_name = (
            labels[category_index - 1]
            if category_index - 1 < len(labels)
            else f"Category {category_index}"
        )
        for qid in ordered_ids[start:]:
            mapping[qid] = category_name

    return question_ids.map(mapping).fillna("unknown")


def compute_run_summary(df_samples: pd.DataFrame) -> dict:
    score_series = pd.to_numeric(df_samples["Score"], errors="coerce")
    pass_series = score_series.apply(lambda x: 1 if x == 1 else (pd.NA if pd.isna(x) else 0))
    error_series = df_samples["Error"].astype(int)
    tool_calls_series = pd.to_numeric(df_samples["Tool Calls"], errors="coerce").fillna(0)

    return {
        "Prompts": df_samples["Question ID"].nunique(),
        "Samples": len(df_samples),
        "Avg Score": safe_mean(score_series),
        "Pass Rate": safe_mean(pass_series),
        "Error Rate": safe_mean(error_series),
        "Avg Tool Calls": safe_mean(tool_calls_series),
        "Tool Use Rate": safe_mean((tool_calls_series > 0).astype(int)),
        "Avg Input Tokens": safe_mean(df_samples["Input Tokens"]),
        "Avg Output Tokens": safe_mean(df_samples["Output Tokens"]),
    }


# Output writers
def write_run_outputs(
    df_samples: pd.DataFrame,
    df_metrics: pd.DataFrame,
    df_tools: pd.DataFrame,
    run_id: str,
    output_dir: Path,
    semantic_splits: list[int],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    if df_samples.empty:
        print(f"No results found for {run_id}.")
        return
    df_samples = df_samples.copy()
    df_samples["Semantic Category"] = assign_semantic_categories(
        df_samples, semantic_splits, DEFAULT_SEMANTIC_LABELS
    )
    if not df_metrics.empty:
        metric_categories = (
            df_samples[["Question ID", "Semantic Category"]]
            .drop_duplicates(subset=["Question ID"])
        )
        df_metrics = df_metrics.merge(
            metric_categories,
            on="Question ID",
            how="left",
        )

    multi_suffix = f"_{run_id}" if run_id else ""
    detailed_csv = output_dir / f"detailed_results{multi_suffix}.csv"
    summary_txt = output_dir / f"summary{multi_suffix}.txt"
    df_samples_out = df_samples.drop(columns=["_metrics_raw"], errors="ignore")
    df_samples_out.to_csv(detailed_csv, index=False)

    category_summary = summarize_groups(df_samples, ["Source CSV"])
    crud_summary = summarize_groups(df_samples, ["CRUD Operation"])
    category_crud_summary = summarize_groups(df_samples, ["Source CSV", "CRUD Operation"])
    semantic_summary = summarize_groups(df_samples, ["Semantic Category"])
    semantic_crud_summary = summarize_groups(df_samples, ["Semantic Category", "CRUD Operation"])

    metrics_summary = summarize_metrics(df_metrics, [])
    metrics_by_category = summarize_metrics(df_metrics, ["Source CSV", "CRUD Operation"])
    metrics_by_semantic = summarize_metrics(df_metrics, ["Semantic Category"])

    if df_tools.empty:
        tools_summary = pd.DataFrame(columns=["Tool Name", "Times Used"])
    else:
        tools_summary = (
            df_tools.groupby(["Tool Name"])
            .size()
            .reset_index(name="Times Used")
            .sort_values("Times Used", ascending=False)
        )
    run_summary = compute_run_summary(df_samples)
    with summary_txt.open("w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"RESULTS SUMMARY: {run_id}\n")
        f.write("=" * 80 + "\n\n")

        f.write("OVERALL STATISTICS\n")
        f.write("-" * 80 + "\n")
        f.write(f"Prompts: {run_summary['Prompts']}\n")
        f.write(f"Samples: {run_summary['Samples']}\n")
        f.write(f"Avg Score: {format_pct(run_summary['Avg Score'])}\n")
        f.write(f"Pass Rate: {format_pct(run_summary['Pass Rate'])}\n")
        f.write(f"Error Rate: {format_pct(run_summary['Error Rate'])}\n")
        f.write(f"Avg Tool Calls: {format_float(run_summary['Avg Tool Calls'])}\n")
        f.write(f"Tool Use Rate: {format_pct(run_summary['Tool Use Rate'])}\n")
        f.write(f"Avg Input Tokens: {format_float(run_summary['Avg Input Tokens'])}\n")
        f.write(f"Avg Output Tokens: {format_float(run_summary['Avg Output Tokens'])}\n\n")

        f.write("STATISTICS BY FILE CATEGORY\n")
        f.write("-" * 80 + "\n")
        f.write(category_summary.to_string(index=False))
        f.write("\n\n")

        f.write("STATISTICS BY SEMANTIC CATEGORY\n")
        f.write("-" * 80 + "\n")
        f.write(semantic_summary.to_string(index=False))
        f.write("\n\n")

        f.write("STATISTICS BY SEMANTIC CATEGORY AND CRUD\n")
        f.write("-" * 80 + "\n")
        f.write(semantic_crud_summary.to_string(index=False))
        f.write("\n\n")

        f.write("STATISTICS BY CRUD OPERATION\n")
        f.write("-" * 80 + "\n")
        f.write(crud_summary.to_string(index=False))
        f.write("\n\n")

        f.write("STATISTICS BY FILE CATEGORY AND CRUD\n")
        f.write("-" * 80 + "\n")
        f.write(category_crud_summary.to_string(index=False))
        f.write("\n\n")

        f.write("TOOLS USAGE SUMMARY\n")
        f.write("-" * 80 + "\n")
        if not tools_summary.empty:
            f.write(tools_summary.to_string(index=False))
        else:
            f.write("No tools used")
        f.write("\n\n")

        f.write("METRICS SUMMARY (OVERALL)\n")
        f.write("-" * 80 + "\n")
        if not metrics_summary.empty:
            metrics_summary = metrics_summary.copy()
            metrics_summary["Success Rate"] = metrics_summary["Mean"].apply(
                lambda v: f"{v * 100:.1f}%"
            )
            f.write(metrics_summary.to_string(index=False))
        else:
            f.write("No metrics recorded")
        f.write("\n")

        f.write("\nMETRICS SUMMARY BY SEMANTIC CATEGORY\n")
        f.write("-" * 80 + "\n")
        if not metrics_by_semantic.empty:
            metrics_by_semantic = metrics_by_semantic.copy()
            metrics_by_semantic["Success Rate"] = metrics_by_semantic["Mean"].apply(
                lambda v: f"{v * 100:.1f}%"
            )
            f.write(metrics_by_semantic.to_string(index=False))
        else:
            f.write("No metrics recorded")
        f.write("\n")

    print(f"Detailed results saved to: {detailed_csv}")
    print(f"Summary text saved to: {summary_txt}")


# Main analysis flow
def analyze_cache_files(
    cache_files: list[Path], output_dir: Path, semantic_splits: list[int]
) -> None:
    run_summaries = []
    all_samples = []

    for cache_path in cache_files:
        run_id = infer_run_id(cache_path)
        cache_data = load_cache(cache_path)
        rows, metric_rows, tool_rows, models = collect_rows(cache_data, run_id, cache_path=cache_path)

        if not rows:
            print(f"No rows found in cache: {cache_path}")
            continue

        df_samples = pd.DataFrame(rows)
        df_metrics = pd.DataFrame(
            metric_rows,
            columns=[
                "Run ID",
                "Question ID",
                "Sample",
                "Source CSV",
                "CRUD Operation",
                "Metric",
                "Value",
            ],
        )
        df_tools = pd.DataFrame(tool_rows, columns=["Run ID", "Tool Name"])
        write_run_outputs(
            df_samples, df_metrics, df_tools, run_id, output_dir, semantic_splits
        )

        run_summary = compute_run_summary(df_samples)
        run_summary["Run ID"] = run_id
        run_summary["Model"] = ", ".join(sorted(models)) if models else "unknown"
        run_summaries.append(run_summary)
        all_samples.append(df_samples)

    if len(run_summaries) > 1:
        print("Multiple runs detected; skipping comparison CSV outputs per settings.")


def resolve_cache_files(
    paths: list[str], latest: bool, run_dir: str | None, cache_path: str | None
) -> list[Path]:
    cache_files: list[Path] = []

    if cache_path:
        p = cache_path
        path_obj = Path(p)
        if path_obj.is_dir():
            cache_candidate = pick_cache_file(path_obj)
            if cache_candidate:
                cache_files.append(cache_candidate)
            else:
                print(f"Warning: no cache file found in specified directory: {p}")
        elif path_obj.is_file():
            cache_files.append(path_obj)
        else:
            print(f"Warning: specified cache path not found: {p}")
        return cache_files

    if run_dir:
        run_path = Path(run_dir)
        if run_path.is_dir():
            cache_path = pick_cache_file(run_path)
            if cache_path:
                cache_files.append(cache_path)
        elif run_path.is_file():
            cache_files.append(run_path)
        return cache_files

    if paths:
        for p in paths:
            path_obj = Path(p)
            if path_obj.is_dir():
                cache_path = pick_cache_file(path_obj)
                if cache_path:
                    cache_files.append(cache_path)
            elif path_obj.is_file():
                cache_files.append(path_obj)
        return cache_files

    if latest:
        latest_run = get_latest_run_dir(Path("results"))
        if latest_run:
            cache_path = pick_cache_file(latest_run)
            if cache_path:
                cache_files.append(cache_path)
        return cache_files

    latest_run = get_latest_run_dir(Path("results"))
    if latest_run:
        cache_path = pick_cache_file(latest_run)
        if cache_path:
            cache_files.append(cache_path)

    return cache_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze benchmark results.")
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to run directories or cache JSON files (can provide multiple).",
    )
    parser.add_argument("--dir", dest="run_dir", help="Specific run directory to analyze.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Analyze the latest run (default if no path provided).",
    )
    parser.add_argument(
        "--cache",
        dest="cache_file",
        help="Path to a specific cache JSON file or directory to analyze (overrides run dir selection).",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory to write analysis outputs (default: run dir or cwd).",
    )
    parser.add_argument(
        "--semantic-splits",
        nargs="*",
        type=int,
        default=None,
        help=(
            "Split questions into semantic categories by counts. "
            "Provide counts like: --semantic-splits 20 20 20 20 20. "
            "Use flag without values for default [20,20,20,20,20]."
        ),
    )
    args = parser.parse_args()

    cache_files = resolve_cache_files(args.paths, args.latest, args.run_dir, args.cache_file)
    if not cache_files:
        print("No cache files found to analyze.")
        return

    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif len(cache_files) == 1:
        output_dir = cache_files[0].parent
    else:
        output_dir = Path.cwd()

    semantic_splits = args.semantic_splits
    if semantic_splits is None or len(semantic_splits) == 0:
        semantic_splits = DEFAULT_SEMANTIC_SPLITS.copy()
    if any(size <= 0 for size in semantic_splits):
        print("Semantic splits must be positive integers.")
        return

    analyze_cache_files(cache_files, output_dir, semantic_splits)


if __name__ == "__main__":
    main()
