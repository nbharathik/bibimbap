from pydantic import BaseModel

from .base import BaseLLMAgent


class CustomAgent(BaseLLMAgent):
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

    def invoke(
        self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None
    ) -> str | BaseModel:
        raise NotImplementedError(
            "CustomAgent is a template. Implement invoke() in llm_agents/custom.py."
        )
