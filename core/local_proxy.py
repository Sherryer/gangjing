"""
Local Agent Proxy — 本地 Agent 代理
====================================
当 provider="local" 时，通过文件通信调用 Agent 能力，无需 API Key。

工作原理：
  1. 项目把请求写入 .agent_requests/req_<id>.json
  2. 等待响应文件 .agent_requests/resp_<id>.txt
  3. Agent (Sherry1号) 检测并处理请求，写入响应
  4. 项目读取响应并返回

使用方式：
  在 OpenClaw 会话中运行项目时，直接说"运行 python main.py ..."
  我会自动处理所有 local provider 的请求。
"""

import json
import os
import time
from pathlib import Path

# 请求/响应目录
REQUEST_DIR = Path(".agent_requests")


def _ensure_request_dir():
    """确保请求目录存在"""
    REQUEST_DIR.mkdir(exist_ok=True)


def _generate_request_id() -> str:
    """生成唯一请求 ID"""
    import uuid
    return f"{time.time():.6f}_{uuid.uuid4().hex[:8]}"


def call_agent(system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
    """
    调用本地 Agent 能力（同步阻塞）。
    
    返回 Agent 生成的回复内容。
    """
    _ensure_request_dir()
    
    request_id = _generate_request_id()
    request_file = REQUEST_DIR / f"req_{request_id}.json"
    response_file = REQUEST_DIR / f"resp_{request_id}.txt"
    
    # 写入请求
    request_data = {
        "id": request_id,
        "system": system_prompt,
        "prompt": user_content,
        "max_tokens": max_tokens,
        "timestamp": time.time(),
    }
    request_file.write_text(json.dumps(request_data, ensure_ascii=False))
    
    print(f"[LocalProxy] 请求已创建: {request_file.name}")
    print(f"[LocalProxy] 等待 Agent 处理...")
    
    # 等待响应（轮询）
    wait_time = 0
    poll_interval = 0.5
    max_wait = 600  # 最多等10分钟
    
    while wait_time < max_wait:
        if response_file.exists():
            try:
                response = response_file.read_text(encoding="utf-8")
                # 清理文件
                request_file.unlink(missing_ok=True)
                response_file.unlink(missing_ok=True)
                return response
            except Exception as e:
                print(f"[LocalProxy] 读取响应出错: {e}")
        
        time.sleep(poll_interval)
        wait_time += poll_interval
        
        # 每 10 秒打印一次等待提示
        if int(wait_time) % 10 == 0 and wait_time > 0:
            print(f"[LocalProxy] 已等待 {int(wait_time)} 秒...")
    
    # 超时清理
    request_file.unlink(missing_ok=True)
    raise TimeoutError(
        f"等待 Agent 响应超时 ({max_wait}秒)。\n"
        "请确保在 OpenClaw 会话中运行，Agent 才能处理请求。"
    )


async def call_agent_async(system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
    """
    异步版本，供三虾并发调用。
    
    注意：local 模式下并发会串行执行。
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, call_agent, system_prompt, user_content, max_tokens)


def check_and_process_requests():
    """
    Agent 端使用：检查并处理待处理的请求。
    
    这个函数应该由 Sherry1号 在 OpenClaw 会话中定期调用。
    
    使用方式（在 OpenClaw 对话中）：
      "检查并处理待处理的 Agent 请求"
    
    返回值：处理的请求数量
    """
    if not REQUEST_DIR.exists():
        return 0
    
    processed = 0
    for req_file in REQUEST_DIR.glob("req_*.json"):
        try:
            # 解析请求
            data = json.loads(req_file.read_text(encoding="utf-8"))
            request_id = data.get("id")
            system_prompt = data.get("system", "")
            user_prompt = data.get("prompt", "")
            
            # 检查是否已处理（避免重复处理）
            resp_file = REQUEST_DIR / f"resp_{request_id}.txt"
            if resp_file.exists():
                continue
            
            print(f"[AgentProxy] 处理请求: {request_id[:20]}...")
            print(f"[AgentProxy] Prompt: {user_prompt[:100]}...")
            
            # 标记请求为处理中
            processing_file = REQUEST_DIR / f"proc_{request_id}.tmp"
            processing_file.write_text("processing")
            
            # 返回待处理状态（实际处理由 Agent 完成）
            # 这里的返回值表示找到了待处理请求
            processed += 1
            
        except Exception as e:
            print(f"[AgentProxy] 处理请求出错: {e}")
    
    return processed


if __name__ == "__main__":
    # 测试
    print("Local Agent Proxy 测试")
    print("=" * 50)
    
    # 创建一个测试请求
    test_id = _generate_request_id()
    test_req = REQUEST_DIR / f"req_{test_id}.json"
    test_resp = REQUEST_DIR / f"resp_{test_id}.txt"
    
    test_data = {
        "id": test_id,
        "system": "你是一个测试助手",
        "prompt": "这是一个测试请求",
        "max_tokens": 100,
        "timestamp": time.time(),
    }
    
    test_req.write_text(json.dumps(test_data, ensure_ascii=False))
    print(f"创建测试请求: {test_req.name}")
    print("请在 OpenClaw 会话中运行: 检查 Agent 请求")
    print("然后创建响应文件继续测试...")
