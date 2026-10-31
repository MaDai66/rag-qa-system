# RAG 知识库问答系统

中文 RAG 问答后端，FastAPI + PostgreSQL/pgvector + LangChain。
支持向量检索、全文检索、RRF 融合和交叉编码器重排，仓库里带了一套评测脚本，用来量化每次改动到底有没有用。

## 链路

```mermaid
flowchart LR
    subgraph ingest[入库]
        D[文档] --> P[切分<br/>优先段落边界]
        P --> V[bge-large-zh<br/>向量化]
        P --> T[全文索引]
        V --> DB[(PostgreSQL<br/>pgvector)]
        T --> DB
    end

    subgraph query[查询]
        Q[提问] --> S1[向量检索]
        Q --> S2[全文检索]
        S1 --> R[RRF 融合]
        S2 --> R
        R --> O[按检索顺序加载 chunk]
        O --> K[交叉编码器重排]
        K --> C[拼接上下文]
        C --> M[DeepSeek 生成]
        M --> A[答案 + 引用]
    end

    DB -.-> S1
    DB -.-> S2
```

两条检索并行发出，RRF 只调整顺序、不增删候选，重排失败时退回 RRF 的顺序，链路不会整体挂掉。四个开关都存在 `data_dictionary` 表里，改配置不用重启。

## 结论

在 45 题评测集上，保留检索顺序、混合检索、重新分块这三项叠起来，延迟只多 10%，前三项指标都有提升。重排能把上下文精确度做到最高，但耗时是原来的 3.6 倍。

| 配置 | 忠实度 | 答案相关性 | 上下文召回 | 上下文精确 | 平均耗时 |
|---|---|---|---|---|---|
| baseline | 0.930 | 0.860 | 0.937 | 0.412 | 1.14s |
| 保留检索顺序 | 0.964 | 0.911 | 0.883 | 0.613 | 1.22s |
| 混合检索（RRF） | 0.942 | 0.876 | 0.946 | 0.278 | 1.08s |
| 重新分块 | 0.972 | 0.933 | 0.946 | 0.350 | 1.20s |
| 三项叠加 | 0.953 | 0.928 | 0.919 | 0.618 | 1.26s |
| 加交叉编码器重排 | 0.976 | 0.900 | 0.896 | 0.671 | 4.06s |

8 道拒答题在所有配置下都是全部拒答正确。完整的对比、噪声带和逐项差值在 [eval/results/对比报告.md](eval/results/对比报告.md)。

关于噪声带：同一份数据重新打一次分，指标本身就会抖。报告里每个差值都标注了有没有落在噪声带内，落在带内的算作没有变化。

## 一次真实的问答

评测集 C01 问的是两篇文档的对比：

> 减肥文章和养生文章在饮食建议上各侧重什么？有什么区别？

向量和全文两路各取回候选，RRF 融合后留下 5 段上下文，命中《养生时代来临，怎么养生.txt》和《减肥陷阱.txt》，耗时 2.05 秒。答案是这么结尾的：

> 养生文章的饮食建议更偏向日常营养的全面均衡与水分补充，目的是维持身体活力与健康；减肥文章的饮食建议在均衡饮食的基础上，更强调控制总能量摄入、规律进餐以及避免极端节食。

拒答题走另一条路。问「诸葛亮的身高是多少」，三篇三国片段只写了刘备、关羽、张飞的身高，系统回：

> 根据现有资料无法回答。

## 项目来源

工程骨架是 DeerFlow（字节跳动开源，MIT）的课程实战版本。在这个基础上我做的是：

- 检索链路改造，集中在 `src/handler/`，新增和改写约 200 行
- 评测脚本 `eval/`，包括评测集、打分、对比报告
- 环境搭建过程记在 [环境搭建记录.md](环境搭建记录.md)，踩过的坑都写在里面

原项目的 MIT 协议和版权声明保留在 [LICENSE.txt](LICENSE.txt)。

## 检索部分改了什么

四处改动，都在 `src/handler/`：

1. **检索顺序丢失**，[chat_model_handler.py:270](src/handler/chat_model_handler.py)
   检索算出来的相关性顺序，在拼上下文那一步被丢掉了，喂给模型的 5 段变成数据库的物理存储顺序。RAGAS 的 context_precision 按上下文顺序算 MAP，顺序一乱，这个指标测出来的是随机顺序下的下界。加了 `keep_retrieval_order` 开关。

2. **RRF 融合**，[chat_model_handler.py:226](src/handler/chat_model_handler.py)
   向量检索和全文检索的结果用 Reciprocal Rank Fusion 合并，`score = Σ 1/(k + rank)`，k 取 60。只改顺序，不增删候选。

3. **交叉编码器重排**，[rerank.py](src/handler/rerank.py)
   bge-reranker 精排，61 行。重排出错时退回原顺序，不会让整条检索挂掉。

4. **重新分块**，[partition_handler.py](src/handler/vector/partition_handler.py)
   原来的定长切分会把句子从中间切断，改成优先按段落边界切，不行再按句子边界。

检索参数（开关、top_n、阈值）存在 `data_dictionary` 表里，改配置不用重启。

## 评测

`eval/` 下有四个脚本，依赖不同，可以分开跑：

| 脚本 | 作用 | 依赖 |
|---|---|---|
| [a3_judge_test.py](eval/a3_judge_test.py) | 先验证裁判本身：确认 LLM 裁判认得出忠实答案，也抓得住编造 | LLM |
| [a5_eval.py](eval/a5_eval.py) | 采集和 RAGAS 打分，collect / score 分开 | LLM + 向量模型 |
| [a7_chunk_audit.py](eval/a7_chunk_audit.py) | 分块质量离线审计，看碎片率和词被切断的比例 | 不连库、不调 LLM |
| [a8_compare.py](eval/a8_compare.py) | 把多个 tag 拉平成对比表，带噪声带判定 | 只读文件 |

评测集 45 题（[eval/评估集.json](eval/评估集.json)）：30 道事实题、7 道对比题、8 道拒答题。拒答题问的是文档里没有的内容，看系统会不会老实说不知道。

打分口径：忠实度、答案相关性、上下文召回、上下文精确只算 37 道可答题，拒答题单独看拒答率。每题带 reference 和 source，答错了能定位到具体是哪一段。设计细节和踩的坑在 [eval/README.md](eval/README.md)。

## 技术栈

Python 3.12、FastAPI、SQLAlchemy(async)、PostgreSQL + pgvector、LangChain 1.x、bge-large-zh-v1.5（向量）、bge-reranker（重排）、DeepSeek（生成和裁判）、RAGAS（评测）。

## 跑起来

```bash
pip install -e .

# 需要 PostgreSQL + pgvector
export PG_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/langchat"
cp conf.example.yaml conf.yaml

python scripts/init_db.py
python server.py
```

`uploads/` 里有 8 份中文测试语料。

跑评测：

```bash
python eval/a5_eval.py all --tag baseline
python eval/a5_eval.py all --tag my_change
python eval/a8_compare.py baseline my_change
```

打分要 `DEEPSEEK_API_KEY`，放环境变量或根目录的 `.env`。向量模型默认从 HuggingFace 拉 `BAAI/bge-large-zh-v1.5`，本地有权重的话设 `EMBEDDING_MODEL_PATH` 指过去，省掉下载。

## 目录

```
src/
├── api/          FastAPI 路由
├── handler/      检索与生成
│   ├── search.py             向量检索、全文检索
│   ├── rerank.py             交叉编码器重排
│   ├── chat_model_handler.py RRF 融合、顺序保留、上下文拼装
│   └── vector/partition_handler.py  文档切分
├── dao/ models/ schemas/
└── core/
eval/             评测集、四个脚本、每次跑的结果
```

## 没做的地方

- 规模只测到 8 份文档、几千个 chunk，更大的语料没试过
- 没有权限隔离，只有单用户
- 只在本地跑过，没部署到公网
- 评测集是自己出的 45 题，不是公开 benchmark
- 只在 Windows + 本地 PostgreSQL 上跑通，Linux 没验证

## License

MIT，沿用 DeerFlow 的协议，见 [LICENSE.txt](LICENSE.txt)。
