import logging
from uuid import UUID
from src.dao.file_dao import FileDAO
from src.schemas.file_dto import FileDTO
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.base_service import BaseService
from src.utils.logger import get_logger
logger = get_logger(__name__)


class FileService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(FileDAO(db), FileDTO)
        self.dao:FileDAO = self.dao

    async def query_files(self, collection_id: str):
        
        results = await self.dao.query_files(collection_id)
        logger.info(f"返回结果：{results}")
        if results:
            return [FileDTO.model_validate(result) for result in results]
        return None
    
    async def delete_file(self, file_id: UUID):
        await self.delete(file_id)
        logger.info(f"Deleted files by file_id {file_id}")
        return True