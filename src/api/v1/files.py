from datetime import datetime, timezone
import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.api_contract import APIContract
from src.config.conf import PROJECT_DIR
from src.db.pg_db import get_db
from src.handler.vector.partition_handler import PartitionHandler
from src.services.chunk_service import ChunkService
from src.services.embedding_service import EmbeddingService
from src.services.file_service import FileService
from src.utils.logger import get_logger
logger = get_logger(__name__)

router = APIRouter(tags=["files"], prefix="/files")


ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt",".csv",".xlsx"}

@router.post("/")
async def upload_files(file: UploadFile = File(...), collection_id: str = Form(None),db: AsyncSession = Depends(get_db)):
    # 验证文件扩展名
    logger.info(f"upload file file.filename={file.filename},collection_id={collection_id}")
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        return APIContract.error(400,f"filename: {file.filename}, Unsupported file type. Only .docx and .pdf are allowed.")
    
    # 保存文件到服务器（原代码硬编码了作者机器的 D:/PythonProject/langchat/uploads，改为项目自身目录）
    upload_dir = os.path.join(PROJECT_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    save_path = os.path.join(upload_dir, file.filename)
    try:
        with open(save_path, "wb") as f:
            f.write(await file.read())
        logger.info(f"File {file.filename} uploaded successfully.")
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {e}")
        return APIContract.error(400,f"Failed to save file {file.filename}: {e}")
    
    file_service = FileService(db)
    file_dto = await file_service.create(file_name=file.filename,
                        uuid=uuid.uuid1(),
                        collection_id = collection_id,
                        file_extension = file_extension[1::],
                        create_time=datetime.now(timezone.utc)
                )
    logger.info(f"File {file.filename} create file table successfully 信息:{file_dto}")

    part_handler = PartitionHandler()
    await part_handler.file_partition(file_id=file_dto.uuid,file_name=file.filename,file_path=save_path,file_extension=file_extension)
    
    return APIContract.success({"filename": file.filename, "message": "File store to chunk successfully."})

@router.get("/")
async def get_all(data: dict, db: AsyncSession = Depends(get_db)):
    service = FileService(db)
    return APIContract.success(await service.query_files(data.get("collection_id")))

@router.delete("/")
async def delete_file(data: dict, db: AsyncSession = Depends(get_db)):
    file_id = data.get("file_id")

    embedding_service = EmbeddingService(db)
    await embedding_service.delete_embedding_by_file_id(file_id)

    chunk_service = ChunkService(db)
    await chunk_service.delete_chunks_by_file_id(file_id)

    service = FileService(db)
    return APIContract.success(await service.delete_file(file_id))