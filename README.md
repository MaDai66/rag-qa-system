# RAG 知识库问答系统 · 检索改造与评测

一个可以在本地跑起来的中文 RAG 问答后端：**FastAPI + PostgreSQL/pgvector + LangChain**。
支持向量检索、全文检索、RRF 融合、交叉编码器重排，并且**带一套可复现的评测**——
45 题评测集、RAGAS 四项指标、9 组检索配置的横向对比。

比"又一个 RAG demo"多做的一件事是：**每次改造都有数字，且改造带来的差异能和噪声区分开。**

---

## 一句话结论

在 45 题评测集上，**零成本组合（保留检索顺序 + 混合检索 + 重新分块）用 +10% 的延迟拿到了四项指标里三项的明显提升**；
重排（rerank）能把上下文精确度推到最高，但延迟是 baseline 的 **3.6 倍**——在本地部署场景里不划算。

| 配置 | 忠实度 | 答案相关性 | 上下文召回 | 上下文精确 | 平均耗时 |
|---|---|---|---|---|---|
| baseline | 0.930 | 0.860 | 0.937 | 0.412 | 1.14s |
| + 保留检索顺序 | 0.964 | 0.911 | 0.883 | 0.613 | 1.22s |
| + 混合检索（RRF） | 0.942 | 0.876 | 0.946 | 0.278 | 1.08s |
| + 重新分块 | 0.972 | 0.933 | 0.946 | 0.350 | 1.20s |
| **combo（三者叠加）** | **0.953** | **0.928** | 0.919 | **0.618** | **1.26s** |
| + 交叉编码器重排 | 0.976 | 0.900 | 0.896 | **0.671** | 4.06s |

> 拒答型 8 题在**所有配置下都是 8/8 正确拒答**——这道防线不是靠调参保住的，是所有配置共有的。
> 完整对比、噪声带和逐项 Δ 见 [`eval/results/对比报告.md`](eval/results/对比报告.md)。

⚠️ **关于「噪声带」**：同一份数据重打分，单项指标本身就会抖动。所以报告里所有 Δ 都标了是否落进噪声带，
贴着带子的差异一律读作「没变」。这是这份评测里我最在意的一点——**不把抖动当成果。**

---

## 这是怎么来的（说明清楚，不遮）

工程骨架来自 **DeerFlow**（字节跳动开源项目，MIT 协议）的课程实战版本，我在此基础上做的是：

- 检索链路改造（下节详述，集中在 `src/handler/`，新增及改写约 200 行）
- 整套评测体系（`eval/`，从评测集设计到对比脚本到噪声带，全部自建）
- 环境搭建与排障记录（[`环境搭建记录.md`](环境搭建记录.md)，含 9 个实际踩到的坑）

原项目的 MIT 协议与版权声明保留在 [`LICENSE.txt`](LICENSE.txt)。

---

## 检索链路改了什么

四处，都在 `src/handler/`：

**1. 检索顺序丢失的修复** — [`chat_model_handler.py:270`](src/handler/chat_model_handler.py)
检索算出来的相关性顺序，在拼上下文那一步被丢掉了，喂给模型的 5 段变成了**数据库物理存储顺序**。
这不只是位置偏置的问题：RAGAS 的 `context_precision` 是按上下文顺序算 MAP 的，
顺序一乱，这个指标测出来的其实是随机顺序下的下界。加了 `keep_retrieval_order` 开关。

**2. RRF 融合** — [`chat_model_handler.py:226`](src/handler/chat_model_handler.py)
向量检索和全文检索的结果用 Reciprocal Rank Fusion 合并（`score = Σ 1/(k + rank)`，k=60）。
只改顺序，不增删候选。

**3. 交叉编码器重排** — [`rerank.py`](src/handler/rerank.py)（新文件，61 行）
bge-reranker 精排，**失败时退回原顺序**，不让重排把整条检索拖挂。

**4. 重新分块（SMART_CHUNKING）** — [`partition_handler.py`](src/handler/vector/partition_handler.py)
原来的定长切分会把句子从中间切断。改成按段落边界优先、句子边界兜底。

> 检索参数（开关、top_n、阈值）走 `data_dictionary` 表，不写死在代码里，改配置不用重启。

---

## 评测体系

`eval/` 下四个脚本，依赖不同、可以分开跑：

| 脚本 | 做什么 | 依赖 |
|---|---|---|
| [`a3_judge_test.py`](eval/a3_judge_test.py) | **先验证裁判本身**：确认 LLM 裁判认得出忠实答案、也抓得住编造 | LLM |
| [`a5_eval.py`](eval/a5_eval.py) | 采集 + RAGAS 打分，`collect` / `score` 两段拆开 | LLM + 向量模型 |
| [`a7_chunk_audit.py`](eval/a7_chunk_audit.py) | 分块质量离线审计：碎片率、词被切断比例 | **不连库、不调 LLM** |
| [`a8_compare.py`](eval/a8_compare.py) | 把多个 tag 拉平成对比表，自带噪声带判定 | 纯文件 |

**评测集 45 题**（[`eval/评估集.json`](eval/评估集.json)）：30 道事实题 + 7 道对比题 + 8 道**拒答题**。
拒答题是故意问文档里没有的东西——看系统会不会老实说"不知道"，而不是编一个。

指标口径：

- 忠实度 / 答案相关性 / 上下文召回 / 上下文精确 —— 只算 **37 道可答题**
- 拒答题不参与 RAGAS 指标，单独看**拒答率**
- 每题带 `reference` 和 `source`，能定位到具体是哪一段答错了

---

## 技术栈

`Python 3.12` · `FastAPI` · `SQLAlchemy(async)` · `PostgreSQL + pgvector` · `LangChain 1.x`
· `bge-large-zh-v1.5`（向量）· `bge-reranker`（重排）· `DeepSeek`（生成 + 裁判）· `RAGAS`（评测）

---

## 快速开始

```bash
# 1. 依赖
pip install -e .

# 2. 数据库：需要 PostgreSQL + pgvector 扩展
export PG_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/langchat"
cp conf.example.yaml conf.yaml       # conf.yaml 已在 .gitignore，不会被提交

# 3. 建表
python scripts/init_db.py

# 4. 起服务
python server.py
```

`uploads/` 里有 8 份中文测试语料（三国演义节选、科普短文）。

**跑评测**（需要先把上面的服务和数据库跑起来）：

```bash
python eval/a5_eval.py all --tag baseline       # 基线
python eval/a5_eval.py all --tag my_change      # 改完再跑一版，换 tag 别覆盖
python eval/a8_compare.py baseline my_change    # 出对比表
```

评分需要 `DEEPSEEK_API_KEY`（环境变量，或仓库根目录的 `.env`）。
向量模型默认用 HuggingFace 的 `BAAI/bge-large-zh-v1.5`，本地已有权重的话设
`EMBEDDING_MODEL_PATH` 指过去，省掉下载。

---

## 目录结构

```
src/
├── api/          # FastAPI 路由（chat / files / chunks / collections）
├── handler/      # 检索与生成的核心
│   ├── search.py            # 向量检索 / 全文检索
│   ├── rerank.py            # 交叉编码器重排
│   ├── chat_model_handler.py# RRF 融合、顺序保留、上下文拼装
│   └── vector/partition_handler.py  # 文档切分
├── dao/ models/ schemas/     # 数据层
└── core/         # 配置、常量、异常
eval/             # 评测集 + 四个评测脚本 + 每次跑的结果
```

---

## 已知边界

写在这里，免得被当成没有：

- **规模没测过。** 语料只有 8 份文档、几千个 chunk。千万级没有做过。
- **没有权限隔离。** 单用户场景，多租户和文档级权限没做。
- **没上过线。** 全部在本地 Docker + 本机服务上跑，没有部署到公网过。
- **评测集是我自己写的 45 题**，不是公开 benchmark，题目分布有我的偏好。
- **只在 Windows + 本地 PostgreSQL 上跑通过**，Linux 没验证。

---

## License

MIT（沿用 DeerFlow 的协议，见 [`LICENSE.txt`](LICENSE.txt)）。
