
import logging
from langchain_deepseek import ChatDeepSeek
from src.core.constant import DEEPSEEK_API_KEY, TEMPERATURE
from src.db.pg_db import get_db
from src.handler.llm_model.base_model import BaseModel
from src.services.data_dictionary_service import DataDictionaryService
from src.utils.logger import get_logger
logger = get_logger(__name__)

class DeepSeekModel(BaseModel):
    """OpenAI Model for generating responses using LangChain's Deepseek."""
    def __init__(self):
        self.llm = None

    async def init_llm_model(self):
        """获取嵌入模型"""
        logger.info("ChatDeepSeek init_llm_model")
        async for db_session in get_db():
            dict_service = DataDictionaryService(db_session)
            dict = await dict_service.get_by_key(DEEPSEEK_API_KEY)
            api_key = dict.value if dict else None
            
            dict = await dict_service.get_by_key(TEMPERATURE)
            temperature = dict.value if dict else "0.5"

            logger.info(f"DeepSeek api_key: {'已配置 len=%d' % len(api_key) if api_key else '未配置'}")
            if api_key:
                self.llm = ChatDeepSeek(model="deepseek-chat", temperature=float(temperature), api_key= api_key)
            else:
                logger.error("DeepSeek api_key is None")

        return self.llm