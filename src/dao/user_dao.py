from src.dao.base_dao import BaseDAO
from src.models.user import User

class UserDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, User)
