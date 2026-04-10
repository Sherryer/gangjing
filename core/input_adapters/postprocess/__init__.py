"""
ASR 后处理策略注册表
===================

根据语言代码返回对应的后处理策略。
未注册的语言自动使用 BaseStrategy（安全兜底）。

扩展新语言：
  1. 新建 xx.py，继承 BaseStrategy
  2. 在 REGISTRY 中注册 {"xx": XxStrategy}
  3. 完成（无需改 video_asr.py 或其他文件）
"""

from __future__ import annotations

from .base import BaseStrategy

# ── 策略注册表 ──
# key: 语言代码（与 SenseVoice 的 language 参数一致）
# value: 策略类（非实例，延迟实例化）
REGISTRY: dict[str, type[BaseStrategy]] = {}

# 策略实例缓存（每种语言只实例化一次）
_cache: dict[str, BaseStrategy] = {}


def _register_builtin():
    """注册内置策略（延迟 import 避免启动开销）"""
    if REGISTRY:
        return

    from .zh import ChineseStrategy

    REGISTRY["zh"] = ChineseStrategy
    REGISTRY["yue"] = ChineseStrategy  # 粤语共享中文策略

    # 将来扩展：
    # from .en import EnglishStrategy
    # REGISTRY["en"] = EnglishStrategy


def get_strategy(language: str) -> BaseStrategy:
    """
    根据语言代码获取后处理策略实例。

    - 已注册的语言 → 返回对应策略
    - 未注册的语言（en/ja/ko/auto 等）→ 返回 BaseStrategy（安全兜底）
    - 结果有缓存，同一语言不会重复实例化
    """
    _register_builtin()

    if language not in _cache:
        strategy_cls = REGISTRY.get(language, BaseStrategy)
        _cache[language] = strategy_cls()

    return _cache[language]
