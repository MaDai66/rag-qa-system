# -*- coding: utf-8 -*-
"""
ragas 0.4.3 兼容补丁 —— 必须在 import ragas 之前导入。

问题：ragas/llms/base.py:12 硬 import 了
      `langchain_community.chat_models.vertexai.ChatVertexAI`，
      而 langchain-community 0.4 已经把这个模块拆出去（独立成 langchain-google-vertexai）。
      于是 `import ragas` 直接 ModuleNotFoundError。

为什么打补丁是安全的：翻 ragas/llms/base.py:38-53 可以看到，ChatVertexAI 只出现在
      `MULTIPLE_COMPLETION_SUPPORTED` 列表里，供 `is_multiple_completion_supported()`
      做 isinstance 判断。我们用 DeepSeek 当裁判，这个分支永远走不到。

替代方案（都不如补丁）：降 langchain-community 会打断 langchat 运行；
      装 langchain-google-vertexai 要拖进整套 google 依赖，只为这一个 isinstance。
"""
import sys
import types

_MOD = "langchain_community.chat_models.vertexai"

if _MOD not in sys.modules:
    try:
        import langchain_community.chat_models.vertexai  # noqa: F401
    except ModuleNotFoundError:
        _shim = types.ModuleType(_MOD)

        class ChatVertexAI:  # 占位符，只为让 isinstance 列表能构造出来
            pass

        _shim.ChatVertexAI = ChatVertexAI
        sys.modules[_MOD] = _shim
