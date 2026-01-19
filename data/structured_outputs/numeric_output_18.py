from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Net room volume of the non-rectangular room")
    raw_model_response: str = Field(description="The raw model response")
