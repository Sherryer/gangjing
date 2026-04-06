"""
LLM 客户端封装
==============
统一接入 DeepSeek / Claude / OpenAI / Qwen / Venus。
切换模型只需改 config.py 里的 DEFAULT_PROVIDER。

设计原则：
- 所有提供商统一走 OpenAI 兼容协议（除 Claude 用 Anthropic SDK）
- 自动重试（网络抖动）
- 统一的错误处理
"""

import time
import asyncio
import httpx
from openai import OpenAI, AsyncOpenAI
import config


# ── 构建各提供商的 client ───────────────────────────────────────

def _make_openai_compat_client(base_url: str, api_key: str) -> OpenAI:
    """创建 OpenAI 兼容协议的客户端（DeepSeek / Qwen / Venus 都用这个）"""
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=config.DEFAULT_TIMEOUT,
        max_retries=config.DEFAULT_MAX_RETRIES,
    )


# 按提供商预建 client（懒加载，用到哪个建哪个）
_clients: dict = {}
_async_clients: dict = {}

def _get_client(provider: str) -> OpenAI:
    if provider in _clients:
        return _clients[provider]

    if provider == "deepseek":
        client = _make_openai_compat_client(config.DEEPSEEK_BASE_URL, config.DEEPSEEK_API_KEY)
    elif provider == "openai":
        client = _make_openai_compat_client(config.OPENAI_BASE_URL, config.OPENAI_API_KEY)
    elif provider == "qwen":
        client = _make_openai_compat_client(config.QWEN_BASE_URL, config.QWEN_API_KEY)
    elif provider == "venus":
        client = _make_openai_compat_client(config.VENUS_BASE_URL, config.VENUS_API_KEY)
    elif provider == "claude":
        client = _make_openai_compat_client(config.CLAUDE_BASE_URL, config.CLAUDE_API_KEY)
    else:
        raise ValueError(f"未知的提供商: {provider}，请检查 config.py 中的 DEFAULT_PROVIDER")

    _clients[provider] = client
    return client


def _get_async_client(provider: str) -> AsyncOpenAI:
    """获取异步版 client（三虾并发调用用）"""
    if provider in _async_clients:
        return _async_clients[provider]

    cfg_map = {
        "deepseek": (config.DEEPSEEK_BASE_URL, config.DEEPSEEK_API_KEY),
        "openai":   (config.OPENAI_BASE_URL,   config.OPENAI_API_KEY),
        "qwen":     (config.QWEN_BASE_URL,     config.QWEN_API_KEY),
        "venus":    (config.VENUS_BASE_URL,    config.VENUS_API_KEY),
        "claude":   (config.CLAUDE_BASE_URL,   config.CLAUDE_API_KEY),
    }
    if provider not in cfg_map:
        raise ValueError(f"未知的提供商: {provider}")

    base_url, api_key = cfg_map[provider]
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=config.DEFAULT_TIMEOUT,
        max_retries=config.DEFAULT_MAX_RETRIES,
    )
    _async_clients[provider] = client
    return client


# ── 核心调用函数 ────────────────────────────────────────────────

def chat(
    messages: list[dict],
    model: str | None = None,
    provider: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    """
    统一的 LLM 调用入口。

    参数：
        messages:    对话历史，格式 [{"role": "system"|"user"|"assistant", "content": "..."}]
        model:       模型名，不传则用各提供商的默认模型
        provider:    提供商，不传则用 config.DEFAULT_PROVIDER
        max_tokens:  最大输出 token 数
        temperature: 温度（DeepSeek R1 推理模型不支持，会自动忽略）

    返回：
        模型输出的文本字符串
    """
    provider = provider or config.DEFAULT_PROVIDER
    max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS

    # 确定模型名
    if model is None:
        model_map = {
            "deepseek": config.DEEPSEEK_MODELS[config.DEEPSEEK_DEFAULT_MODEL],
            "openai":   config.OPENAI_MODELS[config.OPENAI_DEFAULT_MODEL],
            "qwen":     config.QWEN_MODELS[config.QWEN_DEFAULT_MODEL],
            "claude":   config.CLAUDE_MODELS[config.CLAUDE_DEFAULT_MODEL],
            "venus":    config.VENUS_MODELS[config.VENUS_DEFAULT_MODEL],
        }
        model = model_map[provider]

    client = _get_client(provider)

    # 推理模型列表（这类模型不支持 temperature，且需要更大的 max_tokens 完成推理）
    # GLM-5 / DeepSeek R1 / QwQ 都属于推理模型
    is_reasoner = any(k in model.lower() for k in ["reasoner", "r1", "glm-5", "glm5", "qwq"])

    # 推理模型需要更大的 token 空间（推理链本身会消耗大量 token）
    # 如果用户传了 max_tokens 就尊重用户设定，否则推理模型用更大的默认值
    effective_max_tokens = max_tokens if max_tokens else (8192 if is_reasoner else config.DEFAULT_MAX_TOKENS)

    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": effective_max_tokens,
    }
    if not is_reasoner:
        kwargs["temperature"] = temperature

    print(f"[llm_client] 调用 {provider}/{model}，消息数={len(messages)}，max_tokens={effective_max_tokens}")
    start = time.time()

    response = client.chat.completions.create(**kwargs)

    elapsed = time.time() - start
    message = response.choices[0].message
    usage = response.usage

    # 推理模型兼容：GLM-5 / DeepSeek R1 会先输出 reasoning_content（思考过程），
    # 然后再输出 content（最终答案）。当 content 为 None 时说明 max_tokens 不够，
    # 推理还未完成就被截断了——这种情况记录警告并降级返回 reasoning_content。
    content = message.content
    if content is None:
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            print(f"[llm_client] ⚠️  content 为 None，推理模型未完成输出（max_tokens 可能不足）"
                  f"，降级返回 reasoning_content（前100字）：{reasoning[:100]}")
            content = reasoning
        else:
            content = ""
            print("[llm_client] ⚠️  content 和 reasoning_content 均为 None，返回空字符串")

    print(f"[llm_client] 完成，耗时={elapsed:.1f}s，"
          f"input_tokens={usage.prompt_tokens}，"
          f"output_tokens={usage.completion_tokens}")

    return content


def chat_simple(system_prompt: str, user_content: str, **kwargs) -> str:
    """
    最简调用方式，直接传 system prompt 和用户内容。
    适合单轮调用（探针期主要用这个）。
    """
    messages = [
        {"role": "system",  "content": system_prompt},
        {"role": "user",    "content": user_content},
    ]
    return chat(messages, **kwargs)


# ── 异步版本（三虾并发调用专用）──────────────────────────────────

def _extract_content(message) -> str:
    """统一处理推理模型的 content/reasoning_content 兼容逻辑"""
    content = message.content
    if content is None:
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            print("[llm_client] ⚠️  content 为 None，降级返回 reasoning_content")
            return reasoning
        return ""
    return content


def _build_kwargs(model: str, messages: list, max_tokens: int, temperature: float) -> dict:
    """构建 API 调用参数，自动处理推理模型的限制"""
    is_reasoner = any(k in model.lower() for k in ["reasoner", "r1", "glm-5", "glm5", "qwq"])
    effective_max_tokens = max_tokens if max_tokens else (8192 if is_reasoner else config.DEFAULT_MAX_TOKENS)
    kwargs = {"model": model, "messages": messages, "max_tokens": effective_max_tokens}
    if not is_reasoner:
        kwargs["temperature"] = temperature
    return kwargs, is_reasoner, effective_max_tokens


async def chat_async(
    messages: list[dict],
    model: str | None = None,
    provider: str | None = None,
    max_tokens: int | None = None,
    temperature: float = 0.7,
    label: str = "",          # 用于日志区分是哪只虾在调用
) -> str:
    """
    异步版 LLM 调用，供三虾并发使用。
    用法：await chat_async(...)
    并发用法：await asyncio.gather(chat_async(...), chat_async(...))
    """
    provider = provider or config.DEFAULT_PROVIDER

    model_map = {
        "deepseek": config.DEEPSEEK_MODELS[config.DEEPSEEK_DEFAULT_MODEL],
        "openai":   config.OPENAI_MODELS[config.OPENAI_DEFAULT_MODEL],
        "qwen":     config.QWEN_MODELS[config.QWEN_DEFAULT_MODEL],
        "claude":   config.CLAUDE_MODELS[config.CLAUDE_DEFAULT_MODEL],
        "venus":    config.VENUS_MODELS[config.VENUS_DEFAULT_MODEL],
    }
    model = model or model_map[provider]

    client = _get_async_client(provider)
    kwargs, _, effective_max_tokens = _build_kwargs(model, messages, max_tokens, temperature)

    tag = f"[{label}]" if label else "[llm_client_async]"
    print(f"{tag} 调用 {provider}/{model}，max_tokens={effective_max_tokens}")
    start = time.time()

    response = await client.chat.completions.create(**kwargs)

    elapsed = time.time() - start
    content = _extract_content(response.choices[0].message)
    usage = response.usage
    print(f"{tag} 完成，耗时={elapsed:.1f}s，"
          f"input={usage.prompt_tokens}，output={usage.completion_tokens}")

    return content


async def chat_simple_async(
    system_prompt: str,
    user_content: str,
    label: str = "",
    **kwargs,
) -> str:
    """异步版 chat_simple"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content},
    ]
    return await chat_async(messages, label=label, **kwargs)
