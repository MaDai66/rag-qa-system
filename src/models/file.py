from sqlalchemy import Column, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, VARCHAR, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class File(Base):
    __tablename__ = 'file'
    uuid = Column(UUID, primary_key=True, index=True)
    file_name = Column(VARCHAR)
    file_extension = Column(VARCHAR)
    cmetadata = Column(JSON)
    collection_id = Column(UUID)
    create_time = Column(TIMESTAMP(timezone=True),nullable=False)
    