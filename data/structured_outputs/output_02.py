from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    number_of_windows: float = Field(description="The retrieved number of windows")
    room_id: int = Field(description="The step id of the room looked for")
    raw_model_response: str = Field(description="The raw model response")
