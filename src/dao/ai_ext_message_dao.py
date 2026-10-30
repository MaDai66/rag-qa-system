
from sqlalchemy import select
from src.core.exception_handler import handle_db_exceptions
from src.dao.base_dao import BaseDAO
from src.models.ai_ext_message import AiExtMessage

class AiExtMessageDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, AiExtMessage)

    @handle_db_exceptions
    async def get_by_run_id(self, run_id: str):
        result = await self.db.execute(select(AiExtMessage).where(AiExtMessage.run_id == run_id))
        return result.scalar_one_or_none()

    @handle_db_exceptions
    async def create_ext(self, run_id: str, ext_context: str):
        ext_message = AiExtMessage(run_id=run_id, ext_context=ext_context)
        self.db.add(ext_message)
        await self.db.commit()
        await self.db.refresh(ext_message)
        return ext_message

    # 新增的批量查询方法
    @handle_db_exceptions
    async def get_by_run_ids(self, run_ids: list):
        """
        根据run_id数组批量查询AiExtMessage记录
        
        Args:
            run_ids (list): run_id字符串列表
            
        Returns:
            list: 匹配的AiExtMessage对象列表
        """
        if not run_ids:
            return []
            
        result = await self.db.execute(
            select(AiExtMessage).where(AiExtMessage.run_id.in_(run_ids))
        )
        return result.scalars().all()