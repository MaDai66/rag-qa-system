# -*- coding: utf-8 -*-
"""
A8 对比报告 —— 把多次跑的 tag 拉平成一张表。

用法：
    python eval/a8_compare.py baseline keep_order hybrid rerank

读 `results/<tag>_raw.json` + `<tag>_score.json`，写 `results/对比报告.md`。

设计上的两点：
1. **可复现性先于结论**。表头里带「上下文是否与 baseline 逐字一致」这一列 ——
   上下文一致说明检索侧真的没被随机性污染，后面的分数差才敢归因给改造本身。
2. **拒答率单列**。它的分母是 8 道无解题，跟另外几个指标不是一回事，混进均值里没有意义。
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

METRICS = [
    ("faithfulness", "忠实度", "仅可答"),
    ("answer_relevancy", "答案相关性", "仅可答"),
    ("context_recall", "上下文召回", "仅可答"),
    ("llm_context_precision_with_reference", "上下文精确", "仅可答"),
]


def load(tag):
    raw = json.loads((RESULTS / f"{tag}_raw.json").read_text(encoding="utf-8"))
    score_path = RESULTS / f"{tag}_score.json"
    score = json.loads(score_path.read_text(encoding="utf-8")) if score_path.exists() else None
    return raw, score


def agg(score, rows, metric):
    if not score:
        return None
    vals = [score["scores"].get(r["user_input"], {}).get(metric) for r in rows]
    # v == v 用来排掉 NaN —— NaN 是 float、也不 is None，漏掉它会污染整个均值
    vals = [v for v in vals if isinstance(v, (int, float)) and v == v]
    return sum(vals) / len(vals) if vals else None


def ctx_identical(raw, base_raw):
    """逐题比对检索上下文是否与 baseline 完全一致 —— 检索确定性的证据。"""
    if base_raw is None:
        return "—"
    b = {r["id"]: r["contexts"] for r in base_raw["records"]}
    tot = same = 0
    for r in raw["records"]:
        if r["id"] in b:
            tot += 1
            same += r["contexts"] == b[r["id"]]
    return f"{same}/{tot}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+", help="第一个作为 baseline，其余依次对比")
    ap.add_argument("--out", default="对比报告.md")
    args = ap.parse_args()

    loaded = {t: load(t) for t in args.tags}
    base_tag = args.tags[0]
    base_raw, _ = loaded[base_tag]

    L = ["# 检索改造对比报告", ""]
    L += ["| tag | " + " | ".join(m[1] for m in METRICS) + " | 拒答率 | 平均耗时 | 平均召回段数 | 上下文同 baseline |",
          "|---|" + "---|" * (len(METRICS) + 5)]
    for tag in args.tags:
        raw, score = loaded[tag]
        answered = [r for r in raw["records"] if r["answer"]]
        answerable = [r for r in answered if r["type"] != "拒答型"]
        cells = []
        for metric, _, scope in METRICS:
            rows = answered if scope == "全部" else answerable
            v = agg(score, rows, metric)
            cells.append("—" if v is None else f"{v:.3f}")
        ref = score["refusal"] if score else None
        refusal = f"{ref['refused']}/{ref['n']}" if ref else "—"
        lat = [r["latency_s"] for r in answered]
        nctx = [len(r["contexts"]) for r in answered]
        L.append(f"| **{tag}** | " + " | ".join(cells)
                 + f" | {refusal} | {sum(lat)/len(lat):.2f}s | {sum(nctx)/len(nctx):.2f} | {ctx_identical(raw, base_raw)} |")

    # ── 噪声带 ──────────────────────────────────────────────────────────
    # 这堆指标都过 LLM 裁判，裁判本身是随机的。所以「涨了一点」未必是真的涨。
    # 怎么把噪声量出来：找两份**原始数据完全相同**（答案+上下文逐字一致）的 tag，
    # 它们之间的一切差异 100% 来自裁判重跑 —— 那就是噪声。
    # 拿它当尺子，小于它的差异一律读作「没变」。
    def _sig(raw):
        return json.dumps([(r["id"], r["answer"], r["contexts"]) for r in raw["records"]],
                          ensure_ascii=False, sort_keys=True)

    sigs = {t: _sig(r) for t, (r, _) in loaded.items()}

    # 「同条件」= 语料 + **有效**检索配置都一致。同条件的两个 tag 之间，一切差异都不是改造造成的。
    #
    # 为什么要归一化而不能直接比 config 字符串：`retrieval_config` 记的是**采集那一刻**
    # data_dictionary 里的行，而行数是会变的 —— 早期采集只记到 7 个键、后期记到 11 个，
    # 且早期那次记的是修复前的 `threshold_fulltext=0.05`。直接比字符串会判成不同条件。
    # 归一化规则：补齐默认值 + 丢掉「当前模式下不参与检索」的键。
    # 实测背书：归一化后 baseline 与 baseline_run2 被判为同条件，
    # 而它们的检索上下文**45/45 逐字相同** —— 说明那个键确实不参与检索，不是我在硬凑。
    _DEFAULTS = {"search_mode": "embedding", "top_n": "5", "threshold_vector": "0.6",
                 "threshold_fulltext": "0", "keep_retrieval_order": "0",
                 "rerank_enabled": "0", "rerank_candidates": "20",
                 "rrf_enabled": "0"}

    def _eff(cfg):
        e = {k: str(cfg.get(k, v)) for k, v in _DEFAULTS.items()}
        if e["search_mode"] != "hybrid":
            e.pop("threshold_fulltext")      # 全文阈值只在 hybrid 分支里被读
            e.pop("rrf_enabled")             # RRF 只在 hybrid 分支里生效
        if e["rerank_enabled"] != "1":
            e.pop("rerank_candidates")       # 不开 rerank 就没人读它
        return e

    def _cond(t):
        raw = loaded[t][0]
        return raw.get("collection_id"), json.dumps(_eff(raw["retrieval_config"]), sort_keys=True)

    same_cond = [(a, b) for i, a in enumerate(args.tags) for b in args.tags[i + 1:]
                 if _cond(a) == _cond(b) and loaded[a][1] and loaded[b][1]]
    # 分两档，因为它们的含义不同：
    #   纯裁判   —— 原始数据逐字相同，差异 100% 来自裁判重跑
    #   含生成   —— 同条件重新采集过，差异 = 生成抖动 + 裁判噪声（跨 tag 比时该用这档）
    pure = [(a, b) for a, b in same_cond if sigs[a] == sigs[b]]
    full = [(a, b) for a, b in same_cond if sigs[a] != sigs[b]]

    def _answerable(tag):
        """可答题 = 有答案且非拒答型。Δ 和噪声带都只在这个口径上算（跟主表一致）。"""
        return [r for r in loaded[tag][0]["records"]
                if r["answer"] and r["type"] != "拒答型"]

    def _band(pairs):
        out = {}
        for metric, _, _ in METRICS:
            d = 0.0
            for a, b in pairs:
                va = agg(loaded[a][1], _answerable(a), metric)
                vb = agg(loaded[b][1], _answerable(b), metric)
                if va is not None and vb is not None:
                    d = max(d, abs(va - vb))
            out[metric] = d
        return out

    noise, noise_judge = _band(same_cond), _band(pure)
    noise_pairs = same_cond

    L += ["", "## 与 baseline 的差异（Δ）＋ 噪声带", ""]
    if noise_pairs:
        L += ["**噪声带 = 同条件的两个 tag 之间差多少**（语料 + 配置都一样，差异与改造无关）。",
              "`Δ` 后面标 `·` 的，表示**落进噪声带内、应当读作「没变」**。", ""]
        def _fmt(pairs):
            return "、".join(f"`{a}` vs `{b}`" for a, b in pairs)

        if pure:
            L.append(f"- **纯裁判噪声**（{_fmt(pure)}）：原始数据**逐字相同**，"
                     "差异 100% 来自裁判重跑。")
        if full:
            L.append(f"- **含生成噪声**（{_fmt(full)}）：同条件**重新采集**过，"
                     "差异 = 生成抖动 + 裁判噪声。")
        L += ["", "> **跨 tag 比大小要用「含生成」那一档** —— 两个 tag 的答案本来就是两次生成出来的。",
              "> 只有判断「同一份数据重打分稳不稳」才看纯裁判那一档。", "",
              "> ⚠️ **这个带子是下界，别当精确阈值用。** 它只由**同条件的少数几次跑**估出来，",
              "> 样本少 → 天然低估真实波动。而且均值稳不代表逐题稳：",
              "> 实测同一份数据重打分，忠实度**单题**摆动可达 0.200、上下文召回可达 **1.000**",
              "> —— 它们只是互相抵消了。37 题里翻一题 = 0.027，所以**贴着带子的 Δ 一律读作「说不清」**，",
              "> 只有**明显超出**（下面那种 +0.05 / +0.2 量级）才敢下结论。", ""]
    else:
        L += ["> ⚠️ 这次没有同条件对照 tag，**无法估噪声带** —— 下面所有 Δ 都缺少「多大才算真变了」的尺子。",
              "> 补法：同配置再跑一次采集打分（`collect --tag xxx_run2` + `score --tag xxx_run2`）。", ""]
    hdr = "| tag | " + " | ".join(m[1] for m in METRICS) + " |"
    L += [hdr, "|---|" + "---|" * len(METRICS)]
    base_score = loaded[base_tag][1]
    for tag in args.tags:
        if tag == base_tag or not loaded[tag][1]:
            L.append(f"| **{tag}** | " + " | ".join("—" for _ in METRICS) + " |")
            continue
        cells = []
        rows = _answerable(tag)
        for metric, _, scope in METRICS:
            v = agg(loaded[tag][1], rows, metric)
            b = agg(base_score, rows, metric)
            if v is None or b is None:
                cells.append("—")
                continue
            d = v - b
            mark = "·" if abs(d) <= noise[metric] else ""
            cells.append(f"{d:+.3f}{mark}")
        L.append(f"| **{tag}** | " + " | ".join(cells) + " |")
    if noise_pairs:
        rows = [("**噪声带 · 含生成**（跨 tag 该用这档）", noise)]
        if pure:
            rows.append(("噪声带 · 纯裁判", noise_judge))
        for name, band in rows:
            L += [f"| {name} | " + " | ".join(f"{band[m]:.3f}" for m, _, _ in METRICS) + " |"]
    L += ["", "> Δ 是**同一批题**上「该组 − baseline」的均值差，不是两个均值的差（题集随时可能变，同批相减才稳）。"]

    L += ["", "## 每次跑的检索配置", ""]
    for tag in args.tags:
        raw, _ = loaded[tag]
        cfg = raw["retrieval_config"]
        keys = ["search_mode", "top_n", "threshold_vector", "keep_retrieval_order",
                "rerank_enabled", "rerank_candidates", "rrf_enabled"]
        L.append(f"- **{tag}**：`{json.dumps({k: cfg.get(k) for k in keys if k in cfg}, ensure_ascii=False)}`")

    L += ["", "## 分类型指标", "",
          "> ⚠️ **对比型的「上下文精确」恒为 0.000 是结构性结果，不是检索质量** ——",
          "> 该指标拿**跨文档的参考答案**逐段去问裁判「这段能否支撑它」，而任何单段只能覆盖一篇文档，",
          "> 于是全判 0 → 平均精度的分子分母同时为 0 → 直接得 0。详见 `README.md` 坑 7。",
          "> **读这个指标只看「事实型」那一行。**",
          "",
          "| tag | 类型 | 题数 | 忠实度 | 答案相关性 | 上下文召回 | 上下文精确 |",
          "|---|---|---|---|---|---|---|"]
    for tag in args.tags:
        raw, score = loaded[tag]
        if not score:
            continue
        for t in sorted({r["type"] for r in base_raw["records"]}):
            if t == "拒答型":            # 拒答型不参与任何 RAGAS 指标，只用拒答率衡量
                continue
            rows = [r for r in raw["records"] if r["type"] == t and r["answer"]]
            if not rows:
                continue
            cells = []
            for metric, _, _ in METRICS:
                v = agg(score, rows, metric)
                cells.append("—" if v is None else f"{v:.3f}")
            L.append(f"| **{tag}** | {t} | {len(rows)} | " + " | ".join(cells) + " |")

    # ── 不过裁判的硬指标 ────────────────────────────────────────────────
    # 这堆 RAGAS 指标全靠 LLM 裁判，裁判本身有随机性（噪声带就是量它）。
    # 所以再看一组**完全不依赖裁判**的量：模型有没有明确说「答不出」。
    # 它是分类的（说了 / 没说），不受裁判波动影响 —— 均值差淹没在噪声里时，靠它定性。
    REFUSAL_OPEN = "根据现有资料无法回答"

    # ⚠️ 长答案里「到底答没答」没法用字符串规则判，只能读原文 —— 读过的判定登记在这里。
    # 这是整份报告里**唯一**一处人工判读，所以明写出来 + 下面把原文全贴出来供复核，
    # 而不是藏成一个看起来很像自动化的 `len(answer) < 80`。
    MANUAL_LONG_ANSWERED = {
        ("rerank_strict", "F14"): False,   # 99 字长拒答，末尾「因此无法给出确切答案」
        ("combo", "C05"): True,            # 238 字，jiebacfg/jiebaqry 的区别说全了
        ("rerank_strict", "C03"): False,   # 11 字，标准短拒答（列在这只是让它有据可查）
    }

    def _refusal_open(r):
        """答案是不是以「根据现有资料无法回答」开头（且不是拒答型题）。"""
        return (r["type"] != "拒答型" and r["answer"]
                and r["answer"].lstrip().startswith(REFUSAL_OPEN))
    L += ["", "## 硬指标：可答题里模型明确说「答不出」的题数（不过裁判）", "",
          "> 判据是答案**开头**是不是「根据现有资料无法回答」—— 纯字符串，没有裁判参与，",
          "> 所以它**不受裁判噪声影响**。均值差被噪声淹没时，靠这一列定性。", "",
          "> ⚠️ **改这一列之前，先看下面这份对照** —— 我原先以为「题号变了就是生成抖动」，",
          "> 实测**不是**：同配置重跑两次（`baseline` vs `baseline_run2`），",
          "> 检索 45/45 逐字相同，**答案逐字相同的只有 20/45**（56% 换了措辞，最低相似度 0.468），",
          "> 但「答不出」的题号**两份完全一致，零翻转**。",
          "> 结论：**措辞不稳、定性结论稳** —— 这个字符串判据比它看起来可靠。",
          "> 所以 `order` 组把 F14/C07 翻过来，**不能归给抖动**：它和 baseline 只差上下文顺序，",
          "> 而同配置重跑零翻转，那两处翻转只能归给**排序**。", "",
          "> ⚠️ 但「开头拒答」**不等于**「没答」，还得再判一层。我原先用「答案短于 80 字」，",
          "> 实测**两个方向都会错**，各抓到一例 —— 所以这个脚本不猜，改成**逐条读过原文 + 登记判定**：",
          "> - **误判成「答了」**：`rerank_strict` 的 F14 是 **99 字长拒答**，",
          ">   末尾写着「因此无法给出确切答案」—— 它没答，只是啰嗦。",
          "> - **误判成「答不出」**：`combo` 的 C05 有 **238 字**，前半截说「无法回答」，",
          ">   后半截把 `jiebacfg` / `jiebaqry` 的区别**说全了**，只是被检索里混进来的",
          ">   无关段落弄得不敢确认。这本身是个失败模式：",
          ">   **检索垃圾不只是稀释上下文，还能把答对的题逼成拒答。**",
          "> 长度只是第一道筛子，长答案一律看原文。判定登记在脚本的 `MANUAL_LONG_ANSWERED` 里，",
          "> 并且下面把**所有**拒答式开头的答案原文全贴出来，供复核。", "",
          "| tag | 开头拒答 | **真答不出** | 其中：长答案但人工判定「答了内容」 | 真答不出的题号 |",
          "|---|---|---|---|---|"]
    for tag in args.tags:
        really, soft = [], []
        for r in loaded[tag][0]["records"]:
            if not _refusal_open(r):
                continue
            if len(r["answer"]) >= 80 and MANUAL_LONG_ANSWERED.get((tag, r["id"])):
                soft.append(r["id"])
            else:
                really.append(r["id"])
        unregistered = [r["id"] for r in loaded[tag][0]["records"]
                        if _refusal_open(r) and len(r["answer"]) >= 80
                        and (tag, r["id"]) not in MANUAL_LONG_ANSWERED]
        if unregistered:
            print(f"  [warn] {tag} 有未登记的长拒答答案：{unregistered}"
                  f" —— 读原文后补进 MANUAL_LONG_ANSWERED（现在是保守当「答不出」算的）")
        L.append(f"| **{tag}** | {len(really) + len(soft)}/37 | **{len(really)}** | "
                 f"{', '.join(soft) or '—'} | {', '.join(really) or '—'} |")

    # 把原文全贴出来 —— 上面那张表是人工判读的结果，人工判读就必须可复核。
    L += ["", "<details><summary>点开：所有「拒答式开头」的答案原文（供复核上表的判定）</summary>", ""]
    for tag in args.tags:
        rows = [r for r in loaded[tag][0]["records"] if _refusal_open(r)]
        if not rows:
            continue
        L.append(f"- **`{tag}`**")
        for r in rows:
            mark = "✅ 判定：答了内容" if MANUAL_LONG_ANSWERED.get((tag, r["id"])) else "❌ 判定：真答不出"
            L.append(f"  - `{r['id']}`（{len(r['answer'])} 字）{mark} —— "
                     f"{r['answer'][:200].replace(chr(10), ' ')}")
    L += ["", "</details>"]

    # ── 修复矩阵 ────────────────────────────────────────────────────────
    # 把上面那些数字压成一句人话：**哪个改造治好了哪个病**。
    # 行 = 有任何一组答不出的题；列 = tag；格子 = ✅答得出 / ❌答不出。
    # 这张表是整份报告的落点 —— 它把「指标涨了 0.03」这种噪声里的东西，
    # 换成「这一题修好了 / 没修好」这种看得见的事实。
    # 判据和上面「硬指标」表**逐字一致**（开头拒答 + 长答案看 MANUAL 登记）——
    # 两处口径一旦不一致，矩阵和数字表就会互相打脸。
    def _stuck_set(tag):
        return {r["id"] for r in loaded[tag][0]["records"]
                if _refusal_open(r)
                and not (len(r["answer"]) >= 80 and MANUAL_LONG_ANSWERED.get((tag, r["id"])))}

    stuck_all = {t: _stuck_set(t) for t in args.tags}
    problem_ids = sorted(set().union(*stuck_all.values())) if stuck_all else []
    if problem_ids:
        L += ["", "## 修复矩阵：哪个改造治好了哪个病", "",
              "> 行 = 至少有一组答不出的题；格子 = 该组**答得出** ✅ / **答不出** ❌。",
              "> 这张表是整份报告的落点：它把「指标涨了 0.03 算不算涨」这种判不清的问题，",
              "> 换成「这一题修好了没有」这种看得见的事实。", "",
              "| 题号 | " + " | ".join(args.tags) + " |",
              "|---|" + "---|" * len(args.tags)]
        for qid in problem_ids:
            cells = ["✅" if qid not in stuck_all[t] else "❌" for t in args.tags]
            L.append(f"| **{qid}** | " + " | ".join(cells) + " |")
        L += ["| 合计答不出 | " + " | ".join(f"{len(stuck_all[t])}" for t in args.tags) + " |"]
        # 反查：每题是谁修好的。分两种情形 —— baseline 就没答出的（找修好者），
        # 和 baseline 答得出、别组反而答不出的（那说明有改造**引入**了倒退，必须单列）。
        L += ["", "**反查：每一题是谁修好的**", ""]
        for qid in problem_ids:
            if qid in stuck_all[args.tags[0]]:
                fixers = [t for t in args.tags[1:] if qid not in stuck_all[t]]
                L.append(f"- **{qid}**："
                         + ("、".join(f"`{t}`" for t in fixers) if fixers
                            else "❌ **没有一组修好**"))
            else:
                broke = [t for t in args.tags[1:] if qid in stuck_all[t]]
                L.append(f"- **{qid}**：baseline 答得出，但 "
                         + "、".join(f"`{t}`" for t in broke)
                         + " 答不出 ⚠️ **这是改造引入的倒退**")
        L += ["", "> ⚠️ 注意「修好」不等于「稳定修好」：每组只跑了一次。",
              "> 唯一验过稳定性的是同条件三次重跑（`baseline` / `_repeat` / `_run2`）"
              "—— 三次的答不出题号**完全一致**，所以反面（没修好）比较可信；",
              "> 正面（修好了）建议再看一眼「上下文同 baseline」那一列确认机制。"]

    # 「答案层面的拒答」：题目是可答题，但模型实际答不出来。
    # 它们会被 answer_relevancy 判 0（正确的惩罚），但会拉低均值 —— 单列出来才看得清。
    # 只列「真答不出」的（口径同上）。**不能**列所有开头拒答的 ——
    # C05 那种「答了内容但用拒答开头」的题列进来，会和上面那张表的判定直接打架。
    L += ["", "## 可答题里真答不出的（这些题的分数是被判负的源头）", "",
          "> 口径同上面的「硬指标」表：开头拒答 **且**（短答案 或 人工判定确实没答）。",
          "> 「拒答式开头但其实答了内容」的不列入 —— 它们仍会被裁判压低分，但不属于「答不出」。", "",
          "| tag | 题号 | 题目 |", "|---|---|---|"]
    for tag in args.tags:
        stuck = _stuck_set(tag)
        for r in loaded[tag][0]["records"]:
            if r["id"] in stuck:
                L.append(f"| {tag} | {r['id']} | {r['user_input'][:50]} |")

    out = RESULTS / args.out
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
