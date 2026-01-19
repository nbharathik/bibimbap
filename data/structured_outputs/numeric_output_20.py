from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Perimeter of all rooms")
    raw_model_response: str = Field(description="The raw model response")
