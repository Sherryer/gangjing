"""
视频 ASR 适配器
==============
用 SenseVoice-Small 从视频中提取字幕 + 时间戳，供杠精虾 review。

处理流程：
  1. ffmpeg 从视频中提取音频（wav 格式）
  2. SenseVoice-Small 跑 ASR，输出文字 + 时间戳 + 情绪标签
  3. 格式化成带时间戳的字幕文本，丢给 content_review 流程
  4. 支持按时间戳回溯截取视频帧（为视觉分析留口）

ASR 引擎：SenseVoice-Small（阿里达摩院）
  - 中文识别最优，比 Whisper-Small 快 5x+
  - 内置情绪检测（高兴/悲伤/愤怒/中性）和音频事件检测（笑声/掌声等）
  - 模型约 234MB，首次运行自动下载到 ~/.cache/modelscope/

依赖：
  pip install funasr modelscope torch torchaudio
  brew install ffmpeg  # 或 apt install ffmpeg
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# SenseVoice 支持的语言代码
SUPPORTED_LANGUAGES = {"zh", "yue", "en", "ja", "ko", "auto"}
DEFAULT_LANGUAGE = "zh"

# 模型标识（funasr 会自动从 modelscope 下载）
SENSEVOICE_MODEL_ID = "iic/SenseVoiceSmall"

# 单次处理音频最大时长（秒），超长视频建议分段
MAX_AUDIO_DURATION = 7200  # 2小时


@dataclass
class Segment:
    """单条字幕段"""
    start: float        # 开始时间（秒）
    end: float          # 结束时间（秒）
    text: str           # 识别文字
    emotion: str = ""   # 情绪标签（SenseVoice 特有）
    event: str = ""     # 音频事件（笑声/掌声等）

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

    def get_subtitle_text(self) -> str:
        """
        返回带时间戳的字幕文本，格式：
          [00:01:23 → 00:01:27] 这段话的内容 (情绪: 高兴)
        """
        lines = []
        for seg in self.segments:
            line = f"[{seg.start_str} → {seg.end_str}] {seg.text}"
            tags = []
            if seg.emotion and seg.emotion not in ("NEUTRAL", ""):
                tags.append(f"情绪:{seg.emotion}")
            if seg.event and seg.event not in ("Speech", ""):
                tags.append(f"事件:{seg.event}")
            if tags:
                line += f"  ({', '.join(tags)})"
            lines.append(line)
        return "\n".join(lines)


# ============================================================
# 公开接口
# ============================================================

def transcribe_video(
    file_path: str,
    language: str = DEFAULT_LANGUAGE,
) -> ASRResult:
    """
    对视频文件跑 ASR，返回字幕+时间戳。

    参数：
        file_path: 视频文件路径（mp4/mov/avi/mkv 等 ffmpeg 支持的格式）
        language:  语言代码，默认 "zh"，支持 "auto" 自动检测

    返回：
        ASRResult，通过 .get_subtitle_text() 取带时间戳字幕
    """
    path = Path(file_path).resolve()

    # --- 基础校验 ---
    if not path.exists():
        return ASRResult(file_path=str(path), success=False,
                         error=f"文件不存在: {path}")

    if language not in SUPPORTED_LANGUAGES:
        return ASRResult(file_path=str(path), success=False,
                         error=f"不支持的语言代码: {language}，可选: {SUPPORTED_LANGUAGES}")

    # --- 检查 ffmpeg ---
    if not _check_ffmpeg():
        return ASRResult(file_path=str(path), success=False,
                         error="未找到 ffmpeg，请先安装：brew install ffmpeg 或 apt install ffmpeg")

    # --- 检查 funasr ---
    try:
        from funasr import AutoModel  # type: ignore
    except ImportError:
        return ASRResult(file_path=str(path), success=False,
                         error="缺少依赖：请运行 pip install funasr modelscope torch torchaudio")

    print(f"[video_asr] 正在处理: {path.name}")

    # --- 提取音频到临时文件 ---
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")

        extract_ok, extract_err, duration = _extract_audio(str(path), audio_path)
        if not extract_ok:
            return ASRResult(file_path=str(path), success=False,
                             error=f"音频提取失败: {extract_err}")

        if duration > MAX_AUDIO_DURATION:
            return ASRResult(
                file_path=str(path), success=False,
                error=f"视频时长 {duration/3600:.1f}h 超过限制 {MAX_AUDIO_DURATION/3600:.0f}h，建议剪切后再处理"
            )

        print(f"[video_asr] 音频提取完成，时长: {_seconds_to_hms(duration)}，正在加载 SenseVoice 模型...")

        # --- 加载模型 & 推理 ---
        try:
            model = AutoModel(
                model=SENSEVOICE_MODEL_ID,
                trust_remote_code=True,
                disable_update=True,    # 不在推理时检查更新
            )

            res = model.generate(
                input=audio_path,
                cache={},
                language=language,
                use_itn=True,           # 数字/标点规范化
                batch_size_s=60,        # 每批处理 60s，平衡速度和内存
                merge_vad=True,         # 合并短句，减少碎片
            )

        except Exception as e:
            return ASRResult(file_path=str(path), success=False,
                             error=f"SenseVoice 推理失败: {type(e).__name__}: {e}")

        # --- 解析结果 ---
        segments = _parse_sensevoice_result(res)

        if not segments:
            return ASRResult(
                file_path=str(path), duration=duration,
                success=False,
                error="ASR 未识别到任何内容，请检查视频是否有语音"
            )

        full_text = " ".join(seg.text for seg in segments)
        print(f"[video_asr] 识别完成：{len(segments)} 段，{len(full_text)} 字符")

        return ASRResult(
            file_path=str(path),
            segments=segments,
            full_text=full_text,
            duration=duration,
            language=language,
            success=True,
        )


def extract_frame(
    video_path: str,
    timestamp: float,
    output_path: Optional[str] = None,
) -> str:
    """
    按时间戳截取视频帧，返回截图文件路径。

    参数：
        video_path:  视频文件路径
        timestamp:   时间点（秒）
        output_path: 输出图片路径，不传则自动生成到系统临时目录

    返回：
        截图文件的绝对路径（调用方负责清理）

    用途：
        当 ASR 发现某段有问题，可回溯到对应时间截帧，为视觉分析提供原始图像。
    """
    if not _check_ffmpeg():
        raise RuntimeError("未找到 ffmpeg")

    if output_path is None:
        ts_str = _seconds_to_hms(timestamp).replace(":", "-")
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"frame_{Path(video_path).stem}_{ts_str}.jpg"
        )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",        # JPEG 质量（2=高质量）
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"截帧失败: {result.stderr}")

    print(f"[video_asr] 截帧成功: {output_path}（时间戳 {_seconds_to_hms(timestamp)}）")
    return output_path


def transcribe_video_for_review(
    file_path: str,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """
    对视频跑 ASR 并格式化为带元信息的文本，直接可以丢给杠精虾 review。
    失败时抛出异常。

    返回格式示例：
        【来源视频】demo.mp4
        【时长】00:12:34
        【字幕内容】
        [00:00:03 → 00:00:07] 大家好，今天来讲一下这个方案  (情绪:高兴)
        [00:00:08 → 00:00:15] 这个架构的核心思路是...
        ...
    """
    result = transcribe_video(file_path, language=language)

    if not result.success:
        raise RuntimeError(f"视频 ASR 失败: {result.error}\n文件: {file_path}")

    header = (
        f"【来源视频】{Path(file_path).name}\n"
        f"【时长】{_seconds_to_hms(result.duration)}\n"
        f"【语言】{result.language}"
    )
    if result.warning:
        header += f"\n【注意】{result.warning}"

    subtitle_text = result.get_subtitle_text()

    return f"{header}\n\n【字幕内容】\n{subtitle_text}"


# ============================================================
# 内部工具函数
# ============================================================

def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _extract_audio(
    video_path: str,
    output_wav: str,
) -> tuple[bool, str, float]:
    """
    用 ffmpeg 从视频提取单声道 16kHz wav 音频。
    SenseVoice 推荐输入格式：16kHz, mono, 16bit PCM。

    返回: (success, error_msg, duration_seconds)
    """
    # 先探测时长
    duration = _probe_duration(video_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",                  # 不要视频流
        "-acodec", "pcm_s16le", # 16bit PCM
        "-ar", "16000",         # 16kHz 采样率
        "-ac", "1",             # 单声道
        output_wav,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr[-500:], 0.0  # 只取最后 500 字符避免过长

    return True, "", duration


def _probe_duration(video_path: str) -> float:
    """用 ffprobe 获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path,
            ],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _parse_sensevoice_result(res: list) -> list[Segment]:
    """
    解析 SenseVoice AutoModel.generate() 的返回结果。

    SenseVoice 返回格式（列表，每个元素是字典）：
    {
        "key": "audio_0",
        "text": "<|zh|><|NEUTRAL|><|Speech|><|withitn|>你好世界",
        "timestamp": [[0, 500], [500, 1200], ...],   # 毫秒
    }

    text 中包含语言/情绪/事件标签，需要过滤。
    """
    segments: list[Segment] = []

    if not res or not isinstance(res, list):
        return segments

    for item in res:
        if not isinstance(item, dict):
            continue

        raw_text: str = item.get("text", "")
        timestamps = item.get("timestamp", [])  # [[start_ms, end_ms], ...]

        # 解析情绪和事件标签（格式：<|LABEL|>）
        emotion, event, clean_text = _parse_tags(raw_text)

        if not clean_text.strip():
            continue

        # 有时间戳：拆分成词级别再按句子合并
        if timestamps and len(timestamps) > 0:
            # 取整段的起止时间（毫秒转秒）
            start_ms = timestamps[0][0] if timestamps[0] else 0
            end_ms = timestamps[-1][1] if timestamps[-1] else start_ms + 1000
            segments.append(Segment(
                start=start_ms / 1000.0,
                end=end_ms / 1000.0,
                text=clean_text.strip(),
                emotion=emotion,
                event=event,
            ))
        else:
            # 没有时间戳，整段作为一条
            segments.append(Segment(
                start=0.0, end=0.0,
                text=clean_text.strip(),
                emotion=emotion, event=event,
            ))

    return segments


def _parse_tags(raw_text: str) -> tuple[str, str, str]:
    """
    从 SenseVoice 输出的 raw text 中提取情绪标签、事件标签和干净文字。

    示例输入：<|zh|><|HAPPY|><|Speech|><|withitn|>这个方案真的很好
    返回：("HAPPY", "Speech", "这个方案真的很好")
    """
    import re

    emotion = ""
    event = ""

    # 已知情绪标签
    emotion_tags = {"HAPPY", "SAD", "ANGRY", "FEARFUL", "DISGUSTED",
                    "SURPRISED", "NEUTRAL"}
    # 已知事件标签
    event_tags = {"Speech", "BGM", "Applause", "Laughter", "Crying",
                  "Coughing", "Sneezing", "Breath", "Noise"}

    # 提取所有 <|TAG|> 标签
    tags = re.findall(r"<\|([^|]+)\|>", raw_text)
    for tag in tags:
        if tag in emotion_tags:
            emotion = tag
        elif tag in event_tags:
            event = tag

    # 去掉所有标签，得到干净文字
    clean_text = re.sub(r"<\|[^|]+\|>", "", raw_text).strip()

    return emotion, event, clean_text


def _seconds_to_hms(seconds: float) -> str:
    """把秒数转成 HH:MM:SS 格式"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
