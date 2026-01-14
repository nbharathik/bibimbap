from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    global_id: str = Field(description="GlobalId of the shortest wall (IFC GlobalId string only)")
    raw_model_response: str = Field(description="The raw model response")
