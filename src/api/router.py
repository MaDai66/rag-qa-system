from fastapi import APIRouter

from src.api.v1 import (
    dicts_router,
    users_router,
    chat_router,
    files_router,
    chunks_router,
    collections_router,
)

# from api.v2 import (
#     items_router as items_router_v2
# )

router = APIRouter(
    prefix="/api",
)

router_v1 = APIRouter(
    prefix="/v1",
)

# router_v2 = APIRouter(
#     prefix="/v2",
# )

router_v1.include_router(dicts_router)
router_v1.include_router(users_router)
router_v1.include_router(chat_router)
router_v1.include_router(files_router)
router_v1.include_router(chunks_router)
router_v1.include_router(collections_router)



# router_v2.include_router(items_router_v2)



router.include_router(router_v1)
# router.include_router(router_v2)
