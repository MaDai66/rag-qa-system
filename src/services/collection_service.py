from singleton_decorator import singleton
from src.dao.collection_dao import CollectionDAO
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.collection_dto import CollectionDTO
from src.services.base_service import BaseService

class CollectionService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(CollectionDAO(db), CollectionDTO)

    