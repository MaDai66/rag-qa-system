from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.api_contract import APIContract
from src.db.pg_db import get_db
from src.schemas.user_dto import UserDTO
from src.services.user_service import UserService
from src.utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(tags=["users"], prefix="/users")

@router.get("/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user_service = UserService(db)
    return APIContract.success(await user_service.get_by_id(user_id))

@router.get("/")
async def list_users(db: AsyncSession = Depends(get_db)):
    user_service = UserService(db)
    return APIContract.success(await user_service.get_all())