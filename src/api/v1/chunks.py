from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.api_contract import APIContract
from src.db.pg_db import get_db
from src.schemas.chunk_dto import ChunkDTO
from src.schemas.data_dict_dto import DataDictionaryDTO
from src.services.chunk_service import ChunkService
from src.services.data_dictionary_service import DataDictionaryService

router = APIRouter(tags=["chunks"], prefix="/chunks")


@router.post("/")
async def create_chunk(chunk: ChunkDTO,db: AsyncSession = Depends(get_db)):
    chunk_service = ChunkService(db)
    return APIContract.success(await chunk_service.create_chunk(chunk))

@router.put("/{uuid}")
async def update_chunk(uuid: str, content: str, db: AsyncSession = Depends(get_db)):
    chunk_service = ChunkService(db)
    return APIContract.success(await chunk_service.update_chunk_context(uuid, content))

@router.get("/chunk/{uuid}")
async def get_chunk_by_chunk_id(uuid: str, db: AsyncSession = Depends(get_db)):
    chunk_service = ChunkService(db)
    # ChunkService 没有 get_chunk 这个方法，原来这行一定是 500。
    # 改用基类的 get_by_id，它走主键查，而 ChunkDAO 的主键就是 uuid，等价。
    return APIContract.success(await chunk_service.get_by_id(uuid))

@router.get("/file/{file_id}")
async def get_chunks_by_file_id(file_id: str, db: AsyncSession = Depends(get_db)):
    chunk_service = ChunkService(db)
    return APIContract.success(await chunk_service.get_chunks_by_file_id(file_id))

@router.delete("/{uuid}")
async def delete_chunk(uuid: str, db: AsyncSession = Depends(get_db)):
    chunk_service = ChunkService(db)
    return APIContract.success(await chunk_service.delete_chunk(uuid))
