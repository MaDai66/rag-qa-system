# RRF 对比报告

- 日期：2026-10-27
- 目的：验证 hybrid 检索的两路结果用 RRF 融合排序，是否比「向量结果 + 全文结果直接拼接」更好
- 语料：`6df40759-c958-11f1-ab88-2c981197eb9e`（重切分语料）
- 题目：45 题（可答 37，拒答 8）
- 评测脚本：`评测/a5_eval.py`

## 结论

**RRF 在这套 37 题评测集上没有证明出稳定收益，默认保持 `rrf_enabled=0`。**

理由：

1. **候选集完全没变**：`combo` 与 `combo_rrf` 的 45 道题候选集 **45/45 完全相同**，只有 **40/45** 道题的顺序被改变。RRF 是排序融合，不是召回增强。
2. **生成指标落在噪声内**：`faithfulness`、`answer_relevancy` 相对 `combo_repeat` 的变化几乎为 0，95% bootstrap 区间都包含 0。
3. **context_recall 的 +0.028 不可信**：只有 `C04` 一题从 0 变成 1，但它的候选集与 baseline 完全相同；这是 LLM 判卷受顺序影响的噪声，不是检索真的多召回。
4. **context_precision 是唯一弱正向信号**：共同 36 题上 +0.0415，7 题升、4 题降、25 题不变；95% 区间接近 0，**不足以支撑“RRF 有效”**。

当前最优配置仍然是 `combo`：

```text
search_mode=hybrid
top_n=5
threshold_vector=0.6
threshold_fulltext=0
keep_retrieval_order=1
rerank_enabled=0
rrf_enabled=0
```

---

## 1. 实验设计

| 组 | 配置 | 作用 |
|---|---|---|
| `combo` | hybrid + 保序 + 重切分语料，`rrf_enabled=0` | baseline |
| `combo_repeat` | 与 `combo` 完全相同，重复跑一遍 | 估计生成/判卷噪声 |
| `combo_rrf` | 只把 `rrf_enabled` 从 `0` 改成 `1` | 实验组 |

三组使用同一 collection、同一批 45 题、同一套检索参数：

```json
{
  "search_mode": "hybrid",
  "top_n": "5",
  "threshold_vector": "0.6",
  "threshold_fulltext": "0",
  "keep_retrieval_order": "1",
  "rerank_enabled": "0",
  "rrf_enabled": "0/1",
  "temperature": "0.5",
  "llm_model": "deepseek"
}
```

RRF 公式：

```text
score(chunk) = Σ 1 / (k + rank),  k = 60
```

只改变顺序，不增删候选。

---

## 2. 候选集与顺序

| 对比 | 候选集相同 | 顺序相同 | 顺序改变 |
|---|---:|---:|---:|
| `combo` vs `combo_repeat` | 45/45 | 45/45 | 0 |
| `combo` vs `combo_rrf` | 45/45 | 5/45 | 40 |
| `combo_repeat` vs `combo_rrf` | 45/45 | 5/45 | 40 |

这张表是整份报告最重要的证据：**RRF 没有多召回任何一段内容，只改了顺序。**

---

## 3. 指标对比

### 3.1 生成指标（37 题共同有效）

| 指标 | combo | combo_repeat | combo_rrf | RRF vs repeat |
|---|---:|---:|---:|---:|
| faithfulness | 0.9533 | 0.9735 | 0.9759 | **+0.0024** |
| answer_relevancy | 0.9280 | 0.8995 | 0.9002 | **+0.0006** |

`combo` 和 `combo_repeat` 的上下文逐字相同，指标却差了 ±0.02～0.03，这就是生成和判卷的噪声带。RRF 相对 `combo_repeat` 的变化远小于噪声带。

95% bootstrap 区间：

- `faithfulness` RRF vs repeat：`+0.0024 [-0.0107, +0.0171]`
- `answer_relevancy` RRF vs repeat：`+0.0006 [-0.0119, +0.0145]`

均包含 0。

### 3.2 上下文指标（36 题共同有效）

RRF 报告里 `context_recall=0.944`、`context_precision=0.663`，看起来比 baseline 高；但这两项 **只有 36 个有效样本**：

- `F29` 的 `context_precision` 为 NaN
- `C05` 的 `context_recall` 为 NaN

原因：`context_recall + context_precision` 那一组 74 个 judge job 中有 2 个 `APITimeoutError`，重试后仍是 NaN。**不能拿 36 题的 0.944 直接减 37 题的 0.919。**

按三组共同有效的 36 题重算：

| 指标 | combo | combo_repeat | combo_rrf | RRF vs repeat |
|---|---:|---:|---:|---:|
| context_recall | 0.9167 | 0.9167 | 0.9444 | **+0.0278** |
| context_precision | 0.6215 | 0.6190 | 0.6630 | **+0.0440** |

逐题变化：

**context_recall（只有 1 题变化）**

| id | combo | combo_rrf | 说明 |
|---|---:|---:|---|
| C04 | 0.0 | 1.0 | 候选集相同，仅顺序变化；判卷噪声 |

其余 35 题不变。

**context_precision（7 题升、4 题降、25 题不变）**

| id | combo | combo_rrf | 方向 |
|---|---:|---:|---|
| F04 | 0.333 | 0.500 | ↑ |
| F05 | 0.500 | 1.000 | ↑ |
| F09 | 0.500 | 1.000 | ↑ |
| F15 | 0.250 | 0.500 | ↑ |
| F16 | 0.700 | 0.833 | ↑ |
| F24 | 0.756 | 1.000 | ↑ |
| C05 | 0.000 | 0.500 | ↑ |
| F23 | 0.500 | 0.333 | ↓ |
| F25 | 1.000 | 0.867 | ↓ |
| F30 | 0.500 | 0.333 | ↓ |
| C04 | 0.333 | 0.000 | ↓ |

95% bootstrap 区间：

- `context_recall` RRF vs repeat：`+0.0278 [0.0000, +0.0833]`
- `context_precision` RRF vs repeat：`+0.0440 [-0.0014, +0.0972]`
- `context_precision` RRF vs combo：`+0.0415 [-0.0103, +0.1000]`

`context_precision` 有正向迹象，但区间接近 0；`context_recall` 的区间完全由 `C04` 一题撑起，不能当作稳定收益。

---

## 4. 为什么不能算 RRF 的提升

### 4.1 候选集相同，recall 理论上不该变

RRF 只对两路结果的 chunk 做排序，不新增候选。候选集 45/45 相同的情况下，`context_recall` 作为集合指标不应该变化。`C04` 从 0 到 1，最合理的解释是 RAGAS 的 LLM judge 被上下文顺序影响，而不是检索变好了。

### 4.2 判卷本身有噪声

`combo` 与 `combo_repeat` 的上下文逐字相同、顺序也相同，但 `context_precision` 仍有 3 题发生变化：

| id | combo | combo_repeat |
|---|---:|---:|
| F15 | 0.250 | 0.417 |
| F24 | 0.756 | 0.833 |
| C04 | 0.333 | 0.000 |

相同输入的 judge 都有这种波动，RRF 的 +0.04 不能直接当成真实收益。

### 4.3 只有顺序敏感指标可能受益

`context_precision` 是按上下文顺序算的，RRF 改顺序确实可能影响它；这也是唯一有正向迹象的指标。但端到端没有体现：

- `faithfulness`：无变化
- `answer_relevancy`：无变化
- 拒答：三组都是 **8/8**，没有变好也没有变坏

如果 RRF 真的让模型更容易读到关键段落，至少应该在生成指标上留下痕迹；目前没有。

---

## 5. 建议

1. **默认保持 `rrf_enabled=0`**，代码和开关保留，不需要回滚。
2. **不要把“RRF 提升 X%”写进简历**。可以写：

   > 实现 hybrid 检索的 RRF 融合，并做 A/B 评测；在 37 题评测集上未观察到稳定收益，保持默认关闭。

   这是一个真实的工程结论，面试时比编一个数字更经得起追问。
3. **如果一定要继续验证**：把评测集扩到 100+ 题，或同一配置重复 3 轮，再看 `context_precision` 是否还在 +0.04 附近。当前 37 题不够。
4. **从求职优先级看，不建议再为 RRF 投入时间**。`combo` 已经是当前最优组合，继续调这个的收益远低于准备投递和面试。

---

## 附录 A：原始运行记录

以下是 `combo_rrf` 这次完整跑分的终端输出原样保留。

```text
$ .venv/python.exe 评测/a5_eval.py all --tag combo_rrf \
  --collection 6df40759-c958-11f1-ab88-2c981197eb9e
采集 45 题 → tag=combo_rrf
当前检索配置：{'embeddings_path': 'D:/HuggingFace/bge-large-zh-v1.5', 'keep_retrieval_order': '1', 'llm_model': 'deepseek', 'rerank_candidates': '20', 'rerank_enabled': '0', 'rerank_model_path': 'D:/HuggingFace/bge-reranker-base', 'rrf_enabled': '1', 'search_mode': 'hybrid', 'temperature': '0.5', 'threshold_fulltext': '0', 'threshold_vector': '0.6', 'top_n': '5'}

[ 1/45] F01 事实型   0.79s  召回 5 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt']
[ 2/45] F02 事实型   0.84s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '用奇谋孔明借箭 献密计黄盖受刑.txt']
[ 3/45] F03 事实型   1.20s  召回 5 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt']
[ 4/45] F04 事实型   1.08s  召回 8 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[ 5/45] F05 事实型   1.80s  召回 6 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt']
[ 6/45] F06 事实型   1.66s  召回 6 段  ['减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[ 7/45] F07 事实型   0.82s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[ 8/45] F08 事实型   1.01s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[ 9/45] F09 事实型   1.32s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[10/45] F10 事实型   1.25s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[11/45] F11 事实型   1.22s  召回 8 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[12/45] F12 事实型   1.22s  召回 5 段  ['蜂王浆对肺结节有没有影响.txt']
[13/45] F13 事实型   1.22s  召回 5 段  ['蜂王浆对肺结节有没有影响.txt']
[14/45] F14 事实型   1.27s  召回 6 段  ['蜂王浆对肺结节有没有影响.txt']
[15/45] F15 事实型   1.33s  召回 5 段  ['蜂王浆对肺结节有没有影响.txt']
[16/45] F16 事实型   1.49s  召回 7 段  ['蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[17/45] F17 事实型   0.96s  召回 6 段  ['养生时代来临，怎么养生.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[18/45] F18 事实型   1.10s  召回 7 段  ['养生时代来临，怎么养生.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[19/45] F19 事实型   1.02s  召回 8 段  ['养生时代来临，怎么养生.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[20/45] F20 事实型   1.14s  召回 8 段  ['减肥陷阱.txt', '西安交通大学.txt']
[21/45] F21 事实型   1.20s  召回 10 段  ['养生时代来临，怎么养生.txt', '宴桃园豪杰三结义.txt', '蜂王浆对肺结节有没有影响.txt']
[22/45] F22 事实型   1.37s  召回 10 段  ['养生时代来临，怎么养生.txt', '宴桃园豪杰三结义.txt', '蜂王浆对肺结节有没有影响.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[23/45] F23 事实型   1.08s  召回 8 段  ['养生时代来临，怎么养生.txt', '宴桃园豪杰三结义.txt', '蜂王浆对肺结节有没有影响.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[24/45] F24 事实型   1.07s  召回 6 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt']
[25/45] F25 事实型   1.13s  召回 6 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt']
[26/45] F26 事实型   1.05s  召回 6 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt']
[27/45] F27 事实型   1.24s  召回 7 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[28/45] F28 事实型   1.96s  召回 8 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[29/45] F29 事实型   1.24s  召回 8 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '蜂王浆对肺结节有 没有影响.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[30/45] F30 事实型   1.49s  召回 9 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[31/45] C01 对比型   3.02s  召回 9 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '宴桃园豪杰三结义.txt', '用奇谋孔明借箭 献密计黄盖受刑.txt', '蜂王浆对肺结节有没有影响.txt']
[32/45] C02 对比型   2.76s  召回 7 段  ['减肥陷阱.txt', '宴桃园豪杰三结义.txt']
[33/45] C03 对比型   2.80s  召回 5 段  ['减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[34/45] C04 对比型   2.87s  召回 8 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[35/45] C05 对比型   2.48s  召回 7 段  ['减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[36/45] C06 对比型   2.78s  召回 7 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[37/45] C07 对比型   3.83s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[38/45] R01 拒答型   0.86s  召回 7 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '蜂王浆对肺结节有 没有影响.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[39/45] R02 拒答型   1.69s  召回 8 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']
[40/45] R03 拒答型   1.29s  召回 6 段  ['养生时代来临，怎么养生.txt', '西安交通大学.txt']
[41/45] R04 拒答型   1.48s  召回 5 段  ['养生时代来临，怎么养生.txt', '蜂王浆对肺结节有没有影响.txt', '西安交通大学.txt']
[42/45] R05 拒答型   1.21s  召回 6 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '用奇谋孔明借箭 献密计黄盖受刑.txt']
[43/45] R06 拒答型   1.20s  召回 8 段  ['养生时代来临，怎么养生.txt', '宴桃园豪杰三结义.txt', '蜂王浆对肺结节有没有影响.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[44/45] R07 拒答型   2.48s  召回 8 段  ['用奇谋孔明借箭 献密计黄盖受刑.txt', '诸葛亮智算华容 关云长义释曹操.txt']
[45/45] R08 拒答型   1.81s  召回 7 段  ['养生时代来临，怎么养生.txt', '减肥陷阱.txt', '蜂王浆对肺结节有没有影响.txt']

采集完成：45/45 题有答案
单题耗时：平均 1.54s，最慢 3.83s
→ C:\Users\sk\Desktop\我的资源\rag系统\LANGCHAIN-CODING\评测\results\combo_rrf_raw.json
C:\Users\sk\Desktop\我的资源\rag系统\LANGCHAIN-CODING\评测\a5_eval.py:178: DeprecationWarning: LangchainLLMWrapper is deprecated and will be removed in a future version. Use llm_factory instead: from openai import OpenAI; from ragas.llms import llm_factory; llm = llm_factory('gpt-4o-mini', client=OpenAI(api_key='...'))
  judge = LangchainLLMWrapper(
Loading weights: 100%|███████████████████████████████████| 391/391 [00:00<00:00, 28768.93it/s]
C:\Users\sk\Desktop\我的资源\rag系统\LANGCHAIN-CODING\评测\a5_eval.py:180: DeprecationWarning: LangchainEmbeddingsWrapper is deprecated and will be removed in a future version. Use the modern embedding providers instead: embedding_factory('openai', model='text-embedding-3-small', client=openai_client) or from ragas.embeddings import OpenAIEmbeddings, GoogleEmbeddings, HuggingFaceEmbeddings
  embed = LangchainEmbeddingsWrapper(
总 45 题，有答案 45 题，其中可答 37 题

=== faithfulness（仅可答题）：37 题 ===
Evaluating: 100%|█████████████████████████████████████████████| 37/37 [03:03<00:00,  4.97s/it]

=== answer_relevancy（仅可答题）：37 题 ===
Evaluating: 100%|█████████████████████████████████████████████| 37/37 [03:20<00:00,  5.42s/it]

=== context_recall + context_precision（仅可答题）：37 题 ===
Evaluating:  84%|█████████████████████████████████████▋       | 62/74 [11:27<03:18, 16.58s/it]Exception raised in Job[57]: APITimeoutError(Request timed out.)
Exception raised in Job[68]: APITimeoutError(Request timed out.)
Evaluating: 100%|█████████████████████████████████████████████| 74/74 [12:36<00:00, 10.23s/it]

→ C:\Users\sk\Desktop\我的资源\rag系统\LANGCHAIN-CODING\评测\results\combo_rrf_report.md
```

---

## 附录 B：RRF 核心实现

`langchat/src/handler/chat_model_handler.py`：

```python
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
```

调用位置：

```python
if opts and opts.get("rrf_enabled"):
    chunk_ids = self._rrf_fuse(vector_ids, fulltext_ids)
else:
    chunk_ids = vector_ids + fulltext_ids
```
