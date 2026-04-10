# 杠精虾 — 完整项目探索总结

## 1. 项目概述

**项目名称**：杠精虾（GangjingXia）  
**定位**：多模态批判性思维 Review 引擎  
**核心概念**：一个专业、犀利但不带情绪的 AI 红队，帮助发现方案/代码/文章/决策中的漏洞、风险和盲点

### 本质定义
- **不是喷子**，而是高水平审阅者 / 红队
- **不是为了杠而杠**，而是为了让结果更 robust
- **能够审查**：代码、商业方案、内容文案、视频等多种形式的输入
- **三档可调**：温柔杠 / 正常杠 / 魔鬼杠，适配不同场景

---

## 2. 当前功能/特性

### 2.1 核心能力
| 能力 | 说明 | 状态 |
|------|------|------|
| 🦐 **单虾 Review** | 对任意内容进行批判性审查，生成标准化 Review Report | ✅ 已实现 |
| 🦐🦐🦐 **三虾互杠** | ProposalShrimp 出稿 → CriticShrimp + DevilShrimp 并行审查 → 迭代 | ✅ 已实现 |
| 🌐 **URL Review** | 通过 Jina Reader 抓取网页内容后审查 | ✅ 已实现 |
| 📄 **PDF Review** | 用 PyMuPDF 解析 PDF 后审查（支持最多 50 页） | ✅ 已实现 |
| 🎬 **视频 ASR Review** | SenseVoice-Small 提取字幕后审查（支持中英日韩粤) | ✅ 已实现 |
| ❤️ **Heartbeat 巡检** | 定时主动 review 最近的 git commit 改动 | ✅ 已实现 |

### 2.2 杠精等级
- **Level 1 🟢 温柔杠**：只报 P0-P1，最多 3 条，语气温和
- **Level 2 🟡 正常杠**：报 P0-P2，3-8 条，专业直白（默认）
- **Level 3 🔴 魔鬼杠**：报 P0-P3，数量不限，连措辞/命名/格式都不放过

### 2.3 三档内容类型审查规则
| 类型 | Skill 文件 | 关键维度 | 典型 P0 问题 |
|------|----------|---------|-----------|
| **code** | `code_review.md` | 正确性、性能、安全性、可维护性、工程规范 | 逻辑错误、内存泄漏、安全漏洞 |
| **business** | `business_review.md` | 假设合理性、财务可行性、风险评估、市场验证、执行可行性 | 核心假设不成立、本金亏损风险 |
| **content** | `content_review.md` | 事实准确性、逻辑严密性、立场偏差、受众适配、表达质量 | 事实错误、严重误导、法律问题 |

### 2.4 输出格式
- 标准化 Markdown 格式的 Review Report
- 结构：问题总览表格 → 问题详情（P0-P3 分级） → 亮点 → 总结
- 每个问题包含：维度、位置、具体描述、影响分析、修复建议

---

## 3. 整体架构

### 3.1 分层设计
```
┌─────────────────────────────────────────────────────────────┐
│ CLI 入口层（main.py）                                         │
│ - 参数解析（mode/level/type/provider）                       │
│ - 输入读取（stdin/file/url/pdf/video）                      │
│ - 输出保存                                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 工作流层                                                    │
│ - 单虾审查流程（critic_shrimp.py）                         │
│ - 三虾互杠工作流（three_shrimp_workflow.py）               │
│ - Heartbeat 定时巡检（heartbeat/scheduler.py）            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Prompt 系统层（prompts/）                                    │
│ - soul.md：通用批判人格（所有虾共享）                       │
│ - proposal_shrimp.md：方案虾人格                            │
│ - devil_shrimp.md：对立虾人格                               │
│ - skills/*.md：领域专业规则（code/business/content）       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LLM 客户端层（llm_client.py）                               │
│ - 统一的 API 调用接口                                        │
│ - 支持同步 chat() 和异步 chat_async()                       │
│ - 自动重试 + 超时控制                                       │
│ - 推理模型特殊处理（reasoning_content）                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 输入适配层（core/input_adapters/）                          │
│ - url_fetcher.py：网页抓取（Jina Reader）                  │
│ - pdf_parser.py：PDF 解析（PyMuPDF）                       │
│ - video_asr.py：视频 ASR（SenseVoice-Small）              │
│ - models.py：数据模型（Segment, ASRResult）               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 外部系统                                                    │
│ - LLM API（DeepSeek/Claude/OpenAI/Qwen）                   │
│ - Local Agent（通过 bridge_server.py）                     │
│ - 工具服务（Jina Reader, SenseVoice 模型）                 │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 关键模块职责

| 模块 | 文件 | 职责 | 重要接口 |
|------|------|------|---------|
| **CriticShrimp** | `core/critic_shrimp.py` | 核心单虾实现，进行标准化 review | `review(content, type, level)` |
| **工作流** | `core/three_shrimp_workflow.py` | 三虾迭代流程、并发调用、防死循环 | `run_workflow()`, `render_workflow_report()` |
| **LLM 客户端** | `core/llm_client.py` | 统一 API 调用，支持多个 LLM 提供商 | `chat()`, `chat_async()` |
| **Prompt 加载** | `core/prompt_loader.py` | 动态构建 system prompt，自动识别内容类型 | `build_system_prompt()`, `detect_content_type()` |
| **URL 抓取** | `core/input_adapters/url_fetcher.py` | Jina Reader 集成 | `fetch_url_for_review()` |
| **PDF 解析** | `core/input_adapters/pdf_parser.py` | PyMuPDF 集成，限制 50 页 | `parse_pdf_for_review()` |
| **视频 ASR** | `core/input_adapters/video_asr.py` | SenseVoice-Small 模型调用，字幕提取 | `transcribe_video_for_review()` |
| **本地代理** | `core/local_proxy.py` | OpenClaw Agent 文件通信桥接 | `call_agent()`, `call_agent_async()` |
| **定时巡检** | `heartbeat/scheduler.py` | Git commit 监听 + 自动 review | 每天凌晨 2 点执行 |

---

## 4. AI 模型/集成

### 4.1 LLM 提供商支持

| 提供商 | 配置变量 | 默认模型 | 推荐用途 | API 协议 |
|--------|---------|---------|---------|---------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | deepseek-reasoner | 默认推荐（R1 推理强） | OpenAI 兼容 |
| **Claude** | `CLAUDE_API_KEY` | claude-sonnet-4-5 | 重要交付物终审 | Anthropic SDK |
| **OpenAI** | `OPENAI_API_KEY` | gpt-4o | 备选方案 | OpenAI 官方 |
| **Qwen** | `QWEN_API_KEY` | qwen-max | 多模态（视频）、成本优化 | OpenAI 兼容 |
| **Local Agent** | 无需 Key | "sherry1" | 无需 API Key（通过 OpenClaw） | 文件通信 |

### 4.2 模型选择策略
```python
# llm_client.py 中的自动选择逻辑
is_reasoner = any(k in model.lower() for k in ["reasoner", "r1", "glm-5", "glm5", "qwq"])

# 推理模型特殊处理：
# - 不支持 temperature 参数
# - max_tokens 自动扩大到 8192（推理过程消耗 token）
# - 返回值可能包含 reasoning_content（思考过程）
```

### 4.3 其他 AI 集成

| 技术 | 用途 | 模型/服务 | 依赖 |
|------|------|---------|------|
| **网页抓取** | URL 内容预处理 | Jina Reader API | httpx |
| **视频 ASR** | 字幕提取 | SenseVoice-Small（阿里达摩院） | funasr, torch, ffmpeg |
| **音视频处理** | 媒体格式转换 | ffmpeg | brew install ffmpeg |

---

## 5. 主要入口和运行方式

### 5.1 CLI 入口：main.py

```bash
# 单虾 review 模式（默认）
python main.py --file code.py                 # review 文件
python main.py --input "内容"                 # review 直接输入
python main.py --url https://example.com      # review 网页
python main.py --pdf report.pdf               # review PDF
python main.py --video demo.mp4 --lang zh     # review 视频

# 三虾互杠模式
python main.py --mode three --input "需求"

# 参数调整
python main.py --level 3                      # 魔鬼杠
python main.py --type code                    # 明确内容类型
python main.py --provider deepseek            # 选择 LLM 提供商
python main.py --no-save                      # 只打印，不保存文件
python main.py --output path/to/file.md       # 指定输出路径
```

### 5.2 程序流程
```
main.py
├─ 参数解析 (argparse)
├─ 输入读取
│  ├─ URL → fetch_url_for_review()
│  ├─ PDF → parse_pdf_for_review()
│  ├─ 视频 → transcribe_video_for_review()
│  ├─ 文件 → read_from_file()
│  ├─ 直接输入 → args.input
│  └─ stdin → read_from_stdin()
├─ 模式分发
│  ├─ single 模式 → run_single_mode()
│  └─ three 模式 → run_three_mode()
├─ 执行核心逻辑
│  ├─ review(content, type, level) [单虾]
│  └─ run_workflow(request, type, level) [三虾]
├─ 结果渲染
│  ├─ 单虾：直接返回 Review Report
│  └─ 三虾：render_workflow_report(result)
├─ 输出保存
│  └─ save_output(content, output_path, ...)
└─ 终端打印
```

### 5.3 三虾互杠工作流（three_shrimp_workflow.py）

```
Round 1: ProposalShrimp 产出 v1 初稿
         ↓
Round 2: CriticShrimp + DevilShrimp 并行审查
         ↓
         ├─ P0 = 0? → 通过 ✅
         ├─ P0 无减少? → 强制终止 ⚠️
         └─ 还有 P0? → 继续迭代
         ↓
Round 3: ProposalShrimp 根据反馈产出 v2
         ↓
         [重复 Round 2-3，最多 MAX_ROUNDS (3) 轮]
         ↓
最终输出：
  - final_proposal（最优版本）
  - final_critic_report（最终审查）
  - rounds log（完整审查历史）
  - status（passed / forced_stop / max_rounds）
```

关键点：
- **并发调用**：Round 2+ 使用 `asyncio.gather()` 并行运行 Critic + Devil
- **防死循环**：P0 连续不减少时强制终止
- **版本跟踪**：每轮记录 RoundLog（轮次、P0/P1 数量、状态）

### 5.4 Heartbeat 定时巡检（heartbeat/scheduler.py）

```bash
python heartbeat/scheduler.py                 # 启动后台守护进程
python heartbeat/scheduler.py --now           # 立即跑一次（测试）
python heartbeat/scheduler.py --cron "0 2 * * *"  # 自定义 cron 表达式
```

功能：
- 每天凌晨 2 点自动 review 最近的 git commit 变更
- 支持 5 种文件类型：`.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.md`, `.txt`, `.json`, `.yaml`
- 限制每次最多 5 个文件（避免超时）
- 智能降噪：相同问题不重复报告，连续 3 天未修复则升级提醒
- 输出到 `REVIEW_LOG.md`

### 5.5 本地 Agent 桥接（bridge_server.py）

```bash
# 终端 1：启动桥接服务
python bridge_server.py

# 终端 2：运行项目（会自动通过 bridge_server 调用 Agent）
python main.py --input "..." --provider local
```

工作原理：
1. 项目写请求到 `.agent_requests/req_<id>.json`
2. Bridge 监听并处理请求
3. 通过 OpenClaw Agent 执行 LLM 调用
4. 写响应到 `.agent_requests/resp_<id>.txt`
5. 项目读取响应返回

---

## 6. Prompt 系统设计

### 6.1 杠精虾人格体系（soul.md）
核心规则：
1. **审查流程**：不表扬 → 进入"找茬模式" → 按维度逐条过 → 标注问题级别 → 排序输出
2. **检查清单**：论证逻辑、假设审查、完备性、风险评估、替代方案、数据证据
3. **问题分级**：P0(致命) / P1(重要) / P2(一般) / P3(建议)
4. **语气规则**：专业直白、就事论事、禁止嘲讽、5条以上要鼓励

### 6.2 三虾角色 Prompt

| 角色 | 文件 | 职责 | 输出格式 |
|------|------|------|---------|
| **ProposalShrimp** | `proposal_shrimp.md` | 产出初稿 / 根据反馈迭代 | 完整方案 + 自我审查备注 |
| **CriticShrimp** | `soul.md + skills/` | 系统性审查 | 标准 Review Report（表格+详情） |
| **DevilShrimp** | `devil_shrimp.md` | 对立质疑 | 对话式质疑（最多 4 个） |

### 6.3 领域 Skill 加载

```python
# prompt_loader.py 中的拼装逻辑
def build_system_prompt(content_type: str, critic_level: int) -> str:
    parts = []
    parts.append(load_soul())                      # 基础人格
    parts.append(load_skill(content_type))         # 领域规则
    parts.append(LEVEL_DESC[critic_level])         # 等级说明
    parts.append(FORMAT_REQUIREMENT)               # 输出格式
    return "\n".join(parts)
```

**内容类型自动识别**：
```python
def detect_content_type(content: str) -> str:
    code_signals = ["```", "def ", "function ", "import ", ...]
    business_signals = ["收益", "roi", "市场", "融资", ...]
    
    if any(s in content for s in code_signals):
        return "code"
    if any(s in content.lower() for s in business_signals):
        return "business"
    return "content"
```

---

## 7. 配置系统（config.py）

```python
# 当前使用的 LLM 提供商
DEFAULT_PROVIDER = "deepseek"  # 可选：deepseek/claude/openai/qwen/local

# 各提供商的 API 配置
DEEPSEEK_API_KEY = "sk-..."
DEEPSEEK_MODELS = {
    "reasoner": "deepseek-reasoner",   # 推理型，逻辑强
    "chat":     "deepseek-chat",       # 快速型
}
DEEPSEEK_DEFAULT_MODEL = "reasoner"

# 类似的配置也存在于 CLAUDE_*、OPENAI_*、QWEN_*

# 全局参数
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 120      # DeepSeek R1 推理慢，给足时间
DEFAULT_MAX_RETRIES = 3
DEFAULT_CRITIC_LEVEL = 2   # 默认正常杠

# Local Agent 配置
LOCAL_BRIDGE_URL = "http://localhost:8787"
LOCAL_DEFAULT_MODEL = "sherry1"
```

---

## 8. 依赖清单

### 系统依赖
```bash
ffmpeg          # 视频音频处理
```

### Python 依赖（requirements.txt）
```
openai>=1.30.0         # LLM API 调用
httpx>=0.27.0          # HTTP 客户端
pymupdf>=1.24.0        # PDF 解析
apscheduler>=3.10.0    # 定时任务
funasr>=1.1.0          # ASR 推理框架
modelscope>=1.18.0     # 模型下载
torch>=2.0.0           # 深度学习框架
torchaudio>=2.0.0      # 音频处理
```

---

## 9. 项目结构概览

```
gangjingxia/
├── main.py                      # CLI 入口点
├── config.py                    # 全局配置
├── bridge.py                    # Agent 桥接处理
├── bridge_server.py             # 桥接 HTTP 服务
├── requirements.txt             # 依赖声明
├── SKILL.md                     # OpenClaw Skill 文档
│
├── core/
│   ├── __init__.py
│   ├── critic_shrimp.py         # 单虾核心逻辑
│   ├── three_shrimp_workflow.py # 三虾工作流
│   ├── llm_client.py            # 统一 LLM 客户端
│   ├── prompt_loader.py         # Prompt 加载和拼装
│   ├── local_proxy.py           # 本地 Agent 代理
│   │
│   └── input_adapters/
│       ├── __init__.py
│       ├── models.py            # 数据模型（ASRResult等）
│       ├── url_fetcher.py       # URL 抓取（Jina Reader）
│       ├── pdf_parser.py        # PDF 解析（PyMuPDF）
│       ├── video_asr.py         # 视频 ASR（SenseVoice）
│       │
│       └── postprocess/         # ASR 后处理
│
├── prompts/
│   ├── soul.md                  # 杠精虾通用人格
│   ├── proposal_shrimp.md       # 方案虾 prompt
│   ├── devil_shrimp.md          # 对立虾 prompt
│   │
│   └── skills/
│       ├── code_review.md       # 代码审查规则
│       ├── business_review.md   # 商业方案审查规则
│       └── content_review.md    # 内容文案审查规则
│
├── heartbeat/
│   ├── __init__.py
│   └── scheduler.py             # 定时巡检调度
│
├── outputs/                     # Review 结果输出目录
├── doc/                         # 项目文档
│   └── 杠精虾产品介绍.md
├── docs/
│   └── local_agent_mode.md
├── probe/                       # 早期探针测试
└── .git/                        # Git 仓库
```

---

## 10. 核心流程详解

### 10.1 单虾 Review 流程

```python
def review(content: str, content_type: str, critic_level: int, provider: str) -> str:
    # 1. 自动识别内容类型
    if content_type == "auto":
        content_type = detect_content_type(content)
    
    # 2. 构建 system prompt（soul + skill + level + format）
    system_prompt = build_system_prompt(content_type, critic_level)
    
    # 3. 构建用户消息
    user_message = f"请对以下内容进行 review：\n\n{content}"
    
    # 4. 调用 LLM
    report = chat_simple(
        system_prompt=system_prompt,
        user_content=user_message,
        provider=provider,
    )
    
    return report
```

### 10.2 三虾互杠流程

```python
async def run_workflow_async(user_request: str, content_type: str, critic_level: int):
    # Round 1: ProposalShrimp 产出初稿
    proposal = _run_proposal_v1(user_request, provider)
    
    # 迭代循环（最多 MAX_ROUNDS 轮）
    for iteration in range(1, MAX_ROUNDS + 2):
        round_num = iteration + 1
        
        # Round 2+: 并发审查（CriticShrimp + DevilShrimp）
        critic_out, devil_out = await _run_review_round_async(
            proposal, content_type, critic_level, round_num, provider
        )
        
        # 计数 P0/P1
        p0, p1 = _count_issues(critic_out)
        
        # 判断是否通过
        if p0 == 0:
            return WorkflowResult(..., status="passed")
        
        # 判断是否强制终止（P0 未减少）
        if prev_p0 is not None and p0 >= prev_p0:
            return WorkflowResult(..., status="forced_stop")
        
        # 否则继续迭代
        prev_p0 = p0
        proposal = _run_proposal_iterate(
            user_request, proposal, critic_out, devil_out,
            version=iteration + 1, provider=provider
        )
    
    return WorkflowResult(..., status="max_rounds")
```

### 10.3 LLM 客户端统一接口

```python
def chat(messages: list[dict], model: str, provider: str, 
         max_tokens: int, temperature: float) -> str:
    
    # 处理 Local Agent 模式
    if provider == "local":
        response = call_agent(system_prompt, user_content, max_tokens)
        return response
    
    # 获取对应提供商的客户端
    client = _get_client(provider)
    
    # 推理模型特殊处理
    is_reasoner = "reasoner" in model.lower() or "r1" in model.lower()
    if is_reasoner:
        kwargs["max_tokens"] = 8192  # 扩大 token 空间
        # 不支持 temperature
    else:
        kwargs["temperature"] = temperature
    
    # API 调用
    response = client.chat.completions.create(**kwargs)
    
    # 处理响应
    content = response.choices[0].message.content
    if content is None:
        # 推理模型未完成，降级返回 reasoning_content
        reasoning = getattr(response.choices[0].message, "reasoning_content", None)
        if reasoning:
            content = reasoning
    
    return content
```

---

## 11. 关键算法/设计

### 11.1 P0/P1 计数和收敛检测

```python
def _count_issues(critic_output: str) -> tuple[int, int]:
    # 优先从总览表格读取
    table_p0 = re.search(r'P0.*?\|\s*(\d+)\s*条', critic_output)
    if table_p0:
        return int(table_p0.group(1)), ...
    
    # 回退：数正文标题
    p0 = len(re.findall(r'P0\s*🔴', critic_output))
    return p0, ...

# 三虾工作流中的收敛检测
if prev_p0 is not None and p0 >= prev_p0 and iteration > 1:
    # P0 连续不减少 → 强制终止
    return WorkflowResult(..., status="forced_stop")
```

### 11.2 内容类型自动识别

```python
def detect_content_type(content: str) -> str:
    # 策略：按优先级检测信号
    
    # 1. 代码信号最明确
    code_signals = ["```", "def ", "function ", "import ", "const ", "class "]
    if any(s in content for s in code_signals):
        return "code"
    
    # 2. 商业信号
    business_signals = ["收益", "roi", "市场", "用户增长", "融资", ...]
    if any(s in content.lower() for s in business_signals):
        return "business"
    
    # 3. 默认文章/文案
    return "content"
```

### 11.3 推理模型兼容处理

```python
# 推理模型的特性：
# 1. 返回 reasoning_content（思考过程）+ content（最终答案）
# 2. 不支持 temperature 参数
# 3. max_tokens 不足时可能返回 content=None

if content is None:
    reasoning = getattr(message, "reasoning_content", None)
    if reasoning:
        print("[llm_client] ⚠️  max_tokens 可能不足，降级返回 reasoning_content")
        content = reasoning
    else:
        content = ""
```

### 11.4 异步并发架构

```python
# 三虾并发审查（避免串行等待）
critic_out, devil_out = await asyncio.gather(
    chat_simple_async(critic_system, critic_msg, label="CriticShrimp"),
    chat_simple_async(devil_system,  devil_msg,  label="DevilShrimp"),
)
# 总耗时 ≈ max(CriticShrimp耗时, DevilShrimp耗时) 而非相加
```

---

## 12. 性能指标和限制

| 指标 | 值 | 说明 |
|------|-----|------|
| **单虾 review 耗时** | ~30-60 秒 | 取决于 LLM 响应速度 |
| **三虾工作流耗时** | ~2-3 分钟 | 包括 2-3 轮迭代 |
| **PDF 最大页数** | 50 页 | 超过则只取前 50 页 |
| **视频最大时长** | 2 小时 | MAX_AUDIO_DURATION |
| **Heartbeat 最多文件** | 5 个 | HEARTBEAT_MAX_FILES |
| **API 超时** | 120 秒 | DEFAULT_TIMEOUT |
| **API 重试次数** | 3 次 | DEFAULT_MAX_RETRIES |
| **三虾最大迭代轮次** | 3 轮 | MAX_ROUNDS |
| **Local Agent 等待超时** | 10 分钟 | max_wait=600s |

---

## 13. 已知限制和改进方向

### 已知限制
1. **PDF 图片内容**：无 OCR 支持，扫描版 PDF 无法处理
2. **推理模型成本**：DeepSeek R1 等推理模型费用高，实际 token 消耗多
3. **三虾串行问题**：Local Agent 模式下并发退化为串行
4. **内容检测准度**：detect_content_type 基于启发式规则，可能误分类

### 改进方向
1. **OCR 支持**：集成 Paddle OCR 或 Tesseract，处理扫描版 PDF
2. **成本优化**：调用链路中添加缓存、批量处理
3. **模型切换策略**：基于内容复杂度自动选择推理型或快速型模型
4. **视觉理解**：集成视频关键帧分析，支持视觉矛盾检测

---

## 14. 总结

### 项目定位
一个**多模态、多虾、三档可调**的批判性思维 AI 引擎。不是简单的 Prompt 工程，而是一套完整的分层架构：
- **底层**：通用批判方法论（soul.md）
- **中层**：领域专业规则（skills/*.md）
- **上层**：多种工作模式（单虾/三虾/定时巡检）

### 核心价值
- **发现盲点**：系统化审查，按维度分类，不漏关键问题
- **提效显著**：单次 review 从 15-30 分钟压低到 30 秒
- **多模态输入**：代码/方案/文案/网页/视频都能审
- **自动迭代**：三虾协作自动优化方案，人只做终审决策

### 适用场景
代码审查、商业方案评估、内容文案审核、视频质量检查、论文自审

---

**最后更新**：2026-04-10  
**项目版本**：v1.0（探针期）  
**主要贡献者**：Sherryxia
