from pydantic import BaseModel, Field


class ModelOutput(BaseModel): 
    value: float = Field(description="Net floor area of the room")
    raw_model_response: str = Field(description="The raw model response")
