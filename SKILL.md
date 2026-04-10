# 杠精虾 Skill

> 批判性思维 Review 引擎 — 专业、犀利、不带情绪的红队审查

## 触发条件

当用户要求以下操作时激活此 skill：
- Review / 审查 代码、方案、文章、视频
- "帮我杠一下"、"挑挑毛病"、"review 这个"
- "三虾互杠"、"杠精模式"
- "分析这个视频"、"提取视频字幕"

## 能力总览

| 能力 | 说明 | 命令 |
|------|------|------|
| 🦐 单虾 Review | 对任意内容（代码/方案/文案）进行批判性审查 | `--mode single` |
| 🦐🦐🦐 三虾互杠 | ProposalShrimp 出稿 → CriticShrimp + DevilShrimp 并行审查 → 迭代 | `--mode three` |
| 🌐 URL Review | 抓取网页内容并审查 | `--url <URL>` |
| 📄 PDF Review | 解析 PDF 文档并审查 | `--pdf <path>` |
| 🎬 视频 ASR Review | 从视频提取字幕（SenseVoice-Small）并审查 | `--video <path>` |

## 使用方式

### 方式一：直接调用脚本（推荐）

```bash
cd /home/368830_wy/.openclaw/workspace/gangjing

# 单虾 review 代码文件
python3 main.py --file code.py

# 单虾 review 直接输入的内容
python3 main.py --input "你的方案..."

# review 网页
python3 main.py --url https://example.com/article

# review PDF
python3 main.py --pdf report.pdf

# review 视频（ASR 提取字幕后审查）
python3 main.py --video demo.mp4 --lang zh

# 三虾互杠模式
python3 main.py --mode three --input "帮我写一个登录组件"

# 调整杠精等级
python3 main.py --file plan.md --level 3  # 魔鬼杠
```

### 方式二：Agent 内联 Review（无需外部 API）

当用户发来内容要求 review 时，Agent 可以直接用杠精虾的 prompt 体系进行审查：

1. 加载 `prompts/soul.md` 作为基础人格
2. 根据内容类型加载对应 skill：
   - 代码 → `prompts/skills/code_review.md`
   - 商业方案 → `prompts/skills/business_review.md`  
   - 文案内容 → `prompts/skills/content_review.md`
3. 注入杠精等级说明
4. 按标准 Review Report 格式输出

### 方式三：Local Agent 模式（桥接）

配置 `config.py` 中 `DEFAULT_PROVIDER = "local"`，通过桥接服务让杠精虾使用 Agent 自身的能力：

```bash
# 终端 1：启动桥接服务
python3 bridge_server.py

# 终端 2：运行杠精虾
python3 main.py --input "内容..."
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` / `-m` | single（单虾）或 three（三虾互杠） | single |
| `--level` / `-l` | 杠精等级：1=温柔 2=正常 3=魔鬼 | 2 |
| `--type` / `-t` | 内容类型：auto/code/business/content | auto |
| `--provider` / `-p` | LLM 提供商：deepseek/claude/openai/qwen | deepseek |
| `--lang` | 视频语言：zh/yue/en/ja/ko/auto | zh |
| `--no-save` | 不保存文件，只输出到终端 | false |

## 杠精等级

- **Level 1 🟢 温柔杠**：只报 P0-P1，最多 3 条，语气温和
- **Level 2 🟡 正常杠**：报 P0-P2，3-8 条，专业直白（默认）
- **Level 3 🔴 魔鬼杠**：报 P0-P3，不限数量，连措辞/命名/格式都不放过

## 三虾角色

| 角色 | 职责 |
|------|------|
| 🦐 ProposalShrimp（方案虾） | 根据需求产出初稿，根据审查反馈迭代改进 |
| 🦐 CriticShrimp（杠精虾） | 系统性审查，按 P0-P3 分级输出标准 Review Report |
| 🦐 DevilShrimp（对立虾） | 站在对立面质疑根本假设，逼出盲点 |

## 项目路径

```
/home/368830_wy/.openclaw/workspace/gangjing/
├── main.py                    # CLI 入口
├── config.py                  # 全局配置（API Key、模型选择）
├── bridge.py                  # Agent 桥接器
├── bridge_server.py           # 桥接 HTTP 服务
├── core/
│   ├── critic_shrimp.py       # 单虾核心
│   ├── three_shrimp_workflow.py  # 三虾互杠工作流
│   ├── llm_client.py          # LLM 调用封装
│   ├── prompt_loader.py       # Prompt 加载器
│   ├── local_proxy.py         # 本地 Agent 代理
│   └── input_adapters/
│       ├── url_fetcher.py     # 网页抓取
│       ├── pdf_parser.py      # PDF 解析
│       └── video_asr.py       # 视频 ASR（SenseVoice-Small）
└── prompts/
    ├── soul.md                # 杠精虾人格
    ├── proposal_shrimp.md     # 方案虾 prompt
    ├── devil_shrimp.md        # 对立虾 prompt
    └── skills/
        ├── code_review.md     # 代码审查规则
        ├── business_review.md # 商业方案审查规则
        └── content_review.md  # 内容文案审查规则
```

## 依赖

### 系统依赖
- ffmpeg（视频 ASR 需要）

### Python 依赖
- torch, torchaudio（ASR 推理）
- funasr, modelscope（SenseVoice-Small 模型）
- openai, httpx（LLM 调用）
- pymupdf（PDF 解析）
- librosa, scipy, soundfile（音频处理）
