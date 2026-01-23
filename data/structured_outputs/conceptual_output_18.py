from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    number: str = Field(description="The number of vertical facade articulation zones")
    raw_model_response: str = Field(description="The raw model response")