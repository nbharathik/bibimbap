from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    volume: str = Field(description="The volume in cubic meters")
    raw_model_response: str = Field(description="The raw model response")