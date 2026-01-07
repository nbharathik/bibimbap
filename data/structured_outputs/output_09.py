from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    distance: float = Field(description="The distance in meters")
    raw_model_response: str = Field(description="The raw model response")