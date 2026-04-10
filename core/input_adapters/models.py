"""
ASR 数据模型
============

Segment 和 ASRResult 的定义。
独立模块，避免循环依赖。
"""

from dataclasses import dataclass, field


@dataclass
class Segment:
    """单条字幕段"""
    start: float        # 开始时间（秒）
    end: float          # 结束时间（秒）
    text: str           # 识别文字
    emotion: str = ""   # 情绪标签（SenseVoice 特有）
    event: str = ""     # 音频事件（笑声/掌声等）
    suspicious: bool = False  # 疑似识别错误（置信度标注）

    @property
    def start_str(self) -> str:
        """格式化为 HH:MM:SS"""
        return _seconds_to_hms(self.start)

    @property
    def end_str(self) -> str:
        return _seconds_to_hms(self.end)


@dataclass
class ASRResult:
    file_path: str
    segments: list[Segment] = field(default_factory=list)
    full_text: str = ""           # 无时间戳的纯文字（方便直接 review）
    duration: float = 0.0         # 视频总时长（秒）
    language: str = ""            # 检测到的语言
    success: bool = False
    warning: str = ""
    error: str = ""
    metrics: dict = field(default_factory=dict)  # 各阶段耗时

    def get_metrics_text(self) -> str:
        """返回各阶段耗时报告"""
        if not self.metrics:
            return ""
        m = self.metrics
        lines = [
            "⏱ 各阶段耗时：",
            f"  音频提取:   {m.get('extract_audio', 0):.2f}s",
            f"  模型加载:   {m.get('model_load', 0):.2f}s",
            f"  VAD 分段:   {m.get('vad', 0):.2f}s",
            f"  ASR 推理:   {m.get('asr_inference', 0):.2f}s",
            f"  后处理:     {m.get('postprocess', 0):.2f}s",
            f"  总耗时:     {m.get('total', 0):.2f}s",
            f"  分段数:     {m.get('segment_count', 0)}",
            f"  总字符数:   {m.get('char_count', 0)}",
        ]
        return "\n".join(lines)

    def get_subtitle_text(self) -> str:
        """
        返回带时间戳的字幕文本，格式：
          [00:01:23 → 00:01:27] 这段话的内容 (情绪: 高兴)
        """
        lines = []
        for seg in self.segments:
            line = f"[{seg.start_str} → {seg.end_str}] {seg.text}"
            tags = []
            if seg.suspicious:
                tags.append("⚠️ 疑似识别错误")
            if seg.emotion and seg.emotion not in ("NEUTRAL", ""):
                tags.append(f"情绪:{seg.emotion}")
            if seg.event and seg.event not in ("Speech", ""):
                tags.append(f"事件:{seg.event}")
            if tags:
                line += f"  ({', '.join(tags)})"
            lines.append(line)
        return "\n".join(lines)


def _seconds_to_hms(seconds: float) -> str:
    """把秒数转成 HH:MM:SS 格式"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
