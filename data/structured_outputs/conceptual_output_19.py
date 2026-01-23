from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    global_id: str = Field(description="The global id of the door")
    raw_model_response: str = Field(description="The raw model response")