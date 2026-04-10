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

# ============================================================
# 模型单例缓存（避免重复加载 ~900MB 模型）
# ============================================================
_model_cache: dict = {}
_ffmpeg_available: Optional[bool] = None


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

        # --- 后处理：标点切分 → 规则清理 → 置信度标注 ---
        t0 = time.time()
        segments = _split_segments_by_punctuation(raw_segments)
        segments = _clean_and_tag_segments(segments)
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


def _split_segments_by_punctuation(segments: list[Segment]) -> list[Segment]:
    """
    按句末标点对长段落做二次切分。

    SenseVoice 可能返回一整段长文字，这里按句号/问号/感叹号切成多条，
    时间戳按字符比例线性插值分配。
    """
    # 句末标点（中英文）
    SENTENCE_ENDS = re.compile(r'([。！？!?；;]+)')

    result: list[Segment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        # 短段不切（<50字符或没有句末标点）
        if len(text) < 50 or not SENTENCE_ENDS.search(text):
            result.append(seg)
            continue

        # 按句末标点拆分，保留标点
        parts = SENTENCE_ENDS.split(text)
        # 合并：["句子", "。", "句子2", "？"] → ["句子。", "句子2？"]
        sentences: list[str] = []
        i = 0
        while i < len(parts):
            s = parts[i]
            # 下一个如果是标点，粘上去
            if i + 1 < len(parts) and SENTENCE_ENDS.fullmatch(parts[i + 1]):
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

        # 按字符比例分配时间
        total_chars = sum(len(s) for s in sentences)
        total_duration = seg.end - seg.start
        current_time = seg.start

        for sentence in sentences:
            ratio = len(sentence) / total_chars if total_chars > 0 else 1.0 / len(sentences)
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


# ── 第一层：规则清理 + 第二层：置信度标注 ──────────────────────

# 纯 filler / 语气词（完全匹配时丢弃整段）
_FILLER_ONLY = re.compile(
    r'^[呃嗯啊哦哈嗨唉噢嘛呀吧啦额哎呐嘿]*[。，、！？．．．…,.!? ]*$'
)

# 尾部标点（判断置信度时需要先去掉）
_TRAILING_PUNCT = re.compile(r'[。！？!?，,、\s]+$')
_PUNCT_ALL = re.compile(r'[。！？!?，,、\s.…]')

# jieba 延迟加载
_jieba_loaded = False


def _ensure_jieba():
    global _jieba_loaded
    if not _jieba_loaded:
        import jieba
        jieba.setLogLevel(20)  # 抑制 jieba 的 INFO 日志
        _jieba_loaded = True


def _word_quality_score(text: str) -> float:
    """
    分词质量分数：多字词（≥2字符）的字符数占总字符数的比例。
    返回 0.0 ~ 1.0，越高越可信。

    示例：
      "不是"     → ["不是"]           → 1.0  ✅
      "咋介绍"   → ["咋", "介绍"]     → 0.67 ✅
      "耐吉性"   → ["耐", "吉", "性"] → 0.0  ⚠️
      "等脸"     → ["等", "脸"]       → 0.0  ⚠️
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


def _suspicious_check(seg: 'Segment') -> bool:
    """
    多维联合判定是否疑似识别错误。

    策略：表层规则先圈出"候选可疑段"，分词质量高的再捞回来。
    这样既能标出"等脸""耐吉性"，又不会误标"不是""咋介绍"。

    维度：
      1. 字符长度 + 时长（表层粗筛）
      2. 分词可达性（语义层，用于救回正确识别的短段）
      3. 单字重复（形态层，硬规则）
    """
    core = _TRAILING_PUNCT.sub('', seg.text).strip()
    if not core:
        return True

    duration = seg.end - seg.start

    # ── 硬规则：单字重复 3 次以上，直接标记 ──
    if re.search(r'(.)\1{2,}', core):
        return True

    # ── 长段基本可信 ──
    if len(core) > 8:
        return False

    # ── 表层粗筛：短段候选 ──
    is_candidate = False

    # 极短文字 + 短时长
    if len(core) <= 3 and duration < 2.0:
        is_candidate = True

    # 短文字 + 每字不重复（散字特征）
    if (len(core) <= 5
            and len(set(core)) == len(core)
            and duration < 3.0):
        is_candidate = True

    if not is_candidate:
        return False

    # ── 分词救回：如果分词能切出有意义的词，则不标记 ──
    # "不是"(1.0)、"咋介绍"(0.67) 会被救回
    # "等脸"(0.0) 不会被救回
    word_score = _word_quality_score(core)

    # 高分词质量 → 尝试救回
    # 注意：jieba 新词发现可能把乱码也切成"词"（如"耐吉性"），
    # 所以用词频验证：只有词典中确实存在的高频词才有说服力
    if word_score >= 0.5:
        import jieba
        _ensure_jieba()
        words = [w for w in jieba.cut(core) if len(w) >= 2]
        # 检查多字词是否在 jieba 词典中且有词频
        has_known_word = any(
            jieba.dt.FREQ.get(w, 0) > 0 for w in words
        )
        if has_known_word:
            return False  # 救回：含有词典中的已知词

    return True


def _clean_and_tag_segments(segments: list[Segment]) -> list[Segment]:
    """
    第一层：规则清理
      - 去掉纯 filler 段（"呃"、"嗯"、"哎"等）
      - 去掉段首重复的 filler 词（"呃，" "嗯，"）
      - 统一标点为全角

    第二层：置信度标注
      - 对可能识别错误的段标记 suspicious=True
      - 不修改原始文字，只打标记

    设计原则：宁可漏标，不可误改。
    """
    result: list[Segment] = []

    for seg in segments:
        text = seg.text.strip()

        # ── 第一层：规则清理 ──

        # 纯 filler 整段丢弃
        if _FILLER_ONLY.fullmatch(text):
            continue

        # 去掉段首 filler（"呃，大家好" → "大家好"）
        text = re.sub(r'^[呃嗯额哎]+[，,、]\s*', '', text)

        # 半角标点 → 全角
        text = text.replace(',', '，').replace('!', '！').replace('?', '？')

        if not text:
            continue

        # ── 第二层：置信度标注 ──
        suspicious = _suspicious_check(
            Segment(start=seg.start, end=seg.end, text=text)
        )

        result.append(Segment(
            start=seg.start,
            end=seg.end,
            text=text,
            emotion=seg.emotion,
            event=seg.event,
            suspicious=suspicious,
        ))

    return result


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


def _seconds_to_hms(seconds: float) -> str:
    """把秒数转成 HH:MM:SS 格式"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
