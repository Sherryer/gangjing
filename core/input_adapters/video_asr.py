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
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from core.input_adapters.models import Segment, ASRResult, _seconds_to_hms

# SenseVoice 支持的语言代码
SUPPORTED_LANGUAGES = {"zh", "yue", "en", "ja", "ko", "auto"}
DEFAULT_LANGUAGE = "zh"

# 模型标识（funasr 会自动从 modelscope 下载）
SENSEVOICE_MODEL_ID = "iic/SenseVoiceSmall"

# 单次处理音频最大时长（秒），超长视频建议分段
MAX_AUDIO_DURATION = 7200  # 2小时

# ============================================================
# 模型单例缓存（避免重复加载 ~900MB 模型）
# ============================================================
_model_cache: dict = {}
_ffmpeg_available: Optional[bool] = None


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
        from funasr import AutoModel  # type: ignore  # noqa: F811
    except ImportError:
        return ASRResult(file_path=str(path), success=False,
                         error="缺少依赖：请运行 pip install funasr modelscope torch torchaudio")

    print(f"[video_asr] 正在处理: {path.name}")
    metrics: dict = {}
    t_total = time.time()

    # --- 提取音频到临时文件 ---
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")

        t0 = time.time()
        extract_ok, extract_err, duration = _extract_audio(str(path), audio_path)
        metrics["extract_audio"] = time.time() - t0

        if not extract_ok:
            return ASRResult(file_path=str(path), success=False,
                             error=f"音频提取失败: {extract_err}", metrics=metrics)

        if duration > MAX_AUDIO_DURATION:
            return ASRResult(
                file_path=str(path), success=False,
                error=f"视频时长 {duration/3600:.1f}h 超过限制 {MAX_AUDIO_DURATION/3600:.0f}h，建议剪切后再处理",
                metrics=metrics,
            )

        print(f"[video_asr] 音频提取完成（{metrics['extract_audio']:.2f}s），"
              f"时长: {_seconds_to_hms(duration)}，正在加载模型...")

        # --- 加载 VAD + ASR 模型（单例缓存） ---
        try:
            t0 = time.time()
            model_vad = _get_model("fsmn-vad")
            model_asr = _get_model(
                SENSEVOICE_MODEL_ID,
                trust_remote_code=True,
            )
            metrics["model_load"] = time.time() - t0
            print(f"[video_asr] 模型加载完成（{metrics['model_load']:.2f}s）")

            # --- VAD 分段 ---
            t0 = time.time()
            vad_res = model_vad.generate(input=audio_path)
            vad_segments = vad_res[0].get("value", []) if vad_res else []
            metrics["vad"] = time.time() - t0
            print(f"[video_asr] VAD 分段完成（{metrics['vad']:.2f}s），{len(vad_segments)} 段")

            if not vad_segments:
                return ASRResult(
                    file_path=str(path), duration=duration,
                    success=False,
                    error="VAD 未检测到语音活动，请检查视频是否有语音",
                    metrics=metrics,
                )

            # --- 逐段 ASR 识别（直接传 numpy array，避免磁盘 I/O） ---
            import numpy as np
            import soundfile as sf

            audio_data, sr = sf.read(audio_path, dtype="float32")
            t0 = time.time()
            raw_segments: list[Segment] = []

            rms_values = []  # 采集 RMS 数据供分析

            for idx, (start_ms, end_ms) in enumerate(vad_segments):
                start_sample = int(start_ms / 1000 * sr)
                end_sample = int(end_ms / 1000 * sr)
                seg_audio = audio_data[start_sample:end_sample]

                # 确保 float32（funasr 传 array 时的预期 dtype）
                if seg_audio.dtype != np.float32:
                    seg_audio = seg_audio.astype(np.float32)

                # 采集 RMS 能量（供后续分析是否值得作为判定维度）
                rms = float(np.sqrt(np.mean(seg_audio ** 2)))
                rms_db = 20 * np.log10(rms) if rms > 0 else -100.0
                rms_values.append((idx, start_ms, end_ms, rms_db))

                res = model_asr.generate(
                    input=seg_audio,
                    fs=16000,  # 显式指定采样率，不依赖文件头
                    language=language,
                    use_itn=True,
                )

                for r in res:
                    raw_text = r.get("text", "")
                    emotion, event, clean_text = _parse_tags(raw_text)
                    if clean_text.strip():
                        raw_segments.append(Segment(
                            start=start_ms / 1000.0,
                            end=end_ms / 1000.0,
                            text=clean_text.strip(),
                            emotion=emotion,
                            event=event,
                        ))

            metrics["asr_inference"] = time.time() - t0
            print(f"[video_asr] ASR 推理完成（{metrics['asr_inference']:.2f}s），"
                  f"{len(raw_segments)} 段有效结果")

            # RMS 分布数据已采集在 rms_values 中，供将来扩展使用
            # 实测 loudnorm 后 stdev ≈ 2.7dB，区分度不足，暂不用于判定

        except Exception as e:
            return ASRResult(file_path=str(path), success=False,
                             error=f"ASR 处理失败: {type(e).__name__}: {e}",
                             metrics=metrics)

        # --- 后处理：语言策略（标点切分 + 清理 + 标注） ---
        t0 = time.time()
        from core.input_adapters.postprocess import get_strategy
        strategy = get_strategy(language)
        segments = strategy.process(raw_segments)
        metrics["postprocess"] = time.time() - t0

        if not segments:
            return ASRResult(
                file_path=str(path), duration=duration,
                success=False,
                error="ASR 未识别到任何内容，请检查视频是否有语音",
                metrics=metrics,
            )

        full_text = " ".join(seg.text for seg in segments)
        metrics["total"] = time.time() - t_total
        metrics["segment_count"] = len(segments)
        metrics["char_count"] = len(full_text)

        print(f"[video_asr] 识别完成：{len(segments)} 段，{len(full_text)} 字符，"
              f"总耗时 {metrics['total']:.2f}s")

        return ASRResult(
            file_path=str(path),
            segments=segments,
            full_text=full_text,
            duration=duration,
            language=language,
            success=True,
            metrics=metrics,
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
    metrics_text = result.get_metrics_text()

    output = f"{header}\n\n【字幕内容】\n{subtitle_text}"
    if metrics_text:
        output += f"\n\n{metrics_text}"
    return output


# ============================================================
# 内部工具函数
# ============================================================

def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用（结果缓存）"""
    global _ffmpeg_available
    if _ffmpeg_available is not None:
        return _ffmpeg_available
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, check=True
        )
        _ffmpeg_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        _ffmpeg_available = False
    return _ffmpeg_available


def _get_model(model_id: str, **kwargs):
    """
    模型单例缓存。避免每次调用都重新加载 ~900MB 的模型。
    注意：非线程安全，并发场景需要外部加锁。
    """
    from funasr import AutoModel  # type: ignore

    if model_id not in _model_cache:
        _model_cache[model_id] = AutoModel(
            model=model_id,
            disable_update=True,
            **kwargs,
        )
    return _model_cache[model_id]


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
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",  # 音量归一化，提升识别稳定性
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


def _parse_tags(raw_text: str) -> tuple[str, str, str]:
    """
    从 SenseVoice 输出的 raw text 中提取情绪标签、事件标签和干净文字。

    示例输入：<|zh|><|HAPPY|><|Speech|><|withitn|>这个方案真的很好
    返回：("HAPPY", "Speech", "这个方案真的很好")
    """

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
