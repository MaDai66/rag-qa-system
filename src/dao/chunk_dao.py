import os
from uuid import UUID
from jinja2 import Environment, FileSystemLoader

from sqlalchemy import delete, select, text, update
from src.core.exception_handler import handle_db_exceptions
from src.dao.base_dao import BaseDAO
from src.models.chunk import Chunk
from src.utils.sql_template_manager import SQLTemplateManager

class ChunkDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, Chunk, primary_key="uuid")
        # self.jinja_env = Environment(loader=FileSystemLoader(os.path.dirname(__file__)))
        self.sql_template_manager = SQLTemplateManager(os.path.dirname(__file__))

    # @handle_db_exceptions
    # async def get_by_uuid(self, uuid: UUID) -> Chunk:
    #     result = await self.db.execute(select(Chunk).where(Chunk.uuid == uuid))
    #     return result.scalar_one_or_none()
    
    @handle_db_exceptions
    async def get_by_file_id(self, file_id: UUID):
        result = await self.db.execute(
                    select(Chunk)
                    .where(Chunk.file_id == file_id)
                    .order_by(Chunk.index)
                )
        return result.scalars().all()
    
    @handle_db_exceptions
    async def get_chunks_by_ids(self, chunk_ids: list[UUID]):
        """
        根据 chunk_id 列表查询 Chunk 内容。
        
        :param chunk_ids: 要查询的 Chunk ID 列表
        :return: 查询到的 Chunk 对象列表
        """
        if not chunk_ids:
            return []

        stmt = select(Chunk).where(Chunk.uuid.in_(chunk_ids))
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    @handle_db_exceptions
    async def delete_chunks_by_file_id(self, file_id: UUID):
        query = delete(Chunk).where(Chunk.file_id == file_id)
        await self.db.execute(query)
        await self.db.commit()
 
    @handle_db_exceptions
    async def query_embedding_chunks(self):
        try:
            # 确保 db 已正确初始化
            if not self.db:
                print("错误: 数据库连接未初始化.")
                return []
            sql = self.sql_template_manager.render_sql("sql/chunk_query.sql.j2")
            # template = self.jinja_env.get_template('sql/chunk_query.sql.j2')
            # sql = template.render()
            result = await self.db.execute(text(sql))
            # 如果 result 为 None，说明 execute 失败
            if result is None:
                print("错误: SQL 执行返回 None.")
                return []

            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            # await result.close()
            return rows
        except FileNotFoundError:
            print(f"错误: sql模板 'query.sql.j2' 不存在.")
        except Exception as e:
            print(f"错误执行sql: {e}")
        return []

    @handle_db_exceptions
    async def batch_update_status_by_uuids(self, uuids: list[UUID], new_status: int):
        """
        根据 UUID 列表批量更新 chunk 的 status 列。
        
        :param uuids: 要更新的 Chunk 的 UUID 列表
        :param new_status: 新的 status 值
        :return: 受影响的行数
        """
        query = (
            update(Chunk)
            .where(Chunk.uuid.in_(uuids))
            .values(status=new_status)
            .returning(Chunk.uuid)  # 返回受影响的 UUID 列表
        )
        result = await self.db.execute(query)
        await self.db.commit()
        return result.scalars().all()

    # @handle_db_exceptions
    # async def update_context(self, uuid: UUID, new_context: str) -> Chunk:
    #     query = (
    #         update(Chunk)
    #        .where(Chunk.uuid == uuid)
    #        .values(context=new_context)
    #        .returning(Chunk)
    #     )
    #     result = await self.db.execute(query)
    #     await self.db.commit()
    #     return result.scalar_one_or_none()
