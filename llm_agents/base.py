from abc import ABC, abstractmethod

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel

load_dotenv(find_dotenv())


class BaseLLMAgent(ABC):
    def __init__(
        self,
        system_prompt: str | None = None,
        model_name: str | None = None,
        agent_config: dict | None = None,
    ) -> None:
        self.llm_system_prompt: str | None = (
            system_prompt if isinstance(system_prompt, str) and system_prompt.strip() else None
        )
        self.model_name: str | None = (
            model_name if isinstance(model_name, str) and model_name.strip() else None
        )
        self.agent_config: dict = agent_config if isinstance(agent_config, dict) else {}
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.tool_call_iterations: list[dict] = []
        self.last_error: str | None = None
        self.last_recursion_error: bool = False

    @abstractmethod
    def invoke(
        self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None
    ) -> BaseModel | str:
        ...
