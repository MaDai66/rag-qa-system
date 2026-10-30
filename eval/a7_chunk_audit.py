# -*- coding: utf-8 -*-
"""
A7 分块审计 —— 不连数据库、不调 LLM，纯离线量化分块质量。

用法：
    python eval/a7_chunk_audit.py             # 四种配置全跑，出对照表
    python eval/a7_chunk_audit.py --mode both # 只跑一种

存在的理由：README 里「分块策略」那一节的数字（碎片率 12% → 0%）原先是一次性
临时脚本算的，没留档 —— 等于不可复现。这个脚本把它固定下来。

═══ 为什么要拆成四种配置 ═══
`partition_handler.py` 的 `SMART_CHUNKING` 开关**打包了两处改动**：
  ① 中文标点 separators   ② 短块合并回前一块
这跟 rerank 那组的混淆变量是同一类毛病 —— 只知道「合起来变好了」，
说不出是哪一条在起作用。而这两条的成本完全不同：
separators 是零成本的构造参数，短块合并要在入库流程里多跑一遍后处理。
所以必须拆开看。
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
UPLOADS = ROOT / "uploads"
sys.path.insert(0, str(ROOT))

from langchain_community.document_loaders import TextLoader          # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
MIN_CHUNK_CHARS = 120

# ⚠️ 只有这 7 个文件进了 collection（对着 chunk 表核过：83 段 = 20+18+15+13+8+5+4）。
# `三国演义.txt` 躺在 uploads/ 但**没入库**，而它一本书就有 3046 段 ——
# 放进来会占全表 97%，把碎片率从 12% 抬到 20%，测的是一个没人用的语料。
# 所以这里显式限定，并且对漏掉的文件打印告警（不静默丢弃）。
CORPUS_FILES = [
    "养生时代来临，怎么养生.txt",
    "减肥陷阱.txt",
    "蜂王浆对肺结节有没有影响.txt",
    "西安交通大学.txt",
    "宴桃园豪杰三结义.txt",
    "用奇谋孔明借箭 献密计黄盖受刑.txt",
    "诸葛亮智算华容 关云长义释曹操.txt",
]

# 项目原始配置：英文导向的 separators（langchain 的默认值）
SEP_ORIGINAL = ["\n\n", "\n", " ", ""]
# 加了中文标点，切点落在句子边界
SEP_CHINESE = ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]

MODES = ["none", "sep", "merge", "both"]


def split(docs, use_chinese_sep: bool, do_merge: bool):
    sp = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=SEP_CHINESE if use_chinese_sep else SEP_ORIGINAL,
    )
    chunks = sp.split_documents(docs)
    if do_merge:
        merged = []
        for d in chunks:
            if merged and len(d.page_content) < MIN_CHUNK_CHARS:
                merged[-1].page_content += "\n" + d.page_content
            else:
                merged.append(d)
        chunks = merged
    return [c.page_content for c in chunks]


def audit(mode: str):
    use_sep = mode in ("sep", "both")
    do_merge = mode in ("merge", "both")
    total, frags, lens = 0, 0, []
    per_file = {}
    for f in sorted(UPLOADS.glob("*.txt")):
        if f.name not in CORPUS_FILES:
            continue
        docs = TextLoader(str(f), encoding="utf-8").load()
        chunks = split(docs, use_sep, do_merge)
        n_frag = sum(1 for c in chunks if len(c) < MIN_CHUNK_CHARS)
        total += len(chunks)
        frags += n_frag
        lens += [len(c) for c in chunks]
        per_file[f.name] = (len(chunks), n_frag)
    return {
        "mode": mode,
        "chunks": total,
        "frags": frags,
        "rate": frags / total * 100 if total else 0,
        "mean_len": sum(lens) / len(lens) if lens else 0,
        "per_file": per_file,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, help="只跑一种；不给则四种都跑")
    args = ap.parse_args()

    if not UPLOADS.is_dir():
        sys.exit(f"找不到语料目录：{UPLOADS}")

    modes = [args.mode] if args.mode else MODES
    results = [audit(m) for m in modes]

    label = {"none": "原始（英文 separators，无合并）",
             "sep": "+ 只加中文标点 separators",
             "merge": "+ 只做短块合并",
             "both": "+ 两条都做（= SMART_CHUNKING=True）"}

    present = {f.name for f in UPLOADS.glob("*.txt")}
    print(f"\n语料：{UPLOADS}")
    print(f"     入库 {len(CORPUS_FILES)} 个文件；uploads/ 里另有 {len(present - set(CORPUS_FILES))} 个未入库"
          f"（{', '.join(sorted(present - set(CORPUS_FILES))) or '无'}）—— 已排除")
    print(f"参数：chunk_size={CHUNK_SIZE} overlap={CHUNK_OVERLAP} 碎片阈值<{MIN_CHUNK_CHARS}字\n")
    print("| 配置 | 总段数 | 碎片块 | 碎片率 | 平均段长 |")
    print("|---|---|---|---|---|")
    for r in results:
        print(f"| {label[r['mode']]} | {r['chunks']} | {r['frags']} | "
              f"**{r['rate']:.1f}%** | {r['mean_len']:.0f} 字 |")

    print("\n### 逐文件碎片数（<阈值 的块）\n")
    files = sorted({f for r in results for f in r["per_file"]})
    print("| 文件 | " + " | ".join(label[r["mode"]].split("（")[0] for r in results) + " |")
    print("|---|" + "---|" * len(results))
    for f in files:
        cells = [f"{r['per_file'][f][0]}段/{r['per_file'][f][1]}碎" for r in results]
        print(f"| {f} | " + " | ".join(cells) + " |")

    print("\n### 词被从中间切断的检查：`10-HDA` 能不能在被召回的同一块里读到\n")
    print("> 判据是「**同一块里能不能读出这个词**」—— 所以先把空白（含换行）去掉再匹配。")
    print("> 三种状态要分开报，混成一个「有没有」会把结论判反（第一版就判反了）：")
    print("> 短块合并用 `\\n` 拼接、且 overlap 会把那个连字符**复制一份**，")
    print("> 合出来是 `10 -\\n- HDA` → 归一化 `10--HDA`，跟干净 token 差一个连字符。\n")
    fw = UPLOADS / "蜂王浆对肺结节有没有影响.txt"
    if fw.exists():
        docs = TextLoader(str(fw), encoding="utf-8").load()
        pat_clean = re.compile(r"10-HDA")      # 干净 token
        pat_squashed = re.compile(r"10--HDA")  # 归一化后才像 → 有 overlap 污染
        tok = {}
        for r in results:
            chunks = split(docs, r["mode"] in ("sep", "both"), r["mode"] in ("merge", "both"))
            norm = [re.sub(r"\s+", "", c) for c in chunks]
            clean = [i for i, n in enumerate(norm) if pat_clean.search(n)]
            squashed = [i for i, n in enumerate(norm) if pat_squashed.search(n)]
            tok[r["mode"]] = ("✅ 干净" if clean
                              else "⚠️ 同块但被 overlap 污染" if squashed else "❌ 分在两个块")
            if clean:
                print(f"- **{label[r['mode']]}**：✅ 段{clean} 里是**干净** token")
            elif squashed:
                print(f"- **{label[r['mode']]}**：⚠️ 段{squashed} 两半已**并进同一块**，"
                      f"但被 overlap 污染成 `10--HDA`（语义读得出，字节不干净）")
            else:
                print(f"- **{label[r['mode']]}**：❌ 两半**分在两个块里**，信息永久分离")
                for i, c in enumerate(chunks):
                    if "10 -" in c or "- HDA" in c:
                        print(f"    - 段[{i}] 尾部：…{c[-40:]!r}")
                        if i + 1 < len(chunks):
                            print(f"    - 段[{i+1}] 首部：{chunks[i+1][:40]!r}")

    print("\n### 结论：两条改动各治什么\n")
    e = {r["mode"]: r for r in results}
    if len(e) == len(MODES):
        print("| 改动 | 10-HDA 状态 | 碎片率 |")
        print("|---|---|---|")
        for m in MODES:
            print(f"| {label[m]} | {tok.get(m, '—')} | {e[m]['rate']:.1f}% "
                  f"({e[m]['frags']}/{e[m]['chunks']}) |")
        print("\n> 答案和我原先写进 README 的**不一样**，以这张表为准：")
        print("> - **碎片率几乎全靠「短块合并」**：只合并 → 0.0%；只加标点 → 12.2%（比原始 12.0% 还略高）。")
        print("> - **「词被切断」两条都能治**，但形式不同：标点给**干净** token；")
        print(">   只合并不是真修好 —— 它把两半并进同一块，代价是 overlap 复制出一个连字符（`10--HDA`）。")
        print("> - 所以 `SMART_CHUNKING` 打包这两处是合理的：**合并治碎片、标点治切点**，")
        print(">   但**主力是合并**，标点是消除残留瑕疵的那一步。")
        print("\n> ⚠️ 局限：这里只做了**离线分块审计**，两个子改动**没有各自跑端到端评测** ——")
        print("> 端到端只验证了打包版（`--tag rechunk`）。所以「哪一条单独就能让 F14 答对」"
              "目前只有上面这份离线证据，没有分数背书。")


if __name__ == "__main__":
    main()
