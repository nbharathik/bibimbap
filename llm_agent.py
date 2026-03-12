"""Run the IFC benchmark with a local tool-based code generation LLM agent.

Usage:
  python llm_agent.py [--config CONFIG] [--run-name NAME] [--resume-run DIR]
                      [--start-index N] [--tool-timeout S] [--force-subprocess]
                      [--verbose] [--sample-timeout S] [--quiet] [--llm-only]

Example:
    python llm_agent.py --config configs/benchmark.config.json --force-subprocess 
    # other arguments are options, always use --force-subprocess

Options:
    --config CONFIG         Path to JSON config (default: configs/benchmark.config.json)
    --run-name NAME         Suffix for new run folder
    --resume-run DIR        Resume from existing run directory
    --start-index N         Start at this question number (default: 1)
    --tool-timeout S        Subprocess tool timeout (default: 45s)
    --force-subprocess      Force subprocess for all tool calls
    --verbose               Verbose logging
    --sample-timeout S      Timeout for a single sample (default: 300s)
    --quiet                 Only print warnings/errors
    --llm-only              Run LLM only, skip tests/metrics

Notes:
    Use --force-subprocess for risky operations (e.g., geometry) to avoid crashes/timeouts.
"""
import argparse
import ast
import asyncio
import contextlib
import io
import inspect
import json
import os
import site
import sys
import time
import traceback
from collections.abc import Mapping
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from typing import ClassVar, List, Tuple, TypedDict

import importlib
import pandas as pd
import shutil
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END

import subprocess
import tempfile
import textwrap

try:
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception:  # pragma: no cover
    get_usage_metadata_callback = None


LOG_LEVEL = "info"
LOG_DEBUG = False


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    if LOG_LEVEL == "error":
        return
    print(f"[{ts()}] {msg}", flush=True)


def log_error(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def log_debug(msg: str) -> None:
    if not LOG_DEBUG:
        return
    print(f"[{ts()}] {msg}", flush=True)


async def heartbeat(label: str, every_s: int = 10):
    """Print a heartbeat periodically so 'silent waits' are visible."""
    i = 0
    try:
        while True:
            await asyncio.sleep(every_s)
            i += 1
            log_debug(f"... still running ({label}) +{i*every_s}s")
    except asyncio.CancelledError:
        return


def strip_user_site() -> None:
    if os.environ.get("IFC_BENCHMARK_ALLOW_USER_SITE") == "1":
        return
    user_site = site.getusersitepackages()
    user_sites = [user_site] if isinstance(user_site, str) else list(user_site or [])
    for path in user_sites:
        if path in sys.path:
            sys.path.remove(path)


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


def safe_jsonable(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _is_recursion_error(exc: BaseException) -> bool:
    if isinstance(exc, RecursionError):
        return True
    exc_name = type(exc).__name__.lower()
    if "recursion" in exc_name:
        return True
    return "recursion" in str(exc).lower()


class QuotaExceededError(RuntimeError):
    pass


def _is_quota_error(exc: BaseException) -> bool:
    patterns = (
        "insufficient_quota",
        "insufficient quota",
        "quota exceeded",
        "quota_exceeded",
        "exceeded your current quota",
        "resource_exhausted",
    )
    checked = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in checked:
        checked.add(id(current))
        msg = str(current).lower()
        if any(p in msg for p in patterns):
            return True
        code = getattr(current, "code", None)
        if code and "quota" in str(code).lower():
            return True
        status = getattr(current, "status_code", None) or getattr(current, "status", None)
        if status in (402, 429) and "quota" in msg:
            return True
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


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


VERBOSE_TOOL_LOGS = False
VERBOSE_MAX_CHARS = 800


def _truncate(x, n: int = VERBOSE_MAX_CHARS) -> str:
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + " ... <truncated>"


def log_event(event: dict) -> None:
    if not VERBOSE_TOOL_LOGS:
        return

    etype = event.get("event")
    name = event.get("name")
    data = event.get("data", {}) or {}

    if etype == "on_tool_start":
        tool_input = data.get("input") or data.get("inputs") or {}
        print(f"\n[TOOL START] {name}\n  input={_truncate(tool_input)}\n")

    elif etype == "on_tool_end":
        tool_output = data.get("output") or data.get("result") or {}
        print(f"\n[TOOL END] {name}\n  output={_truncate(tool_output)}\n")

    elif etype == "on_tool_error":
        err = data.get("error") or data.get("exception") or data
        print(f"\n[TOOL ERROR] {name}\n  error={_truncate(err)}\n")

    elif etype in ("on_chat_model_start", "on_llm_start"):
        print(f"\n[MODEL START] {name or ''}".strip() + "\n")

    elif etype in ("on_chat_model_end", "on_llm_end"):
        print(f"\n[MODEL END] {name or ''}".strip() + "\n")


def _parse_tool_end_output(event: dict) -> dict | None:
    """Extract tool output dict from LangChain event, best-effort."""
    try:
        data = event.get("data", {}) or {}
        tool_output = data.get("output") or data.get("result")
        if isinstance(tool_output, dict):
            return tool_output
        content = getattr(tool_output, "content", None)
        if isinstance(content, str):
            s = content.strip()
            if s.startswith("{") and s.endswith("}"):
                return json.loads(s)
    except Exception:
        return None
    return None


class ExecuteIFCCodeTool(BaseTool):
    """
    Hybrid execution:
      - Fast path: in-process exec for typical query/modify code.
      - Safe path: subprocess exec for risky geometry/shape code, with timeout.
    """

    name: str = "execute_ifc_code"
    description: str = (
        "Execute Python code using ifcopenshell on a given IFC file. "
        "Inputs: {code: str, ifc_file_path: str}. "
        "The tool loads the IFC as variable `ifc`, provides `commit()` to save, "
        "and you can set `result` to return a value."
    )

    timeout_seconds: int = 45
    force_subprocess: bool = False
    default_ifc_file_path: str | None = None
    read_only: bool = False

    RISKY_MARKERS: ClassVar[Tuple[str, ...]] = (
        "ifcopenshell.geom",
        "create_shape",
        "ifcopenshell.util.shape",
        ".geom.settings",
        "USE_WORLD_COORDS",
        "ifcopenshell.geom.settings",
    )

    def _looks_risky(self, code: str) -> bool:
        c = code or ""
        return any(m in c for m in self.RISKY_MARKERS)

    def _run_in_process(self, code: str, ifc_file_path: str, read_only: bool = False) -> dict:
        try:
            import ifcopenshell  # type: ignore
        except Exception as exc:
            return {
                "status": "error",
                "error": f"Failed to import ifcopenshell: {exc}",
                "traceback": traceback.format_exc(),
                "stdout": "",
                "stderr": "",
                "result": None,
                "backend": "in_process",
            }

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        try:
            ifc = ifcopenshell.open(ifc_file_path)

            def commit(path: str | None = None):
                if read_only:
                    return path or ifc_file_path
                target = path or ifc_file_path
                ifc.write(target)
                return target

            if read_only:
                try:
                    def _blocked_write(path: str | None = None):
                        return path or ifc_file_path

                    ifc.write = _blocked_write  # type: ignore[assignment]
                except Exception:
                    pass

            api = util = guid = element_util = None
            try:
                import ifcopenshell.api as api  # type: ignore
            except Exception:
                api = None
            try:
                import ifcopenshell.util as util  # type: ignore
            except Exception:
                util = None
            try:
                import ifcopenshell.guid as guid  # type: ignore
            except Exception:
                guid = None
            try:
                import ifcopenshell.util.element as element_util  # type: ignore
            except Exception:
                element_util = None

            env = {
                "__builtins__": __builtins__,
                "ifcopenshell": ifcopenshell,
                "ifc": ifc,
                "ifc_file_path": ifc_file_path,
                "commit": commit,
                "api": api,
                "util": util,
                "guid": guid,
                "element_util": element_util,
            }

            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, env, env)

            return {
                "status": "ok",
                "result": safe_jsonable(env.get("result", None)),
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "backend": "in_process",
            }

        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "result": None,
                "backend": "in_process",
            }

    def _run_subprocess(self, code: str, ifc_file_path: str, read_only: bool = False) -> dict:
        # Inline runner executed in a subprocess for isolation and timeouts.
        runner = textwrap.dedent(
            r"""
            import json, io, traceback
            from contextlib import redirect_stdout, redirect_stderr

            def safe_jsonable(v):
                try:
                    json.dumps(v)
                    return v
                except Exception:
                    return str(v)

            payload = json.loads(open(__PAYLOAD_PATH__, "r", encoding="utf-8").read())
            code = payload["code"]
            ifc_file_path = payload["ifc_file_path"]
            read_only = bool(payload.get("read_only"))

            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()

            try:
                import ifcopenshell
            except Exception as exc:
                out = {
                    "status": "error",
                    "error": f"Failed to import ifcopenshell: {exc}",
                    "traceback": traceback.format_exc(),
                    "stdout": "",
                    "stderr": "",
                    "result": None,
                    "backend": "subprocess",
                }
                print(json.dumps(out))
                raise SystemExit(0)

            try:
                ifc = ifcopenshell.open(ifc_file_path)

                def commit(path=None):
                    if read_only:
                        return path or ifc_file_path
                    target = path or ifc_file_path
                    ifc.write(target)
                    return target

                if read_only:
                    try:
                        def _blocked_write(path=None):
                            return path or ifc_file_path

                        ifc.write = _blocked_write
                    except Exception:
                        pass

                api = util = guid = element_util = None
                try:
                    import ifcopenshell.api as api
                except Exception:
                    api = None
                try:
                    import ifcopenshell.util as util
                except Exception:
                    util = None
                try:
                    import ifcopenshell.guid as guid
                except Exception:
                    guid = None
                try:
                    import ifcopenshell.util.element as element_util
                except Exception:
                    element_util = None

                env = {
                    "__builtins__": __builtins__,
                    "ifcopenshell": ifcopenshell,
                    "ifc": ifc,
                    "ifc_file_path": ifc_file_path,
                    "commit": commit,
                    "api": api,
                    "util": util,
                    "guid": guid,
                    "element_util": element_util,
                }

                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    exec(code, env, env)

                out = {
                    "status": "ok",
                    "result": safe_jsonable(env.get("result", None)),
                    "stdout": stdout_buf.getvalue(),
                    "stderr": stderr_buf.getvalue(),
                    "backend": "subprocess",
                }
                print(json.dumps(out))
            except Exception as exc:
                out = {
                    "status": "error",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "stdout": stdout_buf.getvalue(),
                    "stderr": stderr_buf.getvalue(),
                    "result": None,
                    "backend": "subprocess",
                }
                print(json.dumps(out))
            """
        ).strip()

        with tempfile.TemporaryDirectory() as td:
            payload_path = Path(td) / "payload.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "code": code,
                        "ifc_file_path": ifc_file_path,
                        "read_only": bool(read_only),
                    }
                ),
                encoding="utf-8",
            )
            runner_code = runner.replace("__PAYLOAD_PATH__", repr(str(payload_path)))

            try:
                proc = subprocess.run(
                    [sys.executable, "-s", "-c", runner_code],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                log_error(
                    f"TOOL execute_ifc_code subprocess TIMEOUT after {self.timeout_seconds}s"
                )
                return {
                    "status": "error",
                    "error": "SUBPROCESS_TIMEOUT",
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                    "result": None,
                    "backend": "subprocess",
                }

            if proc.returncode != 0:
                return {
                    "status": "error",
                    "error": "SUBPROCESS_CRASH",
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                    "backend": "subprocess",
                }

            out = (proc.stdout or "").strip()
            if not out:
                return {
                    "status": "error",
                    "error": "EMPTY_SUBPROCESS_OUTPUT",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                    "backend": "subprocess",
                }

            try:
                return json.loads(out)
            except Exception:
                return {
                    "status": "error",
                    "error": "INVALID_SUBPROCESS_JSON",
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "result": None,
                    "backend": "subprocess",
                }

    def _run(self, code: str, ifc_file_path: str | None = None) -> dict:
        ifc_path = ifc_file_path or self.default_ifc_file_path
        if not ifc_path:
            return {
                "status": "error",
                "error": "Missing ifc_file_path",
                "traceback": "",
                "stdout": "",
                "stderr": "",
                "result": None,
                "backend": "in_process",
            }
        started = time.time()
        read_only = bool(self.read_only)
        force = self.force_subprocess or os.environ.get("IFC_BENCHMARK_FORCE_SUBPROCESS") == "1"
        risky = self._looks_risky(code)
        backend = "subprocess" if (force or risky) else "in_process"

        log_debug(
            f"TOOL execute_ifc_code start backend={backend} risky={risky} "
            f"ifc={Path(ifc_path).name}"
        )

        try:
            out = (
                self._run_subprocess(code, ifc_path, read_only=read_only)
                if backend == "subprocess"
                else self._run_in_process(code, ifc_path, read_only=read_only)
            )
        except Exception as exc:
            log_error(f"TOOL execute_ifc_code exception after {time.time()-started:.1f}s: {exc}")
            raise

        dur = time.time() - started
        status = out.get("status")
        err = out.get("error")
        log_debug(f"TOOL execute_ifc_code end status={status} dur={dur:.1f}s error={err}")

        if err in ("SUBPROCESS_TIMEOUT", "SUBPROCESS_CRASH", "INVALID_SUBPROCESS_JSON", "EMPTY_SUBPROCESS_OUTPUT"):
            so = (out.get("stdout") or "")[:800]
            se = (out.get("stderr") or "")[:800]
            log_debug(f"TOOL execute_ifc_code diagnostic stdout[:800]={so!r}")
            log_debug(f"TOOL execute_ifc_code diagnostic stderr[:800]={se!r}")

        return out

    async def _arun(self, code: str, ifc_file_path: str | None = None) -> dict:
        return await asyncio.to_thread(self._run, code=code, ifc_file_path=ifc_file_path)


class State(TypedDict):
    prompt: str
    structured_output: object
    ifc_file_path: str
    read_only: bool
    model_output: str
    input_tokens: int
    output_tokens: int
    tool_call_iterations: List[dict]
    recursion_error: bool
    filtered_tools: list


async def main():
    global VERBOSE_TOOL_LOGS, LOG_LEVEL, LOG_DEBUG

    strip_user_site()

    default_config = Path(__file__).resolve().parent / "configs" / "benchmark.config.json"
    parser = argparse.ArgumentParser(
        description="Run the IFC benchmark with a local LLM tool (no MCP)."
    )
    parser.add_argument("--config", default=str(default_config))
    parser.add_argument("--run-name", default="", help="Suffix for new run folder.")
    parser.add_argument("--resume-run", default="", help="Path to existing run dir.")
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="Start at this question number (1-based). Default: 1.",
    )
    parser.add_argument(
        "--tool-timeout",
        type=int,
        default=45,
        help="Timeout in seconds for subprocess tool executions (default: 45).",
    )
    parser.add_argument(
        "--force-subprocess",
        action="store_true",
        help="Force subprocess for ALL tool calls (safest, slowest).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose tool/model logging (slower).",
    )
    parser.add_argument(
        "--sample-timeout",
        type=int,
        default=300,
        help="Hard timeout in seconds for a single sample (default: 300).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print warnings/errors.",
    )
    parser.add_argument(
        "--llm-only",
        action="store_true",
        help="Run LLM only and skip tests/metrics (evaluate later with evaluate_cache.py).",
    )
    args = parser.parse_args()

    VERBOSE_TOOL_LOGS = bool(args.verbose)
    llm_only = bool(args.llm_only)
    LOG_DEBUG = bool(args.verbose) and not bool(args.quiet)
    LOG_LEVEL = "error" if args.quiet else "info"

    repo_root = Path(__file__).resolve().parent

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    config = load_config(config_path)

    base_dir = repo_root
    config_dir = config_path.parent

    env_path = config_dir / ".env"
    load_dotenv(dotenv_path=env_path) if env_path.exists() else load_dotenv()

    questions_val = config["questions_csv"]
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

    resume_run = (args.resume_run or "").strip()
    if resume_run:
        run_dir = Path(resume_run).expanduser().resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        log(f"Resuming run in: {run_dir}")
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
        log(f"Result for this run will be stored in: {run_dir}")
        with (run_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    results_config = config["results"]
    model_suffix_value = model_suffix(model_name)

    cache_filename = results_config["cache_filename_template"].format(
        model_suffix=model_suffix_value
    )
    cache_path = run_dir / cache_filename

    cache: dict = {}
    if cache_path.exists():
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                cache = json.load(f)
            log(f"Loaded existing cache from: {cache_path}")
            log(f"Cache contains {len(cache)} entries.")
        except Exception as e:
            log_error(f"Warning: Failed to load existing cache {cache_path}: {e}")
            log_error("Starting with empty cache.")
    else:
        cache_source = config.get("cache_source")
        if cache_source:
            cache_source_path = resolve_path(base_dir, cache_source)
            if cache_source_path.exists():
                try:
                    with cache_source_path.open("r", encoding="utf-8") as cache_file:
                        cache = json.load(cache_file)
                    log(f"Loaded existing cache from: {cache_source_path}")
                    log(f"Cache contains {len(cache)} entries.")
                except Exception as e:
                    log_error(f"Warning: Failed to load cache source {cache_source_path}: {e}")
                    log_error("Starting with empty cache.")
            else:
                log_error(f"Warning: Cache source file not found: {cache_source_path}")
                log_error("Starting with empty cache.")
        else:
            log_debug("No cache source specified. Starting with empty cache.")

    edited_ifc_dirname = results_config["edited_ifc_dir_template"].format(
        model_suffix=model_suffix_value
    )
    edited_ifc_directory = run_dir / edited_ifc_dirname
    edited_ifc_directory.mkdir(parents=True, exist_ok=True)

    execute_ifc_tool = ExecuteIFCCodeTool(
        timeout_seconds=int(args.tool_timeout),
        force_subprocess=bool(args.force_subprocess),
    )
    tools = [execute_ifc_tool]

    async def call_model(state: State):
        prompt = state["prompt"]
        ifc_file_path = state["ifc_file_path"]
        structured_output = state["structured_output"]
        filtered_tools = state.get("filtered_tools", tools)
        read_only = bool(state.get("read_only", False))

        for tool in filtered_tools:
            if isinstance(tool, ExecuteIFCCodeTool):
                tool.default_ifc_file_path = ifc_file_path
                tool.read_only = read_only

        agent = (
            create_agent(model, filtered_tools, response_format=ToolStrategy(structured_output))
            if structured_output
            else create_agent(model, filtered_tools)
        )

        class _ErrorModelOutput:
            def __init__(self, text: str):
                self.error = text
                self.raw = text

        user_content = (
            f"{prompt}\n\n"
            f"Use the tool `execute_ifc_code` to run ifcopenshell code.\n"
            f"The current IFC file path is:\n{ifc_file_path}\n\n"
            f"Rules:\n"
            f"- Avoid numpy.\n"
            f"- Avoid ifcopenshell.geom / create_shape unless absolutely necessary.\n"
            f"- The tool loads the IFC as variable `ifc`.\n"
            f"- Set a variable `result` to return data.\n"
            f"- Call `commit()` to save modifications back to the same path.\n"
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

        log_debug(
            f"MODEL start ifc={Path(ifc_file_path).name} "
            f"tools={len(filtered_tools)} structured={bool(structured_output)}"
        )
        hb = asyncio.create_task(heartbeat("model_stream", every_s=10))
        got_stream = False
        tool_calls_seen = 0
        tool_call_fallback: list[dict] = []

        def _extract_token_usage_from_message(msg) -> tuple[int, int]:
            usage = getattr(msg, "usage_metadata", None) or {}
            if isinstance(usage, Mapping) and usage:
                in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                return int(in_tok or 0), int(out_tok or 0)

            rm = getattr(msg, "response_metadata", None) or {}
            if isinstance(rm, Mapping) and rm:
                if any(k in rm for k in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")):
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

        def _parse_messages_for_output_and_tool_calls(msgs) -> tuple[str, list[dict], int, int]:
            model_out = ""
            parsed_in = parsed_out = 0
            iterations: list[dict] = []

            def normalize_finish_reason(message) -> str | None:
                rm = getattr(message, "response_metadata", None) or {}
                raw = None
                if isinstance(rm, Mapping):
                    raw = rm.get("finish_reason") or rm.get("stop_reason")
                if raw is None:
                    raw = getattr(message, "finish_reason", None)
                if raw is None:
                    return None
                return str(raw).lower()

            for message in msgs or []:
                msg_input_tokens, msg_output_tokens = _extract_token_usage_from_message(message)
                parsed_in += msg_input_tokens
                parsed_out += msg_output_tokens

                finish_reason = normalize_finish_reason(message)

                if not finish_reason:
                    finish_reason = (
                        message.response_metadata.get("stop_reason")
                        if getattr(message, "response_metadata", None)
                        else None
                    )

                if finish_reason in ["tool_calls", "tool_use"]:
                    tool_calls = []
                    for tool_call in getattr(message, "tool_calls", []) or []:
                        name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name",None)
                        args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args",None)
                        if name and name != "ModelOutput":
                            tool_calls.append({"name": name, "args": args})

                        if name == "ModelOutput":  # this is the end of anthropic chain when using structured output
                            if isinstance(message.content, list) and len(message.content) > 0:
                                model_out = message.content[0]['partial_json']
                    iterations.append(
                        {
                            "tool_calls": tool_calls,
                            "input_tokens": msg_input_tokens,
                            "output_tokens": msg_output_tokens,
                        }
                    )

                if finish_reason == "stop":  # openai
                    model_out = message.content if getattr(message, "content", None) is not None else model_out

                raw_tool_calls: list = []
                tc_list = getattr(message, "tool_calls", None)
                if isinstance(tc_list, list):
                    raw_tool_calls.extend(tc_list)
                elif tc_list:
                    raw_tool_calls.append(tc_list)
                single_tc = getattr(message, "tool_call", None)
                if single_tc:
                    raw_tool_calls.append(single_tc)

                tool_calls = []
                for tool_call in raw_tool_calls:
                    if isinstance(tool_call, dict):
                        name = tool_call.get("name") or tool_call.get("tool")
                        args = tool_call.get("args") or tool_call.get("arguments")
                    else:
                        name = getattr(tool_call, "name", None)
                        args = getattr(tool_call, "args", None) or getattr(tool_call, "arguments", None)
                    if not name:
                        continue
                    if name == "ModelOutput":
                        if isinstance(message.content, list) and message.content:
                            first = message.content[0]
                            if isinstance(first, dict) and "partial_json" in first:
                                model_out = first.get("partial_json", model_out)
                        continue
                    tool_calls.append({"name": name, "args": args})

                if finish_reason in ("tool_calls", "tool_call", "tool_use") or tool_calls:
                    if tool_calls:
                        iterations.append(
                            {
                                "tool_calls": tool_calls,
                                "input_tokens": msg_input_tokens,
                                "output_tokens": msg_output_tokens,
                            }
                        )

                if finish_reason in ("stop", "end_turn", "length", "max_tokens"):
                    content = message.content if getattr(message, "content", None) is not None else model_out
                    if isinstance(content, list):
                        text_parts = []
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") == "text" and "text" in part:
                                    text_parts.append(part["text"])
                                elif "text" in part:
                                    text_parts.append(part["text"])
                        if text_parts:
                            model_out = "".join(text_parts)
                    else:
                        model_out = content

                if finish_reason == "end_turn":  # anthropic
                    content = message.content if getattr(message, "content", None) is not None else model_out
                    print(content)
                    if isinstance(content, list):
                        model_out = "".join([c['text'] for c in content if c['type'] == 'text'])

            return model_out, iterations, parsed_in, parsed_out

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

        # Stream events to reconstruct output, tool calls, and token usage.
        chain = []
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
                if isinstance(event, dict):
                    etype = event.get("event")
                    name = event.get("name")

                    if etype == "on_chat_model_stream" and not got_stream:
                        got_stream = True
                        log_debug("MODEL streaming started (first chunk received)")
                        chain.append(event)
                        continue

                    if etype == "on_tool_start":
                        tool_calls_seen += 1
                        log_debug(f"AGENT tool_start name={name} (#{tool_calls_seen})")
                        if name and name != "ModelOutput":
                            data = event.get("data", {}) or {}
                            args = data.get("input") or data.get("inputs")
                            tool_call_fallback.append(
                                {
                                    "tool_calls": [{"name": name, "args": args}],
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                }
                            )

                    if etype == "on_tool_end":
                        log_debug(f"AGENT tool_end name={name}")

                    if etype == "on_tool_error":
                        log_error(f"AGENT tool_error name={name} data={_truncate(event.get('data', {}))}")
                        if name and name != "ModelOutput":
                            data = event.get("data", {}) or {}
                            args = data.get("input") or data.get("inputs")
                            tool_call_fallback.append(
                                {
                                    "tool_calls": [{"name": name, "args": args}],
                                    "input_tokens": 0,
                                    "output_tokens": 0,
                                }
                            )

                    log_event(event)

                    if etype == "on_tool_end" and name == "execute_ifc_code":
                        out = _parse_tool_end_output(event)
                        if isinstance(out, dict) and out.get("error") in (
                            "SUBPROCESS_CRASH",
                            "SUBPROCESS_TIMEOUT",
                        ):
                            raise RuntimeError(f"IFC_TOOL_FATAL: {out}")

                chain.append(event)
        except BaseException as exc:
            if _is_quota_error(exc):
                raise QuotaExceededError(str(exc)) from exc
            err_text = "ERROR during agent/tool run:\n" + traceback.format_exc()
            appended = f"{prompt}\n\n---AGENT ERROR---\n{err_text}"
            tool_call_iterations = tool_call_fallback
            if structured_output:
                model_output = _ErrorModelOutput(appended)
            else:
                model_output = appended
            cb_totals = _aggregate_token_usage_from_callback(usage_cb)
            if cb_totals is not None:
                input_tokens, output_tokens = cb_totals
            else:
                messages = _extract_messages_from_chain(chain)
                _, _, parsed_input_tokens, parsed_output_tokens = (
                    _parse_messages_for_output_and_tool_calls(messages)
                )
                input_tokens, output_tokens = parsed_input_tokens, parsed_output_tokens
            return {
                "model_output": model_output,
                "tool_call_iterations": tool_call_iterations,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "recursion_error": _is_recursion_error(exc),
                "error": str(exc),
            }
        finally:
            if hb:
                hb.cancel()
                with contextlib.suppress(Exception):
                    await hb
            if usage_cb_cm is not None:
                usage_cb_cm.__exit__(None, None, None)

        log_debug("MODEL end (astream_events completed)")

        model_output = ""
        input_tokens = output_tokens = 0
        tool_call_iterations = []

        messages = _extract_messages_from_chain(chain)
        model_output, tool_call_iterations, parsed_input_tokens, parsed_output_tokens = (
            _parse_messages_for_output_and_tool_calls(messages)
        )
        if not tool_call_iterations and tool_call_fallback:
            tool_call_iterations = tool_call_fallback

        structured_response = _extract_structured_response_from_chain(chain)
        if structured_response is not None:
            model_output = structured_response

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
            "output_tokens": output_tokens,
            "recursion_error": False,
        }

    builder = StateGraph(State)
    builder.add_node("call_model", call_model)
    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", END)
    graph = builder.compile()

    start = max(int(args.start_index) - 1, 0)

    stop_run = False
    for index in range(start, len(questions)):
        row = questions.iloc[index]
        question_id = int(index)

        log(f"QUESTION {index + 1}/{len(questions)} id={question_id} file={row.get('ifc-file')}")

        if str(question_id) in cache:
            log_debug(f"QUESTION id={question_id} already in cache, skipping.")
            continue

        prompt = row["question"]
        if pd.isna(prompt):
            log_error("Empty prompt. Skipping.")
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
            log_debug(f"  SAMPLE {sample + 1}/{num_samples} start")
            t0 = time.time()

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
                "filtered_tools": tools,
                "read_only": is_retrieve,
            }

            model_error = ""
            try:
                result_state = await asyncio.wait_for(
                    graph.ainvoke(model_args, config={"recursion_limit": 15}),
                    timeout=int(args.sample_timeout),
                )
                log_debug(f"  SAMPLE {sample + 1} model done in {time.time() - t0:.1f}s")
            except QuotaExceededError as exc:
                model_error = str(exc)
                log_error(f"  SAMPLE {sample + 1} QUOTA exceeded: {exc}")
                sample_results.append(
                    {
                        "sample": sample + 1,
                        "model_output": "ERROR_INSUFFICIENT_QUOTA",
                        "tool_call_iterations": [],
                        "metrics": None,
                        "score": None,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "error": model_error,
                    }
                )

                continue

            model_output = result_state["model_output"]

            if model_output:
               if is_retrieve:
                    model_output = model_output.__dict__

            test = importlib.import_module(test_path)
            t1 = time.time()
            try:
                metrics = test.execute_test(ifc_path, edited_ifc_path, model_output)
                log(f"  SAMPLE {sample + 1} test done in {time.time() - t1:.1f}s metrics_keys={list(metrics.keys())}")

                stop_run = True
                break

            except Exception as exc:
                model_error = str(exc)
                log_error(
                    f"  SAMPLE {sample + 1} ERROR after {time.time() - t0:.1f}s: {exc}"
                )
                result_state = {
                    "model_output": f"ERROR_OR_RECURSION_LIMIT_OR_TOOL_FATAL: {exc}",
                    "tool_call_iterations": [],
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "recursion_error": _is_recursion_error(exc),
                    "error": str(exc),
                }

            model_error = result_state.get("error") or model_error
            raw_output = result_state["model_output"]
            if output_object and hasattr(raw_output, "__dict__"):
                model_output = raw_output.__dict__
            else:
                model_output = raw_output

            metrics = None
            score = None
            if llm_only:
                log_debug(f"  SAMPLE {sample + 1} llm-only: skipping tests")
            else:
                test = importlib.import_module(test_path)
                t1 = time.time()
                metrics, test_error = execute_test_with_fallback(
                    test, ifc_path, edited_ifc_path, model_output
                )
                if test_error:
                    log_error(f"  SAMPLE {sample + 1} test ERROR: {test_error}")
                log_debug(
                    f"  SAMPLE {sample + 1} test done in "
                    f"{time.time() - t1:.1f}s metrics_keys={list(metrics.keys())}"
                )
                score = sum(metrics.values()) / len(metrics) if metrics else 0

            sample_result = {
                "sample": sample + 1,
                "model_output": model_output,
                "tool_call_iterations": result_state["tool_call_iterations"],
                "metrics": metrics,
                "score": score,
                "input_tokens": result_state["input_tokens"],
                "output_tokens": result_state["output_tokens"],
            }
            if model_error:
                sample_result["error"] = model_error
            sample_results.append(sample_result)

        if stop_run:
            if sample_results:
                source_csv = row.get("source_csv", "")
                cache_object = {
                    "question_id": question_id,
                    "prompt": prompt,
                    "model": model_name,
                    "ifc_file": row["ifc-file"],
                    "source_csv": str(source_csv) if source_csv is not None else "",
                    "crud_operation": crud_value,
                    "results": sample_results,
                    "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                }
                cache[str(question_id)] = cache_object
                with cache_path.open("w", encoding="utf-8") as cache_file:
                    json.dump(cache, cache_file)
                log_error(f"Partial cache written before stopping ({cache_path.name})")
            break

        source_csv = row.get("source_csv", "")
        cache_object = {
            "question_id": question_id,
            "prompt": prompt,
            "model": model_name,
            "ifc_file": row["ifc-file"],
            "source_csv": str(source_csv) if source_csv is not None else "",
            "crud_operation": crud_value,
            "results": sample_results,
            "timestamp": json.dumps(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }

        cache[str(question_id)] = cache_object
        with cache_path.open("w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)

        log(f"QUESTION id={question_id} written to cache ({cache_path.name})")

        if stop_run:
            break

    if stop_run:
        log_error(f"Stopped early due to insufficient quota. Cache at: {cache_path}")
    else:
        log(f"Done. Cache written to: {cache_path}")


if __name__ == "__main__":
    asyncio.run(main())
