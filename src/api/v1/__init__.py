from src.api.v1.dicts import router as dicts_router
from src.api.v1.users import router as users_router
from src.api.v1.chat import router as chat_router
from src.api.v1.files import router as files_router
from src.api.v1.chunks import router as chunks_router
from src.api.v1.collections import router as collections_router

__all__ = [
    "dicts_router",
    "users_router",
    "chat_router",
    "files_router",
    "chunks_router",
    "collections_router",
]
