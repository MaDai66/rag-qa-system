# -*- coding: utf-8 -*-
"""
langchat 数据库一次性初始化（幂等，可重复执行）

背景：仓库里没有任何建表语句 —— `models/*.py` 只有 ORM 定义，
      `user_history_manager.py` 里那句 `await PostgresChatMessageHistory.acreate_tables(...)`
      也是注释掉的。所以新建的空库必须先跑本脚本才能启动服务。

做四件事：
  1. 建 7 张业务表。注意每个 model 文件各自声明了一个独立的 `declarative_base()`，
     必须逐个 `create_all`，一次做不全。
  2. 建 `user_history` 表（langchain_postgres 的多轮对话历史）
  3. 补索引：embedding 表 HNSW 余弦索引 + GIN 全文索引（代码里没有任何 CREATE INDEX）
  4. 灌 data_dictionary 初始配置（DeepSeek key 从项目根的 .env 读，脚本不打印该值）

用法：
    cd langchat
    ../.venv/python.exe scripts/init_db.py
"""
import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ROOT = Path(__file__).resolve().parent.parent          # langchat/
ENV_FILE = ROOT.parent / ".env"                        # LANGCHAIN-CODING/.env
sys.path.insert(0, str(ROOT))

from sqlalchemy import text                                       # noqa: E402
from src.db.pg_db import engine, create_psycopg_connection        # noqa: E402

from src.models.file import Base as FileBase                      # noqa: E402
from src.models.collection import Base as CollectionBase          # noqa: E402
from src.models.chunk import Base as ChunkBase                    # noqa: E402
from src.models.embedding import Base as EmbeddingBase            # noqa: E402
from src.models.user import Base as UserBase                      # noqa: E402
from src.models.ai_ext_message import Base as MessageBase         # noqa: E402
from src.models.data_dictionary import Base as DictBase           # noqa: E402

# 每个文件一个独立 Base，必须逐个建
BASES = {
    "file": FileBase,
    "collection": CollectionBase,
    "chunk": ChunkBase,
    "embedding": EmbeddingBase,
    "user": UserBase,
    "ai_ext_message": MessageBase,
    "data_dictionary": DictBase,
}

PROMPT_SYSTEM = "你是一名严谨、专业的 AI 助手，请始终使用中文回答用户的问题。"

PROMPT_SYSTEM_RAG = (
    "你是一名知识库问答助手。回答时必须严格遵守以下要求：\n"
    "1. 只依据【文档】中的内容作答，不得编造，也不得引入文档之外的信息；\n"
    "2. 如果文档中没有足够信息回答问题，请直接说明“根据现有资料无法回答”，不要猜测；\n"
    "3. 使用中文作答，条理清晰。"
)

# 初始配置。baseline 阶段 search_mode 用纯向量检索（embedding），
# 之后做「混合检索」改造时再改成 hybrid，两次跑分才有对比。
INIT_CONFIG = [
    ("embeddings_path", "D:/HuggingFace/bge-large-zh-v1.5"),
    ("llm_model", "deepseek"),
    ("temperature", "0.5"),
    ("search_mode", "embedding"),
    ("top_n", "5"),
    # 原项目默认 0.5。实测这个绝对值对本语料太紧：bge-large-zh 的距离尺度
    # 会随语料文体漂移（文言文 0.33 起步、通用白话 0.51 起步），0.5 会把
    # 「养生」这类白话文档的正确段落全部滤掉，检索返回 0 条。
    # 取 0.6：6 道样本题的正确段落（同文档最优 0.3263~0.5070）都能进来。
    # 注意 0.6 并不能真正分开相关与不相关（同文档最差 0.5070 > 异文档最好 0.4889），
    # 绝对阈值本身是个有缺陷的设计 —— 留给 A7 的「相对阈值」改造项。
    ("threshold_vector", "0.6"),
    # 原项目默认 0.05，和 threshold_vector 是**同一个设计错误在全文通道上的翻版**：
    # 拿一个与语料无关的绝对 ts_rank 常数当过滤器。实测本语料的匹配 rank 全部落在
    # 0.0067~0.0539（养生题最好 0.0539 过线、三国题最好 0.0431 全灭、pg_jieba 题
    # 最好 0.0249 全灭），任何固定值都必然要么全砍要么全放。
    # 取 0 = 不过滤，靠 `ORDER BY similarity DESC LIMIT top_n` 截断（标准 top-K 全文检索）。
    # 改之前 search_mode=hybrid 是**静默无效果**的：45 题里 38 题全文返回空。
    ("threshold_fulltext", "0"),
    # 检索后处理开关。默认全 0 = 原始行为；做 A7 改造时逐项打开、逐项回测。
    ("keep_retrieval_order", "0"),
    ("rerank_enabled", "0"),
    ("rerank_candidates", "20"),
    ("rerank_model_path", "D:/HuggingFace/bge-reranker-base"),
    ("prompt_system", PROMPT_SYSTEM),
    ("prompt_system_rag", PROMPT_SYSTEM_RAG),
]

DDL_INDEXES = [
    # 向量检索走余弦距离（见 dao/sql/hit_test.sql 的 <=>），列有维度后才能建 HNSW
    ("idx_embedding_vector_hnsw",
     "CREATE INDEX IF NOT EXISTS idx_embedding_vector_hnsw "
     "ON embedding USING hnsw (embedding_vector vector_cosine_ops)"),
    ("idx_embedding_search_vector_gin",
     "CREATE INDEX IF NOT EXISTS idx_embedding_search_vector_gin "
     "ON embedding USING gin (search_vector)"),
    # scheduler 每 10 秒轮询 status=0 的 chunk，是热点查询
    ("idx_chunk_status",
     "CREATE INDEX IF NOT EXISTS idx_chunk_status ON chunk (status)"),
]


def read_deepseek_key():
    """从 .env 读 key。只返回值本身，调用方负责不打印它。"""
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DEEPSEEK_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


async def create_tables():
    async with engine.begin() as conn:
        for name, base in BASES.items():
            await conn.run_sync(base.metadata.create_all)
            print(f"  [表] {name}")
    print("--> 7 张业务表就绪")


async def create_user_history():
    from langchain_postgres import PostgresChatMessageHistory
    conn = await create_psycopg_connection()
    try:
        await PostgresChatMessageHistory.acreate_tables(conn, "user_history")
        print("  [表] user_history")
    finally:
        await conn.close()
    print("--> 聊天历史表就绪")


async def create_indexes():
    async with engine.begin() as conn:
        for label, ddl in DDL_INDEXES:
            await conn.execute(text(ddl))
            print(f"  [索引] {label}")
    print("--> 索引就绪")


async def seed_config():
    async with engine.begin() as conn:
        rows = list(INIT_CONFIG)
        key = read_deepseek_key()
        if key:
            rows.append(("deepseek_api_key", key))
        else:
            print("  !! 没在 .env 里找到 DEEPSEEK_API_KEY，deepseek_api_key 未写入")

        for k, v in rows:
            await conn.execute(
                text("INSERT INTO data_dictionary (key, value) VALUES (:k, :v) "
                     "ON CONFLICT (key) DO NOTHING"),
                {"k": k, "v": v},
            )
            shown = f"<已写入 len={len(v)}>" if k.endswith("api_key") else v
            print(f"  [配置] {k} = {shown}")

        result = await conn.execute(
            text("SELECT key FROM data_dictionary ORDER BY key"))
        print("--> data_dictionary 现有 key:", ", ".join(r[0] for r in result))


async def main():
    print("== 1/4 建业务表 ==")
    await create_tables()
    print("\n== 2/4 建 user_history ==")
    await create_user_history()
    print("\n== 3/4 建索引 ==")
    await create_indexes()
    print("\n== 4/4 灌初始配置 ==")
    await seed_config()
    print("\n完成。")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
