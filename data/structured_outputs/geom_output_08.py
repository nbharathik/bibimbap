from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    distance_m: float = Field(description="Distance between the longest walls, in meters")
    raw_model_response: str = Field(description="The raw model response")
