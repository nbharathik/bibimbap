from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    area: float = Field(description="The area of the room in square meters")
    raw_model_response: str = Field(description="The raw model response")