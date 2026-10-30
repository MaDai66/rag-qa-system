# -*- coding: utf-8 -*-
"""
A3 验证：RAGAS 的裁判模型换成 DeepSeek，并确认它真的会判分。

RAGAS 默认拿 OpenAI 当裁判（清单里点名的"必翻的第一个坑"），
这里换成 DeepSeek，然后故意喂两个方向相反的样本：

  样本 A —— 回答完全来自检索到的 context      → 期望 faithfulness 高分
  样本 B —— 回答编造了 context 里没有的内容    → 期望 faithfulness 0 分

只跑通不算验证通过；**两个方向都对**才说明裁判真的在工作。

用法：
    python eval/a3_judge_test.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # LANGCHAIN-CODING/
sys.path.insert(0, str(HERE))
import _compat  # noqa: F401,E402  —— 必须先于 ragas

from ragas import EvaluationDataset, SingleTurnSample, evaluate      # noqa: E402
from ragas.llms import LangchainLLMWrapper                           # noqa: E402
from ragas.metrics._faithfulness import Faithfulness                 # noqa: E402

from langchain_deepseek import ChatDeepSeek                          # noqa: E402


def read_deepseek_key():
    """优先读环境变量，其次 .env（仓库根或其上一级）；只返回，不打印。"""
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        return key
    for env_path in (ROOT / ".env", ROOT.parent / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("没找到 DEEPSEEK_API_KEY：设置环境变量，或在 .env 里写 "
                     "DEEPSEEK_API_KEY=sk-...")


CTX = ("蜂王浆中的抗氧化成分可中和自由基，降低氧化损伤；抗炎物质能缓解炎症。"
       "但目前关于蜂王浆对肺结节影响的临床研究相对有限，不能简单判定对所有患者都有明确疗效，"
       "也没有证据表明蜂王浆会刺激肺结节生长。")

SAMPLES = [
    SingleTurnSample(
        user_input="蜂王浆对肺结节有什么影响？",
        retrieved_contexts=[CTX],
        response=("蜂王浆的抗氧化和抗炎成分可能有助于减轻肺部的氧化损伤和炎症反应。"
                  "但目前临床研究相对有限，不能判定对所有肺结节患者都有明确疗效，"
                  "也没有证据表明它会刺激结节生长。"),
    ),
    SingleTurnSample(
        user_input="蜂王浆对肺结节有什么影响？",
        retrieved_contexts=[CTX],
        response=("蜂王浆能在一周内让肺结节缩小一半，治愈率高达 90%，"
                  "这是 2024 年北京协和医院的临床结论。"),
    ),
]


def main():
    judge = LangchainLLMWrapper(
        ChatDeepSeek(model="deepseek-chat", api_key=read_deepseek_key(), temperature=0.0)
    )
    print("裁判模型：DeepSeek (deepseek-chat)\n")

    result = evaluate(
        dataset=EvaluationDataset(samples=SAMPLES),
        metrics=[Faithfulness()],
        llm=judge,
        show_progress=False,
    )

    df = result.to_pandas()
    for i, row in df.iterrows():
        label = "样本 A（忠实）" if i == 0 else "样本 B（编造）"
        print(f"{label}: faithfulness = {row['faithfulness']:.2f}")
    print()

    a, b = df["faithfulness"].iloc[0], df["faithfulness"].iloc[1]
    if a > 0.8 and b < 0.2:
        print("✅ 通过：裁判既认得出忠实，也抓得住编造 —— DeepSeek 裁判可用")
    else:
        print(f"❌ 未达预期（A={a:.2f} 应 >0.8，B={b:.2f} 应 <0.2），需要排查")


if __name__ == "__main__":
    main()
