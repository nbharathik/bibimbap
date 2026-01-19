from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Gross floor area of all storeys")
    raw_model_response: str = Field(description="The raw model response")
