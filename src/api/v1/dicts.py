from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.api_contract import APIContract
from src.db.pg_db import get_db
from src.handler.chat_model_handler import ChatModelHandler
from src.schemas.data_dict_dto import DataDictionaryDTO
from src.services.data_dictionary_service import DataDictionaryService
from src.utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(tags=["dicts"], prefix="/dicts")


@router.post("/")
async def create_dict(key: str, value: str,db: AsyncSession = Depends(get_db)):
    dict_service = DataDictionaryService(db)
    return APIContract.success(await dict_service.create(key=value))

@router.put("/{key}")
async def update_dict(key: str, value: str, db: AsyncSession = Depends(get_db)):
    dict_service = DataDictionaryService(db)
    return APIContract.success(await dict_service.update_by_key(key, value))

@router.get("/{key}")
async def get_dict(key: str, db: AsyncSession = Depends(get_db)):
    dict_service = DataDictionaryService(db)
    return APIContract.success(await dict_service.get_by_key(key))

@router.delete("/{key}")
async def delete_dict(key: str, db: AsyncSession = Depends(get_db)):
    dict_service = DataDictionaryService(db)
    return APIContract.success(await dict_service.delete_by_key(key))

@router.put("/batch-update")
async def batch_update_dicts(
    updates: List[dict], db: AsyncSession = Depends(get_db)
):
    dict_service = DataDictionaryService(db)
    await dict_service.batch_update_dicts(updates)
    return APIContract.success("Batch update successful")

@router.post("/batch-upsert")
async def batch_upsert_dicts(
    items: List[dict], db: AsyncSession = Depends(get_db)
):
    dict_service = DataDictionaryService(db)
    await dict_service.batch_upsert_dicts(items)
    await ChatModelHandler().clear_chains()
    return APIContract.success("Batch upsert successful")