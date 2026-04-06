"""
Prompt 加载器
=============
从 prompts/ 目录加载 soul.md 和各领域 skill 文件，
拼装成最终的 system prompt 注入给模型。

设计原则：
- soul.md 是所有 Agent 的基础，永远加载
- skill 文件按内容类型动态叠加
- 拼装结果可以直接作为 system prompt 传给 llm_client
"""

import os
from pathlib import Path

# prompts/ 目录的绝对路径
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# 内容类型 → skill 文件映射
SKILL_MAP = {
    "code":     "skills/code_review.md",
    "business": "skills/business_review.md",
    "content":  "skills/content_review.md",
}


def _load_file(relative_path: str) -> str:
    """加载 prompts/ 下的 md 文件，返回文本内容"""
    full_path = PROMPTS_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {full_path}")
    return full_path.read_text(encoding="utf-8")


def load_soul() -> str:
    """加载通用杠精人格"""
    return _load_file("soul.md")


def load_skill(content_type: str) -> str | None:
    """
    加载领域 skill 文件。

    参数：
        content_type: "code" | "business" | "content"

    返回：
        skill 文件内容，或 None（类型不在映射表里时）
    """
    skill_path = SKILL_MAP.get(content_type)
    if not skill_path:
        return None
    return _load_file(skill_path)


def build_system_prompt(
    content_type: str,
    critic_level: int = 2,
) -> str:
    """
    构建完整的 system prompt。

    拼装顺序：
        1. soul.md（通用杠精人格）
        2. 对应 skill 文件（领域专属审查维度）
        3. 当前杠精等级说明

    参数：
        content_type:  "code" | "business" | "content" | "auto"
        critic_level:  1=温柔杠 / 2=正常杠 / 3=魔鬼杠

    返回：
        拼装好的 system prompt 字符串
    """
    parts = []

    # ① 基础人格
    parts.append(load_soul())

    # ② 领域 skill
    skill = load_skill(content_type)
    if skill:
        parts.append(f"\n\n---\n\n## 当前领域：{content_type} 专属审查规则\n\n{skill}")

    # ③ 杠精等级说明
    level_desc = {
        1: "【当前杠精等级：Level 1 🟢 温柔杠】只报 P0 和 P1，最多 3 条，语气温和。",
        2: "【当前杠精等级：Level 2 🟡 正常杠】报 P0-P2，3-8 条，专业直白。（默认）",
        3: "【当前杠精等级：Level 3 🔴 魔鬼杠】报 P0-P3，数量不限，连措辞/命名/格式都不放过，附带替代方案对比。",
    }
    parts.append(f"\n\n---\n\n{level_desc.get(critic_level, level_desc[2])}")

    # ④ 输出格式要求（每次都注入，确保格式一致）
    parts.append("""

---

## 输出格式要求（严格遵守）

用以下 Markdown 格式输出 Review Report，不要增减字段：

```
## 🦐 杠精虾 Review Report

**输入类型**: [代码 / 商业方案 / 内容文案]
**杠精等级**: Level [1/2/3]

---

### 📊 问题总览

| 级别 | 数量 |
|-----|------|
| P0 🔴 | X 条 |
| P1 🟠 | X 条 |
| P2 🟡 | X 条 |
| P3 🔵 | X 条 |

---

### 🔍 问题详情

#### P0 🔴 [维度] 问题标题
- **位置**: 第 X 行 / 第 X 段
- **问题**: 具体描述
- **影响**: 会导致什么后果
- **修复建议**: 具体可执行的改进方案

（按 P0 → P3 排列，同级按影响范围大小排序）

---

### ✅ 亮点

- 亮点1
- 亮点2

---

### 📝 总结

[1-2 句话概括整体质量和最需要关注的改进方向]
```
""")

    return "\n".join(parts)


def detect_content_type(content: str) -> str:
    """
    自动识别输入内容类型。

    规则：
    - 包含代码块（```）或明显代码语法 → code
    - 包含商业关键词 → business
    - 其他 → content
    """
    content_lower = content.lower()

    # 代码特征
    code_signals = ["```", "def ", "function ", "import ", "const ", "class ",
                    "return ", "async ", "await ", "useEffect", "useState"]
    if any(s in content for s in code_signals):
        return "code"

    # 商业特征
    business_signals = ["收益", "roi", "市场", "用户增长", "融资", "估值",
                        "竞品", "商业模式", "盈利", "投资", "revenue", "market"]
    if any(s in content_lower for s in business_signals):
        return "business"

    return "content"
