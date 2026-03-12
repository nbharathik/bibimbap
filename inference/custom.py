from base_class import TextToBIM
from pydantic import BaseModel

class CustomTextToBIM(TextToBIM):

    def __init__(self, system_prompt: str | None = None, model_name: str | None = None):
        """Initialize your Custom TextToBIM system here."""
        super().__init__(system_prompt=system_prompt, model_name=model_name)

    def invoke(self, prompt: str, ifc_path: str, output_format: type[BaseModel] | None) -> str | BaseModel:
        """This method must edit the ifc file and return the model output in the specified format (String or Pydantic Model)."""

