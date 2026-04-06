"""
CriticShrimp — 杠精虾单虾核心
==============================
探针期最小实现：接收任意内容，输出标准化 Review Report。

这是整个系统最核心的单元，后续三虾互杠都基于这个单虾扩展。
"""

from core.llm_client import chat_simple
from core.prompt_loader import build_system_prompt, detect_content_type
import config


def review(
    content: str,
    content_type: str = "auto",
    critic_level: int | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """
    对输入内容进行杠精审查，返回 Review Report。

    参数：
        content:      要审查的内容（代码/方案/文章等）
        content_type: "code" | "business" | "content" | "auto"（自动识别）
        critic_level: 1=温柔杠 / 2=正常杠 / 3=魔鬼杠，默认用 config 里的值
        provider:     LLM 提供商，默认用 config.DEFAULT_PROVIDER
        model:        模型名，默认用各提供商的默认模型

    返回：
        Markdown 格式的 Review Report 字符串
    """
    # 自动识别内容类型
    if content_type == "auto":
        content_type = detect_content_type(content)
        print(f"[CriticShrimp] 自动识别内容类型: {content_type}")

    critic_level = critic_level or config.DEFAULT_CRITIC_LEVEL

    # 构建 system prompt（soul + skill + 等级 + 格式要求）
    system_prompt = build_system_prompt(content_type, critic_level)

    # 构建用户消息
    user_message = f"请对以下内容进行 review：\n\n{content}"

    print(f"[CriticShrimp] 开始 review，类型={content_type}，等级=Level {critic_level}")

    # 调用 LLM
    report = chat_simple(
        system_prompt=system_prompt,
        user_content=user_message,
        provider=provider,
        model=model,
    )

    return report
