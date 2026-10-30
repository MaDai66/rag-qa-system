from sqlalchemy import TIMESTAMP, Column
from sqlalchemy.dialects.postgresql import UUID, JSON, TSVECTOR
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Embedding(Base):
    __tablename__ = 'embedding'
    uuid = Column(UUID, primary_key=True, index=True)
    file_id = Column(UUID)
    chunk_id = Column(UUID)
    collection_id = Column(UUID)
    embedding_vector = Column(Vector(1024))  # bge-large-zh-v1.5 输出 1024 维；不写维度则建不了 HNSW 索引
    search_vector = Column(TSVECTOR)
    cmetadata = Column(JSON)
    create_time = Column(TIMESTAMP(timezone=True),nullable=False)
    