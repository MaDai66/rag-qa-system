from src.dao.base_dao import BaseDAO
from src.models.collection import Collection


class CollectionDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, Collection, primary_key="uuid")