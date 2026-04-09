"""
杠精虾 — 命令行交互入口
========================

使用方式：

  # 单虾模式（默认）：直接 review
  python main.py --file code.py
  python main.py --input "你的方案..."
  python main.py --url https://example.com/article     # review 网页内容
  python main.py --pdf path/to/report.pdf              # review PDF 文档
  python main.py --video path/to/demo.mp4              # review 视频字幕内容（ASR）

  # 三虾互杠模式：ProposalShrimp 出初稿 → 三虾迭代
  python main.py --mode three --input "帮我写一个 React Popover 组件"
  python main.py --mode three --file request.txt --level 3

  # 常用参数
  --mode,     -m   single（默认，直接 review） | three（三虾互杠）
  --input,    -i   直接传入内容字符串
  --file,     -f   从文件读取内容
  --url,      -u   抓取网页内容并 review（Jina Reader，无需 Key）
  --pdf,           解析 PDF 文件并 review
  --video,         从视频提取字幕并 review（SenseVoice-Small ASR，中文最优）
  --lang,          视频语言代码，默认 zh（可选：yue/en/ja/ko/auto）
  --type,     -t   内容类型：auto（默认）| code | business | content
  --level,    -l   杠精等级：1=温柔 2=正常（默认）3=魔鬼
  --provider, -p   LLM 提供商：venus（默认）| deepseek | claude | openai | qwen
  --output,   -o   指定输出文件路径
  --no-save        不保存文件，只打印到终端

注意：
  - single 模式：把已有内容直接丢给杠精虾 review
  - three  模式：把"需求描述"丢给三虾，由 ProposalShrimp 先产出初稿再迭代
  - --url / --pdf / --video 只支持 single 模式
"""

import argparse
import sys
import os
import threading
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.critic_shrimp import review
from core.three_shrimp_workflow import run_workflow, render_workflow_report
from core.input_adapters.url_fetcher import fetch_url_for_review
from core.input_adapters.pdf_parser import parse_pdf_for_review
from core.input_adapters.video_asr import transcribe_video_for_review
import config


# ── 进度提示 ────────────────────────────────────────────────────

class Spinner:
    FRAMES = ["🦐 思考中   ", "🦐 思考中.  ", "🦐 思考中.. ", "🦐 思考中..."]

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        print("\r" + " " * 40 + "\r", end="", flush=True)

    def _spin(self):
        i = 0
        while self._running:
            print(f"\r{self.FRAMES[i % len(self.FRAMES)]}", end="", flush=True)
            time.sleep(0.4)
            i += 1


# ── 输入读取 ────────────────────────────────────────────────────

def read_from_stdin(mode: str) -> str:
    if mode == "three":
        print("📋 请输入你的需求（ProposalShrimp 将据此产出初稿），Ctrl+D 提交：")
    else:
        print("📋 请粘贴要审查的内容，Ctrl+D 提交：")
    print("─" * 60)
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)


def read_from_file(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        print(f"❌ 文件内容为空：{file_path}")
        sys.exit(1)
    print(f"📄 已读取文件：{file_path}（{len(content)} 字符）")
    return content


# ── 输出保存 ────────────────────────────────────────────────────

def save_output(content: str, output_path: str | None, prefix: str, content_type: str, level: int) -> str:
    if output_path:
        save_path = Path(output_path)
    else:
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = output_dir / f"{prefix}_{content_type}_L{level}_{timestamp}.md"

    save_path.write_text(content, encoding="utf-8")
    return str(save_path)


# ── 单虾模式 ────────────────────────────────────────────────────

def run_single_mode(content: str, args) -> str:
    level_names = {1: "🟢 温柔杠", 2: "🟡 正常杠", 3: "🔴 魔鬼杠"}
    print(f"\n{'─'*60}")
    print(f"  模式：单虾 review")
    print(f"  等级：Level {args.level} {level_names[args.level]}")
    print(f"  类型：{args.type}  提供商：{args.provider or config.DEFAULT_PROVIDER}")
    print(f"{'─'*60}\n")

    spinner = Spinner()
    spinner.start()
    try:
        report = review(
            content=content,
            content_type=args.type,
            critic_level=args.level,
            provider=args.provider,
        )
    except KeyboardInterrupt:
        spinner.stop()
        print("\n⚠️  已中断")
        sys.exit(0)
    except Exception as e:
        spinner.stop()
        _print_error(e)
        sys.exit(1)
    spinner.stop()
    return report


# ── 三虾模式 ────────────────────────────────────────────────────

def run_three_mode(request: str, args) -> str:
    level_names = {1: "🟢 温柔杠", 2: "🟡 正常杠", 3: "🔴 魔鬼杠"}
    print(f"\n{'─'*60}")
    print(f"  模式：三虾互杠")
    print(f"  等级：Level {args.level} {level_names[args.level]}")
    print(f"  类型：{args.type}  提供商：{args.provider or config.DEFAULT_PROVIDER}")
    print(f"{'─'*60}\n")

    try:
        result = run_workflow(
            user_request=request,
            content_type=args.type,
            critic_level=args.level,
            provider=args.provider,
        )
    except KeyboardInterrupt:
        print("\n⚠️  已中断")
        sys.exit(0)
    except Exception as e:
        _print_error(e)
        sys.exit(1)

    return render_workflow_report(result)


# ── 错误提示 ────────────────────────────────────────────────────

def _print_error(e: Exception):
    print(f"\n❌ 失败：{type(e).__name__}: {e}")
    print("\n可能的原因：")
    print("  1. API Key 无效或过期 → 检查 config.py")
    print("  2. 网络问题 → 检查网络连接")
    print("  3. 模型名称错误 → 检查 config.py 中的模型配置")


# ── 主入口 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🦐 杠精虾 — 批判性思维 Review 引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py --file mycode.py                          # 单虾 review 代码文件
  python main.py --file plan.md --type business --level 3 # 魔鬼级商业方案 review
  python main.py --mode three --input "写一个登录组件"     # 三虾互杠：需求→初稿→迭代
        """
    )
    parser.add_argument("--mode",     "-m", default="single", choices=["single", "three"],
                        help="single=直接review内容（默认）；three=三虾互杠（需求驱动）")
    parser.add_argument("--input",    "-i", type=str,  help="直接传入内容")
    parser.add_argument("--file",     "-f", type=str,  help="从文件读取内容")
    parser.add_argument("--url",      "-u", type=str,  help="抓取网页内容并 review")
    parser.add_argument("--pdf",            type=str,  help="解析 PDF 并 review")
    parser.add_argument("--video",          type=str,  help="从视频提取字幕并 review（SenseVoice ASR）")
    parser.add_argument("--lang",           type=str,  default="zh",
                        choices=["zh", "yue", "en", "ja", "ko", "auto"],
                        help="视频语言代码（默认 zh，auto=自动检测）")
    parser.add_argument("--type",     "-t", default="auto",
                        choices=["auto", "code", "business", "content"],
                        help="内容类型（默认 auto 自动识别）")
    parser.add_argument("--level",    "-l", type=int, default=config.DEFAULT_CRITIC_LEVEL,
                        choices=[1, 2, 3], help="杠精等级 1/2/3（默认 2）")
    parser.add_argument("--provider", "-p", type=str, default=None,
                        choices=["venus", "deepseek", "claude", "openai", "qwen"])
    parser.add_argument("--output",   "-o", type=str,  help="输出文件路径")
    parser.add_argument("--no-save",        action="store_true", help="不保存文件")

    args = parser.parse_args()

    # ① 获取输入内容
    if args.url:
        # URL 模式：Jina Reader 抓取网页
        if args.mode == "three":
            print("⚠️  --url 不支持 three 模式，已自动切换为 single 模式")
            args.mode = "single"
        print(f"🌐 正在抓取网页：{args.url}")
        try:
            content = fetch_url_for_review(args.url)
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)
        # URL 内容多为文章，默认 content 类型
        if args.type == "auto":
            args.type = "content"
    elif args.pdf:
        # PDF 模式：PyMuPDF 解析
        if args.mode == "three":
            print("⚠️  --pdf 不支持 three 模式，已自动切换为 single 模式")
            args.mode = "single"
        pdf_path = str(Path(args.pdf).resolve())   # 转绝对路径，避免 cwd 歧义
        print(f"📄 正在解析 PDF：{pdf_path}")
        try:
            content = parse_pdf_for_review(pdf_path)
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)
    elif args.video:
        # 视频 ASR 模式：SenseVoice-Small 提取字幕
        if args.mode == "three":
            print("⚠️  --video 不支持 three 模式，已自动切换为 single 模式")
            args.mode = "single"
        video_path = str(Path(args.video).resolve())
        print(f"🎬 正在提取视频字幕：{video_path}（语言: {args.lang}）")
        print("   首次运行会自动下载 SenseVoice-Small 模型（~234MB），请耐心等待...")
        try:
            content = transcribe_video_for_review(video_path, language=args.lang)
        except RuntimeError as e:
            print(f"❌ {e}")
            sys.exit(1)
        # 视频字幕默认走 content review
        if args.type == "auto":
            args.type = "content"
    elif args.input:
        content = args.input
    elif args.file:
        content = read_from_file(args.file)
    else:
        content = read_from_stdin(args.mode)

    if not content.strip():
        print("❌ 内容为空，已退出")
        sys.exit(0)

    # ② 运行对应模式
    if args.mode == "three":
        output = run_three_mode(content, args)
        prefix = "three_shrimp"
    else:
        output = run_single_mode(content, args)
        prefix = "review"

    # ③ 打印结果
    print("\n" + "═" * 60)
    print(output)
    print("═" * 60)

    # ④ 保存文件
    if not args.no_save:
        file_type = args.type if args.type != "auto" else "auto"
        saved_path = save_output(output, args.output, prefix, file_type, args.level)
        print(f"\n💾 已保存到：{saved_path}")

    print()


if __name__ == "__main__":
    main()
