from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import router
from src.core.exception_handler import register_exception_handlers
from src.core.embedding_manager import initialize_embeddings
from src.utils.logger import get_logger
from src.job.scheduler_setup import scheduled_job
from contextlib import asynccontextmanager
import asyncio

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化 embeddings
    try:
        await initialize_embeddings()
        logger.info("Embeddings model initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize embeddings: {e}")
        raise

    # 启动时创建后台任务
    task = asyncio.create_task(scheduled_job())
    logger.info("Scheduled job started")
    
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Scheduled job cancelled successfully")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(router)

register_exception_handlers(app)



