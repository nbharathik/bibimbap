from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    volume: float = Field(description="The volume of the room in cubic meters")
    raw_model_response: str = Field(description="The raw model response")