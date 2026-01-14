from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    wall_ids: list[str] = Field(
        description="List of wall GlobalIds that form a triangle (exactly 3 ids)."
    )
    raw_model_response: str = Field(description="The raw model response")
