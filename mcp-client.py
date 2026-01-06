import argparse
import asyncio
import json
from pathlib import Path
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from typing import List
import pandas as pd
import importlib
from typing import TypedDict
from datetime import datetime
import shutil

class State(TypedDict):
    prompt: str
    structured_output: object
    ifc_file_path: str
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_call_iterations: List[dict]

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
    return model_name.split(":")[-1]

# TODO: catch errors while calling tools so that the benchmark does not end
async def main():
    default_config = Path(__file__).with_name("benchmark.config.json")
    parser = argparse.ArgumentParser(description="Run the IFC MCP benchmark.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)
    base_dir = config_path.parent

    env_path = base_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    questions_path = resolve_path(base_dir, config["questions_csv"])
    questions = pd.read_csv(questions_path)

    num_samples = config["num_samples"]
    model_name = config["model_name"]
    model = init_chat_model(model_name)
    system_prompt = config["system_prompt"]

    paths_config = config["paths"]
    ifc_dir = resolve_path(base_dir, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    structured_outputs_module = paths_config["structured_outputs_module"]
    results_dir = resolve_path(base_dir, paths_config["results_dir"])
    results_dir.mkdir(parents=True, exist_ok=True)

    # Create a unique directory for this run
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = results_dir / f"run_{run_timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"Result for this run will be stored in: {run_dir}")

    # Save a copy of the configuration for reproducibility
    with (run_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    results_config = config["results"]
    model_suffix_value = model_suffix(model_name)
    
    # Cache file for THIS run
    cache_filename = results_config["cache_filename_template"].format(
        model_suffix=model_suffix_value
    )
    cache_path = run_dir / cache_filename

    # Edited IFC directory for THIS run
    edited_ifc_dirname = results_config["edited_ifc_dir_template"].format(
        model_suffix=model_suffix_value
    )
    edited_ifc_directory = run_dir / edited_ifc_dirname
    edited_ifc_directory.mkdir(parents=True, exist_ok=True)

    # Connect to MCP server and load tools
    client = MultiServerMCPClient(
        config["mcp_servers"]
    )
    mcp_tools = await client.get_tools()

    load_ifc_tool = next(
        (
            tool
            for tool in mcp_tools
            if tool.name == "load_ifc_file" or tool.name.endswith("load_ifc_file")
        ),
        None,
    )

    async def preload_ifc_in_blender(ifc_file_path: str) -> None:
        """Load the IFC into Blender via MCP directly (no LLM tokens)."""

        if load_ifc_tool is None:
            print(
                "Warning: MCP tool 'load_ifc_file' not found. "
                "Falling back to prompting the model with the file path."
            )
            return

        try:
            await load_ifc_tool.ainvoke(
                {
                    "filepath": ifc_file_path,
                    "use_relative_path": False,
                    "start_fresh_session": True,
                }
            )
        except Exception as exc:
            # Do not crash the benchmark if Blender/MCP fails for one sample.
            print(f"Warning: Failed to preload IFC via MCP tool: {exc}")

    async def call_model(state: State):
        """function that calls the model and writes the output to the state"""

        # read prompt, structured output, ifc file path from state and initialize llm-agent
        prompt = state["prompt"]
        ifc_file_path = state["ifc_file_path"]
        structured_output = state["structured_output"]

        # Pre-load IFC into Blender without involving the LLM.
        await preload_ifc_in_blender(ifc_file_path)

        if structured_output:
            agent = create_agent(model, mcp_tools, response_format=ToolStrategy(structured_output))
        else:
            agent = create_agent(model, mcp_tools)

        # invoke agents
        if load_ifc_tool is None:
            user_content = f"{prompt}\nThe ifc file path is {ifc_file_path}."
        else:
            user_content = f"{prompt}\n(The IFC file is already loaded in Blender.)"

        chain = [
            event
            async for event in agent.astream_events(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ]
                }
            )
        ]

        # retrieve outputs containing model output, tool calls and token uses
        chain_end = chain[-1]

        model_output = ""
        input_tokens = output_tokens = 0
        tool_call_iterations = []
        messages = chain_end.get("data", {}).get("output", {}).get("messages", [])
        for message in messages:
            if not getattr(message, "response_metadata", None):
                continue

            tokens = getattr(message, "usage_metadata", None) or {}
            input_tokens = int(tokens.get("input_tokens", 0))
            output_tokens = int(tokens.get("output_tokens", 0))

            finish_reason = message.response_metadata.get("finish_reason") if message.response_metadata else None

            if finish_reason == "tool_calls":
                tool_calls = []
                for tool_call in getattr(message, "tool_calls", []) or []:
                    name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                    args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", None)
                    if name and name != "ModelOutput":
                        tool_calls.append({"name": name, "args": args})
                tool_call_iterations.append(
                    {"tool_calls": tool_calls, "input_tokens": input_tokens, "output_tokens": output_tokens}
                )

            if finish_reason == "stop":
                model_output = message.content if getattr(message, "content", None) is not None else model_output


        if "structured_response" in chain_end["data"]["output"].keys():
            model_output = chain_end["data"]["output"]["structured_response"]

        return {
            "model_output": model_output,
            "tool_call_iterations": tool_call_iterations,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }


    # Initialize cache
    cache = {}
    
    # Load cache from source if specified
    cache_source = config.get("cache_source")
    if cache_source:
        cache_source_path = resolve_path(base_dir, cache_source)
        if cache_source_path.exists():
            try:
                with cache_source_path.open("r", encoding="utf-8") as cache_file:
                    cache = json.load(cache_file)
                print(f"Loaded existing cache from: {cache_source_path}")
                print(f"Cache contains {len(cache)} entries.")
            except Exception as e:
                print(f"Warning: Failed to load cache source {cache_source_path}: {e}")
                print("Starting with empty cache.")
        else:
             print(f"Warning: Cache source file not found: {cache_source_path}")
             print("Starting with empty cache.")
    else:
        print("No cache source specified. Starting with empty cache.")

    # build langchain graph
    builder = StateGraph(State)
    builder.add_node("call_model", call_model)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    graph = builder.compile()


    # iterate over every prompt from the csv file
    for index, row in questions.iterrows():
        print(f"Processing question {int(str(index))+1} of {len(questions)}...")
        question_id = int(str(index))

        # if prompt already processed, use the cached result
        if str(question_id) in cache:
            print("Question already in cache. Using cached result.")
            print(cache[str(question_id)])
            continue

        # read the prompt, test, ifc file path, and structured output from the csv file
        prompt = row["question"]
        test_path = f"{tests_module}.{row['test']}"
        ifc_path = ifc_dir / row["ifc-file"]

        # load the structured output python object
        if not pd.isna(row["structured-output"]):
            structured_output = f"{structured_outputs_module}.{row['structured-output']}"
            output_object = importlib.import_module(structured_output).ModelOutput
        else:
            output_object = None

        # creating subdirectory for storing edited ifc files per question
        edited_question_directory = edited_ifc_directory / str(question_id)
        edited_question_directory.mkdir(parents=True, exist_ok=True)

        # iterate over sample size and store results for every sample
        sample_results = []
        for sample in range(num_samples):

            # create the ifc file that will be edited. Create a new one per sample.
            ifc_stem = Path(row["ifc-file"]).stem
            edited_ifc_path = edited_question_directory / f"{ifc_stem}_{sample}.ifc"
            shutil.copyfile(ifc_path, edited_ifc_path)

            # set the arguments for the LLM
            model_args = {
                "prompt": prompt,
                "structured_output": output_object,
                "ifc_file_path": str(edited_ifc_path.resolve()),
            }

            # invoke LLM
            try:
                result_state = await graph.ainvoke(
                    model_args,
                    config={"recursion_limit": 25}
                )
            except Exception as exc:
                print(f"Error in question {question_id}, sample {sample}: {exc}")
                sample_cache_object = {
                    "sample": sample + 1,
                    "model_output": "ERROR_OR_RECURSION_LIMIT_OF_25_EXCEEDED",
                    "tool_call_iterations": [],
                    "metrics": {},
                    "score": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": str(exc)
                }
                sample_results.append(sample_cache_object)
                continue

            # process structured output
            if output_object:
                model_output = result_state["model_output"].__dict__
            else:
                model_output = result_state["model_output"]

            # load and execute test
            test = importlib.import_module(test_path)
            # now you can call test.execute_test() and retrieve the evaluation metrics
            metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)

            # store results for a sample
            sample_cache_object = {
                "sample": sample + 1,
                "model_output": model_output,
                "tool_call_iterations": result_state["tool_call_iterations"],
                "metrics": metrics, # dictionary of metrics
                "score": sum(metrics.values())/len(metrics), # score = fulfilled metrics / all metrics
                "input_tokens": result_state["input_tokens"],
                "output_tokens": result_state["output_tokens"]
            }
            sample_results.append(sample_cache_object)

        # store results for a question
        cache_object = {
            "question_id": question_id,
            "prompt": prompt,
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }

        # store results in the cache
        cache[question_id] = cache_object

        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)

        # input("Please prepare open Blender file so that the next question can be processed. Press enter to continue.")
        # for manually opening the right ifc file in blender


if __name__ == "__main__":
    asyncio.run(main())
