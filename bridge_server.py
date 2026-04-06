#!/usr/bin/env python3
"""
Bridge Server — OpenClaw Agent 桥接服务
========================================
在 OpenClaw 会话中运行此服务，让外部项目可以调用 Sherry1号 的能力。

启动：
  python bridge_server.py [--port 8787]

然后在外部项目终端正常使用，所有 provider=local 的调用会走这里。
"""

import argparse
import json
import http.server
import socketserver
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


def call_agent_with_tools(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """
    使用 OpenClaw 工具调用 Agent 能力。
    这个函数只能在 OpenClaw 会话环境中运行。
    """
    # 尝试导入 OpenClaw 工具
    try:
        # 在 OpenClaw 环境中，这些工具可以直接使用
        from sessions_send import sessions_send
        from sessions_list import sessions_list
        print(f"[Bridge] 调用 Agent... prompt长度={len(user_prompt)}")
        
        # 组合成完整提示
        full_prompt = f"""[System]
{system_prompt}

[User Request]
{user_prompt}

请直接输出回答内容，不要添加额外说明。"""
        
        # 在当前会话中发送消息（我们需要知道自己的 session key）
        # 实际上，我们需要一个不同的机制，因为 sessions_send 需要 target session
        # 在 bridge server 中，我们应该直接处理请求
        
        # 暂时返回一个提示，说明需要实现具体的调用逻辑
        return """[Bridge Server Active]

当前已实现桥接服务框架，但需要具体的 Agent 调用实现。

可选方案：
1. 使用 OpenClaw 的 MCP (Model Context Protocol) 功能
2. 通过 sessions_spawn 创建一个专门的 Agent 会话处理请求
3. 在当前会话中轮询请求文件并响应

请确认你希望使用哪种方式。"""
        
    except ImportError:
        return """错误：Bridge Server 必须在 OpenClaw 会话环境中运行。

在 OpenClaw 会话中启动：
  python bridge_server.py

然后在另一个终端运行你的项目。"""


class BridgeHandler(http.server.BaseHTTPRequestHandler):
    """处理来自项目端的 HTTP 请求"""
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[Bridge] {self.client_address[0]} - {format % args}")
    
    def do_POST(self):
        if self.path == "/chat":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                
                system_prompt = data.get("system", "")
                user_prompt = data.get("prompt", "")
                max_tokens = data.get("max_tokens", 4096)
                
                print(f"[Bridge] 收到请求: prompt长度={len(user_prompt)}")
                
                # 调用 Agent
                response = call_agent_with_tools(system_prompt, user_prompt, max_tokens)
                
                # 返回响应
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "response": response,
                    "status": "ok"
                }, ensure_ascii=False).encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": str(e),
                    "status": "error"
                }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """健康检查端点"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "service": "gangjing-bridge",
                "agent": "Sherry1号"
            }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def main():
    parser = argparse.ArgumentParser(description="Gangjing Bridge Server")
    parser.add_argument("--port", "-p", type=int, default=8787, help="服务端口 (默认: 8787)")
    parser.add_argument("--host", "-H", default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    args = parser.parse_args()
    
    with socketserver.TCPServer((args.host, args.port), BridgeHandler) as httpd:
        print(f"=" * 60)
        print(f"🌉 Gangjing Bridge Server 已启动")
        print(f"   地址: http://{args.host}:{args.port}")
        print(f"   Agent: Sherry1号 (OpenClaw)")
        print(f"=" * 60)
        print(f"\n在另一个终端运行项目：")
        print(f"   export GANGJING_BRIDGE_URL=http://{args.host}:{args.port}")
        print(f"   python main.py --input \"测试内容\"")
        print(f"\n按 Ctrl+C 停止服务\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Bridge] 服务已停止")


if __name__ == "__main__":
    main()
