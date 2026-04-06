# ============================================================
# 杠精虾 — 全局配置
# ============================================================
# 说明：
#   - 每个模型提供商单独一个 block，按需启用
#   - DEFAULT_PROVIDER 控制当前用哪个
#   - 探针期先跑通单模型，后期换模型只改这一行
# ============================================================

# ---- 当前使用的提供商 ----
# 可选: "deepseek" | "claude" | "openai" | "qwen" | "local"
# local = 调用 Sherry1号(OpenClaw Agent) 的能力，无需 API Key
DEFAULT_PROVIDER = "deepseek"

# ---- DeepSeek（待补充 key） ----
DEEPSEEK_API_KEY  = "sk-your-deepseek-key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = {
    "reasoner": "deepseek-reasoner",   # R1，逻辑推理强，用于代码/商业 review
    "chat":     "deepseek-chat",       # V3，速度快，用于文案 review / 日常
}
DEEPSEEK_DEFAULT_MODEL = "reasoner"

# ---- Claude（待补充 key） ----
CLAUDE_API_KEY  = "sk-ant-your-claude-key"
CLAUDE_BASE_URL = "https://api.anthropic.com"
CLAUDE_MODELS = {
    "sonnet": "claude-sonnet-4-5",     # 性价比最优，日常 review
    "opus":   "claude-opus-4-5",       # 最强，重要交付物终审
}
CLAUDE_DEFAULT_MODEL = "sonnet"

# ---- OpenAI 官方（待补充 key） ----
OPENAI_API_KEY  = "sk-your-openai-key"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODELS = {
    "gpt4o":  "gpt-4o",
    "gpt4om": "gpt-4o-mini",
}
OPENAI_DEFAULT_MODEL = "gpt4o"

# ---- 通义千问（待补充 key） ----
QWEN_API_KEY  = "sk-your-qwen-key"
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
QWEN_MODELS = {
    "max":    "qwen-max",
    "vl":     "qwen-vl-max",           # 多模态，视频/图片 review 用
    "turbo":  "qwen-turbo",            # 最便宜，Heartbeat 用
}
QWEN_DEFAULT_MODEL = "max"

# ============================================================
# 通用参数
# ============================================================
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT    = 120     # 秒，DeepSeek R1 推理慢，给足时间
DEFAULT_MAX_RETRIES = 3

# 杠精等级默认值（1=温柔杠 / 2=正常杠 / 3=魔鬼杠）
DEFAULT_CRITIC_LEVEL = 2

# ---- Local Agent（无需 API Key，通过桥接服务调用 Sherry1号） ----
# 使用步骤：
#   1. 在 OpenClaw 会话中启动桥接服务: python bridge_server.py
#   2. 修改 DEFAULT_PROVIDER = "local"
#   3. 正常在项目终端运行命令
LOCAL_BRIDGE_URL = "http://localhost:8787"  # 桥接服务地址
LOCAL_DEFAULT_MODEL = "sherry1"  # 虚拟模型名
