from sqlalchemy import select, update, delete
from src.core.exception_handler import handle_db_exceptions
from src.dao.base_dao import BaseDAO
from src.models.data_dictionary import DataDictionary

class DataDictionaryDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, DataDictionary)

    # @handle_db_exceptions
    # async def create_dict(self, key: str, value: str):
    #     dict = DataDictionary(key=key, value=value)
    #     self.db.add(dict)
    #     await self.db.commit()
    #     await self.db.refresh(dict)
    #     return dict

    @handle_db_exceptions
    async def get_by_key(self, key: str):
        result = await self.db.execute(select(DataDictionary).where(DataDictionary.key == key))
        return result.scalar_one_or_none()

    # @handle_db_exceptions
    # async def update_dict(self, id: int, key: str, value: str):
    #     query = (
    #         update(DataDictionary)
    #        .where(DataDictionary.id == id)
    #        .values(key=key, value=value)
    #        .returning(DataDictionary)
    #     )
    #     result = await self.db.execute(query)
    #     await self.db.commit()
    #     return result.scalar_one_or_none()

    @handle_db_exceptions
    async def update_by_key(self, key: str, value: str):
        query = (
            update(DataDictionary)
           .where(DataDictionary.key == key)
           .values(value=value)
           .returning(DataDictionary)
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.scalar_one_or_none()

    # @handle_db_exceptions
    # async def delete_dict(self, id: int):
    #     query = delete(DataDictionary).where(DataDictionary.id == id).returning(DataDictionary)
    #     result = await self.db.execute(query)
    #     await self.db.commit()
    #     return result.scalar_one_or_none()
    
    @handle_db_exceptions
    async def delete_by_key(self, key: str):
        query = delete(DataDictionary).where(DataDictionary.key == key).returning(DataDictionary)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.scalar_one_or_none()

    @handle_db_exceptions
    async def batch_create_dicts(self, items: list[dict]):
        """
        批量新增字典项
        :param items: 包含新增数据的列表，每个元素是一个字典，格式为 {"key": key, "value": value}
        """
        dicts = [DataDictionary(key=item["key"], value=item["value"]) for item in items]
        self.db.add_all(dicts)
        await self.db.commit()
        return dicts
    
    @handle_db_exceptions
    async def batch_update_dicts(self, updates: list[dict]):
        """
        批量更新字典项
        :param updates: 包含更新数据的列表，每个元素是一个字典，格式为 {"key": key, "value": value}
        """
        for update_item in updates:
            query = (
                update(DataDictionary)
                .where(DataDictionary.key == update_item["key"])
                .values(value=update_item["value"])
            )
            await self.db.execute(query)
        await self.db.commit()

    @handle_db_exceptions
    async def batch_delete_dicts(self, keys: list[str]):
        """
        批量删除字典项
        :param keys: 要删除的 key 列表
        """
        query = delete(DataDictionary).where(DataDictionary.key.in_(keys))
        await self.db.execute(query)
        await self.db.commit()

    @handle_db_exceptions
    async def batch_upsert_dicts(self, items: list[dict]):
        """
        批量新增或更新字典项
        :param items: 包含数据的列表，每个元素是一个字典，格式为 {"key": key, "value": value}
        """
        for item in items:
            query = (
                update(DataDictionary)
                .where(DataDictionary.key == item["key"])
                .values(value=item["value"])
                .returning(DataDictionary.id)
            )
            result = await self.db.execute(query)
            if result.scalar_one_or_none() is None:  # 如果没有更新到任何记录，则新增
                dict_item = DataDictionary(key=item["key"], value=item["value"])
                self.db.add(dict_item)
        await self.db.commit()