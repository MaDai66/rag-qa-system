# src/core/embedding_manager.py
from langchain_huggingface import HuggingFaceEmbeddings
from src.db.pg_db import get_db
from src.services.data_dictionary_service import DataDictionaryService
from src.core.constant import EMBEDDINGS_PATH
from src.utils.logger import get_logger
import torch

logger = get_logger(__name__)

# 全局 embeddings 实例
_embeddings = None

async def initialize_embeddings():
    global _embeddings  # 添加这一行来声明使用全局变量
    try:
        # 从数据库获取配置
        async for db_session in get_db():
            dict_service = DataDictionaryService(db_session)
            embedding_path = await dict_service.get_by_key(EMBEDDINGS_PATH)
        
        # 初始化模型
        if embedding_path:
            model_path = embedding_path.value
            logger.info(f"Embeddings model path from config: {model_path}")
        else:
            # 回退到默认路径
            model_path = "D:/HuggingFace/bge-large-zh-v1.5"
            logger.warning(f"Using default embeddings path: {model_path}")
        
        # 检测设备
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        # 根据设备类型设置不同的模型参数
        if device == "cuda":
            model_kwargs = {'device': device}
            encode_kwargs = {'normalize_embeddings': True}
        else:
            # CPU优化配置
            model_kwargs = {
                'device': device,
                'trust_remote_code': True
            }
            encode_kwargs = {
                'normalize_embeddings': True,
                'batch_size': 32  # CPU环境下设置合理的批次大小
            }
            
            # 如果可能，启用多线程
            import os
            if hasattr(torch, 'set_num_threads'):
                torch.set_num_threads(os.cpu_count())
        
        _embeddings = HuggingFaceEmbeddings(
            model_name=model_path,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        
        logger.info(f"Embeddings model initialized with path: {model_path} on device: {device}")
            
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        raise

def get_embeddings():
    global _embeddings  # 添加这一行来声明使用全局变量
    if _embeddings is None:
        raise RuntimeError("Embeddings model not initialized. Call initialize_embeddings() first.")
    return _embeddings