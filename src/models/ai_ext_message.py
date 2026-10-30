from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class AiExtMessage(Base):
    __tablename__ = 'ai_ext_message'
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    run_id = Column(String,unique=True, index=True)
    ext_context = Column(String)
    