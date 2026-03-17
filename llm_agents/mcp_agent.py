import asyncio
from collections.abc import Mapping

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel

from .base import BaseLLMAgent
from .runtime.runtime_core import is_recursion_error
from .runtime.runtime_langchain import (
    aggregate_token_usage_from_callback,
    extract_messages_from_events,
    extract_structured_response_from_events,
    fallback_tool_iteration_from_event,
    init_model,
    parse_messages_for_output_and_tool_calls,
)

try:
    from langchain_core.callbacks import get_usage_metadata_callback
except Exception:  # pragma: no cover
    get_usage_metadata_callback = None


def _normalize_mcp_config(agent_config: dict) -> dict:
    raw = agent_config.get("mcp_servers", {})
    if not isinstance(raw, Mapping) or not raw:
        return {}
    if "mcp_servers" in raw:
        return dict(raw)
    return {"mcp_servers": dict(raw)}


class MCPAgent(BaseLLMAgent):
    def __init__(
        self,
        system_prompt: str | None = None,
        model_name: str | None = None,
        agent_config: dict | None = None,
    ):
        super().__init__(
            system_prompt=system_prompt,
            model_name=model_name,
            agent_config=agent_config,
        )
        self.llm = init_model(self.model_name, "openai:gpt-5.2")
        mcp_config = _normalize_mcp_config(self.agent_config)
        self.mcp_client = MultiServerMCPClient(mcp_config) if mcp_config else None

    async def _ainvoke(
        self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None
    ) -> str | BaseModel:
        self.input_tokens = 0
        self.output_tokens = 0
        self.tool_call_iterations = []
        self.last_error = None
        self.last_recursion_error = False

        if self.mcp_client is None:
            raise RuntimeError(
                "MCPAgent requires agent.mcp_servers in config. "
                "Provide MCP server config in benchmark config JSON."
            )

        mcp_tools = await self.mcp_client.get_tools()
        load_ifc_tool = next(
            (
                tool
                for tool in mcp_tools
                if tool.name == "load_ifc_file" or tool.name.endswith("load_ifc_file")
            ),
            None,
        )

        if load_ifc_tool is not None:
            try:
                await load_ifc_tool.ainvoke(
                    {
                        "filepath": ifc_path,
                        "use_relative_path": False,
                        "start_fresh_session": True,
                    }
                )
            except Exception:
                pass

        agent = (
            create_agent(self.llm, mcp_tools, response_format=ToolStrategy(output_format))
            if output_format
            else create_agent(self.llm, mcp_tools)
        )

        if load_ifc_tool is None:
            user_content = f"{prompt}\nThe ifc file path is {ifc_path}."
        else:
            user_content = f"{prompt}\n(The IFC file is already loaded in Blender.)"

        usage_cb_cm = None
        usage_cb = None
        if get_usage_metadata_callback is not None:
            try:
                usage_cb_cm = get_usage_metadata_callback()
                usage_cb = usage_cb_cm.__enter__()
            except Exception:
                usage_cb_cm = None
                usage_cb = None

        chain = []
        tool_call_fallback: list[dict] = []
        try:
            async for event in agent.astream_events(
                {
                    "messages": [
                        {"role": "system", "content": self.llm_system_prompt or ""},
                        {"role": "user", "content": user_content},
                    ]
                },
                config={"callbacks": [usage_cb]} if usage_cb is not None else None,
            ):
                if isinstance(event, dict):
                    fallback_item = fallback_tool_iteration_from_event(event)
                    if fallback_item is not None:
                        tool_call_fallback.append(fallback_item)
                chain.append(event)
        except BaseException as exc:
            self.last_error = str(exc)
            self.last_recursion_error = is_recursion_error(exc)

            messages = extract_messages_from_events(chain)
            _, parsed_iterations, parsed_in, parsed_out = parse_messages_for_output_and_tool_calls(
                messages
            )

            cb_totals = aggregate_token_usage_from_callback(usage_cb)
            if cb_totals is not None:
                self.input_tokens, self.output_tokens = cb_totals
            else:
                self.input_tokens, self.output_tokens = parsed_in, parsed_out

            self.tool_call_iterations = (
                parsed_iterations if parsed_iterations else tool_call_fallback
            )
            raise
        finally:
            if usage_cb_cm is not None:
                usage_cb_cm.__exit__(None, None, None)

        messages = extract_messages_from_events(chain)
        model_output, parsed_iterations, parsed_in, parsed_out = (
            parse_messages_for_output_and_tool_calls(messages)
        )

        structured_response = extract_structured_response_from_events(chain)
        if structured_response is not None:
            model_output = structured_response

        cb_totals = aggregate_token_usage_from_callback(usage_cb)
        if cb_totals is not None:
            self.input_tokens, self.output_tokens = cb_totals
        else:
            self.input_tokens, self.output_tokens = parsed_in, parsed_out

        self.tool_call_iterations = parsed_iterations if parsed_iterations else tool_call_fallback

        return model_output

    def invoke(
        self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None
    ) -> str | BaseModel:
        return asyncio.run(
            self._ainvoke(prompt=prompt, ifc_path=ifc_path, output_format=output_format)
        )
