from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class CollectionDTO(BaseModel):
    uuid: UUID
    name: Optional[str]
    cmetadata: Optional[dict]
    create_time: datetime

    model_config = {
        'from_attributes': True
    }