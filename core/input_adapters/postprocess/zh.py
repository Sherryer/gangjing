"""
中文 ASR 后处理策略
==================

覆盖语言：zh（普通话）、yue（粤语）

标点切分：中文句末标点（。！？；），不含英文句号 .
  （避免小数点、缩写等被误切）

第一层（清理）：
  - 去掉纯 filler 段（呃、嗯、哎等）
  - 去掉段首 filler 词
  - 半角标点 → 全角

第二层（置信度标注）：
  - 通用规则（单字符重复）
  - 字符长度 + 时长粗筛
  - jieba 分词 + 词频验证精筛（区分"不是"和"耐吉性"）
"""

from __future__ import annotations

import re
from dataclasses import replace

from core.input_adapters.models import Segment
from .base import BaseStrategy


# ── 中文句末标点（不含英文句号，避免误切） ──
_SENTENCE_ENDS_ZH = re.compile(r'([。！？!?；;]+)')

# ── 中文 filler 模式 ──
_FILLER_ONLY = re.compile(
    r'^[呃嗯啊哦哈嗨唉噢嘛呀吧啦额哎呐嘿]*[。，、！？．．．…,.!? ]*$'
)
_LEADING_FILLER = re.compile(r'^[呃嗯额哎]+[，,、]\s*')

# 标点清理用
_PUNCT_ALL = re.compile(r'[。！？!?，,、\s.…]')

# ── jieba 延迟加载 ──
_jieba_loaded = False


def _ensure_jieba():
    global _jieba_loaded
    if not _jieba_loaded:
        import jieba
        jieba.setLogLevel(20)
        _jieba_loaded = True


def _word_quality_score(text: str) -> float:
    """
    分词质量分数：多字词（≥2字符）的字符数占总字符数的比例。
    返回 0.0 ~ 1.0，越高越可信。
    """
    import jieba
    _ensure_jieba()

    core = _PUNCT_ALL.sub('', text)
    if not core:
        return 0.0

    words = [w for w in jieba.cut(core) if len(w) > 0]
    if not words:
        return 0.0

    multi_char_count = sum(len(w) for w in words if len(w) >= 2)
    return multi_char_count / len(core)


def _has_known_word(text: str) -> bool:
    """检查文本中是否包含 jieba 词典中词频 > 0 的多字词"""
    import jieba
    _ensure_jieba()

    core = _PUNCT_ALL.sub('', text)
    words = [w for w in jieba.cut(core) if len(w) >= 2]
    return any(jieba.dt.FREQ.get(w, 0) > 0 for w in words)


class ChineseStrategy(BaseStrategy):
    """中文/粤语后处理策略"""

    # 覆写标点切分模式（中文标点，不含英文句号）
    SENTENCE_ENDS = _SENTENCE_ENDS_ZH

    # ── 第一层：规则清理 ──

    def clean(self, segments: list[Segment]) -> list[Segment]:
        # 先调基类做通用清理（strip 等）
        segments = super().clean(segments)

        result = []
        for seg in segments:
            text = seg.text

            # 纯 filler 整段丢弃
            if _FILLER_ONLY.fullmatch(text):
                continue

            # 去掉段首 filler（"呃，大家好" → "大家好"）
            text = _LEADING_FILLER.sub('', text)

            # 半角标点 → 全角
            text = text.replace(',', '，').replace('!', '！').replace('?', '？')

            if not text:
                continue

            result.append(replace(seg, text=text))
        return result

    # ── 第二层：置信度标注 ──

    def tag(self, segments: list[Segment]) -> list[Segment]:
        result = []
        for seg in segments:
            # 先检查通用规则
            if self._check_universal(seg):
                result.append(replace(seg, suspicious=True))
                continue

            # 再检查中文特定规则
            suspicious = self._check_chinese(seg)
            result.append(replace(seg, suspicious=suspicious))
        return result

    def _check_chinese(self, seg: Segment) -> bool:
        """
        中文置信度检测。

        策略：表层粗筛（字符长度+时长）→ 分词精筛（救回正确的短段）
        """
        core = self._strip_punct(seg.text)
        if not core:
            return True

        duration = seg.end - seg.start

        # 长段基本可信
        if len(core) > 8:
            return False

        # ── 表层粗筛 ──
        is_candidate = False

        if len(core) <= 3 and duration < 2.0:
            is_candidate = True

        if (len(core) <= 5
                and len(set(core)) == len(core)
                and duration < 3.0):
            is_candidate = True

        if not is_candidate:
            return False

        # ── 分词精筛：救回含已知词的短段 ──
        word_score = _word_quality_score(core)

        if word_score >= 0.5 and _has_known_word(core):
            return False  # 含已知高频词，救回

        return True
