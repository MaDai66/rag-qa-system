import asyncio
import json
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PostgresChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
import urllib
import psycopg
from src.schemas.ai_ext_message_dto import AiExtMessageDTO
from src.services.ai_ext_message_service import AiExtMessageService
from src.core.constant import (
    EMBEDDINGS_PATH, KEEP_RETRIEVAL_ORDER, LLM_MODEL, RAG_SUFFIX, RERANK_CANDIDATES,
    RERANK_ENABLED, RERANK_MODEL_PATH, RRF_ENABLED, SEARCH_MODE, THRESHOLD_FULLTEXT,
    THRESHOLD_VECTOR, TOP_N,
)
from src.db.pg_db import get_db,create_psycopg_connection
from src.handler.llm_model.llm_factory import LLMFactory
from src.handler.prompt.prompt_template import CustomPromptTemplate
from src.handler.search import EmbeddingSearch, SearchMode, search_handler_map
from src.services.chunk_service import ChunkService
from src.services.data_dictionary_service import DataDictionaryService
from singleton_decorator import singleton
from langchain_core.messages import AIMessage, HumanMessage
from src.core.embedding_manager import get_embeddings
from src.utils.logger import get_logger
from src.utils.serializers import json_serializer
from sqlalchemy.ext.asyncio import AsyncSession
from src.handler.callback_handler import CustomCallbackHandler
logger = get_logger(__name__)

@singleton
class ChatModelHandler:
    def __init__(self):
        self.llm = None
        self.llm_model = None
        self.user_chains = {}
        self.callbacks = [CustomCallbackHandler()]

    async def _init_llm_model(self):
        async for db_session in get_db():
            dict_service = DataDictionaryService(db_session)
            dict = await dict_service.get_by_key(LLM_MODEL)
            self.llm_model = dict.value if dict else None

        logger.info("init_chain")

        # 使用工厂创建模型实例
        llm_instance = LLMFactory.create_model(self.llm_model)
        self.llm = await llm_instance.init_llm_model()

    async def init_chain(self, user_id, is_rag = False):

        chain_key = user_id

        if is_rag:
            chain_key = chain_key + RAG_SUFFIX

        if chain_key in self.user_chains:
            return self.user_chains[chain_key]

        await self._init_llm_model()

        prompt = await CustomPromptTemplate().create_prompt(is_rag)

        chain = prompt | self.llm

        # parsed = urllib.parse.urlparse(get_db_conn_url())
        # # 构建 psycopg 连接字符串
        # psycopg_conn_str = f"user={parsed.username} password={parsed.password} host={parsed.hostname} port={parsed.port} dbname={parsed.path.lstrip('/')}"
        # logger.info(f"psycopg_conn_str: {psycopg_conn_str}")
        # async_connection = await psycopg.AsyncConnection.connect(psycopg_conn_str)
        
        async_connection =  await create_psycopg_connection()

        chain_with_message_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: PostgresChatMessageHistory(
                "user_history",
                session_id,
                async_connection=async_connection,
            ),
            input_messages_key="question",
            history_messages_key="chat_history",
            vebose=True,
        )
        
        self.user_chains[chain_key] = chain_with_message_history

        return chain_with_message_history
    
    
    async def get_response(self, user_id, message):
        user_message =  HumanMessage(content=message)
        chain = await self.init_chain(user_id,False)
        
        config = {"configurable": {"session_id": user_id}}
        response = await chain.ainvoke({"question": user_message}, config=config)
        result = {}
        # 检查 response 类型并提取内容
        if isinstance(response, AIMessage):
            result["content"]=response.content  # 使用属性访问内容
        elif isinstance(response, dict) and "content" in response:
            result["content"]=response["content"]
        else:
            raise ValueError("Unexpected response type")
        result["file_info_list"] = ""
        return result
        
        
    async def get_rag_response(self, user_id, collection_id,message,db):
        user_message =  HumanMessage(content=message)
        chain = await self.init_chain(user_id,True)
        
        
        dict_service = DataDictionaryService(db)
        # 改为串行执行，避免并发访问同一个session
        search_mode_dict = await dict_service.get_by_key(SEARCH_MODE)
        top_dict = await dict_service.get_by_key(TOP_N)
        threshold_vector_dict = await dict_service.get_by_key(THRESHOLD_VECTOR)
        threshold_fulltext_dict = await dict_service.get_by_key(THRESHOLD_FULLTEXT)
            
        
        
        search_mode = search_mode_dict.value if search_mode_dict else None
        top_n = int(top_dict.value) if top_dict else 5
        threshold_vector = float(threshold_vector_dict.value) if threshold_vector_dict and threshold_vector_dict.value else 0.5
        threshold_fulltext = float(threshold_fulltext_dict.value) if threshold_fulltext_dict and threshold_fulltext_dict.value else 0.05

        logger.info("search_mode: %s, top_n: %s, threshold_vector: %s, threshold_fulltext: %s", search_mode, top_n, threshold_vector, threshold_fulltext)

        # 评测用的改造开关，全部读自 data_dictionary，关掉即回到原始行为
        opts = await self._load_retrieval_options(dict_service, top_n)
        logger.info("检索后处理开关: %s", opts)

        if opts["rrf_enabled"] and not opts["keep_order"]:
            logger.warning("rrf_enabled=1 但 keep_retrieval_order=0：RRF 的顺序会在 _build_context 被丢掉")

        # 重排要先多召回一些候选（精排是"大候选里挑 top_n"，不是重排原有的 5 条）
        search_top_n = opts["rerank_candidates"] if opts["rerank_enabled"] else top_n

        # 根据搜索模式检索相关chunk
        chunk_ids = await self._retrieve_chunk_ids(
            collection_id, message, search_mode, search_top_n,
            threshold_vector, threshold_fulltext, opts=opts
        )

        # 构建上下文
        context_str, chunk_dict, context_list = await self._build_context(
            chunk_ids, db, message=message, top_n=top_n, opts=opts)

        config = {"configurable": {"session_id": user_id},"callbacks":self.callbacks}
        response = await chain.ainvoke({"question": user_message,"context": context_str}, config=config)

          # 提取响应内容和处理引用信息
        result = await self._process_response(response, user_id, chunk_dict,db)

        # 评测需要：把检索到的原文一并返回。
        # RAGAS 的 faithfulness / context_recall / context_precision 都要拿 retrieved_contexts 当输入，
        # 而原来的响应里只有答案文本和 file_info_list（那个只有文件名，没有正文），算不了。
        result["contexts"] = context_list
        return result
    
    
    async def _retrieve_chunk_ids(self, collection_id, message, search_mode, top_n, 
                             threshold_vector, threshold_fulltext, opts=None):
        """
        根据搜索模式检索相关的chunk IDs
        """
        chunk_ids = []
        
        if search_mode == SearchMode.FULLTEXT.value:
            search_result = await search_handler_map[SearchMode.FULLTEXT].handle(
                collection_id, message, None, top_n, threshold_fulltext, search_mode
            )
            logger.info(f"FULLTEXT search_result: {search_result}")
            if search_result:
                chunk_ids.extend([item["chunk_id"] for item in search_result])
                
        elif search_mode == SearchMode.EMBEDDING.value:
            # embeddings = HuggingFaceEmbeddings(model_name=embedding_path)
            # 获取全局 embeddings 实例
            embeddings_model = get_embeddings()
            query_embedding = embeddings_model.embed_query(message)
            search_result = await search_handler_map[SearchMode.EMBEDDING].handle(
                collection_id, message, query_embedding, top_n, threshold_vector, search_mode
            )
            logger.info(f"EMBEDDING search_result: {search_result}")
            if search_result:
                chunk_ids.extend([item["chunk_id"] for item in search_result])
                
        elif search_mode == SearchMode.HYBRID.value:
            # embeddings = HuggingFaceEmbeddings(model_name=embedding_path)
            embeddings_model = get_embeddings()
            query_embedding = embeddings_model.embed_query(message)
            
            # 并行执行向量搜索和全文搜索
            search_vector_result, search_fulltext_result = await asyncio.gather(
                search_handler_map[SearchMode.EMBEDDING].handle(
                    collection_id, message, query_embedding, top_n, threshold_vector, SearchMode.EMBEDDING.value
                ),
                search_handler_map[SearchMode.FULLTEXT].handle(
                    collection_id, message, None, top_n, threshold_fulltext, SearchMode.FULLTEXT.value
                )
            )
            
            logger.info(f"HYBRID search_vector_result: {search_vector_result}")
            logger.info(f"HYBRID search_fulltext_result: {search_fulltext_result}")
            
            vector_ids = [item["chunk_id"] for item in (search_vector_result or [])]
            fulltext_ids = [item["chunk_id"] for item in (search_fulltext_result or [])]

            if opts and opts.get("rrf_enabled"):
                chunk_ids = self._rrf_fuse(vector_ids, fulltext_ids)
                logger.info("RRF 融合: vector=%d, fulltext=%d, fused=%d",
                            len(vector_ids), len(fulltext_ids), len(chunk_ids))
            else:
                chunk_ids = vector_ids + fulltext_ids
        
        # 去重
        unique_chunk_ids = list(dict.fromkeys(chunk_ids))

        # hybrid 会返回最多 2×top_n 条（向量 top_n 条 + 全文 top_n 条），
        # 而 RRF 只改顺序不增删候选。下游只有重排那条路会截到 top_n，
        # 不重排时这些候选会原样全塞进 prompt（top_n=5 却出 7 条引用）。
        if not (opts and opts.get("rerank_enabled")):
            unique_chunk_ids = unique_chunk_ids[:top_n]

        logger.info(f"检索出来的chunk_ids: {unique_chunk_ids}")
        return unique_chunk_ids

    @staticmethod
    def _rrf_fuse(vector_ids, fulltext_ids, k=60):
        """RRF：score = Σ 1/(k + rank)。只改顺序，不增删候选。"""
        scores = {}
        first_seen = {}
        for ids in (vector_ids, fulltext_ids):
            for rank, cid in enumerate(dict.fromkeys(ids), start=1):
                first_seen.setdefault(cid, len(first_seen))
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        return [cid for cid, _ in sorted(
            scores.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))]

    async def _load_retrieval_options(self, dict_service, top_n):
        """读检索后处理开关。任何一项没配都退回「原始行为」，保证关掉即回到 baseline。"""
        async def _get(key, default):
            d = await dict_service.get_by_key(key)
            v = d.value if d else None
            return v if v not in (None, "") else default

        def _flag(v):
            return str(v).strip().lower() in ("1", "true", "yes", "on")

        return {
            "keep_order": _flag(await _get(KEEP_RETRIEVAL_ORDER, "0")),
            "rerank_enabled": _flag(await _get(RERANK_ENABLED, "0")),
            "rerank_candidates": int(await _get(RERANK_CANDIDATES, max(top_n * 4, 20))),
            "rerank_model_path": await _get(RERANK_MODEL_PATH, "D:/HuggingFace/bge-reranker-base"),
            "rrf_enabled": _flag(await _get(RRF_ENABLED, "0")),
        }

    def _rerank_chunks(self, query, chunks, top_n, opts):
        """交叉编码器精排。失败时退回原顺序，不让检索整体挂掉。"""
        from src.handler.rerank import Reranker

        try:
            scores = Reranker.instance().rerank(
                query, [c.context for c in chunks], opts["rerank_model_path"])
        except Exception as e:                                        # noqa: BLE001
            logger.error(f"重排失败，退回向量顺序：{e}")
            return chunks[:top_n]

        ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)[:top_n]
        logger.info(f"重排后分数: {[round(s, 4) for _, s in ranked]}")
        return [c for c, _ in ranked]

    async def _build_context(self, chunk_ids, db, message=None, top_n=None, opts=None):
        """
        根据chunk IDs构建上下文字符串和chunk字典

        message / top_n / opts 只有做「保序」「重排」改造时才用得到，
        默认全为 None 时行为跟改造前完全一致。
        """
        if not chunk_ids:
            return "", {}, []

        opts = opts or {}

        chunk_service = ChunkService(db)
        chunks = await chunk_service.get_chunks_by_ids(chunk_ids)

        # 【改造项：保序】get_chunks_by_ids 是 `WHERE uuid IN (...)`，不带 ORDER BY，
        # 检索算出来的相关性顺序会在这一步丢掉 —— 喂给模型的 5 段变成物理存储顺序。
        # 这不只是「位置偏置」：RAGAS 的 context_precision 是按上下文顺序算 MAP 的，
        # 顺序一乱，这个指标测出来的其实是随机顺序下的下界。
        if opts.get("keep_order"):
            rank = {cid: i for i, cid in enumerate(chunk_ids)}
            chunks = sorted(chunks, key=lambda c: rank.get(c.uuid, len(rank)))

        # 【改造项：重排】交叉编码器精排：大候选 → 打分 → 取 top_n
        if opts.get("rerank_enabled") and message and len(chunks) > 1:
            chunks = self._rerank_chunks(message, chunks, top_n or len(chunks), opts)

        context_list = []
        chunk_dict = {}
        for chunk in chunks:
            context_list.append(chunk.context)
            chunk_dict[str(chunk.uuid)] = {
                "file_id": str(chunk.file_id),
                "file_name": chunk.file_name,
                "chunk_id": str(chunk.uuid)
            }
        
        context_str = "\n".join(context_list)
        logger.info(f"context_list: {context_list}")
        logger.info(f"context_str: {context_str}")

        return context_str, chunk_dict, context_list
    
    async def _process_response(self, response, user_id, chunk_dict,db):
        """
        处理LLM响应，提取内容并处理引用信息
        """
        result = {}
        
        # 提取响应内容和run_id
        if isinstance(response, AIMessage):
            content = response.content
            run_id = response.id
        elif isinstance(response, dict) and "content" in response:
            content = response["content"]
            run_id = response["id"]
        else:
            raise ValueError("Unexpected response type")
        
        result["content"] = content
        
        # 处理引用信息
        if chunk_dict:
            ext_context_str = json.dumps(chunk_dict, default=json_serializer)
            await self.add_ai_ext_message(run_id, ext_context_str,db)
            
            logger.info(f"用户ID: {user_id}, AI回复 ext_context_str: {ext_context_str}")
            logger.info(f"用户ID: {user_id}, AI回复: {chunk_dict}")
            
            # 构建文件信息列表
            file_info_list = [
                {
                    "file_id": value["file_id"],
                    "file_name": value["file_name"],
                    "chunk_id": value["chunk_id"]
                }
                for value in chunk_dict.values()
            ]
            
            logger.info(f"用户ID: {user_id}, AI回复 file_info_list: {file_info_list}")
            result["file_info_list"] = file_info_list
        
        return result
    async def add_ai_ext_message(self, run_id: str, ext_context_str: str,db: AsyncSession):
        # async for db_session in get_db():
        ai_ext_message_service = AiExtMessageService(db)
        await ai_ext_message_service.create_ext(run_id,ext_context_str)
    

    async def clear_chains(self):
        self.user_chains.clear()
