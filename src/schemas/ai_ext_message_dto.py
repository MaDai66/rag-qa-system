from typing import Optional
from pydantic import BaseModel


class AiExtMessageDTO(BaseModel):
    id: int
    run_id: str
    ext_context: str

    model_config = {
        'from_attributes': True
    }
