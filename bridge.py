#!/usr/bin/env python3
"""
Agent Bridge — OpenClaw Agent 请求处理器
=========================================
在 OpenClaw 会话中后台运行，自动处理项目的 Local Agent 请求。

使用方法（在 OpenClaw 对话中）：
  1. 后台启动桥接器：python bridge.py &
  2. 运行项目：python main.py --input "..."
  3. 桥接器自动处理所有 LLM 请求
  4. 完成后关闭桥接器：kill %1

或者更简单的方式：
  直接让我运行项目，我会同时处理请求
"""

import json
import sys
import time
from pathlib import Path

REQUEST_DIR = Path(".agent_requests")


def process_pending_requests(agent_callback=None):
    """
    处理所有待处理的请求。
    
    agent_callback: 处理请求的回调函数，接收 (system_prompt, user_prompt, max_tokens)
                    返回响应字符串
    
    返回值: 处理的请求数量
    """
    if not REQUEST_DIR.exists():
        return 0
    
    processed = 0
    for req_file in sorted(REQUEST_DIR.glob("req_*.json")):
        try:
            data = json.loads(req_file.read_text(encoding="utf-8"))
            request_id = data.get("id")
            
            # 检查是否已处理
            resp_file = REQUEST_DIR / f"resp_{request_id}.txt"
            if resp_file.exists():
                continue
            
            # 检查是否正在处理
            proc_file = REQUEST_DIR / f"proc_{request_id}.tmp"
            if proc_file.exists():
                continue
            
            # 标记为处理中
            proc_file.write_text("processing")
            
            system_prompt = data.get("system", "")
            user_prompt = data.get("prompt", "")
            max_tokens = data.get("max_tokens", 4096)
            
            print(f"[Bridge] 处理请求 {request_id[:16]}...")
            
            if agent_callback:
                try:
                    response = agent_callback(system_prompt, user_prompt, max_tokens)
                    resp_file.write_text(response, encoding="utf-8")
                    print(f"[Bridge] 响应已写入")
                    processed += 1
                except Exception as e:
                    print(f"[Bridge] 处理出错: {e}")
                    resp_file.write_text(f"[Error] {e}", encoding="utf-8")
            else:
                # 无回调，等待外部处理
                print(f"[Bridge] 等待外部处理...")
                
        except Exception as e:
            print(f"[Bridge] 读取请求出错: {e}")
    
    return processed


def run_bridge_loop(agent_callback=None, interval: float = 1.0):
    """
    持续运行桥接循环，处理请求。
    
    按 Ctrl+C 停止。
    """
    print("=" * 60)
    print("🌉 Agent Bridge 已启动")
    print(f"   请求目录: {REQUEST_DIR.absolute()}")
    print(f"   检查间隔: {interval}秒")
    print("=" * 60)
    print("\n现在可以在另一个进程运行项目：")
    print(f"   python main.py --input \"...\"")
    print("\n按 Ctrl+C 停止桥接服务\n")
    
    try:
        while True:
            count = process_pending_requests(agent_callback)
            if count > 0:
                print(f"[Bridge] 本轮处理 {count} 个请求")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[Bridge] 服务已停止")


def run_once(agent_callback=None):
    """处理一次所有待处理的请求"""
    count = process_pending_requests(agent_callback)
    print(f"[Bridge] 处理了 {count} 个请求")
    return count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Bridge")
    parser.add_argument("--once", action="store_true", help="只处理一次")
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="检查间隔(秒)")
    args = parser.parse_args()
    
    if args.once:
        run_once()
    else:
        run_bridge_loop(interval=args.interval)
