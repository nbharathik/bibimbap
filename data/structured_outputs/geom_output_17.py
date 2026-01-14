from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    deleted_wall_guids: list[str] = Field(description="List of wall GlobalIds deleted from the IFC")
    raw_model_response: str = Field(description="The raw model response")
