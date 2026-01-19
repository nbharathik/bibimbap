from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Area of the openings that are larger than 2 sqm")
    raw_model_response: str = Field(description="The raw model response")
