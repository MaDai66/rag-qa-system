from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class ChunkDTO(BaseModel):
    uuid: UUID
    file_id: Optional[UUID]
    file_name: Optional[str]
    context: Optional[str]
    index: Optional[int]
    status: Optional[int] = 0
    create_time: datetime

    model_config = {
        'from_attributes': True
    }