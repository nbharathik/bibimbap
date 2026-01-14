from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Total inner length of the two specified walls, in meters")
    raw_model_response: str = Field(description="The raw model response")
