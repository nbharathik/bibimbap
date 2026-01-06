from pydantic import BaseModel, Field

class ModelOutput(BaseModel):
    area: float = Field(description="The calculated area")
