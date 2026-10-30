from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class DataDictionary(Base):
    __tablename__ = 'data_dictionary'
    id = Column(Integer, primary_key=True, index=True,autoincrement=True)
    key = Column(String,unique=True, index=True)
    value = Column(String)
    