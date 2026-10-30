from sqlalchemy import Column, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, VARCHAR,INTEGER
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Chunk(Base):
    __tablename__ = 'chunk'
    uuid = Column(UUID, primary_key=True, index=True)
    file_id = Column(UUID)
    file_name = Column(VARCHAR)
    context = Column(VARCHAR)
    index = Column(INTEGER)
    status = Column(INTEGER)
    create_time = Column(TIMESTAMP(timezone=True),nullable=False)
    