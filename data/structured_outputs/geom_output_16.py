from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    deleted_guid: str = Field(description="GlobalId of the door that was deleted")
    raw_model_response: str = Field(description="The raw model response")
