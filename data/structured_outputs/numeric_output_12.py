from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Combined width of the openings with a sill")
    raw_model_response: str = Field(description="The raw model response")
