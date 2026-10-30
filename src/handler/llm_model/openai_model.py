import logging
from langchain_openai import ChatOpenAI

from src.core.constant import OPENAI_API_BASE, OPENAI_API_KEY, TEMPERATURE
from src.db.pg_db import get_db
from src.handler.llm_model.base_model import BaseModel
from src.services.data_dictionary_service import DataDictionaryService
from src.utils.logger import get_logger
logger = get_logger(__name__)

class OpenAIModel(BaseModel):
    """OpenAI Model for generating responses using LangChain's ChatOpenAI."""
    def __init__(self):
        self.llm = None
    
    async def init_llm_model(self):
        
        logger.info("OpenAIModel init_llm_model")
        
        openai_api_key = None
        openai_base_url = None
        temperature = "0.5"
        
        async for db_session in get_db():
            dict_service = DataDictionaryService(db_session)

            dict_key = await dict_service.get_by_key(OPENAI_API_KEY)
            openai_api_key = dict_key.value if dict_key else None
                
            dict_base = await dict_service.get_by_key(OPENAI_API_BASE)
            openai_base_url = dict_base.value if dict_base else None

            dict_temp = await dict_service.get_by_key(TEMPERATURE)
            temperature = dict_temp.value if dict_temp else "0.5"
            
        # 确保 openai_api_key 存在
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured in the database.")

        # 正确地将参数传递给 ChatOpenAI 构造函数
        self.llm = ChatOpenAI(
            model="gpt-4",
            openai_api_key=openai_api_key,
            openai_api_base=openai_base_url,
            temperature=float(temperature)
        )

        return self.llm