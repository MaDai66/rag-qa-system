import logging
from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.ai_ext_message_dao import AiExtMessageDAO
from src.schemas.ai_ext_message_dto import AiExtMessageDTO
from src.services.base_service import BaseService
from src.utils.logger import get_logger
logger = get_logger(__name__)

class AiExtMessageService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(AiExtMessageDAO(db), AiExtMessageDTO)


    async def create_ext(self, run_id: str, ext_context: str):
        ext_message = await self.dao.create_ext(run_id, ext_context)
        if ext_message:
            logger.info(f"ext_message:{ext_message}")
            return AiExtMessageDTO.model_validate(ext_message)
        return None

    async def get_by_run_id(self, run_id: str):
        dict = await self.dao.get_by_run_id(run_id)
        if dict:
            logger.info(f"data dict:{dict}")
            return AiExtMessageDTO.model_validate(dict)
        return None
    
    async def get_by_run_ids(self, run_ids: list):
        """
        根据run_id数组批量查询AiExtMessage记录
        
        Args:
            run_ids (list): run_id字符串列表
            
        Returns:
            list: 匹配的AiExtMessageDTO对象列表
        """
        dicts = await self.dao.get_by_run_ids(run_ids)
        if dicts:
            logger.info(f"data dicts:{dicts}")
            return [AiExtMessageDTO.model_validate(item) for item in dicts]
        return []