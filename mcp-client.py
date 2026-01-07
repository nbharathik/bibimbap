import argparse
import asyncio
import json
from collections.abc import Mapping
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

try:
    # Universal token counting callback (aggregates across multi-step agent runs).
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception:  # pragma: no cover
    get_usage_metadata_callback = None

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
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(description="Run the IFC MCP benchmark.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)

    base_dir = repo_root
    config_dir = config_path.parent

    env_path = config_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    questions_path = resolve_path(base_dir, config["questions_csv"])
    questions = pd.read_csv(questions_path)

    num_samples = config["num_samples"]
    model_name = config["model_name"]
    model = init_chat_model(model_name)

    # Best-effort: ensure token usage is included in streaming responses.
    # Some providers (notably OpenAI) omit usage in streaming unless explicitly enabled.
    try:
        if hasattr(model, "stream_options"):
            existing = getattr(model, "stream_options") or {}
            if isinstance(existing, dict):
                model.stream_options = {**existing, "include_usage": True}
        if hasattr(model, "model_kwargs"):
            mk = getattr(model, "model_kwargs") or {}
            if isinstance(mk, dict):
                so = mk.get("stream_options") or {}
                if isinstance(so, dict):
                    mk["stream_options"] = {**so, "include_usage": True}
                    model.model_kwargs = mk
    except Exception:
        # If the underlying model does not support this, fall back silently.
        pass
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

        # Collect events. If available, use LangChain's aggregated usage callback,
        # which counts tokens across *all* underlying model calls (tool loops included).
        usage_cb_cm = None
        usage_cb = None
        if get_usage_metadata_callback is not None:
            try:
                usage_cb_cm = get_usage_metadata_callback()
                usage_cb = usage_cb_cm.__enter__()
            except Exception:
                usage_cb_cm = None
                usage_cb = None

        try:
            chain = [
                event
                async for event in agent.astream_events(
                    {
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ]
                    },
                    config={"callbacks": [usage_cb]} if usage_cb is not None else None,
                )
            ]
        finally:
            if usage_cb_cm is not None:
                usage_cb_cm.__exit__(None, None, None)

        # retrieve outputs containing model output, tool calls and token uses
        chain_end = chain[-1]

        def _extract_token_usage_from_message(msg) -> tuple[int, int]:
            """Return (input_tokens, output_tokens) best-effort for a LangChain message."""
            usage = getattr(msg, "usage_metadata", None) or {}
            if isinstance(usage, Mapping) and usage:
                in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                return int(in_tok or 0), int(out_tok or 0)

            rm = getattr(msg, "response_metadata", None) or {}
            if isinstance(rm, Mapping) and rm:
                # Some integrations put usage directly on response_metadata.
                if any(
                    k in rm
                    for k in (
                        "input_tokens",
                        "prompt_tokens",
                        "output_tokens",
                        "completion_tokens",
                    )
                ):
                    in_tok = rm.get("input_tokens") or rm.get("prompt_tokens") or 0
                    out_tok = rm.get("output_tokens") or rm.get("completion_tokens") or 0
                    return int(in_tok or 0), int(out_tok or 0)

                token_usage = rm.get("token_usage") or rm.get("usage") or {}
                if isinstance(token_usage, Mapping) and token_usage:
                    in_tok = token_usage.get("input_tokens") or token_usage.get("prompt_tokens") or 0
                    out_tok = token_usage.get("output_tokens") or token_usage.get("completion_tokens") or 0
                    return int(in_tok or 0), int(out_tok or 0)

            return 0, 0

        def _aggregate_token_usage_from_callback(cb) -> tuple[int, int] | None:
            """Return (input_tokens, output_tokens) aggregated across agent run, or None."""
            if cb is None or not getattr(cb, "usage_metadata", None):
                return None
            try:
                cb_in = cb_out = 0
                for v in cb.usage_metadata.values():
                    if not isinstance(v, Mapping):
                        continue
                    cb_in += int(v.get("input_tokens") or v.get("prompt_tokens") or 0)
                    cb_out += int(v.get("output_tokens") or v.get("completion_tokens") or 0)
                return cb_in, cb_out
            except Exception:
                return None

        def _parse_messages_for_output_and_tool_calls(msgs) -> tuple[str, list[dict], int, int]:
            """Return (model_output, tool_call_iterations, parsed_in, parsed_out)."""
            model_out = ""
            parsed_in = parsed_out = 0
            iterations: list[dict] = []

            for message in msgs or []:
                msg_input_tokens, msg_output_tokens = _extract_token_usage_from_message(message)
                parsed_in += msg_input_tokens
                parsed_out += msg_output_tokens

                finish_reason = (
                    message.response_metadata.get("finish_reason")
                    if getattr(message, "response_metadata", None)
                    else None
                )

                if finish_reason == "tool_calls":
                    tool_calls = []
                    for tool_call in getattr(message, "tool_calls", []) or []:
                        name = (
                            tool_call.get("name")
                            if isinstance(tool_call, dict)
                            else getattr(tool_call, "name", None)
                        )
                        args = (
                            tool_call.get("args")
                            if isinstance(tool_call, dict)
                            else getattr(tool_call, "args", None)
                        )
                        if name and name != "ModelOutput":
                            tool_calls.append({"name": name, "args": args})
                    iterations.append(
                        {
                            "tool_calls": tool_calls,
                            "input_tokens": msg_input_tokens,
                            "output_tokens": msg_output_tokens,
                        }
                    )

                if finish_reason == "stop":
                    model_out = (
                        message.content
                        if getattr(message, "content", None) is not None
                        else model_out
                    )

            return model_out, iterations, parsed_in, parsed_out

        model_output = ""
        input_tokens = output_tokens = 0
        tool_call_iterations = []

        messages = chain_end.get("data", {}).get("output", {}).get("messages", [])
        (
            model_output,
            tool_call_iterations,
            parsed_input_tokens,
            parsed_output_tokens,
        ) = _parse_messages_for_output_and_tool_calls(messages)

        if "structured_response" in chain_end["data"]["output"].keys():
            model_output = chain_end["data"]["output"]["structured_response"]

        # Prefer callback totals if available (covers multi-step agent runs reliably).
        cb_totals = _aggregate_token_usage_from_callback(usage_cb)
        if cb_totals is not None:
            input_tokens, output_tokens = cb_totals
        else:
            input_tokens = parsed_input_tokens
            output_tokens = parsed_output_tokens

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
        if pd.isna(prompt):
            print("Empty prompt. Skipping.")
            continue
        test_path = f"{tests_module}.{row['test']}"
        ifc_path = ifc_dir / row["ifc-file"]

        # load the structured output python object
        if not pd.isna(row["structured-output"]):
            structured_output = f"{structured_outputs_module}.{row['structured-output']}"
            output_object = importlib.import_module(structured_output).ModelOutput
        else:
            output_object = None

        # crud = row["CRUD"]
        
        # if crud != "retrieve":
        
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
            try:
                metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)
            except Exception as exc:
                print(f"Error executing test for question {question_id}, sample {sample}: {exc}")
                metrics = {}

            # store results for a sample
            sample_cache_object = {
                "sample": sample + 1,
                "model_output": model_output,
                "tool_call_iterations": result_state["tool_call_iterations"],
                "metrics": metrics, # dictionary of metrics
                "score": sum(metrics.values())/len(metrics) if metrics else 0, # score = fulfilled metrics / all metrics
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
