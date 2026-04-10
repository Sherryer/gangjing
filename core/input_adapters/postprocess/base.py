"""
ASR 后处理策略基类
=================

所有语言策略继承此类，实现三个能力：
  1. split()  — 标点切分（长段按句末标点拆成短句）
  2. clean()  — 规则清理（去 filler、标点规范化等）
  3. tag()    — 置信度标注（标记疑似识别错误）

BaseStrategy 本身提供语言无关的通用兜底实现：
  - split: 按 . ! ? ; 切分（覆盖中英文常见句末标点）
  - clean: 去掉纯空白段、strip
  - tag:   仅用通用规则（单字符重复检测）

新增语言只需：
  1. 在 postprocess/ 下新建 xx.py
  2. 继承 BaseStrategy，覆写需要的方法
  3. 在 __init__.py 的 REGISTRY 中注册
"""

from __future__ import annotations

import re
from dataclasses import replace

from core.input_adapters.models import Segment


# 尾部标点（跨语言通用）
TRAILING_PUNCT = re.compile(r'[。！？!?，,、.\s]+$')

# 通用句末标点（含英文句号，兜底用）
_SENTENCE_ENDS_UNIVERSAL = re.compile(r'([.。！？!?；;]+)')

# 切分最小长度（短于此不切）
_MIN_SPLIT_LEN = 50


class BaseStrategy:
    """
    语言无关的兜底策略。
    不做任何语言特定处理，仅做安全的通用操作。
    """

    # ── 标点切分模式（子类可覆写） ──
    SENTENCE_ENDS = _SENTENCE_ENDS_UNIVERSAL

    # ── 0. 标点切分 ──

    def split(self, segments: list[Segment]) -> list[Segment]:
        """
        按句末标点对长段落做二次切分。
        时间戳按字符比例线性插值分配。
        子类可覆写 SENTENCE_ENDS 属性来改变切分模式。
        """
        result: list[Segment] = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            if len(text) < _MIN_SPLIT_LEN or not self.SENTENCE_ENDS.search(text):
                result.append(seg)
                continue

            parts = self.SENTENCE_ENDS.split(text)
            sentences: list[str] = []
            i = 0
            while i < len(parts):
                s = parts[i]
                if (i + 1 < len(parts)
                        and self.SENTENCE_ENDS.fullmatch(parts[i + 1])):
                    s += parts[i + 1]
                    i += 2
                else:
                    i += 1
                s = s.strip()
                if s:
                    sentences.append(s)

            if len(sentences) <= 1:
                result.append(seg)
                continue

            total_chars = sum(len(s) for s in sentences)
            total_duration = seg.end - seg.start
            current_time = seg.start

            for sentence in sentences:
                ratio = (len(sentence) / total_chars
                         if total_chars > 0
                         else 1.0 / len(sentences))
                seg_duration = total_duration * ratio
                result.append(Segment(
                    start=current_time,
                    end=current_time + seg_duration,
                    text=sentence,
                    emotion=seg.emotion,
                    event=seg.event,
                ))
                current_time += seg_duration

        return result

    # ── 1. 规则清理 ──

    def clean(self, segments: list[Segment]) -> list[Segment]:
        """
        规则清理。返回清理后的 segments 列表。
        基类：仅 strip 空白。
        """
        result = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            result.append(replace(seg, text=text))
        return result

    # ── 2. 置信度标注 ──

    def tag(self, segments: list[Segment]) -> list[Segment]:
        """
        置信度标注。基类：仅用通用规则。
        """
        result = []
        for seg in segments:
            suspicious = self._check_universal(seg)
            result.append(replace(seg, suspicious=suspicious))
        return result

    # ── 组合入口 ──

    def process(self, segments: list[Segment]) -> list[Segment]:
        """split → clean → tag 的完整流水线。一般不需要覆写。"""
        segments = self.split(segments)
        segments = self.clean(segments)
        segments = self.tag(segments)
        return segments

    # ── 通用检测规则（所有语言共享） ──

    def _check_universal(self, seg: Segment) -> bool:
        """
        语言无关的通用可疑检测：
          - 单字符重复 3 次以上（"aaa"、"的的的的"）
        """
        core = self._strip_punct(seg.text)
        if not core:
            return True
        if re.search(r'(.)\1{2,}', core):
            return True
        return False

    # ── 工具方法（供子类使用） ──

    @staticmethod
    def _strip_punct(text: str) -> str:
        """去掉尾部标点，返回核心文字"""
        return TRAILING_PUNCT.sub('', text).strip()
