from uuid import UUID
from singleton_decorator import singleton
from src.dao.embedding_dao import EmbeddingDAO
from src.models.embedding import Embedding
from src.schemas.embedding_dto import EmbeddingDTO
from src.services.base_service import BaseService
from sqlalchemy.ext.asyncio import AsyncSession

class EmbeddingService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(EmbeddingDAO(db), EmbeddingDTO)
        self.dao:EmbeddingDAO = self.dao
    
 
    async def batch_embedding_create(self, data: list[EmbeddingDTO]):
        """
        批量新增 Embedding 数据
        
        :param embedding_dtos: 包含多个 EmbeddingDTO 的列表
        :return: 插入结果或数量（根据实际 DAO 返回值调整）
        """
        return await self.dao.batch_embedding_create(data)
    
    async def delete_embedding_by_file_id(self, file_id: UUID):
        return await self.dao.delete_embedding_by_file_id(file_id)