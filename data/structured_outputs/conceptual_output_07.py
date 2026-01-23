from pydantic import BaseModel, Field
from typing import List

class ModelOutput(BaseModel):
    global_ids: List[str] = Field(description="The global ids of the doors")
    raw_model_response: str = Field(description="The raw model response")