from pydantic import BaseModel, Field


class ModelOutput(BaseModel):
	length: float = Field(description="Length (longest side) of the non-square room, in meters")
	raw_model_response: str = Field(description="The raw model response")
