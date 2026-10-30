import logging
from fastapi import FastAPI, Request
from sqlalchemy.exc import SQLAlchemyError

from src.core.api_contract import APIContract
from src.core.response_code import ResponseCode

from src.utils.logger import get_logger
logger = get_logger(__name__)

def handle_db_exceptions(func):
    async def wrapper(*args, **kwargs):
        self = args[0]  # 获取类实例
        try:
            return await func(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"Database operation failed in {func.__name__}: {e}")
            await self.db.rollback()  # 回滚事务
            raise
    return wrapper

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"SQLAlchemyError: {exc}")
        return APIContract.error(
            status_code=ResponseCode.DATABASE_ERROR,
            message="Database operation failed. Please try again later.",
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return APIContract.error(
            status_code=ResponseCode.INTERNAL_SERVER_ERROR,
            message="An unexpected error occurred. Please try again later.",
        )