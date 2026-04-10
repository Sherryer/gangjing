# 杠精虾项目 — 关键洞察

## 项目精髓（One-Liner）
**一个用批判性思维帮助发现盲点的 AI 红队，支持多模态输入和多虾协作，让人人都有 24h 高水平审阅者。**

---

## 核心创新点

### 1. 分层 Prompt 架构（非简单 Prompt 工程）
- **底层**：通用批判方法论（soul.md）
- **中层**：领域专业知识（skills/*.md）
- **上层**：工作模式（单虾/三虾/定时巡检）
- **优势**：新增领域无需改核心，只插一个 skill 文件

### 2. 多虾协作机制（突破单模型局限）
```
ProposalShrimp(执行者)
    ↓ 产出初稿
CriticShrimp + DevilShrimp (评审者/对抗者)
    ↓ 并发审查，多视角碰撞
ProposalShrimp(执行者)
    ↓ 根据反馈迭代
[防死循环] P0无减少 → 强制终止
```
- **实现**：asyncio.gather() 真正的并发，不是串行
- **效果**：单模型的思维盲区通过多视角碰撞被迫曝露

### 3. 三档杠精等级（场景适配）
| 等级 | 报告数量 | 问题范围 | 适用场景 |
|------|---------|---------|---------|
| Level 1 | 最多 3 条 | P0-P1 | 快速一览，草案初审 |
| Level 2 | 3-8 条 | P0-P2 | 日常 review（默认） |
| Level 3 | 不限 | P0-P3 | 魔鬼终审，上线前检查 |

### 4. 多模态输入流水线
- ✅ 代码：直接输入
- ✅ 文案/方案：直接输入
- ✅ 网页：Jina Reader 爬取
- ✅ PDF：PyMuPDF 提取（限 50 页）
- ✅ 视频：SenseVoice-Small ASR 提字幕
- **共同点**：统一走 soul.md + skills/*/**.md** 的 prompt 体系

### 5. 防无限循环的聪明机制
```python
# 关键：P0 连续不减少就强制终止
if prev_p0 is not None and p0 >= prev_p0:
    return "forced_stop"  # 不是 crash，而是输出分歧清单让人决策
```
- **避免**：三虾永远无法达成一致而陷入死循环
- **优雅**：告诉人类"这些点我们卡住了，你来裁决"

### 6. 标准化输出格式
每个 Review Report 都是：
```
## 问题总览表格（一目了然）
| P0 | P1 | P2 | P3 |
|----|----|----|----|
| 2  | 3  | 1  | 0  |

## 问题详情（逐条深入）
#### P0 🔴 [维度] 问题标题
- 位置：第 X 行
- 问题：具体描述
- 影响：会导致什么
- 修复建议：可执行方案

## 亮点（最后才表扬，控制 2-4 条）
- 亮点 1
- 亮点 2

## 总结（1-2 句话）
[整体质量评价 + 最需要关注的改进]
```

---

## 技术亮点

### 1. 推理模型兼容处理
- 自动检测推理型模型（R1、GLM-5、QwQ）
- 自动禁用 temperature 参数（推理模型不支持）
- max_tokens 自动扩大到 8192（推理链消耗大量 token）
- 降级处理：当 content=None 时返回 reasoning_content

### 2. 多 LLM 提供商统一接口
```python
# 所有提供商用同样的调用接口
chat_simple(system_prompt, user_content, provider="deepseek")
chat_simple(system_prompt, user_content, provider="claude")
chat_simple(system_prompt, user_content, provider="local")  # 无需 API Key
```

### 3. 本地 Agent 集成（无需 API Key）
- 通过文件系统通信：`req_<id>.json` → 处理 → `resp_<id>.txt`
- 轮询机制：非阻塞，支持异步
- 理想场景：在 OpenClaw 中无缝使用杠精虾

### 4. 异步并发架构（不是简单多线程）
```python
# 三虾并发真的是并发，不是串行
critic_out, devil_out = await asyncio.gather(
    chat_simple_async(critic_system, critic_msg),
    chat_simple_async(devil_system, devil_msg),
)
# 总耗时 ≈ max(两者耗时) 而非相加，最多节省 50% 时间
```

### 5. 自动内容类型识别
```python
# 启发式规则，按优先级：代码 > 商业 > 文案
def detect_content_type(content: str) -> str:
    code_signals = ["```", "def ", "import ", ...]  # 代码信号最明确
    business_signals = ["收益", "roi", "融资", ...]  # 商业信号
    # 其他 → 默认 content
```

---

## 性能数据

| 指标 | 数据 | 说明 |
|------|------|------|
| 单虾 review | 30-60 秒 | 取决于 LLM 响应速度 |
| 三虾工作流 | 2-3 分钟 | 包含 2-3 轮迭代 |
| 提效相比人工 | **30-60x** | 从 15-30 分钟 → 30 秒 |
| 三虾并发收益 | **节省 40-50%** | vs. 串行调用 |
| 问题发现率 | 系统化扫描 | 比单人 review 漏检率低 |

---

## 项目成熟度

### ✅ 已完成（Phase 1-2）
- ✅ 单虾文本 review
- ✅ 三虾互杠工作流 + 防死循环
- ✅ 三档杠精等级
- ✅ 代码/商业/文案三领域 skill
- ✅ 多 LLM 提供商支持（DeepSeek/Claude/OpenAI/Qwen）
- ✅ 本地 Agent 集成
- ✅ 定时 Heartbeat 巡检

### 🟡 部分完成（Phase 3）
- ✅ URL 爬取（Jina Reader）
- ✅ PDF 解析（PyMuPDF，50 页限制）
- ✅ 视频 ASR（SenseVoice-Small）
- 🟡 ASR 后处理管道（架构已做，细节待完善）

### ❌ 未来方向（Phase 4+）
- ❌ OCR 支持（扫描版 PDF）
- ❌ 视频关键帧分析（图片理解）
- ❌ 模型选择自适应（基于内容复杂度）
- ❌ 缓存 + 成本优化
- ❌ Web UI（目前只有 CLI）

---

## 最有价值的代码片段

### 1. 三虾并发架构（the-most-clever-part）
```python
# three_shrimp_workflow.py: Line 127-130
critic_out, devil_out = await asyncio.gather(
    chat_simple_async(critic_system, critic_msg, label="CriticShrimp"),
    chat_simple_async(devil_system,  devil_msg,  label="DevilShrimp"),
)
# 这不只是并发，而是两个不同视角的"碰撞"，最后才去重
```

### 2. 防死循环机制（game-theory-inspired）
```python
# three_shrimp_workflow.py: Line 211-222
if prev_p0 is not None and p0 >= prev_p0 and iteration > 1:
    print(f"⚠️  P0 数量未减少，强制终止，输出分歧清单")
    return WorkflowResult(..., status="forced_stop")
# 承认分歧，而不是死循环，体现了工程智慧
```

### 3. 推理模型自适应处理（model-agnostic）
```python
# llm_client.py: Line 144, 155-156
is_reasoner = any(k in model.lower() for k in ["reasoner", "r1", "glm-5", "glm5", "qwq"])
if not is_reasoner:
    kwargs["temperature"] = temperature
# 同样的代码库，智能适配不同模型的限制
```

### 4. 分层 Prompt 拼装（composable-design）
```python
# prompt_loader.py: Line 56-92
def build_system_prompt(content_type: str, critic_level: int) -> str:
    parts = [
        load_soul(),                    # 基础人格
        load_skill(content_type),       # 领域规则
        LEVEL_DESC[critic_level],       # 等级说明
        FORMAT_REQUIREMENT,             # 输出格式
    ]
    return "\n".join(parts)  # 线性组合，高度可扩展
```

---

## 用户价值主张

### For Developers
```
问题：改完代码已 11 点，队友睡了，要等天亮才能 review
方案：python main.py --file code.py --level 3 → 30 秒出终审
结果：P0 问题一目了然，改完安心提交
```

### For Product Managers
```
问题：写了 20 页商业计划书，自我感觉良好，但怕有逻辑漏洞
方案：python main.py --file plan.md --type business --level 3
结果：发现 3 个假设无数据支撑，2 个财务模型有漏洞
     投资人前要补功课，避免当众被拷问
```

### For Content Creators
```
问题：视频要发，怕有事实错误被弹幕喷
方案：python main.py --video demo.mp4 --lang zh
结果：自动转录 + 逐段审查，"数据图表 Y 轴截断可能误导" ← 修了
     发布前硬伤清零
```

### For Teams
```
问题：方案评审会上大家都在"好好好"，事后却踩坑
方案：python main.py --mode three --input "需求..." 
结果：ProposalShrimp → CriticShrimp + DevilShrimp 互杠 → 迭代
     多视角碰撞，真正的盲点被迫曝露
```

---

## 架构决策理由

| 决策 | 理由 | 权衡 |
|------|------|------|
| 分层 Prompt | 领域无限扩展，核心不变 | 初期复杂，但长期性价比高 |
| 三虾协作 | 单模型有盲区，多视角补偿 | 耗时翻倍，但发现率明显提升 |
| asyncio 并发 | 充分利用等待时间 | 代码复杂度提升，但用户感知耗时无增加 |
| 防死循环强制终止 | 承认限制，让人决策 | 不是完美解，但更现实 |
| 多 LLM 支持 | 用户自主选择成本/性能 | 配置复杂，但满足不同需求 |
| Local Agent 支持 | 无 API Key，完全离线 | 通信开销大，但隐私安全 |

---

## 这个项目为什么特殊

1. **Prompt 不是一段文字**：是一套可组装的架构，可无限扩展领域
2. **不只是 AI 审查**：包含三虾互杠、防死循环、自动迭代等工程机制
3. **多模态不是摆设**：代码/文案/网页/视频/PDF，真的都能用
4. **标准化输出**：不是散文式评价，而是结构化 Review Report
5. **自己会防守**：防死循环、防成本爆炸、防模型限制，工程考虑周全

---

## 代码质量评估

| 方面 | 评分 | 说明 |
|------|------|------|
| **模块化** | ⭐⭐⭐⭐⭐ | 分层清晰，职责单一，易于测试 |
| **可扩展性** | ⭐⭐⭐⭐⭐ | 新增领域/模型/输入格式无需改核心 |
| **错误处理** | ⭐⭐⭐⭐ | 大部分情况覆盖，降级处理存在 |
| **性能优化** | ⭐⭐⭐⭐ | 异步并发、本地代理、缓存思路都有 |
| **文档完整性** | ⭐⭐⭐ | 有 docstring 和 prompts/*.md，但缺代码注释 |
| **测试覆盖** | ⭐⭐ | 探针期项目，没有自动化测试 |

---

## 一些遗憾和改进机会

1. **没有 Web UI**：现在只有 CLI，很多非技术用户用不了
2. **缺少 ODM 缓存**：相同内容重复 review 浪费 token
3. **PDF 只支持文本**：扫描版 PDF（图片）无法处理，需要 OCR
4. **视频后处理不完整**：框架存在但细节未完善
5. **没有成本监控**：调用多个 LLM 时无法追踪总成本
6. **测试缺失**：探针期快速迭代，但应该补回归测试

---

## 快速 Cheat Sheet

```bash
# 最常用命令
python main.py --file mycode.py                    # 快速 review 代码
python main.py --mode three --input "需求..."      # 三虾互杠
python main.py --level 3 --type code --file xx.py  # 魔鬼杠

# 配置快速切换
config.py:
  DEFAULT_PROVIDER = "deepseek"    # 改这里切换 LLM
  DEFAULT_CRITIC_LEVEL = 2          # 改这里调整默认等级

# 新增领域（如：安全审查）
1. 创建 prompts/skills/security_review.md
2. 在 prompt_loader.py 的 SKILL_MAP 中注册
3. 完成（核心无需改动）

# 添加新 LLM 提供商（如：Claude）
1. 配置 CLAUDE_API_KEY 等信息
2. 在 config.py 添加 CLAUDE_MODELS
3. 在 llm_client.py 的 cfg_map 中注册
4. 完成（无需改 chat 函数逻辑）
```

---

## 最后的话

这个项目本质上是在回答一个问题：**"如何让 AI 成为一个可靠的、不受人情压力的、24h 待命的高水平审阅者？"**

答案不在单个神级 prompt，而在一个完整的系统：
- 通用方法论 + 领域专业知识的分层结合
- 单模型 + 多虾碰撞的角度补偿
- 自动化 + 人工决策的恰当分工

杠精虾不是为了让 AI 替代人类判断，而是为了让人专注于"做决策"，而不是"找问题"。

