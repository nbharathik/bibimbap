import asyncio
from langchain.agents.structured_output import ToolStrategy
from langchain_mcp_adapters.client import MultiServerMCPClient

from base_class import TextToBIM
from pydantic import BaseModel

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model


class CustomTextToBIM(TextToBIM):

    def __init__(self, system_prompt: str | None = None, model_name: str | None = None):
        """Custom TextToBIM constructor"""
        super().__init__(system_prompt=system_prompt, model_name=model_name)
        self.llm = init_chat_model(self.model_name or "openai:gpt-5.2")
        self.mcp_client = MultiServerMCPClient(
            # TODO: have this more abstract as an example?
            {
                "mcp_servers": {
                    "ifc-bonsai-mcp": {
                        "command": "C:\\\\Users\\\\ckujatadm\\\\Documents\\\\AI4SC\\\\ifc-bonsai-mcp\\\\.venv\\\\Scripts\\\\python.exe",
                        "args": ["-m", "blender_mcp.server"],
                        "transport": "stdio"
                    }
                }
            }
        )
        self.mcp_tools = None

    async def _ainvoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None) -> str | BaseModel:
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

        chain = [
            event
            async for event in agent.astream_events(
                {
                    "messages": [
                        {"role": "system", "content": self.llm_system_prompt or ""},
                        {"role": "user", "content": user_content},
                    ]
                }
            )
        ]

        chain_end = chain[-1] if chain else {}

        def _parse_messages_for_output(msgs) -> str:
            model_out = ""
            for message in msgs or []:
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
            return model_out

        messages = (
            chain_end.get("data", {})
            .get("output", {})
            .get("messages", [])
            if isinstance(chain_end, dict)
            else []
        )
        model_output = _parse_messages_for_output(messages)

        if (
            isinstance(chain_end, dict)
            and "structured_response" in chain_end.get("data", {}).get("output", {}).keys()
        ):
            model_output = chain_end["data"]["output"]["structured_response"]

        return model_output

    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None) -> str | BaseModel:
        return asyncio.run(self._ainvoke(prompt=prompt, ifc_path=ifc_path, output_format=output_format))

