# -*- coding: utf-8 -*-
"""
A5 评测脚本 —— 把《评估集》跑成数字。

用法（在仓库根目录下）：

    python eval/a5_eval.py all     --tag baseline
    python eval/a5_eval.py collect --tag baseline
    python eval/a5_eval.py score   --tag baseline

    # 冒烟：只跑 3 题，确认链路通了再跑全量
    python eval/a5_eval.py all --tag smoke --limit 3

为什么拆成 collect / score 两段
--------------------------------
`collect` 走的是真接口（真的检索、真的调 DeepSeek 生成），
所以它贵在"真实"，一次采集的结果要能反复用；
`score` 是折腾段（换指标、调裁判、重算），几百次 LLM 调用中途挂掉很常见。
两段各自落盘，打分失败不会把采集结果一起带走。

评测口径（为什么拒答型不跟其他题一起算分）
------------------------------------------
拒答型题目的「参考答案」是"文档里没有，应当拒答"，
这意味着它的 reference 天然不可能出现在检索上下文里 ——
context_recall 必然为 0、context_precision 必然为 0。
把它们混在一起算均值，等于用 8 道结构上不可能得分的题去拉低整体分数。

所以：
  · faithfulness / answer_relevancy —— 全部 40 题都算（这两项不依赖 reference）
  · context_recall / context_precision —— 只算 37 道可答题
  · 拒答型 —— 单独看"拒答率"（有没有老实说不知道，而不是编）
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                                  # 仓库根目录（langchat/）
RESULTS = HERE / "results"

BASE_URL = os.getenv("EVAL_BASE_URL", "http://127.0.0.1:8000")
TEST_USER_ID = os.getenv("EVAL_USER_ID", "11111111-1111-1111-1111-111111111111")
DEFAULT_COLLECTION = os.getenv("EVAL_COLLECTION_ID",
                               "426c2b35-c94e-11f1-96c8-2c981197eb9e")

# 本机模型权重路径优先顺序：环境变量 → eval/local_paths.py（已 gitignore）→ HuggingFace 仓库名
try:
    from local_paths import EMBEDDING_MODEL_PATH as _LOCAL_EMBEDDING_PATH
except ImportError:
    _LOCAL_EMBEDDING_PATH = None
EMBEDDING_PATH = (os.getenv("EMBEDDING_MODEL_PATH")
                  or _LOCAL_EMBEDDING_PATH
                  or "BAAI/bge-large-zh-v1.5")

REFUSAL_MARKERS = [
    "没有提到", "未提及", "没有提及", "文档中没有", "文中没有", "文中未",
    "没有相关信息", "无相关信息", "没有给出", "未给出", "没有说明", "未说明",
    "无法回答", "无法确定", "无法从", "资料中没有", "不包含", "未涉及",
]


# --------------------------------------------------------------------------
# 采集
# --------------------------------------------------------------------------

def read_config():
    """尽力记录这次跑的是哪套检索配置。取不到就标 unknown，不影响评测。"""
    try:
        import psycopg
        import yaml

        conf = yaml.safe_load((ROOT / "conf.yaml").read_text(encoding="utf-8"))
        url = conf["db"]["url"].replace("+psycopg", "").replace("+asyncpg", "")
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            cur.execute("SELECT key, value FROM data_dictionary WHERE key <> 'deepseek_api_key' "
                        "AND key NOT LIKE 'prompt%' ORDER BY key")
            return dict(cur.fetchall())
    except Exception as exc:                                     # noqa: BLE001
        return {"_error": f"{type(exc).__name__}: {exc}"}


def collect(tag: str, collection_id: str, limit: int | None, only: str | None):
    items = json.loads((HERE / "评估集.json").read_text(encoding="utf-8"))
    if only:
        wanted = {t.strip() for t in only.split(",")}
        items = [it for it in items if it["type"] in wanted]
    if limit:
        items = items[:limit]

    config = read_config()
    print(f"采集 {len(items)} 题 → tag={tag}")
    print(f"当前检索配置：{config}\n")

    records, t_start = [], time.time()
    for i, it in enumerate(items, 1):
        # 关键：每题之前清空聊天历史。
        # chain 是 RunnableWithMessageHistory，session_id 就是 user_id ——
        # 不清的话第 20 题的上下文里躺着前 19 题的问答，等于给模型开卷提示，分数全虚高。
        try:
            requests.post(f"{BASE_URL}/api/v1/chat/clear-history",
                          params={"user_id": TEST_USER_ID}, timeout=30)
        except Exception as exc:                                 # noqa: BLE001
            print(f"  [warn] 清历史失败：{exc}")

        t0 = time.time()
        try:
            resp = requests.post(
                f"{BASE_URL}/api/v1/chat/",
                json={"user_id": TEST_USER_ID, "message": it["user_input"],
                      "collection_id": collection_id},
                timeout=300,
            )
            resp.raise_for_status()
            body = resp.json()
            cost = time.time() - t0

            if body.get("code") not in (200, 0) and not body.get("data"):
                raise RuntimeError(f"接口返回异常：{json.dumps(body, ensure_ascii=False)[:200]}")

            data = body.get("data") or {}
            answer = data.get("content", "")
            contexts = data.get("contexts") or []
            filenames = sorted({f["file_name"] for f in (data.get("file_info_list") or [])})
        except Exception as exc:                                 # noqa: BLE001
            cost = time.time() - t0
            answer, contexts, filenames = "", [], []
            print(f"[{i:>2}/{len(items)}] {it['id']} ❌ {type(exc).__name__}: {exc}")

        if answer:
            print(f"[{i:>2}/{len(items)}] {it['id']} {it['type']}  {cost:5.2f}s  "
                  f"召回 {len(contexts)} 段  {filenames}")

        records.append({
            **it,
            "answer": answer,
            "contexts": contexts,
            "retrieved_files": filenames,
            "latency_s": round(cost, 2),
        })

    out = {
        "tag": tag,
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "collection_id": collection_id,
        "retrieval_config": config,
        "total_latency_s": round(time.time() - t_start, 1),
        "records": records,
    }
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{tag}_raw.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for r in records if r["answer"])
    lat = [r["latency_s"] for r in records if r["answer"]]
    print(f"\n采集完成：{ok}/{len(records)} 题有答案")
    if lat:
        print(f"单题耗时：平均 {sum(lat) / len(lat):.2f}s，最慢 {max(lat):.2f}s")
    print(f"→ {path}")
    return path


# --------------------------------------------------------------------------
# 打分
# --------------------------------------------------------------------------

def _judge_and_embeddings():
    sys.path.insert(0, str(HERE))
    import _compat                                              # noqa: F401
    from langchain_deepseek import ChatDeepSeek
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        for env_path in (ROOT / ".env", ROOT.parent / ".env"):
            if not env_path.exists():
                continue
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("DEEPSEEK_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if key:
                break
    if not key:
        raise SystemExit("没找到 DEEPSEEK_API_KEY：设置环境变量，或在 .env 里写 "
                         "DEEPSEEK_API_KEY=sk-...")

    judge = LangchainLLMWrapper(
        ChatDeepSeek(model="deepseek-chat", api_key=key, temperature=0.0))
    embed = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name=EMBEDDING_PATH,
                              encode_kwargs={"normalize_embeddings": True}))
    return judge, embed


def _score_group(name, metrics, samples, judge, embed):
    """跑一组指标，返回 {user_input: 分数}。一组一个 evaluate 调用，挂一个不带走另一个。"""
    from ragas import EvaluationDataset, evaluate
    from ragas.run_config import RunConfig

    if not samples:
        return {}
    print(f"\n=== {name}：{len(samples)} 题 ===")
    try:
        # 默认 timeout=180s，实测 DeepSeek 偶发超时（一次跑里挂了 2 个 job），放宽到 10 分钟
        result = evaluate(dataset=EvaluationDataset(samples=samples), metrics=metrics,
                          llm=judge, embeddings=embed, show_progress=True,
                          run_config=RunConfig(timeout=600, max_retries=3))
    except Exception as exc:                                     # noqa: BLE001
        # 一组几百次 LLM 调用，中途挂掉是常态；不能让它把已经算好的指标一起带走
        print(f"⚠️  {name} 这一组失败：{type(exc).__name__}: {exc}")
        return {}
    df = result.to_pandas()
    out = {}
    for _, row in df.iterrows():
        out[row["user_input"]] = {m.name: row.get(m.name) for m in metrics}
    return out


def score(tag: str):
    raw = json.loads((RESULTS / f"{tag}_raw.json").read_text(encoding="utf-8"))
    judge, embed = _judge_and_embeddings()

    import _compat                                              # noqa: F401
    from ragas import SingleTurnSample
    from ragas.metrics._answer_relevance import ResponseRelevancy
    from ragas.metrics._context_precision import LLMContextPrecisionWithReference
    from ragas.metrics._context_recall import LLMContextRecall
    from ragas.metrics._faithfulness import Faithfulness

    answered = [r for r in raw["records"] if r["answer"]]
    answerable = [r for r in answered if r["type"] != "拒答型"]
    print(f"总 {len(raw['records'])} 题，有答案 {len(answered)} 题，其中可答 {len(answerable)} 题")

    def mk(rows):
        return [SingleTurnSample(user_input=r["user_input"],
                                 retrieved_contexts=r["contexts"] or [""],
                                 response=r["answer"],
                                 reference=r["reference"]) for r in rows]

    # 上下文全空的题（可能被阈值过滤光了）RAGAS 会算崩，单独挑出来标记
    empty = [r["id"] for r in answered if not r["contexts"]]
    if empty:
        print(f"⚠️  没有召回任何上下文的题：{empty}")

    scores = {}

    def merge(group):
        # 必须按题面**合并**指标字典。
        # 原来写的是 scores.update(group) —— 那是顶层替换：后一组的 {题面: 指标} 会
        # 整个覆盖前一组的同名题面，结果是「每组只活下自己那批题、前面全丢」。
        # 表现极具迷惑性：45 题被 context 组覆盖 37 题后，恰好剩 8 道拒答题
        # 带着 answer_relevancy，看起来像「拒答题特例」，其实是覆盖顺序的产物。
        for ui, d in group.items():
            scores.setdefault(ui, {}).update(d)

    merge(_score_group("faithfulness（仅可答题）",
                       [Faithfulness(llm=judge)], mk(answerable), judge, embed))
    merge(_score_group("answer_relevancy（仅可答题）",
                       # strictness 就是「每个答案生成几个问题」，ragas 默认 3，
                       # 但它是通过 n=3 传给 LLM 的，而 DeepSeek 只支持 n=1，
                       # 不设成 1 会整组 400 报错（踩过）。
                       [ResponseRelevancy(llm=judge, embeddings=embed, strictness=1)],
                       mk(answerable), judge, embed))
    merge(_score_group("context_recall + context_precision（仅可答题）",
                       [LLMContextRecall(llm=judge),
                        LLMContextPrecisionWithReference(llm=judge)],
                       mk(answerable), judge, embed))

    # 拒答型：不看 RAGAS，看有没有老实说"不知道"
    refusals, hallucinated = [], []
    for r in raw["records"]:
        if r["type"] != "拒答型" or not r["answer"]:
            continue
        hit = [m for m in REFUSAL_MARKERS if m in r["answer"]]
        (refusals if hit else hallucinated).append((r["id"], r["answer"][:80], hit))

    out = {
        "tag": tag,
        "scored_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "retrieval_config": raw["retrieval_config"],
        # 必须记下来：rechunk 那组的检索配置和 baseline **逐字相同**，
        # 唯一的变量是「语料落在哪个 collection」，而 chunking 策略是入库时决定的、
        # 不出现在 retrieval_config 里。不记的话这份报告在纸面上和 baseline 无法区分。
        "collection_id": raw.get("collection_id", "?"),
        "n_total": len(raw["records"]),
        "n_answered": len(answered),
        "n_answerable": len(answerable),
        "scores": scores,
        "refusal": {
            "n": len(refusals) + len(hallucinated),
            "refused": len(refusals),
            "hallucinated": [{"id": i, "answer": a} for i, a, _ in hallucinated],
        },
    }
    (RESULTS / f"{tag}_score.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    write_report(tag, out, raw)
    return out


def write_report(tag, out, raw):
    """出一份能直接看的 Markdown —— 简历/汇报要用的是这张表，不是 JSON。"""
    by_type = {}
    for r in raw["records"]:
        by_type.setdefault(r["type"], []).append(r)

    def agg(rows, metric):
        vals = [out["scores"].get(r["user_input"], {}).get(metric) for r in rows]
        # 必须显式排掉 NaN：它 isinstance(float) 也 is not None，
        # 只要有一个 NaN，sum() 就把整个均值污染成 nan（踩过）。
        vals = [v for v in vals if isinstance(v, (int, float)) and v == v]
        return sum(vals) / len(vals) if vals else float("nan"), len(vals)

    answered = [r for r in raw["records"] if r["answer"]]
    answerable = [r for r in answered if r["type"] != "拒答型"]

    lines = [
        f"# 评测报告 · {tag}",
        "",
        f"- 时间：{out['scored_at']}",
        f"- 题目：{out['n_total']} 题（有答案 {out['n_answered']}），可答 {out['n_answerable']} 题",
        f"- 拒答型不参与 RAGAS 指标，只用拒答率衡量（理由见 `评测/README.md`）",
        f"- 检索配置：`{json.dumps(out['retrieval_config'], ensure_ascii=False)}`",
        # 语料（collection）变了但配置没变的情况必须显式标出来 —— 否则报告自相矛盾。
        (f"- 语料：`{out.get('collection_id', '?')}`"
         + ("" if out.get("collection_id") == DEFAULT_COLLECTION
            else "  ⚠️ **非 baseline 语料**（入库时用了不同的分块策略）")),
        "",
        "## 总体指标",
        "",
        "| 指标 | 均值 | 有效题数 |",
        "|---|---|---|",
    ]
    for metric, rows in [("faithfulness", answerable),
                         ("answer_relevancy", answerable),
                         ("context_recall", answerable),
                         ("llm_context_precision_with_reference", answerable)]:
        m, n = agg(rows, metric)
        lines.append(f"| {metric} | {m:.3f} | {n} |")

    lines += ["", "## 拒答型（8 题）", "",
              f"拒答 {out['refusal']['refused']} / {out['refusal']['n']}", ""]
    if out["refusal"]["hallucinated"]:
        lines.append("**编造了答案的题（要人工看）**：")
        lines.append("")
        for h in out["refusal"]["hallucinated"]:
            lines.append(f"- `{h['id']}` {h['answer']}")
        lines.append("")

    lines += ["## 分类型", "", "| 类型 | 题数 | faithfulness | answer_relevancy |", "|---|---|---|---|"]
    for t, rows in by_type.items():
        f, _ = agg(rows, "faithfulness")
        a, _ = agg(rows, "answer_relevancy")
        lines.append(f"| {t} | {len(rows)} | {f:.3f} | {a:.3f} |")

    lines += ["", "## 逐题", "", "| id | 类型 | 耗时 | 召回段数 | faithfulness | answer_rel | ctx_recall | ctx_prec |",
              "|---|---|---|---|---|---|---|---|"]
    for r in raw["records"]:
        s = out["scores"].get(r["user_input"], {})
        def fmt(k):
            v = s.get(k)
            return f"{v:.2f}" if isinstance(v, (int, float)) else "—"
        lines.append(f"| {r['id']} | {r['type']} | {r['latency_s']:.1f}s | {len(r['contexts'])} "
                     f"| {fmt('faithfulness')} | {fmt('answer_relevancy')} "
                     f"| {fmt('context_recall')} | {fmt('llm_context_precision_with_reference')} |")

    path = RESULTS / f"{tag}_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n→ {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["collect", "score", "all"])
    ap.add_argument("--tag", default="baseline", help="结果文件前缀，如 baseline / hybrid")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 题（冒烟用）")
    ap.add_argument("--only", default=None, help="只跑某类，如 '拒答型' 或 '事实型,对比型'")
    args = ap.parse_args()

    if args.stage in ("collect", "all"):
        if args.tag == "smoke" and not args.limit:
            args.limit = 3
        collect(args.tag, args.collection, args.limit, args.only)
    if args.stage in ("score", "all"):
        score(args.tag)


if __name__ == "__main__":
    main()
