import asyncio
import io
import json
import subprocess
import sys
import tempfile
import textwrap
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from typing import ClassVar, Tuple

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.chat_models import init_chat_model
from langchain_core.tools import BaseTool
from pydantic import BaseModel
try:
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception:  # pragma: no cover
    get_usage_metadata_callback = None

from base_class import TextToBIM


def _safe_jsonable(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


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

    def _run_in_process(self, code: str, ifc_file_path: str) -> dict:
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
                target = path or ifc_file_path
                ifc.write(target)
                return target

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
                "result": _safe_jsonable(env.get("result", None)),
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

    def _run_subprocess(self, code: str, ifc_file_path: str) -> dict:
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
                    target = path or ifc_file_path
                    ifc.write(target)
                    return target

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
                json.dumps({"code": code, "ifc_file_path": ifc_file_path}),
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

    def _run(self, code: str, ifc_file_path: str) -> dict:
        force = self.force_subprocess
        risky = self._looks_risky(code)
        backend = "subprocess" if (force or risky) else "in_process"

        if backend == "subprocess":
            return self._run_subprocess(code, ifc_file_path)
        return self._run_in_process(code, ifc_file_path)

    async def _arun(self, code: str, ifc_file_path: str) -> dict:
        return await asyncio.to_thread(self._run, code=code, ifc_file_path=ifc_file_path)


class OpenAICodeAgent(TextToBIM):
    def __init__(self, system_prompt: str | None = None, model_name: str | None = None):
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self.llm = init_chat_model(self.model_name or "openai:gpt-5.2")
        self.execute_ifc_tool = ExecuteIFCCodeTool()

    async def _ainvoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None):
        tools = [self.execute_ifc_tool]
        agent = (
            create_agent(self.llm, tools, response_format=ToolStrategy(output_format))
            if output_format
            else create_agent(self.llm, tools)
        )

        user_content = (
            f"{prompt}\n\n"
            f"Use the tool `execute_ifc_code` to run ifcopenshell code.\n"
            f"The current IFC file path is:\n{ifc_path}\n\n"
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

        try:
            chain = [
                event
                async for event in agent.astream_events(
                    {
                        "messages": [
                            {"role": "system", "content": self.llm_system_prompt or ""},
                            {"role": "user", "content": user_content},
                        ]
                    },
                    config={"callbacks": [usage_cb]} if usage_cb is not None else None,
                )
            ]
        finally:
            if usage_cb_cm is not None:
                usage_cb_cm.__exit__(None, None, None)

        chain_end = chain[-1] if chain else {}

        def _extract_token_usage_from_message(msg) -> tuple[int, int]:
            usage = getattr(msg, "usage_metadata", None) or {}
            if isinstance(usage, dict) and usage:
                in_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                out_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                return int(in_tok or 0), int(out_tok or 0)

            rm = getattr(msg, "response_metadata", None) or {}
            if isinstance(rm, dict) and rm:
                if any(k in rm for k in ("input_tokens", "prompt_tokens", "output_tokens", "completion_tokens")):
                    in_tok = rm.get("input_tokens") or rm.get("prompt_tokens") or 0
                    out_tok = rm.get("output_tokens") or rm.get("completion_tokens") or 0
                    return int(in_tok or 0), int(out_tok or 0)
                token_usage = rm.get("token_usage") or rm.get("usage") or {}
                if isinstance(token_usage, dict) and token_usage:
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
                    if not isinstance(v, dict):
                        continue
                    cb_in += int(v.get("input_tokens") or v.get("prompt_tokens") or 0)
                    cb_out += int(v.get("output_tokens") or v.get("completion_tokens") or 0)
                return cb_in, cb_out
            except Exception:
                return None

        def _parse_messages_for_output(msgs) -> tuple[str, int, int]:
            model_out = ""
            parsed_in = parsed_out = 0
            for message in msgs or []:
                msg_in, msg_out = _extract_token_usage_from_message(message)
                parsed_in += msg_in
                parsed_out += msg_out
                finish_reason = (
                    message.response_metadata.get("finish_reason")
                    if getattr(message, "response_metadata", None)
                    else None
                )
                if finish_reason == "stop":
                    model_out = (
                        message.content
                        if getattr(message, "content", None) is not None
                        else model_out
                    )
                if finish_reason == "end_turn":
                    content = (
                        message.content
                        if getattr(message, "content", None) is not None
                        else model_out
                    )
                    if isinstance(content, list):
                        model_out = "".join([c["text"] for c in content if c.get("type") == "text"])
            return model_out, parsed_in, parsed_out

        messages = (
            chain_end.get("data", {})
            .get("output", {})
            .get("messages", [])
            if isinstance(chain_end, dict)
            else []
        )
        model_output, parsed_in, parsed_out = _parse_messages_for_output(messages)

        if (
            isinstance(chain_end, dict)
            and "structured_response" in chain_end.get("data", {}).get("output", {}).keys()
        ):
            model_output = chain_end["data"]["output"]["structured_response"]

        cb_totals = _aggregate_token_usage_from_callback(usage_cb)
        if cb_totals is not None:
            self.input_tokens, self.output_tokens = cb_totals
        else:
            self.input_tokens, self.output_tokens = parsed_in, parsed_out

        return model_output

    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None):
        return asyncio.run(self._ainvoke(prompt=prompt, ifc_path=ifc_path, output_format=output_format))
