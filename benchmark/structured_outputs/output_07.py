from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    length: float = Field(description="The length of the wall in meters")
    raw_model_response: str = Field(description="The raw model response")