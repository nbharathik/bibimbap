from abc import ABC, abstractmethod
from pydantic import BaseModel
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

load_dotenv(find_dotenv())

class TextToBIM(ABC):
    def __init__(self, system_prompt: str | None = None, model_name: str | None = None) -> None:
        self.llm_system_prompt: str | None = (
            system_prompt if isinstance(system_prompt, str) and system_prompt.strip() else None
        )
        self.model_name: str | None = (
            model_name if isinstance(model_name, str) and model_name.strip() else None
        )
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None

    @abstractmethod
    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None) -> BaseModel | str:
        ...
