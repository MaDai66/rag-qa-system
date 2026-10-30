
# 数据库连接串走 conf.yaml 的 db.url（见 conf.example.yaml），不要写死在这里。

# 默认分页参数
DEFAULT_SKIP = 0
DEFAULT_LIMIT = 100


# 数据字典里面的key 
EMBEDDINGS_PATH = "embeddings_path"

OPENAI_API_KEY = "openai_api_key"
OPENAI_API_BASE = "openai_api_base"
TEMPERATURE = "temperature"

DEEPSEEK_API_KEY = "deepseek_api_key"

PROMPT_SYSTEM_KEY = "prompt_system"
PROMPT_RAG_SYSTEM_KEY = "prompt_system_rag"

RAG_SUFFIX = "_rag"

# 模型类型常量
LLM_MODEL = "llm_model"  # LLM模型类型
OPENAI_MODEL = "openai"  # OpenAI模型类型
DEEPSEEK_MODEL = "deepseek"  # DeepSeek模型类型
LLM_MODELS = [OPENAI_MODEL, DEEPSEEK_MODEL]  # 支持的LLM模型类型列表


SEARCH_MODE = "search_mode"
TOP_N = "top_n"
THRESHOLD_VECTOR = "threshold_vector"
THRESHOLD_FULLTEXT = "threshold_fulltext"

# 检索后处理开关（评测用：每项改造都能单独打开/关闭，才能单独回测）
KEEP_RETRIEVAL_ORDER = "keep_retrieval_order"  # 取正文时保持检索相关性顺序
RERANK_ENABLED = "rerank_enabled"
RERANK_CANDIDATES = "rerank_candidates"        # 精排前先召回多少条
RERANK_MODEL_PATH = "rerank_model_path"
RRF_ENABLED = "rrf_enabled"                    # hybrid 两路结果用 RRF 融合排序
