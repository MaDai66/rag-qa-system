from sqlalchemy import Column, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, VARCHAR, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Collection(Base):
    __tablename__ = 'collection'
    uuid = Column(UUID, primary_key=True, index=True)
    name = Column(VARCHAR)
    cmetadata = Column(JSON)
    create_time = Column(TIMESTAMP(timezone=True),nullable=False)
    