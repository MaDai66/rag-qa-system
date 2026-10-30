from uuid import UUID
from typing import Any
from pgvector.utils import Vector
def json_serializer(obj: Any) -> str:
    """
    将 UUID 或具有 isoformat 方法的对象序列化为字符串。
    """
    if isinstance(obj, UUID):
        return str(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")