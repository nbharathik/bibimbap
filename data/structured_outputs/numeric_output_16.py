from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Volume of the openings in the slab")
    raw_model_response: str = Field(description="The raw model response")
