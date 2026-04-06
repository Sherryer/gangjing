# 本地 Agent 模式 — 最终方案

## 方案选择

根据你的使用场景，推荐以下两种方案：

---

## 方案 1: OpenClaw 直接运行（最简单 ⭐⭐⭐）

**适用场景:** 日常开发，快速 review

**使用方法:**

1. **配置项目** (`config.py`):
```python
DEFAULT_PROVIDER = "local"
```

2. **在 OpenClaw 对话中直接告诉我:**
> "帮我 review 这个文件：python main.py --file code.py"

3. **我直接处理:**
- 读取 code.py
- 根据项目 prompt 生成 review
- 输出结果并保存到 outputs/

**优点:**
- ✅ 无需 API Key
- ✅ 无需复杂配置
- ✅ 对话式交互

**工作原理:**
项目代码实际上**不会真正运行**。我看到命令后，直接：
1. 解析你要 review 的内容
2. 使用项目的 prompts/ 目录下的 system prompt
3. 生成 review report
4. 保存到 outputs/ 目录

---

## 方案 2: 混合模式（最灵活 ⭐⭐）

**适用场景:** 需要项目实际运行（如测试新功能）

**使用方法:**

1. **保持 API 模式开发** (`config.py`):
```python
DEFAULT_PROVIDER = "deepseek"  # 或其他
DEEPSEEK_API_KEY = "sk-xxx"
```

2. **需要我 review 时，直接发内容给我:**
> "帮我 review 这段代码：[粘贴代码]"

或

> "读取 gangjing/outputs/xxx.md，帮我改进"

**优点:**
- ✅ 项目完全独立运行
- ✅ 需要我时直接对话
- ✅ 适合复杂场景

---

## 方案对比

| 场景 | 推荐方案 | 说明 |
|------|----------|------|
| 快速 review 代码/文档 | 方案 1 | 直接告诉我运行命令 |
| 测试项目新功能 | 方案 2 | 用 API Key 运行，有问题问我 |
| 批量处理文件 | 方案 1 | 我帮你批量处理 |
| CI/CD 部署 | API Key | 生产环境必须用 API |

---

## 快速开始（方案 1）

### 步骤 1: 配置 local 模式

```bash
# 修改 config.py
sed -i 's/DEFAULT_PROVIDER = "deepseek"/DEFAULT_PROVIDER = "local"/' config.py
```

### 步骤 2: 使用项目

直接在 OpenClaw 对话中说：

```
运行杠精虾 review 这个文件：python main.py --file src/utils.py --type code
```

或

```
帮我用三虾模式生成一个 React Popover 组件方案：
python main.py --mode three --input "写一个 React Popover 组件，支持定位、动画、点击外部关闭"
```

### 步骤 3: 获取结果

我会：
1. 执行你的意图（读取文件、理解需求）
2. 使用项目的 prompts/ 生成回复
3. 保存到 outputs/ 目录
4. 输出结果给你

---

## 示例对话

### 示例 1: Review 代码文件

**你:**
> 帮我 review gangjing/src/main.py

**我:**
> 我来帮你 review 这个文件...
> 
> [读取 main.py]
> 
> 根据 code_review.md skill，以下是 review 结果：
> 
> ## Code Review Report
> 
> ### 1. 代码结构
> ...
> 
> 已保存到: outputs/review_code_L2_20260406_143022.md

### 示例 2: 三虾模式生成方案

**你:**
> 用三虾模式帮我设计一个用户登录系统

**我:**
> 好的，启动三虾互杠模式...
> 
> **ProposalShrimp (初稿):**
> ...
> 
> **CriticShrimp (审查):**
> ...
> 
> **DevilShrimp (魔鬼杠):**
> ...
> 
> **最终方案:**
> ...
> 
> 已保存到: outputs/three_shrimp_business_L2_20260406_143500.md

### 示例 3: Review URL 内容

**你:**
> 帮我 review 这篇文章：https://example.com/article

**我:**
> 抓取文章内容中...
> 
> 根据 content_review.md skill，以下是 review：
> ...

---

## 技术说明

### 为什么不需要 bridge_server？

在方案 1 中，项目代码**不会真正执行 LLM 调用**。当我看到你要运行项目的命令时，我会：

1. 解析命令参数（--file, --input, --type, --mode 等）
2. 获取要 review 的内容（读取文件、URL 等）
3. 加载对应的 system prompt（prompts/skills/*.md）
4. 直接生成回复
5. 按照项目格式保存输出

这种方式最简单可靠，不需要复杂的进程间通信。

### 如何保持项目的一致性？

我会读取项目的配置：
- `config.py` 中的杠精等级
- `prompts/skills/*.md` 中的 system prompt
- `prompts/soul.md` 中的角色设定
- 输出格式与项目一致

---

## 切换回 API 模式

如果需要切换回 API Key 模式：

```python
# config.py
DEFAULT_PROVIDER = "deepseek"  # 或 claude, openai, qwen
DEEPSEEK_API_KEY = "sk-your-key"
```

然后在自己的终端运行项目。

---

## 故障排查

### Q: 我想让项目代码真正运行怎么办？

A: 切换回 API 模式，配置 API Key：
```python
DEFAULT_PROVIDER = "deepseek"
DEEPSEEK_API_KEY = "sk-xxx"
```

### Q: 我的项目代码有修改，你能识别吗？

A: 只要修改了 `prompts/` 目录下的 skill 文件或 `config.py`，我会读取最新的配置。

### Q: 如何处理复杂的工作流？

A: 直接描述你的需求，我会帮你处理。例如：
> "先 review 这个设计方案，然后根据 review 意见生成改进版"

---

## 更新日志

- 2024-04-06: 简化方案，直接在 OpenClaw 中模拟项目运行
