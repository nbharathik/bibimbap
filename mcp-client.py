"""Simple script to run the IFC MCP benchmark.

Usage:
  python mcp-client.py --config configs/benchmark.config.json [--only-llm]

How it works:
  Loads a benchmark config, prepares questions, connects to IFC Bonsai MCP server
  (use the 'benchmark-v1' branch of the MCP server), runs an LLM agent per question, 
  and stores results in a run directory.
  
  Check how to use IFC Bonsai MCP here (https://github.com/Show2Instruct/ifc-bonsai-mcp)
  Quick setup: Create a zip file for blender_addon, import into Blender addon in the plugin tab
    click connect to MCP server. You are now run this benchmark.

Args:
  --config: path to JSON config (default: configs/benchmark.config.json)
  --only-llm: skip evaluation step
"""

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
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception: 
    get_usage_metadata_callback = None

# Tool group definitions used to map CRUD operations to allowed MCP tool names
TOOL_GROUPS_CONFIG = {
    "tool_groups": {
        "ANALYSIS_SCREENSHOTS": [
            "capture_blender_window_screenshot",
            "capture_blender_3dviewport_screenshot",
        ],
        "INSPECT_SCENE": [
            "get_scene_info",
            "get_ifc_scene_overview",
        ],
        "INSPECT_OBJECTS": [
            "get_selected_objects",
            "get_object_info",
            "get_blender_object_info",
        ],
        "FILE_OPERATIONS": [
            "load_ifc_file",
            "load_ifc_from_json",
        ],
        "DISCOVER_COMMANDS": [
            "list_blender_commands",
        ],
        "LOOKUP_TYPES_OPTIONS": [
            "get_roof_types",
            "get_stairs_types",
            "get_door_operation_types",
            "get_window_partition_types",
        ],
        "STYLES_READ": [
            "list_styles",
        ],
        "STYLES_WRITE": [
            "create_surface_style",
            "create_pbr_style",
            "apply_style_to_object",
            "update_style",
            "remove_style",
        ],
        "MESH_HELPERS": [
            "list_ifc_entities",
            "get_trimesh_examples",
        ],
        "CODE_EXEC": [
            "execute_blender_code",
            "execute_ifc_code_tool",
        ],
        "CREATE_ELEMENTS": [
            "create_wall",
            "create_two_point_wall",
            "create_polyline_walls",
            "create_roof",
            "create_slab",
            "create_door",
            "create_window",
            "create_stairs",
            "create_trimesh_ifc",
            "create_mesh_ifc",
        ],
        "UPDATE_ELEMENTS": [
            "update_wall",
            "update_roof",
            "update_slab",
            "update_door",
            "update_window",
            "update_stairs",
        ],
        "DELETE_ELEMENTS": [
            "delete_roof",
            "delete_stairs",
        ],
        "GET_PROPERTIES": [
            "get_wall_properties",
            "get_slab_properties",
            "get_door_properties",
            "get_window_properties",
            "get_roof_properties",
            "get_stairs_properties",
        ],
        "RAG_ANY": [
            "ensure_ifc_knowledge_ready",
            "search_ifc_knowledge",
            "get_ifc_knowledge_status",
            "find_ifc_function",
            "get_ifc_module_info",
            "get_ifc_function_details",
            "clear_ifc_knowledge_cache",
            "get_cache_statistics",
        ],
    },
    "crud_operations": {
        "create": [
            "INSPECT_SCENE",
            "INSPECT_OBJECTS",
            "LOOKUP_TYPES_OPTIONS",
            "MESH_HELPERS",
            "CREATE_ELEMENTS",
            "STYLES_WRITE",
            "ANALYSIS_SCREENSHOTS",
            "CODE_EXEC",
            "RAG_ANY",
        ],
        "update": [
            "INSPECT_SCENE",
            "INSPECT_OBJECTS",
            "GET_PROPERTIES",
            "UPDATE_ELEMENTS",
            "ANALYSIS_SCREENSHOTS",
            "CODE_EXEC",
            "RAG_ANY",
            {
                "inline_tools": [
                    "apply_style_to_object",
                    "update_style",
                ],
            },
        ],
        "retrieve": [
            "ANALYSIS_SCREENSHOTS",
            "INSPECT_SCENE",
            "INSPECT_OBJECTS",
            "FILE_OPERATIONS",
            "DISCOVER_COMMANDS",
            "LOOKUP_TYPES_OPTIONS",
            "STYLES_READ",
            "MESH_HELPERS",
            "GET_PROPERTIES",
            "CODE_EXEC",
            "RAG_ANY",
        ],
        "delete": [
            "INSPECT_SCENE",
            "INSPECT_OBJECTS",
            "DELETE_ELEMENTS",
            "ANALYSIS_SCREENSHOTS",
            "CODE_EXEC",
            "RAG_ANY",
            {
                "inline_tools": [
                    "remove_style",
                ],
            },
        ],
    },
}

# Load and normalize tool groups config
def load_tool_groups(config_source) -> dict:
    try:
        if isinstance(config_source, Mapping):
            config = config_source
        else:
            config_path = Path(config_source)
            with config_path.open("r", encoding="utf-8") as f:
                config = json.load(f)
        
        tool_groups = config["tool_groups"]
        crud_ops = config["crud_operations"]
        
        result = {}
        for crud_type, components in crud_ops.items():
            tools = []
            for component in components:
                if isinstance(component, dict) and "inline_tools" in component:
                    tools.extend(component["inline_tools"])
                elif isinstance(component, str) and component in tool_groups:
                    tools.extend(tool_groups[component])
            result[crud_type] = tools
        
        return result
    except Exception as e:
        print(f"Warning: Failed to load tool groups config: {e}")
        print("Using all available tools as fallback.")
        return {}

# Typed dict representing the per-invocation state passed to the agent
class State(TypedDict):
    prompt: str
    structured_output: object
    ifc_file_path: str
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_call_iterations: List[dict]
    recursion_error: bool
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

# Return suffix part of a model identifier (after ':')
def model_suffix(model_name: str) -> str:
    return model_name.split(":")[-1]

# Guidance passed to the agent about preferred tools and behavior
TOOL_GUIDANCE = (
    "Use the tool `execute_ifc_code_tool` for IFC inspection or calculations when possible. "
    "Use other IFC/MCP tools only if they are the best fit for the task. "
    "Avoid repeated tool calls with the same query. "
    "When you have enough information, stop and return the final answer."
)

# Detect recursion-related exceptions for special handling
def _is_recursion_error(exc: BaseException) -> bool:
    if isinstance(exc, RecursionError):
        return True
    exc_name = type(exc).__name__.lower()
    if "recursion" in exc_name:
        return True
    return "recursion" in str(exc).lower()

# Phrases considered non-fatal vs fatal connection failure hints
_CONNECTIVITY_NON_FATAL = (
    "no ifc file loaded",
    "no objects selected",
)

_CONNECTIVITY_FAILURE_HINTS = (
    "could not connect",
    "not connected",
    "not connect",
    "failed to connect",
    "connection refused",
    "connection to blender lost",
    "connection error",
    "communication error",
    "socket timeout",
    "socket error",
    "timed out",
    "timeout while",
    "no module named 'bonsai'",
    'no module named "bonsai"',
)

# Try to parse a string as JSON, return None if not JSON
def _parse_json_if_possible(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None

# Iterate over nested structures yielding all strings
def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _iter_strings(item)

# Check nested payloads for explicit error indicators
def _payload_has_error(payload) -> bool:
    if isinstance(payload, Mapping):
        if payload.get("error") or payload.get("errors"):
            return True
        status = payload.get("status")
        if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
            return True
        success = payload.get("success")
        if success is False:
            return True
        return any(_payload_has_error(v) for v in payload.values())
    if isinstance(payload, (list, tuple, set)):
        return any(_payload_has_error(v) for v in payload)
    return False

# Heuristic to decide if a probe result indicates a connection failure
def _probe_result_indicates_failure(result) -> bool:
    if result is None:
        return True
    parsed = None
    if isinstance(result, str):
        parsed = _parse_json_if_possible(result.strip())
    payload = parsed if parsed is not None else result

    strings = [s.lower() for s in _iter_strings(payload)]
    has_nonfatal = any(
        phrase in text for text in strings for phrase in _CONNECTIVITY_NON_FATAL
    )

    if _payload_has_error(payload) and not has_nonfatal:
        return True

    if not has_nonfatal and any(
        phrase in text for text in strings for phrase in _CONNECTIVITY_FAILURE_HINTS
    ):
        return True

    return False


# Probe MCP server to ensure Blender connectivity and fail early if needed
async def ensure_blender_connectivity(mcp_tools, probe_names=None, context_label="") -> None:
    probe_names = probe_names or [
        "list_blender_commands",
        "get_scene_info",
        "get_selected_objects",
        "get_ifc_scene_overview",
    ]
    probe_tool = None
    for name in probe_names:
        probe_tool = next(
            (
                tool
                for tool in mcp_tools
                if tool.name == name or tool.name.endswith(name)
            ),
            None,
        )
        if probe_tool is not None:
            break

    if probe_tool is None:
        msg = "No probe tool found to check Blender MCP connectivity. Aborting."
        raise SystemExit(msg)

    try:
        result = await probe_tool.ainvoke({})
    except Exception as exc:
        label = f" ({context_label})" if context_label else ""
        msg = f"Failed to reach Blender MCP server{label}: {exc}"
        print("connect False")
        raise SystemExit(msg)

    if _probe_result_indicates_failure(result):
        label = f" ({context_label})" if context_label else ""
        msg = f"Probe output suggests connection failure{label}: {result}"
        print("connect False")
        raise SystemExit(msg)


async def main():
    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(description="Run the IFC MCP benchmark.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to the benchmark config JSON file.",
    )
    parser.add_argument(
        "--only-llm",
        action="store_true",
        help="Skip evaluation and only run the LLM pipeline.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    TOOL_GROUPS = load_tool_groups(TOOL_GROUPS_CONFIG)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)
    evaluate = not args.only_llm

    base_dir = repo_root
    config_dir = config_path.parent

    env_path = config_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    questions_val = config["questions_csv"]
    f_list = questions_val if isinstance(questions_val, list) else [questions_val]
    if not f_list:
        raise SystemExit("Config 'questions_csv' must be a path or a non-empty list of paths.")
    
    questions_list = []
    for f in f_list:
        csv_path = resolve_path(base_dir, f)
        df = pd.read_csv(csv_path)
        df['source_csv'] = Path(f).name  
        questions_list.append(df)
    
    questions = pd.concat(questions_list, ignore_index=True)

    num_samples = config["num_samples"]
    model_name = config["model_name"]
    model = init_chat_model(model_name)

    try:
        if "openai" in model_name.lower():
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
        pass
    system_prompt = config["system_prompt"]

    paths_config = config["paths"]
    ifc_dir = resolve_path(base_dir, paths_config["ifc_dir"])
    tests_module = paths_config["tests_module"]
    structured_outputs_module = paths_config["structured_outputs_module"]
    results_dir = resolve_path(base_dir, paths_config["results_dir"])
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

    client = MultiServerMCPClient(config["mcp_servers"])
    mcp_tools = await client.get_tools()

    try:
        await ensure_blender_connectivity(mcp_tools, context_label="startup")
    except SystemExit:
        raise SystemExit("MCP Plugin not reachable")

    load_ifc_tool = next(
        (
            tool
            for tool in mcp_tools
            if tool.name == "load_ifc_file" or tool.name.endswith("load_ifc_file")
        ),
        None,
    )

    async def preload_ifc_in_blender(ifc_file_path: str) -> None:
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
            print(f"Warning: Failed to preload IFC via MCP tool: {exc}")

    async def call_model(state: State):
        prompt = state["prompt"]
        ifc_file_path = state["ifc_file_path"]
        structured_output = state["structured_output"]
        filtered_tools = state.get("filtered_tools", mcp_tools)

        await ensure_blender_connectivity(mcp_tools)

        await preload_ifc_in_blender(ifc_file_path)

        if structured_output:
            agent = create_agent(model, filtered_tools, response_format=ToolStrategy(structured_output))
        else:
            agent = create_agent(model, filtered_tools)

        if load_ifc_tool is None:
            user_content = (
                f"{prompt}\nThe ifc file path is {ifc_file_path}.\n\n{TOOL_GUIDANCE}"
            )
        else:
            user_content = (
                f"{prompt}\n(The IFC file is already loaded in Blender.)\n\n{TOOL_GUIDANCE}"
            )

        usage_cb_cm = None
        usage_cb = None
        if get_usage_metadata_callback is not None:
            try:
                usage_cb_cm = get_usage_metadata_callback()
                usage_cb = usage_cb_cm.__enter__()
            except Exception:
                usage_cb_cm = None
                usage_cb = None

        class _ErrorModelOutput:
            def __init__(self, text: str):
                self.error = text
                self.raw_model_response = text

        chain = []
        caught_error = None
        try:
            async for event in agent.astream_events(
                {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ]
                },
                config={"callbacks": [usage_cb]} if usage_cb is not None else None,
            ):
                chain.append(event)
        except Exception as exc:
            caught_error = exc
        finally:
            if usage_cb_cm is not None:
                usage_cb_cm.__exit__(None, None, None)

        def _extract_token_usage_from_message(msg) -> tuple[int, int]:
            usage = getattr(msg, "usage_metadata", None) or {}
            if isinstance(usage, Mapping) and usage:
                in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                return int(in_tok or 0), int(out_tok or 0)

            rm = getattr(msg, "response_metadata", None) or {}
            if isinstance(rm, Mapping) and rm:
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

        def _extract_messages_from_chain(events: list) -> list:
            for event in reversed(events or []):
                if isinstance(event, dict):
                    messages = event.get("data", {}).get("output", {}).get("messages")
                    if messages is not None:
                        return messages
            return []

        def _extract_structured_response_from_chain(events: list):
            for event in reversed(events or []):
                if isinstance(event, dict):
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict) and "structured_response" in output:
                        return output.get("structured_response")
            return None

        def _parse_messages_for_output_and_tool_calls(msgs) -> tuple[str, list[dict], int, int]:
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

                if tool_calls or finish_reason == "tool_calls":
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

        messages = _extract_messages_from_chain(chain)
        (
            model_output,
            tool_call_iterations,
            parsed_input_tokens,
            parsed_output_tokens,
        ) = _parse_messages_for_output_and_tool_calls(messages)

        structured_response = _extract_structured_response_from_chain(chain)
        if structured_response is not None:
            model_output = structured_response

        cb_totals = _aggregate_token_usage_from_callback(usage_cb)
        if cb_totals is not None:
            input_tokens, output_tokens = cb_totals
        else:
            input_tokens = parsed_input_tokens
            output_tokens = parsed_output_tokens

        if caught_error is not None:
            err_text = f"ERROR during agent/tool run: {caught_error}"
            if structured_output:
                model_output = _ErrorModelOutput(err_text)
            else:
                model_output = f"{prompt}\n\n---AGENT ERROR---\n{err_text}"
            return {
                "model_output": model_output,
                "tool_call_iterations": tool_call_iterations,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "recursion_error": _is_recursion_error(caught_error),
                "error": str(caught_error),
            }

        return {
            "model_output": model_output,
            "tool_call_iterations": tool_call_iterations,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "recursion_error": False,
        }


    cache = {}
    
    cache_source = config.get("cache_source")
    cache_source_path = None
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

    if cache_source_path and cache_source_path.exists():
        source_run_dir = cache_source_path.parent
        for edited_dir in source_run_dir.glob("edited_ifc_*"):
            if not edited_dir.is_dir():
                continue
            dest_dir = run_dir / edited_dir.name
            try:
                shutil.copytree(edited_dir, dest_dir, dirs_exist_ok=True)
            except Exception as exc:
                print(f"Warning: Failed to copy {edited_dir} to {dest_dir}: {exc}")

    builder = StateGraph(State)
    builder.add_node("call_model", call_model)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)

    graph = builder.compile()

# Simple state graph: START -> call_model -> END

    for index, row in questions.iterrows():
        print(f"Processing question {int(str(index))+1} of {len(questions)}...")
        question_id = int(str(index))

        await ensure_blender_connectivity(mcp_tools, context_label=f"question {question_id+1}")

        cache_key = str(question_id)
        if cache_key in cache:
            print("Question already in cache. Using cached result.")
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
        if not pd.isna(row["CRUD"]):
            crud_value = str(row["CRUD"]).strip().lower()
        is_retrieve = crud_value == "retrieve"

        # Filter MCP tools by the allowed tool names for the configured CRUD operation
        allowed_tool_names = TOOL_GROUPS.get(crud_value, [])
        filtered_tools = [t for t in mcp_tools if any(t.name.endswith(name) for name in allowed_tool_names)] if allowed_tool_names else mcp_tools

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
                shutil.copyfile(ifc_path, edited_ifc_path)

            model_args = {
                "prompt": prompt,
                "structured_output": output_object,
                "ifc_file_path": str(edited_ifc_path.resolve()),
                "filtered_tools": filtered_tools,
            }

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

            if output_object:
                model_output = result_state["model_output"].__dict__
            else:
                model_output = result_state["model_output"]

            metrics = None
            score = None
            if evaluate:
                test = importlib.import_module(test_path)
                try:
                    metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)
                except Exception as exc:
                    print(f"Error executing test for question {question_id}, sample {sample}: {exc}")
                    metrics = {}
                score = sum(metrics.values()) / len(metrics) if metrics else 0

            sample_cache_object = {
                "sample": sample + 1,
                "model_output": model_output,
                "tool_call_iterations": result_state["tool_call_iterations"],
                "metrics": metrics,
                "score": score,
                "input_tokens": result_state["input_tokens"],
                "output_tokens": result_state["output_tokens"]
            }
            sample_results.append(sample_cache_object)

        cache_object = {
            "question_id": question_id,
            "prompt": prompt,
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "source_csv": row.get("source_csv", "unknown"),
            "crud_operation": crud_value,
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        }

        cache[cache_key] = cache_object

        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)


if __name__ == "__main__":
    asyncio.run(main())
