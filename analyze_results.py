"""
Analyze benchmark results and generate summary statistics and reports.

How to use:
    python analyze_results.py [path_to_run_dir_or_cache_file]
    python analyze_results.py path1.json path2.json  # Merge multiple JSON files
    If no path is provided, analyzes the latest run in the 'results' directory.
"""

import argparse
import json
import glob
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from collections import defaultdict

def get_latest_run_dir(results_base_dir):
    runs = glob.glob(os.path.join(results_base_dir, "run_*"))
    if not runs:
        return None
    return max(runs, key=os.path.getmtime)

def load_and_merge_json_files(file_paths):
    """Load and merge multiple JSON cache files into a single dataset."""
    merged_data = {}
    
    for file_path in file_paths:
        print(f"Loading: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge data, using file path prefix to avoid key conflicts
                for key, value in data.items():
                    unique_key = f"{Path(file_path).stem}_{key}"
                    merged_data[unique_key] = value
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return merged_data

def analyze_file(cache_file):
    run_dir = os.path.dirname(cache_file)
    print(f"\nAnalyzing file: {cache_file}")
    print("=" * 80)

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading cache file: {e}")
        return

    df_rows = []
    category_stats = defaultdict(lambda: {"total_score": 0, "count": 0, "prompts": 0})
    crud_stats = defaultdict(lambda: {"total_score": 0, "count": 0, "prompts": 0})
    category_crud_stats = defaultdict(lambda: defaultdict(lambda: {"total_score": 0, "count": 0, "prompts": 0}))
    tools_used = defaultdict(int)
    metrics_summary = defaultdict(lambda: {"true": 0, "total": 0})
    metrics_detailed = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"true": 0, "total": 0})))
    total_errors = 0
    total_score = 0
    total_prompts = len(data)
    total_input_tokens = 0
    total_output_tokens = 0

    for q_id, q_data in data.items():
        source_csv = q_data.get("source_csv", "unknown")
        crud_op = q_data.get("crud_operation", "unknown")
        
        category_stats[source_csv]["prompts"] += 1
        crud_stats[crud_op]["prompts"] += 1
        category_crud_stats[source_csv][crud_op]["prompts"] += 1
        
        for sample in q_data.get("results", []):
            score = sample.get("score", 0)
            metrics = sample.get("metrics", {})
            input_tok = sample.get("input_tokens", 0)
            output_tok = sample.get("output_tokens", 0)
            model_output = sample.get("model_output", "")
            tool_calls = sample.get("tool_call_iterations", [])
            
            is_error = isinstance(model_output, str) and "ERROR" in model_output

            total_score += score
            total_input_tokens += input_tok
            total_output_tokens += output_tok
            
            if is_error:
                total_errors += 1
            
            tools_called = []
            num_tool_calls = 0
            for iteration in tool_calls:
                calls = iteration.get("tool_calls", [])
                num_tool_calls += len(calls)
                for call in calls:
                    tool_name = call.get("name", "unknown")
                    if tool_name not in tools_called:
                        tools_called.append(tool_name)
                    tools_used[tool_name] += 1
            
            for metric_key, metric_value in metrics.items():
                metrics_summary[metric_key]["total"] += 1
                metrics_detailed[metric_key][source_csv][crud_op]["total"] += 1
                if metric_value:
                    metrics_summary[metric_key]["true"] += 1
                    metrics_detailed[metric_key][source_csv][crud_op]["true"] += 1

            category_stats[source_csv]["total_score"] += score
            category_stats[source_csv]["count"] += 1
            crud_stats[crud_op]["total_score"] += score
            crud_stats[crud_op]["count"] += 1
            category_crud_stats[source_csv][crud_op]["total_score"] += score
            category_crud_stats[source_csv][crud_op]["count"] += 1

            df_rows.append({
                "Question ID": q_id,
                "Prompt": q_data.get("prompt", "")[:60] + "...",
                "File Name": source_csv,
                "CRUD Operation": crud_op,
                "Score": score,
                "Metrics": json.dumps(metrics),
                "Number of Tool Calls": num_tool_calls,
                "Tools Called": ", ".join(tools_called) if tools_called else "none",
                "Input Tokens": input_tok,
                "Output Tokens": output_tok,
                "Error": is_error,
            })

    if not df_rows:
        print("No results found in cache file.")
        return

    df = pd.DataFrame(df_rows)
    
    num_samples = len(df)
    avg_score = total_score / num_samples if num_samples else 0
    avg_input = total_input_tokens / num_samples if num_samples else 0
    avg_output = total_output_tokens / num_samples if num_samples else 0
    pass_rate = (df["Score"] == 1.0).mean() * 100

    print(f"\n{'OVERALL STATISTICS':^80}")
    print("=" * 80)
    print(f"Total Prompts: {total_prompts}")
    print(f"Total Samples: {num_samples}")
    print(f"Total Score: {avg_score*100:.2f}%")
    print(f"Pass Rate (Perfect Score): {pass_rate:.1f}%")
    print(f"Avg Input Tokens: {avg_input:.1f}")
    print(f"Avg Output Tokens: {avg_output:.1f}")
    
    # Print statistics by source_csv (file category)
    print(f"\n{'STATISTICS BY FILE CATEGORY':^80}")
    print("=" * 80)
    category_summary = []
    for source_csv in sorted(category_stats.keys()):
        stats = category_stats[source_csv]
        avg = stats["total_score"] / stats["count"] if stats["count"] else 0
        avg = round(avg * 100, 2)
        category_summary.append({
            "File Category": source_csv,
            "No. of Prompts": stats["prompts"],
            "Total Score": avg,
        })
        print(f"{source_csv:30} | No. of Prompts: {stats['prompts']:3} | "
              f"Avg Score: {avg:.2f}%")
    
    print(f"\n{'STATISTICS BY CRUD OPERATION':^80}")
    print("=" * 80)
    crud_summary = []
    for crud_op in sorted(crud_stats.keys()):
        stats = crud_stats[crud_op]
        avg = stats["total_score"] / stats["count"] if stats["count"] else 0
        avg = round(avg * 100, 2)
        crud_summary.append({
            "CRUD Operation": crud_op,
            "No. of Prompts": stats["prompts"],
            "Total Score": avg,
        })
        print(f"{crud_op:20} | No. of Prompts: {stats['prompts']:3} | "
              f"Avg Score: {avg:.2f}%")
    
    if run_dir:
        detailed_csv = os.path.join(run_dir, "detailed_results.csv")
        summary_txt = os.path.join(run_dir, "summary.txt")
    else:
        detailed_csv = "detailed_results.csv"
        summary_txt = "summary.txt"
    
    category_df = pd.DataFrame(category_summary)
    crud_df = pd.DataFrame(crud_summary)
    for df_obj in (category_df, crud_df):
        if not df_obj.empty:
            if "Total Score" in df_obj:
                df_obj["Total Score"] = df_obj["Total Score"].astype(float).round(2)
    
    df.to_csv(detailed_csv, index=False)
    print(f"\n✓ Detailed results saved to: {detailed_csv}")
    
    with open(summary_txt, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("RESULTS ANALYSIS SUMMARY\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("STATISTICS BY FILE CATEGORY\n")
        f.write("-" * 80 + "\n")
        f.write(category_df.to_string(index=False))
        f.write("\n\n")
        f.write("STATISTICS BY CRUD OPERATION\n")
        f.write("-" * 80 + "\n")
        f.write(crud_df.to_string(index=False))
        f.write("\n\n")

        f.write("CRUD SUMMARY BY FILE TYPE\n")
        f.write("=" * 80 + "\n\n")
        for source_csv in sorted(category_crud_stats.keys()):
            f.write(f"FILE TYPE: {source_csv}\n")
            f.write("-" * 80 + "\n")
            category_crud_rows = []
            for crud_op in sorted(category_crud_stats[source_csv].keys()):
                stats = category_crud_stats[source_csv][crud_op]
                avg = stats["total_score"] / stats["count"] if stats["count"] else 0
                avg = round(avg * 100, 2)
                category_crud_rows.append({
                    "CRUD Operation": crud_op,
                    "No. of Prompts": stats["prompts"],
                    "Total Score": avg,
                })
            if category_crud_rows:
                category_crud_df = pd.DataFrame(category_crud_rows)
                if "Total Score" in category_crud_df:
                    category_crud_df["Total Score"] = category_crud_df["Total Score"].astype(float).round(2)
                f.write(category_crud_df.to_string(index=False))
                f.write("\n\n")
            else:
                f.write("No CRUD data\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("TOOLS USAGE SUMMARY\n")
        f.write("=" * 80 + "\n")
        if tools_used:
            tools_df = pd.DataFrame(sorted(tools_used.items(), key=lambda x: x[1], reverse=True), 
                                   columns=["Tool Name", "Times Used"])
            f.write(tools_df.to_string(index=False))
            f.write(f"\nTotal Unique Tools: {len(tools_used)}\n")
            f.write(f"Total Tool Calls: {sum(tools_used.values())}\n")
        else:
            f.write("No tools used\n")
        f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("METRICS SUMMARY BY FILE TYPE\n")
        f.write("=" * 80 + "\n\n")
        
        if metrics_summary:
            all_file_types = set()
            for metric_dict in metrics_detailed.values():
                all_file_types.update(metric_dict.keys())
            
            for file_type in sorted(all_file_types):
                f.write(f"FILE TYPE: {file_type}\n")
                f.write("-" * 80 + "\n")
                
                metrics_data = []
                for metric_name, counts in sorted(metrics_summary.items(), key=lambda x: x[1]["true"], reverse=True):
                    if file_type in metrics_detailed[metric_name]:
                        crud_ops_dict = metrics_detailed[metric_name][file_type]
                        total_for_type = sum(op_data["total"] for op_data in crud_ops_dict.values())
                        true_for_type = sum(op_data["true"] for op_data in crud_ops_dict.values())
                        
                        if total_for_type > 0:
                            success_rate = f"{(true_for_type/total_for_type*100):.1f}%"
                            metrics_data.append({
                                "Metric Name": metric_name,
                                "True": true_for_type,
                                "Total": total_for_type,
                                "Success Rate": success_rate,
                                "CRUD Operations": ", ".join(sorted(crud_ops_dict.keys()))
                            })
                
                if metrics_data:
                    metrics_df = pd.DataFrame(metrics_data)
                    f.write(metrics_df.to_string(index=False))
                    f.write("\n\n")
                else:
                    f.write("No metrics for this file type\n\n")
        else:
            f.write("No metrics recorded\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("OVERALL STATISTICS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total Prompts: {total_prompts}\n")
        f.write(f"Total Samples: {num_samples}\n")
        f.write(f"Total Score: {avg_score*100:.2f}%\n")
        f.write(f"Pass Rate (Perfect Score): {pass_rate:.1f}%\n")
        f.write(f"Total Input Tokens: {total_input_tokens}\n")
        f.write(f"Total Output Tokens: {total_output_tokens}\n")
        f.write(f"Total Errors: {total_errors}\n")
    
    print(f"✓ Summary text saved to: {summary_txt}")

def analyze_run(run_dir):
    cache_files = glob.glob(os.path.join(run_dir, "cache_*.json"))
    if not cache_files:
        print(f"No cache/result file found in directory: {run_dir}")
        return

    cache_file = cache_files[0] 
    analyze_file(cache_file)

def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results.")
    parser.add_argument("paths", nargs="*", help="Paths to run directories or cache JSON files (can provide multiple)")
    parser.add_argument("--dir", help="Specific run directory to analyze (optional)")
    parser.add_argument("--latest", action="store_true", help="Analyze the latest run (default if no path provided)")
    
    args = parser.parse_args()
    
    base_dir = Path("results")
    
    # Handle multiple paths for merging
    if args.paths and len(args.paths) > 1:
        # Check if all are JSON files
        json_files = [p for p in args.paths if Path(p).suffix == ".json"]
        if len(json_files) == len(args.paths):
            print(f"\nMerging {len(json_files)} JSON files...")
            merged_data = load_and_merge_json_files(json_files)
            
            # Create a temporary analysis with merged data
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
                json.dump(merged_data, tmp)
                tmp_path = tmp.name
            
            try:
                analyze_file(tmp_path)
            finally:
                os.unlink(tmp_path)
            return
        else:
            print("Error: When providing multiple paths, all must be JSON files.")
            return
    
    # Single path handling
    target_path = args.paths[0] if args.paths else args.dir
    
    if target_path:
        path_obj = Path(target_path)
        if path_obj.is_file() and path_obj.suffix == ".json":
             analyze_file(str(path_obj))
        elif path_obj.is_dir():
             analyze_run(str(path_obj))
        else:
             print(f"Invalid path: {target_path}")
    else:
        target_dir = get_latest_run_dir(base_dir)
        if target_dir:
            analyze_run(target_dir)
        else:
            print("No run directory found or specified.")

if __name__ == "__main__":
    main()
