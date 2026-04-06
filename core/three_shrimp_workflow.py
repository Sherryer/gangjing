"""
三虾互杠工作流
==============

流程：
  Round 1  ProposalShrimp 产出 v1 初稿
      ↓
  Round 2  CriticShrimp + DevilShrimp 并行审查（asyncio.gather）
      ↓
  Round 3  ProposalShrimp 逐条回应 + 产出 v2
      ↓
  Round 4  CriticShrimp 终审：P0 全消 → 通过；还有 P0 → 继续（最多 3 轮）
      ↓
  输出最终版本 + 完整审查日志

防死循环：
  - 最多迭代 MAX_ROUNDS 轮
  - 每轮若 P0 数量没减少 → 强制终止，输出分歧清单让用户决策
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from core.llm_client import chat_simple, chat_simple_async
from core.prompt_loader import build_system_prompt, detect_content_type
import config

MAX_ROUNDS = 3   # 最多迭代轮次（不含初稿轮）


# ── 数据结构 ────────────────────────────────────────────────────

@dataclass
class RoundLog:
    round_num: int
    proposal_v: str        # ProposalShrimp 当轮输出
    critic_review: str     # CriticShrimp 当轮审查
    devil_review: str      # DevilShrimp 当轮质疑（Round 2 起）
    p0_count: int          # 当轮 P0 数量
    p1_count: int          # 当轮 P1 数量
    status: str            # "ongoing" | "passed" | "forced_stop"


@dataclass
class WorkflowResult:
    final_proposal: str         # 最终版方案/代码
    final_critic_report: str    # 最终审查报告
    rounds: list[RoundLog]      # 每轮 log
    total_rounds: int
    status: str                 # "passed" | "forced_stop" | "max_rounds"
    content_type: str
    critic_level: int


# ── Prompt 加载 ──────────────────────────────────────────────────

def _load_md(relative_path: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / relative_path
    return path.read_text(encoding="utf-8")


def _build_proposal_prompt() -> str:
    return _load_md("proposal_shrimp.md")


def _build_devil_prompt() -> str:
    return _load_md("devil_shrimp.md")


def _build_critic_prompt(content_type: str, critic_level: int) -> str:
    return build_system_prompt(content_type, critic_level)


# ── P0/P1 计数（从 CriticShrimp 的输出里提取） ──────────────────

def _count_issues(critic_output: str) -> tuple[int, int]:
    """
    从 Review Report 的"问题总览"表格中提取 P0、P1 数量。
    回退策略：如果表格不存在，用正则数正文中的 P0/P1 标题数量。
    """
    # 优先从总览表格读
    table_p0 = re.search(r'P0.*?\|\s*(\d+)\s*条', critic_output)
    table_p1 = re.search(r'P1.*?\|\s*(\d+)\s*条', critic_output)
    if table_p0 and table_p1:
        return int(table_p0.group(1)), int(table_p1.group(1))

    # 回退：数正文标题
    p0 = len(re.findall(r'P0\s*🔴', critic_output))
    p1 = len(re.findall(r'P1\s*🟠', critic_output))
    return p0, p1


# ── 各角色调用函数 ───────────────────────────────────────────────

def _run_proposal_v1(user_request: str, provider: str | None) -> str:
    """Round 1：ProposalShrimp 产出初稿"""
    system = _build_proposal_prompt()
    user_msg = f"请根据以下需求产出初稿：\n\n{user_request}"
    print("[ProposalShrimp] 正在产出 v1 初稿...")
    return chat_simple(system, user_msg, provider=provider)


async def _run_review_round_async(
    proposal: str,
    content_type: str,
    critic_level: int,
    round_num: int,
    provider: str | None,
) -> tuple[str, str]:
    """
    并发运行 CriticShrimp + DevilShrimp，返回 (critic_output, devil_output)。
    使用 asyncio.gather 实现真正的并行调用，总耗时 ≈ max(两者耗时) 而非相加。
    """
    critic_system = _build_critic_prompt(content_type, critic_level)
    devil_system  = _build_devil_prompt()

    critic_msg = f"请对以下内容进行 review（第 {round_num} 轮审查）：\n\n{proposal}"
    devil_msg  = (
        f"这是 ProposalShrimp 的第 {round_num} 轮版本，请从对立角度质疑其根本假设：\n\n{proposal}"
    )

    print(f"[Round {round_num}] CriticShrimp + DevilShrimp 并发审查中...")
    critic_out, devil_out = await asyncio.gather(
        chat_simple_async(critic_system, critic_msg, label="CriticShrimp", provider=provider),
        chat_simple_async(devil_system,  devil_msg,  label="DevilShrimp",  provider=provider),
    )
    return critic_out, devil_out


def _run_proposal_iterate(
    original_request: str,
    current_proposal: str,
    critic_review: str,
    devil_review: str,
    version: int,
    provider: str | None,
) -> str:
    """ProposalShrimp 根据审查意见迭代"""
    system = _build_proposal_prompt()
    user_msg = (
        f"原始需求：\n{original_request}\n\n"
        f"你的当前版本（v{version - 1}）：\n{current_proposal}\n\n"
        f"【CriticShrimp 审查意见】\n{critic_review}\n\n"
        f"【DevilShrimp 对立质疑】\n{devil_review}\n\n"
        f"请逐条回应所有 P0/P1 问题，产出改进后的 v{version} 版本。"
    )
    print(f"[ProposalShrimp] 正在根据反馈产出 v{version}...")
    return chat_simple(system, user_msg, provider=provider)


async def _run_final_review_async(
    proposal: str,
    content_type: str,
    critic_level: int,
    provider: str | None,
) -> str:
    """终审：只跑 CriticShrimp，DevilShrimp 不参与最终裁决"""
    critic_system = _build_critic_prompt(content_type, critic_level)
    critic_msg = f"请对以下内容进行终审 review：\n\n{proposal}"
    print("[CriticShrimp] 正在进行终审...")
    return await chat_simple_async(critic_system, critic_msg, label="CriticShrimp[终审]", provider=provider)


# ── 主工作流 ─────────────────────────────────────────────────────

async def run_workflow_async(
    user_request: str,
    content_type: str = "auto",
    critic_level: int | None = None,
    provider: str | None = None,
) -> WorkflowResult:
    """
    三虾互杠完整工作流（异步版）。
    外部调用请用 asyncio.run(run_workflow_async(...)) 或在异步上下文中 await。
    """
    if content_type == "auto":
        content_type = detect_content_type(user_request)
        print(f"[Workflow] 自动识别内容类型: {content_type}")

    critic_level = critic_level or config.DEFAULT_CRITIC_LEVEL
    rounds: list[RoundLog] = []
    prev_p0 = None

    print(f"\n{'='*60}")
    print(f"  🦐🦐🦐 三虾互杠工作流启动")
    print(f"  类型={content_type}  等级=Level {critic_level}  最大轮次={MAX_ROUNDS}")
    print(f"{'='*60}\n")

    # ── Round 1：ProposalShrimp 出初稿 ──────────────────────────
    print(f"[Round 1] ProposalShrimp 产出初稿")
    proposal = _run_proposal_v1(user_request, provider)

    # ── 迭代循环 ────────────────────────────────────────────────
    for iteration in range(1, MAX_ROUNDS + 2):   # +2 是因为最后一轮是终审
        round_num = iteration + 1   # 对外展示的轮次（Round 2 开始）

        # Round 2, 3, 4...：并发审查
        print(f"\n[Round {round_num}] 双虾并发审查...")
        critic_out, devil_out = await _run_review_round_async(
            proposal, content_type, critic_level, round_num, provider
        )

        p0, p1 = _count_issues(critic_out)
        print(f"[Round {round_num}] 审查完成：P0={p0}  P1={p1}")

        # ── 防死循环：P0 没有减少 → 强制终止 ────────────────────
        if prev_p0 is not None and p0 >= prev_p0 and iteration > 1:
            print(f"\n⚠️  P0 数量未减少（上轮={prev_p0}，本轮={p0}），强制终止，输出分歧清单")
            rounds.append(RoundLog(round_num, proposal, critic_out, devil_out, p0, p1, "forced_stop"))
            return WorkflowResult(
                final_proposal=proposal,
                final_critic_report=critic_out,
                rounds=rounds,
                total_rounds=round_num,
                status="forced_stop",
                content_type=content_type,
                critic_level=critic_level,
            )

        # ── 通过条件：P0 = 0 ─────────────────────────────────────
        if p0 == 0:
            print(f"\n✅ P0 = 0，终审通过！")
            rounds.append(RoundLog(round_num, proposal, critic_out, devil_out, p0, p1, "passed"))
            return WorkflowResult(
                final_proposal=proposal,
                final_critic_report=critic_out,
                rounds=rounds,
                total_rounds=round_num,
                status="passed",
                content_type=content_type,
                critic_level=critic_level,
            )

        # ── 还有 P0，且未到最大轮次 → ProposalShrimp 迭代 ────────
        rounds.append(RoundLog(round_num, proposal, critic_out, devil_out, p0, p1, "ongoing"))
        prev_p0 = p0

        if iteration > MAX_ROUNDS:
            # 超过最大轮次，强制结束
            print(f"\n⚠️  已达最大轮次 {MAX_ROUNDS}，强制结束")
            return WorkflowResult(
                final_proposal=proposal,
                final_critic_report=critic_out,
                rounds=rounds,
                total_rounds=round_num,
                status="max_rounds",
                content_type=content_type,
                critic_level=critic_level,
            )

        # ProposalShrimp 迭代
        print(f"\n[Round {round_num}→迭代] ProposalShrimp 产出 v{iteration + 1}")
        proposal = _run_proposal_iterate(
            user_request, proposal, critic_out, devil_out,
            version=iteration + 1, provider=provider,
        )

    # 不应该走到这里，保险起见
    return WorkflowResult(
        final_proposal=proposal,
        final_critic_report="",
        rounds=rounds,
        total_rounds=MAX_ROUNDS + 1,
        status="max_rounds",
        content_type=content_type,
        critic_level=critic_level,
    )


def run_workflow(
    user_request: str,
    content_type: str = "auto",
    critic_level: int | None = None,
    provider: str | None = None,
) -> WorkflowResult:
    """同步包装器，非 async 上下文直接调用这个"""
    return asyncio.run(run_workflow_async(user_request, content_type, critic_level, provider))


# ── 报告渲染 ─────────────────────────────────────────────────────

def render_workflow_report(result: WorkflowResult) -> str:
    """把 WorkflowResult 渲染成完整的 Markdown 报告"""
    status_emoji = {"passed": "✅", "forced_stop": "⚠️", "max_rounds": "⏰"}
    status_desc  = {
        "passed":      "终审通过，无 P0 问题",
        "forced_stop": "强制终止，P0 数量未收敛，需人工介入",
        "max_rounds":  f"已达最大轮次（{MAX_ROUNDS} 轮），尚有未解决问题",
    }

    lines = [
        "# 🦐🦐🦐 三虾互杠工作流报告\n",
        f"**内容类型**: {result.content_type}",
        f"**杠精等级**: Level {result.critic_level}",
        f"**总轮次**: {result.total_rounds} 轮",
        f"**最终状态**: {status_emoji.get(result.status, '?')} {status_desc.get(result.status, result.status)}",
        f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
    ]

    # 每轮摘要
    lines.append("## 📋 各轮审查摘要\n")
    lines.append("| 轮次 | P0 | P1 | 状态 |")
    lines.append("|-----|----|----|------|")
    for r in result.rounds:
        status_map = {"ongoing": "🔄 继续迭代", "passed": "✅ 通过", "forced_stop": "⚠️ 强制终止"}
        lines.append(f"| Round {r.round_num} | {r.p0_count} | {r.p1_count} | {status_map.get(r.status, r.status)} |")

    lines.append("\n---\n")

    # 最终版方案
    lines.append("## 🏆 最终版本（ProposalShrimp 产出）\n")
    lines.append(result.final_proposal)
    lines.append("\n---\n")

    # 最终审查报告
    lines.append("## 🔍 终审 Review Report（CriticShrimp）\n")
    lines.append(result.final_critic_report)
    lines.append("\n---\n")

    # 完整轮次 log（折叠展示）
    if len(result.rounds) > 1:
        lines.append("## 📜 完整审查历史\n")
        for r in result.rounds:
            lines.append(f"<details>\n<summary>Round {r.round_num} 详情（P0={r.p0_count}, P1={r.p1_count}）</summary>\n")
            lines.append(f"\n### CriticShrimp 审查\n\n{r.critic_review}\n")
            lines.append(f"\n### DevilShrimp 质疑\n\n{r.devil_review}\n")
            lines.append("</details>\n")

    # 强制终止时输出分歧清单
    if result.status == "forced_stop":
        lines.append("\n---\n")
        lines.append("## ⚠️ 分歧清单（需人工决策）\n")
        lines.append("以下问题在多轮迭代后仍未收敛，请人工判断：\n")
        lines.append(result.final_critic_report)

    return "\n".join(lines)
