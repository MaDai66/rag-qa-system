# -*- coding: utf-8 -*-
"""交叉编码器重排（Cross-Encoder Rerank）。

向量检索是双塔（bi-encoder）：query 和文档**各自独立**编码成向量，再比余弦距离。
好处是文档向量可以离线算好、建索引；代价是 query 和文档之间没有交互，
只能比"整体像不像"，抓不住细粒度的词面匹配 —— 比如两个主题相近但细节不同的段落，
向量距离会几乎一样。

Reranker 是交叉编码器：把 `(query, 文档)` **拼在一起**过一遍模型，直接输出相关性分数。
精度明显更高，但每对都要现算、没法预先建索引，
所以只能对少量候选做精排，不能替代向量召回。

标准用法就是两段式：
    向量召回 candidate_n 条  →  reranker 打分  →  取 top_n

本文件用 sentence_transformers 的 CrossEncoder 加载 bge-reranker-base
（本地已有，CPU 也能跑：20 条候选大约 0.3~1 秒）。
"""
from sentence_transformers import CrossEncoder

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """进程内单例式持有模型，避免每次请求都重新加载权重。

    刻意不用 @singleton 装饰器：这个类要能被测试单独实例化，
    而且加载时机希望由调用方控制（第一次真正用到才加载，不拖慢启动）。
    """

    _instance = None

    def __init__(self):
        self._model = None
        self._model_path = None

    @classmethod
    def instance(cls) -> "Reranker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_model(self, model_path: str) -> CrossEncoder:
        if self._model is None or self._model_path != model_path:
            logger.info(f"加载 reranker 模型：{model_path}")
            self._model = CrossEncoder(model_path, max_length=512)
            self._model_path = model_path
            logger.info("reranker 模型加载完成")
        return self._model

    def rerank(self, query: str, texts: list[str], model_path: str,
               batch_size: int = 16) -> list[float]:
        """给 (query, text) 逐对打分，返回与 texts 等长的分数列表（越大越相关）。"""
        if not texts:
            return []
        model = self._ensure_model(model_path)
        pairs = [(query, t) for t in texts]
        scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
        return [float(s) for s in scores]
