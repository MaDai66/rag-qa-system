import logging
from uuid import UUID
from singleton_decorator import singleton
from src.dao.chunk_dao import ChunkDAO
from src.schemas.chunk_dto import ChunkDTO
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.chunk_embedding_dto import ChunkEmbeddingDTO
from src.services.base_service import BaseService
from src.utils.logger import get_logger
logger = get_logger(__name__)

class ChunkService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(ChunkDAO(db), ChunkDTO)
        self.dao: ChunkDAO = self.dao
        

    async def get_chunks_by_file_id(self, file_id: UUID) -> list[ChunkDTO]:
        chunks = await self.dao.get_by_file_id(file_id)
        return [
            ChunkDTO(
                uuid=chunk.uuid,
                file_id=chunk.file_id,
                file_name=chunk.file_name,
                context=chunk.context,
                index=chunk.index,
                status=chunk.status,
                create_time=chunk.create_time
            ) for chunk in chunks
        ]
    
    async def get_chunks_by_ids(self, chunk_ids: list[UUID]):
        chunks = await self.dao.get_chunks_by_ids(chunk_ids)
        return [
            ChunkDTO(
                uuid=chunk.uuid,
                file_id=chunk.file_id,
                file_name=chunk.file_name,
                context=chunk.context,
                index=chunk.index,
                status=chunk.status,
                create_time=chunk.create_time
            ) for chunk in chunks
        ]

    async def query_embedding_chunks(self):
        results = await self.dao.query_embedding_chunks()
        if results:
            return [ChunkEmbeddingDTO.model_validate(result) for result in results]
        return None
    
    async def batch_update_status_by_uuids(self, uuids: list[UUID], new_status: int):
        results = await self.dao.batch_update_status_by_uuids(uuids, new_status)
        logger.info(f"Updated {len(results)} chunks to status {new_status}")
    
    async def delete_chunks_by_file_id(self, file_id: UUID):
        await self.dao.delete_chunks_by_file_id(file_id)
        logger.info(f"Deleted chunks by file_id {file_id}")