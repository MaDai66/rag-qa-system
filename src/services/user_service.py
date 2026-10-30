from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.user_dao import UserDAO
from singleton_decorator import singleton
from src.schemas.user_dto import UserDTO
from src.services.base_service import BaseService


class UserService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(UserDAO(db), UserDTO)