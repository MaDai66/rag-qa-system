from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Json
from pgvector.utils import Vector
    
class EmbeddingDTO(BaseModel):
    uuid: UUID
    file_id: Optional[UUID]
    chunk_id: Optional[UUID]
    collection_id: Optional[UUID]
    embedding_vector: Vector
    search_vector: Optional[str]
    cmetadata: Optional[Json] = None
    create_time: datetime

    model_config = {
        'from_attributes': True,
        'arbitrary_types_allowed': True
    }