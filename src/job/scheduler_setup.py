from datetime import datetime, timezone
import uuid
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from src.db.pg_db import get_db
from src.models.embedding import Embedding
from src.services.chunk_service import ChunkService
from src.services.embedding_service import EmbeddingService
from src.utils.logger import get_logger
from src.utils.ts_vector import to_ts_vector
from src.core.embedding_manager import get_embeddings
from src.schemas.embedding_dto import EmbeddingDTO
from pgvector.utils import Vector
logger = get_logger(__name__)

# async def _create_embeddings(chunk_embedding_dtos, embeddings_model):
    
#     import time
#     start_time = time.time()  # 记录开始时间
    
#     """生成嵌入"""
#     texts = [row.context for row in chunk_embedding_dtos]
#     chunk_ids = [row.chunk_id for row in chunk_embedding_dtos]
    
#     if not texts:
#         return []
    
#      # 记录数据准备时间
#     preparation_time = time.time() - start_time
#     logger.info(f"数据准备耗时: {preparation_time:.2f}秒, 处理文本数量: {len(texts)}")
    
#     # 根据数据量动态调整批次大小
#     # 批次大小范围分析
#     # 最小值: 20

#     # 当 len(texts) // 4 < 20 时，即 len(texts) < 80 时，批次大小为 20
#     # 最大值: 100

#     # 当 len(texts) // 4 > 100 时，即 len(texts) > 400 时，批次大小为 100
#     # 动态值: len(texts) // 4

#     # 当 80 <= len(texts) <= 400 时，批次大小为 len(texts) // 4
#     # 具体示例
#     # texts数量	计算过程	最终batch_size
#     # 0-79	len(texts)//4 < 20	20
#     # 80-119	len(texts)//4 = 20-29	20-29
#     # 200-299	len(texts)//4 = 50-74	50-74
#     # 300-399	len(texts)//4 = 75-99	75-99
#     # 400+	len(texts)//4 >= 100	100
    
#      # 根据数据量动态调整批次大小
#     batch_size_calc_start = time.time()
#     batch_size = max(20, min(100, len(texts) // 4))
#     batch_size_calc_time = time.time() - batch_size_calc_start
    
#      # 分批处理
#      # 分批处理
#     batching_start = time.time()
#     batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
#     batch_indices = [chunk_ids[i:i + batch_size] for i in range(0, len(chunk_ids), batch_size)]
#     batching_time = time.time() - batching_start
    
#     logger.info(f"批次大小计算耗时: {batch_size_calc_time:.4f}秒, "
#                 f"分批处理耗时: {batching_time:.4f}秒, "
#                 f"总批次数: {len(batches)}, 批次大小: {batch_size}")
    
#     # 对于计算密集型任务，使用线程池执行
#     embedding_start_time = time.time()
#     embeddings_dict = {}
#     try:
#         for i, (batch, batch_chunk_ids) in enumerate(zip(batches, batch_indices)):
#             batch_start_time = time.time()
#             batch_embeddings = embeddings_model.embed_documents(batch)
#             # 将嵌入结果与chunk_id关联存储
#             for chunk_id, embedding in zip(batch_chunk_ids, batch_embeddings):
#                 embeddings_dict[chunk_id] = embedding
            
#             batch_time = time.time() - batch_start_time
#             logger.info(f"批次 {i+1}/{len(batches)} 处理完成，耗时: {batch_time:.2f}秒")
#     except Exception as e:
#         logger.error(f"嵌入生成过程中出错: {e}")
#         raise
    
#     embedding_time = time.time() - embedding_start_time
#     total_time = time.time() - start_time
    
#     logger.info(f"嵌入生成总耗时: {embedding_time:.2f}秒")
#     logger.info(f"总耗时: {total_time:.2f}秒")
        
#     return embeddings_dict
    
async def _create_embeddings(chunk_embedding_dtos, embeddings_model):
    
    
    import time
    start_time = time.time()  # 记录开始时间
    
    """生成嵌入"""
    texts = [row.context for row in chunk_embedding_dtos]
    chunk_ids = [row.chunk_id for row in chunk_embedding_dtos]
    
    if not texts:
        return []
    
    embeddings =  embeddings_model.embed_documents(texts)
    # 构建 {chunk_id: embedding} 字典以避免索引错位
    embeddings_dict = dict(zip(chunk_ids, embeddings))
    
    
    total_time = time.time() - start_time
    logger.info(f"总耗时: {total_time:.2f}秒, ")
    
    return embeddings_dict

async def _prepare_embedding_list(chunk_embedding_dtos, embeddings_dict):
    """准备 Embedding 列表"""
    embedding_dto_list = []
    for dto in chunk_embedding_dtos:
        embedding_dto = EmbeddingDTO(
            uuid=uuid.uuid4(),
            chunk_id=dto.chunk_id,
            collection_id=dto.collection_id,
            file_id=dto.file_id,
            embedding_vector=Vector(embeddings_dict[dto.chunk_id]),
            search_vector=to_ts_vector(dto.context),
            create_time=datetime.now(timezone.utc)
        )
        embedding_dto_list.append(embedding_dto)

    return embedding_dto_list

# 假设这些是你已有的函数和变量
async def do_embedding_chunks():
    try:
        async for session in get_db():
            chunk_service = ChunkService(session)
            rows = await chunk_service.query_embedding_chunks()
            if not rows:  # 如果没有查询到任何数据，则返回空列表
                logger.debug("没有需要向量化的数据")
                return []
            logger.info(f"成功查询出需要向量化的数据:{len(rows)}条")

            # 使用全局 embeddings 实例
            embeddings_model = get_embeddings()
            
            chunk_embeddings_dict = await _create_embeddings(rows, embeddings_model)

            embedding_dto_list = await _prepare_embedding_list(rows, chunk_embeddings_dict)

            embedding_service = EmbeddingService(session)
            logger.info(f"准备批量新增前---embedding_list:{len(embedding_dto_list)}条")
            await embedding_service.batch_embedding_create(embedding_dto_list)
            logger.info(f"成功批量新增embedding_list:{len(embedding_dto_list)}条")

            await chunk_service.batch_update_status_by_uuids([row.chunk_id for row in rows], 1)

    except Exception as e:
        logger.info(f"错误: 执行 SQL 查询时出错: {e}")
        # await session.rollback()
        return []

async def scheduled_job():
    try:
        while True:
            await do_embedding_chunks()
            logger.info("等待 10 秒后重新执行...")
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info("定时任务已被取消")
        raise  # 重新抛出 CancelledError 以便外部可以正确处理