# 杠精虾 项目探索完成报告

## 📋 探索范围与成果

### ✅ 已完成的探索

1. **项目核心理解** ✓
   - 定位：多模态批判性思维 Review 引擎
   - 核心特色：三虾互杠、多档调节、多模态输入

2. **功能特性梳理** ✓
   - 6 大核心能力（单虾/三虾/URL/PDF/视频/定时巡检）
   - 3 档杠精等级（温柔/正常/魔鬼）
   - 3 个内容类型专家（代码/商业/文案）

3. **架构与设计** ✓
   - 5 层系统架构（CLI → 适配器 → 提示系统 → LLM → 输出）
   - 分层提示设计（soul.md 基础 + skills 专业 + level 调节 + format 约束）
   - 异步并发架构（asyncio.gather 并行三虾审查）
   - 文件通信代理（无 API Key 的本地 Agent 模式）

4. **LLM 集成** ✓
   - 5 个 LLM 提供商（DeepSeek/Claude/OpenAI/Qwen/Local Agent）
   - 推理模型特殊处理（R1/GLM-5/QwQ 自动检测和兼容）
   - 统一调用接口（chat/chat_async/chat_simple）

5. **输入适配器** ✓
   - 文件/stdin 输入
   - URL 网页抓取（Jina Reader）
   - PDF 解析（PyMuPDF，支持最多 50 页）
   - 视频 ASR（SenseVoice-Small，支持 6 种语言）

6. **核心流程** ✓
   - 单虾工作流：输入 → 类型检测 → 提示组装 → LLM 调用 → Report 输出
   - 三虾工作流：Proposal v1 → 并行 Critic+Devil → 迭代 → 收敛检测 → Report 渲染
   - 定时巡检：Git diff 解析 → 文件过滤 → 温柔审查 → 日志积累

7. **配置系统** ✓
   - 集中式全局配置（config.py）
   - 提供商灵活切换
   - 模型选择和参数调优空间

---

## 📊 文档生成成果

### 生成的两份核心文档

| 文档 | 行数 | 章节数 | 关键内容 |
|------|------|--------|---------|
| **CODEBASE_SUMMARY.md** | ~450 | 14 节 | 项目总览、功能、架构、集成、流程、提示系统、配置、依赖 |
| **KEY_INSIGHTS.md** | ~500 | 10+ 节 | 创新点、技术亮点、性能数据、成熟度评估、代码质量、参考清单 |

### 文档价值
- **入门指南**：新开发者快速理解项目全貌
- **参考手册**：核心类/函数/流程的精确定位
- **扩展蓝图**：如何添加新 LLM 提供商、新内容类型、新适配器
- **决策支持**：架构权衡、性能考虑、质量评估

---

## 🔍 代码覆盖情况

### 已深度读取和分析的文件

**核心模块（100% 覆盖）**
- ✓ main.py - CLI 入口和命令行解析
- ✓ config.py - 全局配置管理
- ✓ core/critic_shrimp.py - 单虾核心逻辑
- ✓ core/llm_client.py - LLM 统一接口
- ✓ core/prompt_loader.py - 提示组装
- ✓ core/three_shrimp_workflow.py - 三虾互杠工作流
- ✓ core/local_proxy.py - 本地 Agent 代理

**输入适配器（100% 覆盖）**
- ✓ core/input_adapters/url_fetcher.py
- ✓ core/input_adapters/pdf_parser.py
- ✓ core/input_adapters/video_asr.py

**提示系统（100% 覆盖）**
- ✓ prompts/soul.md
- ✓ prompts/proposal_shrimp.md
- ✓ prompts/devil_shrimp.md
- ✓ prompts/skills/code_review.md
- ✓ prompts/skills/business_review.md
- ✓ prompts/skills/content_review.md

**工具模块（部分覆盖）**
- ✓ core/bridge.py - Agent 桥接器
- ✓ heartbeat/scheduler.py - 定时巡检调度

---

## 🎯 关键发现

### 1. 架构优势
- **灵活的 LLM 支持**：一行代码切换提供商，包括无 API Key 的本地模式
- **优雅的提示组装**：分层设计实现代码/业务/文案三个领域的专业审查
- **高效的并发机制**：asyncio.gather 并行三虾评审，显著提升审查吞吐量
- **多模态输入能力**：通过适配器模式统一处理文本/URL/PDF/视频

### 2. 性能特点
- **推理模型兼容**：DeepSeek R1 等推理模型自动检测，max_tokens 自适应
- **智能内容检测**：关键词启发式自动判定代码/业务/文案类型
- **资源缓存**：模型单例缓存避免重复加载（尤其是 ASR 模型）
- **增量日志**：Heartbeat 模式下的结果积累和去重

### 3. 可扩展性
- **新 LLM 提供商**：添加 3 行代码（config + client 初始化）
- **新内容类型**：新增 skill 文件 + SKILL_MAP 条目 + 关键词配置
- **新输入适配器**：实现 Adapter 接口 + main.py 中注册
- **新提示角色**：创建 prompt 文件，加载到 llm_client 调用链

### 4. 生产准备度
- **错误处理**：完整的异常捕获和降级逻辑
- **日志系统**：分阶段进度打印和指标跟踪
- **配置灵活性**：所有常数都参数化
- **版本控制**：支持输出版本跟踪和问题去重

---

## 🚀 可能的后续方向

### 优先级高（1-2 周）
1. **测试覆盖**：单元测试（提示组装、LLM 调用、工作流收敛）
2. **文档完善**：API 文档、使用案例、集成指南
3. **依赖优化**：梳理并固定依赖版本，CI/CD 检查

### 优先级中（3-4 周）
1. **新内容类型**：产品文案、技术文档、法律文件等专家
2. **新 LLM 提供商**：Gemini、Grok、开源模型本地推理等
3. **性能优化**：批量处理、流式输出、缓存策略
4. **UI/Web 界面**：替代 CLI 的图形化审查平台

### 优先级低（1-3 个月）
1. **多语言支持**：非中文提示词和报告格式
2. **定制化角色**：用户自定义 Shrimp 角色和审查维度
3. **历史追踪**：问题改进追踪、趋势分析、质量度量
4. **集成生态**：与 IDE、Git、CI/CD、Slack 等工具的集成

---

## 💾 提交信息

**Commit Hash**: 09a5c63  
**Commit Time**: 2026-04-10  
**Files Added**:
- CODEBASE_SUMMARY.md (14 sections, ~450 lines)
- KEY_INSIGHTS.md (10+ sections, ~500 lines)

**Message**: docs: Add comprehensive codebase exploration and insights documentation

---

## 📌 快速参考

### 运行项目

```bash
# 单虾 review 代码
python main.py --file code.py --level 2

# 三虾互杠模式
python main.py --mode three --input "写一个登录组件" --level 3

# URL/PDF/视频 review
python main.py --url https://example.com/article
python main.py --pdf report.pdf
python main.py --video demo.mp4 --lang zh

# 本地 Agent 模式
python main.py --file code.py --provider local
```

### 扩展项目

1. **新 Skill**：`prompts/skills/new_type.md` + 关键词配置
2. **新 LLM**：config.py + 两行 client 初始化
3. **新适配器**：`core/input_adapters/new_adapter.py` + main.py 注册

---

## ✨ 项目评价

**整体印象**：
- 架构清晰、设计优雅
- 代码质量中上水平
- 功能完整，已达到 MVP 的完全版
- 扩展性强，易于定制和集成
- 实用价值高，可直接用于生产环境

**核心竞争力**：
1. 三虾互杠的创新审查模式
2. 多档可调的柔性评估等级
3. 多模态输入的完整支持
4. 推理模型的深度集成
5. 本地 Agent 代理的独特设计

