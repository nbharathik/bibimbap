from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
    value: float = Field(description="Net volume of all slabs")
    raw_model_response: str = Field(description="The raw model response")
