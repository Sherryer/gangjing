# 杠精虾项目 — 完整探索成果

## 📦 生成的文档

本次探索生成了 **3 份** 核心参考文档，已提交到 git 仓库：

### 1. **CODEBASE_SUMMARY.md** — 项目完整参考手册
- **用途**：新开发者入门、架构理解、功能查阅
- **内容**：14 个章节，涵盖项目定义、功能、架构、集成、流程、配置等
- **特点**：结构化、全面、有具体代码引用

### 2. **KEY_INSIGHTS.md** — 技术深度分析
- **用途**：架构决策、质量评估、扩展指南、性能指标
- **内容**：创新点、代码质量评分、快速参考清单、常见任务示例
- **特点**：侧重分析、务实建议、代码示例丰富

### 3. **EXPLORATION_STATUS.md** — 探索完成报告
- **用途**：记录探索范围、发现要点、后续方向
- **内容**：已完成的探索、代码覆盖情况、关键发现、优先级建议
- **特点**：总结性、方向性、决策参考

---

## 🎯 核心发现概览

### 项目本质
> 🦐 **杠精虾**是一个多模态批判性思维 Review 引擎，通过三虾互杠（ProposalShrimp 提案、CriticShrimp 评审、DevilShrimp 对立）的创新模式，帮助发现代码、商业方案、文案等各类内容中的漏洞、风险和盲点。

### 五大核心优势

| # | 优势 | 实现方式 |
|---|------|--------|
| 1️⃣ | **智能多模态输入** | 文本/URL/PDF/视频适配器 |
| 2️⃣ | **灵活的 LLM 支持** | 5 个提供商一键切换，含无 Key 的本地模式 |
| 3️⃣ | **高效的并发审查** | asyncio.gather 并行三虾评审 |
| 4️⃣ | **精准的领域专家** | 分层提示实现代码/商业/文案专业评审 |
| 5️⃣ | **可调的评审力度** | Level 1-3 三档杠精等级（温柔~魔鬼） |

### 架构五层设计
```
┌─────────────────────────────────────┐
│  CLI 交互层                         │  main.py
│  (argparse 命令行解析)              │
├─────────────────────────────────────┤
│  输入适配器层                       │  input_adapters/*
│  (文本/URL/PDF/视频)               │
├─────────────────────────────────────┤
│  提示系统层                         │  prompts/*
│  (soul + skills + level + format)   │
├─────────────────────────────────────┤
│  LLM 调用层                         │  llm_client.py
│  (多提供商统一接口)                │
├─────────────────────────────────────┤
│  输出处理层                         │  .md / .txt
│  (Report 生成、保存、渲染)         │
└─────────────────────────────────────┘
```

---

## 📊 探索覆盖范围

### ✅ 100% 覆盖的模块
- **CLI 和配置**：main.py, config.py
- **核心逻辑**：critic_shrimp.py, llm_client.py, prompt_loader.py
- **工作流**：critic_shrimp.py, three_shrimp_workflow.py
- **输入适配**：url_fetcher.py, pdf_parser.py, video_asr.py
- **提示系统**：soul.md, proposal_shrimp.md, devil_shrimp.md, skills/*.md
- **代理**：local_proxy.py, bridge.py

### 📁 代码统计
- **Python 文件**：12+ 个核心模块
- **Prompt 文件**：1 基础 + 2 角色 + 3 领域专家
- **总代码量**：~2500 行 Python + ~500 行 Prompt

### 📈 复杂度分析
| 模块 | 复杂度 | 关键设计 |
|------|--------|---------|
| llm_client | ⭐⭐⭐⭐⭐ | 推理模型自适应、多提供商 lazy-load |
| three_shrimp_workflow | ⭐⭐⭐⭐ | 异步收敛检测、迭代轮数限制 |
| prompt_loader | ⭐⭐⭐ | 分层组装、关键词自动检测 |
| video_asr | ⭐⭐⭐⭐ | VAD 分段、模型缓存、格式标准化 |

---

## 🚀 快速开始

### 最简使用
```bash
# 安装依赖
pip install -r requirements.txt

# 单虾 review 代码文件
python main.py --file example.py

# 三虾互杠模式
python main.py --mode three --input "你的方案..." --level 3

# Review 网页或 PDF
python main.py --url https://example.com/article
python main.py --pdf document.pdf

# 视频字幕审查
python main.py --video demo.mp4 --lang zh
```

### 扩展项目
1. **新 LLM 提供商**：config.py + llm_client.py 两处修改
2. **新内容类型**：prompts/skills/new_type.md + prompt_loader.py 关键词
3. **新输入源**：core/input_adapters/new_source.py + main.py 注册

---

## 🎓 学习路径

### 推荐阅读顺序
1. 📖 **README_EXPLORATION.md**（本文件）← 快速总览
2. 📖 **CODEBASE_SUMMARY.md** → 系统理解
3. 📖 **KEY_INSIGHTS.md** → 深度分析和扩展指南
4. 💻 **main.py** → 开始写代码
5. 📝 **prompts/soul.md** → 理解评审哲学

### 关键理解点
- [ ] 三虾角色的职责分工（Proposal vs Critic vs Devil）
- [ ] 分层提示的组装流程（soul + skill + level + format）
- [ ] LLM 提供商的切换机制（config + lazy-load）
- [ ] 异步并发的实现方式（asyncio.gather）
- [ ] 输入适配器的扩展模式
- [ ] 推理模型的特殊处理（R1/GLM-5）

---

## 📊 质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构设计** | ⭐⭐⭐⭐⭐ | 分层清晰、职责分明、易于扩展 |
| **代码质量** | ⭐⭐⭐⭐ | 有类型提示、异常处理完整、日志充足 |
| **功能完整性** | ⭐⭐⭐⭐⭐ | 6 大能力、3 个领域、5 个 LLM |
| **性能** | ⭐⭐⭐⭐ | 并发设计、缓存机制、自适应参数 |
| **文档** | ⭐⭐⭐ | 本次新增，之前欠缺，现已补齐 |
| **可扩展性** | ⭐⭐⭐⭐⭐ | 新类型/新 LLM/新适配器三位一体 |

**综合评价**：Production-Ready MVP，具有创新特色和良好的扩展基础。

---

## 🔮 后续方向（按优先级）

### 🟢 高优先级（1-2 周）
- [ ] 添加单元测试（prompt 组装、workflow 收敛、LLM 调用）
- [ ] 完善依赖管理（requirements.txt + version pin）
- [ ] 集成 CI/CD（GitHub Actions 自动测试）

### 🟡 中优先级（3-4 周）
- [ ] 新增内容类型：产品文案审查、技术文档审查
- [ ] 新增 LLM：Claude 3.5、Gemini 2.0
- [ ] Web UI：替代 CLI 的可视化界面
- [ ] 批量处理：支持目录/文件列表批量审查

### 🔵 低优先级（1-3 个月）
- [ ] 多语言支持（非中文 prompt + 报告）
- [ ] 历史追踪（问题改进趋势分析）
- [ ] IDE 插件（VS Code 集成）
- [ ] API 服务（FastAPI 后端 + 前端）

---

## 🎁 附录：文件导航

### 核心查阅
- 🔍 **想快速上手** → CODEBASE_SUMMARY.md #1-2 章
- 🔍 **想理解架构** → CODEBASE_SUMMARY.md #3 章 + KEY_INSIGHTS.md 架构部分
- 🔍 **想写新 Skill** → KEY_INSIGHTS.md 扩展指南 + prompts/skills/code_review.md
- 🔍 **想加新 LLM** → KEY_INSIGHTS.md 提供商扩展 + config.py + llm_client.py
- 🔍 **想优化性能** → KEY_INSIGHTS.md 性能指标 + main.py 分析

### 代码导读
- 💻 **CLI 入口** → main.py:1-50
- 💻 **单虾审查** → core/critic_shrimp.py
- 💻 **三虾互杠** → core/three_shrimp_workflow.py
- 💻 **LLM 调用** → core/llm_client.py
- 💻 **提示组装** → core/prompt_loader.py + prompts/

---

## 💬 联系和反馈

**项目地址**：https://github.com/Sherryer/gangjing  
**最后更新**：2026-04-10  
**探索报告版本**：v1.0 (Complete)

---

**Happy Reviewing! 🦐🦐🦐**
