
from abc import ABC, abstractmethod
from enum import StrEnum
import json
import os

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import text

from src.config.conf import PROJECT_DIR
from src.db.pg_db import get_db
from src.utils.ts_vector import to_query
from src.utils.logger import get_logger
logger = get_logger(__name__)

class SearchMode(StrEnum):
    EMBEDDING = "embedding"
    FULLTEXT = "fulltext"
    HYBRID = "hybrid"

class ISearch(ABC):
    @abstractmethod
    def support(self, search_mode: SearchMode):
        pass

    @abstractmethod
    async def handle(self, collection_id, query_text, query_embedding, top_n: int,
               score_threshold: float, search_mode: SearchMode):
        pass


class EmbeddingSearch(ISearch):
    async def handle(self,
               collection_id,
               query_text,
               query_embedding,
               top_n: int,
               vector_score_threshold: float,
               search_mode: SearchMode):
        try:
            if search_mode == SearchMode.EMBEDDING.value:
                logger.info(f"SearchMode: {search_mode} 匹配 EmbeddingSearch")

                loader = FileSystemLoader([
                    os.path.join(PROJECT_DIR, "src","dao", "sql")  # 实际模板存放路径
                ])
                jieba_env = Environment(loader=loader)
                template_path = os.path.join( "embedding_search.sql.j2")
                template = jieba_env.get_template(template_path)

                sql = template.render(collection_id=collection_id,
                                    top_n=top_n,
                                    query_embedding=query_embedding,
                                    vector_score_threshold=vector_score_threshold)

                logger.info(f"向量检索sql:{sql}")

                async for session in get_db():
                    result = await session.execute(text(sql))

                # 获取列名
                columns = result.keys()
                # 将每一行转换为字典
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                return rows
            else:
                logger.warning(f"SearchMode与EmbeddingSearch 不配对.")
                return []
        except FileNotFoundError:
            logger.error(f"Error: SQL template file 'embedding_search.sql.j2' not found.")
        except Exception as e:
            logger.error(f"Error: {e}")
        return []

    def support(self, search_mode: SearchMode):
        return search_mode == SearchMode.EMBEDDING.value


class FullTextSearch(ISearch):
    async def handle(self,
               collection_id,
               query_text,
               query_embedding,
               top_n: int,
               full_score_threshold: float,
               search_mode: SearchMode):
        try:
            if search_mode == SearchMode.FULLTEXT.value:
                logger.info(f"SearchMode: {search_mode} 匹配 FullTextSearch")

                loader = FileSystemLoader([
                    os.path.dirname(__file__),  # 当前脚本目录
                    os.path.join(PROJECT_DIR, "src","dao", "sql")  # 实际模板存放路径
                ])
                jieba_env = Environment(loader=loader)
                template_path = os.path.join( "fulltext_search.sql.j2")
                template = jieba_env.get_template(template_path)

                sql = template.render(collection_id=collection_id,
                                    query = to_query(query_text),
                                    top_n=top_n,
                                    full_score_threshold=full_score_threshold)
                logger.info(f"全文检索SQL: {sql}")
                async for session in get_db():
                    result = await session.execute(text(sql))

                # 获取列名
                columns = result.keys()
                # 将每一行转换为字典
                rows = [dict(zip(columns, row)) for row in result.fetchall()]

                return rows
            else:
                logger.warning(f"SearchMode与FullTextSearch 不配对.")
                return []
        except FileNotFoundError:
            logger.error(f"Error: SQL template file 'fulltext_search.sql.j2' not found.")
        except Exception as e:
            logger.error(f"Error: {e}")
        return []

    def support(self, search_mode: SearchMode):
        return search_mode == SearchMode.FULLTEXT.value


# class HybridSearch(ISearch):
#     async def handle(self,
#                collection_id,
#                query_text,
#                query_embedding,
#                top_n: int,
#                score_threshold: float,
#                search_mode: SearchMode):
#         try:
#             if search_mode == SearchMode.HYBRID.value:
#                 logger.info(f"SearchMode: {search_mode} 匹配 HybridSearch")

#                 loader = FileSystemLoader([
#                     os.path.dirname(__file__),  # 当前脚本目录
#                     os.path.join(PROJECT_DIR, "src","dao", "sql")  # 实际模板存放路径
#                 ])
#                 jieba_env = Environment(loader=loader)
#                 template_path = os.path.join( "hybrid_search.sql.j2")
#                 template = jieba_env.get_template(template_path)

#                 sql = template.render(collection_id=collection_id,
#                                     query = to_query(query_text),
#                                     query_embedding=query_embedding,
#                                     top_n=top_n,
#                                     score_threshold=score_threshold)

#                 async for session in get_db():
#                     result = await session.execute(text(sql))

#                 # 获取列名
#                 columns = result.keys()
#                 # 将每一行转换为字典
#                 rows = [dict(zip(columns, row)) for row in result.fetchall()]

#                 return rows
#             else:
#                 logger.warning(f"SearchMode与HybridSearch 不配对.")
#                 return []
#         except FileNotFoundError:
#             logger.error(f"Error: SQL template file 'hybrid_search.sql.j2' not found.")
#         except Exception as e:
#             logger.error(f"Error: {e}")
#         return []

#     def support(self, search_mode: SearchMode):
#         return search_mode == SearchMode.HYBRID.value


# search_handle_list = [EmbeddingSearch(), FullTextSearch()]
# 将 search_handle_list 修改为字典类型
search_handler_map = {
    SearchMode.EMBEDDING: EmbeddingSearch(),
    SearchMode.FULLTEXT: FullTextSearch(),
    # 如果启用 HybridSearch 可以取消下面的注释
    # SearchMode.HYBRID: HybridSearch(),
}
