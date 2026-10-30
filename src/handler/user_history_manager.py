from src.services.ai_ext_message_service import AiExtMessageService
from singleton_decorator import singleton
from src.db.pg_db import get_db,get_db_conn_url,create_psycopg_connection
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.messages import AIMessage
import psycopg
import urllib.parse
from src.db.pg_db import engine  # 添加这个导入
from src.utils.logger import get_logger
logger = get_logger(__name__)

@singleton
class UserHistoryManager:
    def __init__(self):
        self.user_historys = {}
        
    
    async def get_user_history(self, user_id: str):
        """获取用户的历史记录"""
        if user_id not in self.user_historys:
            try:
                async_connection =  await create_psycopg_connection()
            except Exception as e:
                logger.error(f"数据库连接失败: {e}. 请检查 db url: {get_db_conn_url()}")
                raise
            # await PostgresChatMessageHistory.acreate_tables(async_connection, "user_history")
            self.user_historys[user_id] = PostgresChatMessageHistory(
                "user_history",
                user_id,
                async_connection=async_connection
            )
            
        return self.user_historys[user_id]

    async def get_user_history_messages(self, user_id: str):
        history = await self.get_user_history(user_id)
        messages = await history.aget_messages()
        logger.info(f"用户ID: {user_id}, 历史消息: {messages}")

        if messages is None or len(messages) == 0:
            return []
        
        run_ids = []
        for message in messages:
            if isinstance(message, AIMessage):
               run_ids.append(message.id)
        
        logger.info(f"用户ID: {user_id}, 历史消息ai run_ids: {run_ids}")
         
        if len(run_ids) > 0:
            async for db_session in get_db():
                ai_ext_message_service = AiExtMessageService(db_session)
                ai_ext_messages = await ai_ext_message_service.get_by_run_ids(run_ids)
                
                logger.info(f"用户ID: {user_id}, 历史消息ai ai_ext_messages: {ai_ext_messages}")
        
                for message in messages:
                    if isinstance(message, AIMessage):
                        run_id = message.id
                        for ai_ext_message in ai_ext_messages:
                            if ai_ext_message.run_id == run_id:
                                import re
                                import json
                                import ast
                                logger.info(f"用户ID: {user_id}, 历史消息ai ai_exai_ext_message.ext_contextt_messages: {ai_ext_message.ext_context}")
                                # ext_context_str = re.sub(r"UUID\(['\"]([^'\"]*)['\"]\)", r'"\1"', ai_ext_message.ext_context)
                                ext_context_str = ai_ext_message.ext_context
                                # logger.info(f"用户ID: {user_id}, 历史消息ai ext_context_str: {ext_context_str}")
                                # 在 json.loads 之前添加处理逻辑
                                # ext_context_str = re.sub(r"'([^']*)':", r'"\1":', ext_context_str)  # 替换键的单引号
                                # ext_context_str = re.sub(r":\s*'([^']*)'", r': "\1"', ext_context_str)  # 替换值的单引号
                                ext_dict = ast.literal_eval(ext_context_str)
                                logger.info(f"用户ID: {user_id}, 历史消息解析后: {ext_dict}")
                                file_info_list = []
                                for key, value in ext_dict.items():
                                    file_info = value
                                    file_info_list.append(file_info)
                                logger.info(f"用户ID: {user_id}, 历史消息解析后file_info_list: {file_info_list}")
                                message.response_metadata["file_info_list"] = file_info_list
                                break
        
        return messages
    
    async def delete_user_history_messages(self, user_id: str):
        history = await self.get_user_history(user_id)
        await history.aclear()