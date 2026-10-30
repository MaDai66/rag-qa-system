import datetime
import os
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text
from src.core.exception_handler import handle_db_exceptions
from src.dao.base_dao import BaseDAO
from src.models.file import File
from src.utils.sql_template_manager import SQLTemplateManager

class FileDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, File, primary_key="uuid")
        self.sql_template_manager = SQLTemplateManager(os.path.dirname(__file__))

    @handle_db_exceptions
    async def query_files(self, collection_id: str):
        try:
            sql = self.sql_template_manager.render_sql("sql/file_query.sql.j2",collection_id=collection_id)
            # template = self.jinja_env.get_template('sql/file_query.sql.j2')
            # sql = template.render(collection_id=collection_id)
            result = await self.db.execute(text(sql))
            # 获取列名
            columns = result.keys()
            # 将每一行转换为字典
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows
        except FileNotFoundError:
            print(f"Error: SQL template file 'query.sql.j2' not found.")
        except Exception as e:
            print(f"Error executing SQL: {e}")
        return []