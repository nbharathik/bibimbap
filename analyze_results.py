import argparse
import json
import glob
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

def get_latest_run_dir(results_base_dir):
    runs = glob.glob(os.path.join(results_base_dir, "run_*"))
    if not runs:
        return None
    return max(runs, key=os.path.getmtime)

def analyze_file(cache_file):
    run_dir = os.path.dirname(cache_file)
    print(f"\nAnalyzing file: {cache_file}")
    print("=" * 60)

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading cache file: {e}")
        return

    df_rows = []
    
    total_score = 0
    total_questions = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for q_id, q_data in data.items():
        total_questions += 1
        
        for sample in q_data.get("results", []):
            score = sample.get("score", 0)
            metrics = sample.get("metrics", {})
            input_tok = sample.get("input_tokens", 0)
            output_tok = sample.get("output_tokens", 0)
            model_output = sample.get("model_output", "")
            
            is_error = isinstance(model_output, str) and "ERROR" in model_output

            total_score += score
            total_input_tokens += input_tok
            total_output_tokens += output_tok

            df_rows.append({
                "Question ID": q_id,
                "Prompt": q_data.get("prompt", "")[:50] + "...",
                "Sample": sample.get("sample"),
                "Score": score,
                "Input Tokens": input_tok,
                "Output Tokens": output_tok,
                "Error": is_error,
                "Metrics": json.dumps(metrics)
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

    print(f"Total Questions: {total_questions}")
    print(f"Total Samples: {num_samples}")
    print(f"Average Score: {avg_score:.2f} / 1.0")
    print(f"Pass Rate (Perfect Score): {pass_rate:.1f}%")
    print(f"Avg Input Tokens: {avg_input:.1f}")
    print(f"Avg Output Tokens: {avg_output:.1f}")
    print("-" * 60)
    print("Detailed Results (first 5 shown):")
    print(df[["Question ID", "Score", "Error", "Input Tokens"]].head(5).to_string(index=False))
    
    # Option to save to CSV
    if run_dir:
        csv_path = os.path.join(run_dir, "summary.csv")
    else:
        csv_path = "summary.csv"
        
    df.to_csv(csv_path, index=False)
    print(f"\nFull summary saved to: {csv_path}")

def analyze_run(run_dir):
    cache_files = glob.glob(os.path.join(run_dir, "cache_*.json"))
    if not cache_files:
        print(f"No cache/result file found in directory: {run_dir}")
        return

    cache_file = cache_files[0] 
    analyze_file(cache_file)

def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results.")
    parser.add_argument("path", nargs="?", help="Path to a run directory or a specific cache JSON file")
    parser.add_argument("--dir", help="Specific run directory to analyze (optional, prefer positional arg)")
    parser.add_argument("--latest", action="store_true", help="Analyze the latest run (default if no path provided)", default=True)
    
    args = parser.parse_args()
    
    base_dir = Path("results")
    
    target_path = args.path or args.dir
    
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
