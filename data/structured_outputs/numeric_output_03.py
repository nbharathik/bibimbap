from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Gross floor area of the second floor")
    raw_model_response: str = Field(description="The raw model response")
