from typing import Optional
from pydantic import BaseModel


class DataDictionaryDTO(BaseModel):
    id: int
    key: str
    value: Optional[str]

    model_config = {
        'from_attributes': True
    }
