from pydantic import BaseModel, Json
from typing import Optional
from datetime import datetime
from uuid import UUID

class FileDTO(BaseModel):
    uuid: UUID
    file_name: str
    collection_id: Optional[UUID]
    collection_name: Optional[str] = None
    file_extension: Optional[str]
    cmetadata: Optional[Json]
    create_time: datetime

    model_config = {
        'from_attributes': True
    }