from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Area of the opening in the slab")
    raw_model_response: str = Field(description="The raw model response")
