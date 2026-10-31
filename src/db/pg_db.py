from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from src.config.loader import load_yaml_config
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

_db_url: str = None

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    db = None
    try:
        db = async_session()
        yield db
    except Exception as e:
        print(f"数据操作错误: {e}")
        if db and db.in_transaction():  # 如果存在未完成的事务，则回滚
            await db.rollback()
        # 必须抛出去。吞掉的话 FastAPI 只会看到「Response not awaited」，
        # 真正的原因被埋掉，排查全靠猜。
        raise
    finally:
        if db:
            await db.close()
    
def get_db_conn_url() -> str:
    global _db_url
    # 如果已经获取过db url，则直接返回缓存的值
    if _db_url is not None:
        return _db_url
    
    conf = load_yaml_config(
        str((Path(__file__).parent.parent.parent / "conf.yaml").resolve())
    )
    url = conf["db"]["url"]
    logger.info(f"db url: {url}")
    return url

# 添加导入
import psycopg
import urllib.parse

# 添加函数
async def create_psycopg_connection():
    """创建 psycopg 异步连接，与 SQLAlchemy 引擎使用相同配置"""
    parsed = urllib.parse.urlparse(get_db_conn_url())
    psycopg_conn_str = f"user={parsed.username} password={parsed.password} host={parsed.hostname} port={parsed.port} dbname={parsed.path.lstrip('/')}"
    return await psycopg.AsyncConnection.connect(psycopg_conn_str)

engine = create_async_engine(
    get_db_conn_url(),
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True  # 防止连接因长时间空闲而断开
)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)