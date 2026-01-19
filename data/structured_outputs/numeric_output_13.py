from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Length of all walls")
    raw_model_response: str = Field(description="The raw model response")
