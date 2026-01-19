from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Outer net wall area of the specified walls")
    raw_model_response: str = Field(description="The raw model response")
