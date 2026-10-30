import logging
from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.data_dictionary_dao import DataDictionaryDAO
from src.schemas.data_dict_dto import DataDictionaryDTO
from singleton_decorator import singleton

from src.services.base_service import BaseService
from src.utils.logger import get_logger
logger = get_logger(__name__)

class DataDictionaryService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(DataDictionaryDAO(db), DataDictionaryDTO)
        self.dao:DataDictionaryDAO = self.dao

    async def get_by_key(self, key: str):
        dict = await self.dao.get_by_key(key)
        if dict:
            logger.info(f"data dict:{dict}")
            return DataDictionaryDTO.model_validate(dict)
        return None

    async def update_by_key(self, key: str, value: str):
        dict = await self.dao.update_by_key(key, value)
        if dict:
            return DataDictionaryDTO.model_validate(dict)
        return None
    
    async def delete_by_key(self, key: str):
        dict = await self.dao.delete_by_key(key)
        if dict:
            return DataDictionaryDTO.model_validate(dict)
        return None
    
    async def batch_create_dicts(self, items: list[dict]):
        dicts = await self.dao.batch_create_dicts(items)
        if dicts:
            return [DataDictionaryDTO.model_validate(dict) for dict in dicts]
        return None
    
    async def batch_update_dicts(self, updates: list[dict]):
        await self.dao.batch_update_dicts(updates)

    async def batch_delete_dicts(self, keys: list[str]):
        await self.dao.batch_delete_dicts(keys)

    async def batch_upsert_dicts(self, items: list[dict]):
        await self.dao.batch_upsert_dicts(items)