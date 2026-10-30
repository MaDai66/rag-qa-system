import json
from uuid import UUID
from sqlalchemy import bindparam, delete, select, text, update,insert, func
from src.core.exception_handler import handle_db_exceptions
from src.dao.base_dao import BaseDAO
from src.models.embedding import Embedding
from src.utils.logger import get_logger
from src.utils.serializers import json_serializer

logger = get_logger(__name__)

class EmbeddingDAO(BaseDAO):
    def __init__(self, db):
        super().__init__(db, Embedding, primary_key="uuid")

    @handle_db_exceptions
    async def batch_embedding_create(self, items: list):
        """
        批量插入 Embedding 数据，并在插入时计算 search_vector 字段为 to_tsvector(search_vector)

        :param items: 包含多个模型对象的列表
        """
        data = [
            {
                "uuid": item.uuid,
                "file_id": item.file_id,
                "chunk_id": item.chunk_id,
                "collection_id": item.collection_id,
                "embedding_vector": item.embedding_vector.to_list(),
                "search_vector": item.search_vector,
                "cmetadata": item.cmetadata,
                "create_time": item.create_time,
            }
            for item in items
        ]

        insert_sql = text(
            """
            INSERT INTO embedding (uuid, file_id, chunk_id, collection_id, embedding_vector, search_vector, cmetadata, create_time)
            SELECT 
                (element->>'uuid')::UUID,
                (element->>'file_id')::UUID,
                (element->>'chunk_id')::UUID,
                (element->>'collection_id')::UUID,
                (element->>'embedding_vector')::VECTOR,
                to_tsvector(element->>'search_vector'), 
                (element->'cmetadata')::JSONB,
                (element->>'create_time')::TIMESTAMP WITH TIME ZONE
            FROM json_array_elements(:data) AS element
            """
        )

        await self.db.execute(insert_sql, {"data": json.dumps(data,default = json_serializer)})
        await self.db.commit()
        # """
        # 批量插入数据
        
        # :param items: 包含多个模型对象的列表
        # """
        # self.db.add_all(items)
        # await self.db.commit()
    @handle_db_exceptions
    async def delete_embedding_by_file_id(self, file_id: UUID):
        await self.db.execute(delete(self.model).where(self.model.file_id == file_id))
        await self.db.commit()
        logger.info(f"Deleted embeddings by file_id {file_id}")