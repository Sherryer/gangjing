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
  --html           同时导出 HTML 报告
  --open           导出 HTML 后自动用浏览器打开
  --no-save        不保存文件，只打印到终端

注意：
  - single 模式：把已有内容直接丢给杠精虾 review
  - three  模式：把"需求描述"丢给三虾，由 ProposalShrimp 先产出初稿再迭代
  - --url / --pdf / --video 只支持 single 模式
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
from rich.rule import Rule
from rich.theme import Theme

from core.critic_shrimp import review
from core.three_shrimp_workflow import run_workflow, render_workflow_report
from core.input_adapters.url_fetcher import fetch_url_for_review
from core.input_adapters.pdf_parser import parse_pdf_for_review
from core.input_adapters.video_asr import transcribe_video_for_review
from core.html_exporter import export_html
import config


# ── Rich Console 全局实例 ────────────────────────────────────────

SHRIMP_THEME = Theme({
    "shrimp":     "bold bright_red",
    "p0":         "bold white on red",
    "p1":         "bold black on dark_orange",
    "p2":         "bold black on yellow",
    "p3":         "bold black on green",
    "passed":     "bold green",
    "forced":     "bold yellow",
    "max_rounds": "bold dark_orange",
    "level1":     "bold green",
    "level2":     "bold yellow",
    "level3":     "bold red",
    "info":       "dim cyan",
    "dim":        "dim",
})

console = Console(theme=SHRIMP_THEME)

LEVEL_STYLE = {1: ("level1", "🟢 温柔杠"), 2: ("level2", "🟡 正常杠"), 3: ("level3", "🔴 魔鬼杠")}
SHRIMP_ART = "🦐"


# ── 头部 Banner ──────────────────────────────────────────────────

def print_banner():
    console.print()
    console.print(Panel(
        Text("🦐  杠精虾  ·  批判性思维 Review 引擎  🦐", justify="center", style="bold bright_red"),
        subtitle="[dim]让你的方案经得起最刁钻的审查[/dim]",
        border_style="red",
        padding=(0, 4),
    ))
    console.print()


# ── 模式信息面板 ─────────────────────────────────────────────────

def print_mode_panel(mode: str, level: int, content_type: str, provider: str):
    level_style, level_label = LEVEL_STYLE[level]
    mode_label = "三虾互杠 🦐🦐🦐" if mode == "three" else "单虾 Review 🦐"

    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", justify="right")
    table.add_column()
    table.add_row("模式",   f"[bold]{mode_label}[/bold]")
    table.add_row("等级",   f"[{level_style}]Level {level}  {level_label}[/{level_style}]")
    table.add_row("类型",   f"[cyan]{content_type}[/cyan]")
    table.add_row("提供商", f"[cyan]{provider}[/cyan]")

    console.print(Panel(table, title="[bold]任务配置[/bold]", border_style="bright_black", padding=(0, 1)))
    console.print()


# ── Spinner（单虾等待）───────────────────────────────────────────

class RichSpinner:
    def __init__(self, label: str = "🦐 杠精虾思考中"):
        self._progress = Progress(
            SpinnerColumn("dots", style="bright_red"),
            TextColumn(f"[bold bright_red]{label}[/bold bright_red]"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        self._task_id = None

    def start(self):
        self._progress.start()
        self._task_id = self._progress.add_task("thinking")

    def stop(self):
        self._progress.stop()


# ── 结果展示 ─────────────────────────────────────────────────────

def print_review_result(report: str, mode: str = "single"):
    console.print()
    console.print(Rule("[bold bright_red]Review 结果[/bold bright_red]", style="red"))
    console.print()
    try:
        console.print(Markdown(report))
    except Exception:
        console.print(report)
    console.print()


def print_three_shrimp_summary(rounds_info: list[dict], status: str):
    """打印三虾迭代进度表"""
    table = Table(show_header=True, header_style="bold", border_style="bright_black", padding=(0, 2))
    table.add_column("轮次",   justify="center")
    table.add_column("P0 🔴", justify="center")
    table.add_column("P1 🟠", justify="center")
    table.add_column("状态",   justify="center")

    status_map = {
        "ongoing":     ("🔄 继续", "yellow"),
        "passed":      ("✅ 通过", "green"),
        "forced_stop": ("⚠️ 强制终止", "yellow"),
        "max_rounds":  ("⏰ 达到上限", "dark_orange"),
    }

    for r in rounds_info:
        s_label, s_style = status_map.get(r["status"], (r["status"], "white"))
        table.add_row(
            f"Round {r['round_num']}",
            Text(str(r["p0"]), style="bold red" if r["p0"] > 0 else "green"),
            Text(str(r["p1"]), style="bold dark_orange" if r["p1"] > 0 else "dim"),
            Text(s_label, style=s_style),
        )

    final_style = {"passed": "passed", "forced_stop": "forced", "max_rounds": "max_rounds"}.get(status, "white")
    final_desc  = {"passed": "✅ 终审通过，无 P0 问题", "forced_stop": "⚠️ P0 未收敛，需人工介入", "max_rounds": "⏰ 已达最大轮次"}.get(status, status)

    console.print(Panel(
        table,
        title="[bold]三虾互杠迭代记录[/bold]",
        subtitle=f"[{final_style}]{final_desc}[/{final_style}]",
        border_style="bright_black",
    ))


# ── 输入读取 ─────────────────────────────────────────────────────

def read_from_stdin(mode: str) -> str:
    if mode == "three":
        console.print(Panel(
            "[dim]请输入你的需求（ProposalShrimp 将据此产出初稿），[bold]Ctrl+D[/bold] 提交[/dim]",
            border_style="bright_black",
        ))
    else:
        console.print(Panel(
            "[dim]请粘贴要审查的内容，[bold]Ctrl+D[/bold] 提交[/dim]",
            border_style="bright_black",
        ))
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
        console.print(f"[bold red]❌ 文件不存在：{file_path}[/bold red]")
        sys.exit(1)
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        console.print(f"[bold red]❌ 文件内容为空：{file_path}[/bold red]")
        sys.exit(1)
    console.print(f"[info]📄 已读取文件：{file_path}（{len(content)} 字符）[/info]")
    return content


# ── 输出保存 ─────────────────────────────────────────────────────

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


# ── 单虾模式 ─────────────────────────────────────────────────────

def run_single_mode(content: str, args) -> str:
    print_mode_panel("single", args.level, args.type, args.provider or config.DEFAULT_PROVIDER)

    spinner = RichSpinner("杠精虾 审查中")
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
        console.print("\n[yellow]⚠️  已中断[/yellow]")
        sys.exit(0)
    except Exception as e:
        spinner.stop()
        _print_error(e)
        sys.exit(1)
    spinner.stop()
    return report


# ── 三虾模式 ─────────────────────────────────────────────────────

def run_three_mode(request: str, args) -> str:
    print_mode_panel("three", args.level, args.type, args.provider or config.DEFAULT_PROVIDER)

    try:
        result = run_workflow(
            user_request=request,
            content_type=args.type,
            critic_level=args.level,
            provider=args.provider,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  已中断[/yellow]")
        sys.exit(0)
    except Exception as e:
        _print_error(e)
        sys.exit(1)

    # 打印迭代摘要表
    rounds_info = [
        {"round_num": r.round_num, "p0": r.p0_count, "p1": r.p1_count, "status": r.status}
        for r in result.rounds
    ]
    console.print()
    print_three_shrimp_summary(rounds_info, result.status)

    return render_workflow_report(result)


# ── 错误提示 ─────────────────────────────────────────────────────

def _print_error(e: Exception):
    console.print(Panel(
        f"[bold red]{type(e).__name__}[/bold red]: {e}\n\n"
        "[dim]可能的原因：\n"
        "  1. API Key 无效或过期 → 检查 config.py\n"
        "  2. 网络问题 → 检查网络连接\n"
        "  3. 模型名称错误 → 检查 config.py 中的模型配置[/dim]",
        title="[bold red]❌ 调用失败[/bold red]",
        border_style="red",
    ))


# ── 主入口 ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🦐 杠精虾 — 批判性思维 Review 引擎",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py --file mycode.py                          # 单虾 review 代码文件
  python main.py --file plan.md --type business --level 3 # 魔鬼级商业方案 review
  python main.py --mode three --input "写一个登录组件"     # 三虾互杠：需求→初稿→迭代
  python main.py --file code.py --html --open              # 导出 HTML 并自动打开浏览器
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
    parser.add_argument("--output",   "-o", type=str,  help="输出文件路径（.md）")
    parser.add_argument("--html",           action="store_true", help="同时导出 HTML 报告")
    parser.add_argument("--open",           action="store_true", help="导出 HTML 后自动用浏览器打开")
    parser.add_argument("--no-save",        action="store_true", help="不保存文件，只打印到终端")

    args = parser.parse_args()

    print_banner()

    # ① 获取输入内容
    if args.url:
        if args.mode == "three":
            console.print("[yellow]⚠️  --url 不支持 three 模式，已自动切换为 single 模式[/yellow]")
            args.mode = "single"
        console.print(f"[info]🌐 正在抓取网页：{args.url}[/info]")
        try:
            content = fetch_url_for_review(args.url)
        except RuntimeError as e:
            console.print(f"[bold red]❌ {e}[/bold red]")
            sys.exit(1)
        if args.type == "auto":
            args.type = "content"

    elif args.pdf:
        if args.mode == "three":
            console.print("[yellow]⚠️  --pdf 不支持 three 模式，已自动切换为 single 模式[/yellow]")
            args.mode = "single"
        pdf_path = str(Path(args.pdf).resolve())
        console.print(f"[info]📄 正在解析 PDF：{pdf_path}[/info]")
        try:
            content = parse_pdf_for_review(pdf_path)
        except RuntimeError as e:
            console.print(f"[bold red]❌ {e}[/bold red]")
            sys.exit(1)

    elif args.video:
        if args.mode == "three":
            console.print("[yellow]⚠️  --video 不支持 three 模式，已自动切换为 single 模式[/yellow]")
            args.mode = "single"
        video_path = str(Path(args.video).resolve())
        console.print(f"[info]🎬 正在提取视频字幕：{video_path}（语言: {args.lang}）[/info]")
        console.print("[dim]   首次运行会自动下载 SenseVoice-Small 模型（~234MB），请耐心等待...[/dim]")
        try:
            content = transcribe_video_for_review(video_path, language=args.lang)
        except RuntimeError as e:
            console.print(f"[bold red]❌ {e}[/bold red]")
            sys.exit(1)
        if args.type == "auto":
            args.type = "content"

    elif args.input:
        content = args.input
    elif args.file:
        content = read_from_file(args.file)
    else:
        content = read_from_stdin(args.mode)

    if not content.strip():
        console.print("[bold red]❌ 内容为空，已退出[/bold red]")
        sys.exit(0)

    # ② 运行对应模式
    if args.mode == "three":
        output = run_three_mode(content, args)
        prefix = "three_shrimp"
    else:
        output = run_single_mode(content, args)
        prefix = "review"

    # ③ 打印结果
    print_review_result(output, args.mode)

    # ④ 保存文件
    saved_md = None
    if not args.no_save:
        file_type = args.type if args.type != "auto" else "auto"
        saved_md = save_output(output, args.output, prefix, file_type, args.level)
        console.print(f"[info]💾 Markdown 已保存：{saved_md}[/info]")

    # ⑤ HTML 导出（--no-save 时也允许导出 HTML，用临时路径）
    if args.html or args.open:
        file_type = args.type if args.type != "auto" else "auto"
        if saved_md:
            html_path = saved_md.replace(".md", ".html") if saved_md.endswith(".md") else saved_md + ".html"
        else:
            output_dir = Path(__file__).parent / "outputs"
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = str(output_dir / f"{prefix}_{file_type}_L{args.level}_{timestamp}.html")
        export_html(
            markdown_content=output,
            output_path=html_path,
            mode=args.mode,
            level=args.level,
            content_type=file_type,
            provider=args.provider or config.DEFAULT_PROVIDER,
            auto_open=args.open,
        )
        console.print(f"[info]🌐 HTML 已导出：{html_path}[/info]")
        if args.open:
            console.print("[dim]   正在用浏览器打开...[/dim]")

    console.print()


if __name__ == "__main__":
    main()
