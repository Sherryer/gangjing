"""
Heartbeat 定时巡检
==================
功能：
  1. 定时（默认每天凌晨 2 点）自动 review 最近 git commit 改动的文件
  2. 把 review 结果追加写入 REVIEW_LOG.md
  3. 智能降噪：相同问题（同文件同行）不重复报告，连续 3 天未修复则升级提醒

运行方式：
  python heartbeat/scheduler.py               # 启动后台守护进程
  python heartbeat/scheduler.py --now         # 立即跑一次（测试用）
  python heartbeat/scheduler.py --cron "0 2 * * *"  # 自定义 cron 表达式

依赖：pip install apscheduler
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.critic_shrimp import review
from core.prompt_loader import detect_content_type
import config

# 项目根目录
ROOT = Path(__file__).parent.parent
REVIEW_LOG = ROOT / "REVIEW_LOG.md"

# 支持自动 review 的文件扩展名
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",    # 代码
    ".md", ".txt",                           # 文档
    ".json", ".yaml", ".yml",               # 配置（视为 content 类型）
}

# Heartbeat 默认使用最轻量的模型（成本控制）
HEARTBEAT_LEVEL = 1      # 温柔杠，只报 P0/P1
HEARTBEAT_MAX_FILES = 5  # 每次最多 review 5 个文件，避免超时


# ── Git 工具 ──────────────────────────────────────────────────────

def get_recently_changed_files(n_commits: int = 1) -> list[str]:
    """
    获取最近 n_commits 个 commit 改动的文件列表。
    只返回存在且可 review 的文件。
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"HEAD~{n_commits}", "HEAD"],
            capture_output=True, text=True, cwd=ROOT, timeout=10
        )
        if result.returncode != 0:
            # 可能是初始 commit，用 git show 代替
            result = subprocess.run(
                ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
                capture_output=True, text=True, cwd=ROOT, timeout=10
            )

        files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]

        # 过滤：只保留可 review 的文件
        valid = []
        for f in files:
            path = ROOT / f
            if path.exists() and path.suffix in REVIEWABLE_EXTENSIONS:
                valid.append(str(path))

        print(f"[Heartbeat] 最近改动文件：{len(valid)} 个可 review")
        return valid[:HEARTBEAT_MAX_FILES]

    except Exception as e:
        print(f"[Heartbeat] ⚠️  获取 git diff 失败：{e}")
        return []


# ── REVIEW_LOG 读写 ───────────────────────────────────────────────

def _load_review_log() -> str:
    """读取现有日志，不存在则返回空字符串"""
    if REVIEW_LOG.exists():
        return REVIEW_LOG.read_text(encoding="utf-8")
    return ""


def _save_review_log(content: str):
    """写入日志文件"""
    REVIEW_LOG.write_text(content, encoding="utf-8")


def _extract_existing_issues(log_content: str) -> dict[str, dict]:
    """
    从日志中提取已记录的问题，用于降噪判断。
    返回格式：{ "文件名:问题关键词" -> {"count": N, "last_date": "YYYY-MM-DD", "status": "待处理/已修复/已忽略"} }
    """
    issues = {}
    # 从历史日志里提取 P0/P1 问题标题（CriticShrimp 输出用 #### 四级标题）
    pattern = re.compile(r'####\s*(P[01]\s*[🔴🟠].*?)[\n\r]')
    for match in pattern.finditer(log_content):
        key = match.group(1).strip()[:80]   # 取前 80 字作为 key
        if key not in issues:
            issues[key] = {"count": 0, "last_date": "", "status": "待处理"}
        issues[key]["count"] += 1

    return issues


def _is_duplicate(issue_title: str, existing: dict) -> tuple[bool, int]:
    """
    判断问题是否已存在于日志中。
    返回 (is_duplicate, days_count)
    """
    key = issue_title.strip()[:80]
    if key in existing:
        return True, existing[key]["count"]
    return False, 0


# ── 单次巡检逻辑 ──────────────────────────────────────────────────

def run_heartbeat_once(files: list[str] | None = None):
    """
    执行一次 Heartbeat 巡检：
    1. 获取近期改动文件
    2. 逐个 review（Level 1 温柔杠）
    3. 降噪后写入 REVIEW_LOG.md
    """
    print(f"\n{'='*60}")
    print(f"  🦐 Heartbeat 巡检启动 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 获取要 review 的文件
    target_files = files or get_recently_changed_files()
    if not target_files:
        print("[Heartbeat] 没有需要 review 的文件，本次跳过")
        _append_log_entry("本次巡检无改动文件，跳过", [], datetime.now())
        return

    # 加载现有日志（用于降噪）
    existing_log = _load_review_log()
    existing_issues = _extract_existing_issues(existing_log)

    results = []
    for file_path in target_files:
        path = Path(file_path)
        print(f"\n[Heartbeat] 正在 review: {path.name}")

        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                print(f"[Heartbeat] 文件为空，跳过：{path.name}")
                continue

            content_type = detect_content_type(content)
            report = review(
                content=content,
                content_type=content_type,
                critic_level=HEARTBEAT_LEVEL,   # Level 1：只报 P0/P1
                provider=config.DEFAULT_PROVIDER,
            )

            # 降噪处理：提取报告里的问题标题，检查是否重复
            issue_titles = re.findall(r'####\s*(P[01].*?)[\n\r]', report)
            new_issues = []
            suppressed = []

            for title in issue_titles:
                is_dup, count = _is_duplicate(title, existing_issues)
                if is_dup:
                    if count >= 3:
                        # 连续 3 次未修复，升级提醒
                        new_issues.append(f"{title} ⚠️ **已连续 {count} 次未修复，请优先处理**")
                    else:
                        suppressed.append(title)
                else:
                    new_issues.append(title)

            if suppressed:
                print(f"[Heartbeat] 降噪：{len(suppressed)} 个重复问题已过滤")

            results.append({
                "file": path.name,
                "file_path": str(file_path),
                "content_type": content_type,
                "report": report,
                "new_issues": new_issues,
                "suppressed_count": len(suppressed),
            })

        except Exception as e:
            print(f"[Heartbeat] ❌ review 失败 {path.name}: {e}")
            results.append({
                "file": path.name,
                "file_path": str(file_path),
                "error": str(e),
            })

    # 写入日志
    _append_log_entry(None, results, datetime.now())
    print(f"\n[Heartbeat] ✅ 本次巡检完成，结果已写入 REVIEW_LOG.md")


def _append_log_entry(note: str | None, results: list, dt: datetime):
    """把本次巡检结果追加到 REVIEW_LOG.md 头部（最新在前）"""
    timestamp = dt.strftime("%Y-%m-%d %H:%M")
    lines = []

    if note:
        lines += [f"\n## {timestamp} | Heartbeat 巡检\n", f"{note}\n", "---\n"]
    else:
        total_new = sum(len(r.get("new_issues", [])) for r in results)
        total_suppressed = sum(r.get("suppressed_count", 0) for r in results)

        lines += [
            f"\n## {timestamp} | Heartbeat 巡检\n",
            f"**文件数**: {len(results)}  "
            f"**新问题**: {total_new} 条  "
            f"**已过滤重复**: {total_suppressed} 条\n",
        ]

        for r in results:
            if "error" in r:
                lines.append(f"\n### ❌ {r['file']} — review 失败\n{r['error']}\n")
                continue

            new_count = len(r.get("new_issues", []))
            lines.append(f"\n### 📄 {r['file']} （{r['content_type']}）\n")

            if new_count == 0:
                lines.append("✅ 无新问题\n")
            else:
                lines.append(f"**新问题 {new_count} 条**（Level 1 温柔杠）\n\n")
                lines.append(r["report"])
                lines.append("\n**状态**: ⏳ 待处理\n")

        lines.append("\n---\n")

    # 追加到文件头部
    existing = _load_review_log()
    if not existing:
        header = "# 📋 杠精虾 Heartbeat 审查日志\n\n"
        new_content = header + "".join(lines)
    else:
        # 在标题行后插入新记录
        insert_pos = existing.find("\n\n") + 2 if "\n\n" in existing else len(existing)
        new_content = existing[:insert_pos] + "".join(lines) + existing[insert_pos:]

    _save_review_log(new_content)


# ── 调度器主程序 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="🦐 杠精虾 Heartbeat 定时巡检")
    parser.add_argument("--now",  action="store_true", help="立即执行一次（测试用）")
    parser.add_argument("--cron", type=str, default="0 2 * * *",
                        help="Cron 表达式（默认：每天凌晨 2 点）")
    parser.add_argument("--files", nargs="+", help="手动指定要 review 的文件路径列表")
    args = parser.parse_args()

    if args.now or args.files:
        # 立即执行一次
        run_heartbeat_once(files=args.files)
        return

    # 启动定时调度
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("❌ 缺少依赖：请运行 pip install apscheduler")
        sys.exit(1)

    # 解析 cron 表达式（分 时 日 月 周）
    parts = args.cron.split()
    if len(parts) != 5:
        print(f"❌ Cron 表达式格式错误（应为 5 段，如 '0 2 * * *'）：{args.cron}")
        sys.exit(1)
    minute, hour, day, month, day_of_week = parts

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_heartbeat_once,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week),
        id="heartbeat",
        name="杠精虾 Heartbeat 巡检",
    )

    print(f"🦐 Heartbeat 调度器已启动，Cron: {args.cron}（Asia/Shanghai）")
    print("   按 Ctrl+C 停止\n")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n[Heartbeat] 已停止")


if __name__ == "__main__":
    main()
