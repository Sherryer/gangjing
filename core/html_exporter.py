"""
HTML 报告导出器
==============
把 Markdown Review Report 转成带样式的自包含 HTML 文件。
- 内嵌 CSS，不依赖外部网络，离线可用
- P0/P1/P2/P3 色块高亮
- 三虾互杠的 <details> 折叠历史原生支持
- 支持 auto_open 参数直接用系统浏览器打开
"""

import re
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import markdown2
    _HAS_MARKDOWN2 = True
except ImportError:
    _HAS_MARKDOWN2 = False


# ── CSS 样式 ─────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
    font-size: 15px;
    line-height: 1.75;
    color: #1a1a1a;
    background: #f7f7f8;
    padding: 0;
}

/* ── 顶部 Header ── */
.header {
    background: linear-gradient(135deg, #c0392b 0%, #8b0000 100%);
    color: white;
    padding: 32px 40px 24px;
}
.header h1 {
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
}
.header .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
    opacity: 0.88;
}
.meta-tag {
    background: rgba(255,255,255,0.18);
    border-radius: 4px;
    padding: 2px 10px;
    font-weight: 500;
}
.meta-tag.level1 { background: rgba(46,204,113,0.35); }
.meta-tag.level2 { background: rgba(241,196,15,0.35); }
.meta-tag.level3 { background: rgba(231,76,60,0.5); }

/* ── 主体内容区 ── */
.container {
    max-width: 960px;
    margin: 32px auto;
    padding: 0 24px;
}

/* ── 卡片 ── */
.card {
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    padding: 28px 32px;
    margin-bottom: 24px;
}

/* ── Markdown 正文样式 ── */
.card h1 { font-size: 22px; font-weight: 700; margin: 20px 0 12px; color: #c0392b; }
.card h2 { font-size: 18px; font-weight: 700; margin: 20px 0 10px; color: #2c3e50;
           padding-bottom: 6px; border-bottom: 2px solid #f0f0f0; }
.card h3 { font-size: 15px; font-weight: 700; margin: 16px 0 8px; color: #34495e; }
.card p  { margin: 8px 0; }
.card ul, .card ol { padding-left: 24px; margin: 8px 0; }
.card li { margin: 4px 0; }
.card code {
    background: #f4f4f5;
    border-radius: 3px;
    padding: 1px 5px;
    font-family: "SF Mono", "Fira Code", Consolas, monospace;
    font-size: 13px;
    color: #c0392b;
}
.card pre {
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 8px;
    padding: 16px 20px;
    overflow-x: auto;
    margin: 12px 0;
    font-size: 13px;
    line-height: 1.6;
}
.card pre code { background: none; color: inherit; padding: 0; }
.card blockquote {
    border-left: 4px solid #e0e0e0;
    margin: 12px 0;
    padding: 4px 16px;
    color: #666;
    background: #fafafa;
    border-radius: 0 6px 6px 0;
}
.card hr {
    border: none;
    border-top: 1px solid #f0f0f0;
    margin: 20px 0;
}
.card a { color: #c0392b; text-decoration: none; }
.card a:hover { text-decoration: underline; }

/* ── 表格 ── */
.card table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 14px;
}
.card th {
    background: #f4f4f5;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 2px solid #e0e0e0;
}
.card td {
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
}
.card tr:hover td { background: #fafafa; }

/* ── P0/P1/P2/P3 色块 ── */
.card td:first-child,
.card th:first-child { width: 80px; }

/* 表格里的 P0/P1/P2/P3 标签高亮 */
.card td:first-child { font-weight: 600; }

/* ── details 折叠历史 ── */
.card details {
    margin: 12px 0;
    border: 1px solid #e8e8e8;
    border-radius: 8px;
    overflow: hidden;
}
.card details summary {
    padding: 10px 16px;
    background: #f7f7f8;
    cursor: pointer;
    font-weight: 600;
    font-size: 14px;
    color: #2c3e50;
    user-select: none;
}
.card details summary:hover { background: #eeeef0; }
.card details[open] summary { border-bottom: 1px solid #e8e8e8; }
.card details > *:not(summary) { padding: 16px; }

/* ── P 级别 badge（用 JS 注入）── */
.p-badge {
    display: inline-block;
    border-radius: 4px;
    padding: 1px 8px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.p0-badge { background: #e74c3c; color: white; }
.p1-badge { background: #e67e22; color: white; }
.p2-badge { background: #f1c40f; color: #333; }
.p3-badge { background: #2ecc71; color: white; }

/* ── 状态 badge ── */
.status-passed      { color: #27ae60; font-weight: 700; }
.status-forced      { color: #e67e22; font-weight: 700; }
.status-max-rounds  { color: #e67e22; font-weight: 700; }

/* ── Footer ── */
.footer {
    text-align: center;
    color: #aaa;
    font-size: 12px;
    padding: 24px 0 40px;
}
"""

# ── JS（P 级别自动高亮）────────────────────────────────────────

_JS = """
document.querySelectorAll('td, th').forEach(function(cell) {
    var text = cell.textContent.trim();
    if (/^P0/.test(text)) cell.innerHTML = '<span class="p-badge p0-badge">' + text + '</span>';
    else if (/^P1/.test(text)) cell.innerHTML = '<span class="p-badge p1-badge">' + text + '</span>';
    else if (/^P2/.test(text)) cell.innerHTML = '<span class="p-badge p2-badge">' + text + '</span>';
    else if (/^P3/.test(text)) cell.innerHTML = '<span class="p-badge p3-badge">' + text + '</span>';
});
"""

# ── HTML 模板 ────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🦐 杠精虾 · __TITLE__</title>
<style>__CSS__</style>
</head>
<body>

<div class="header">
  <h1>🦐 杠精虾 · Review 报告</h1>
  <div class="meta">
    <span class="meta-tag">📅 __TIMESTAMP__</span>
    <span class="meta-tag">⚙️ 模式：__MODE_LABEL__</span>
    <span class="meta-tag level__LEVEL__">等级：Level __LEVEL__ __LEVEL_LABEL__</span>
    <span class="meta-tag">🗂️ 类型：__CONTENT_TYPE__</span>
    <span class="meta-tag">🤖 模型：__PROVIDER__</span>
  </div>
</div>

<div class="container">
  <div class="card">
    __BODY__
  </div>
</div>

<div class="footer">
  由 <strong>杠精虾</strong> 生成 · __TIMESTAMP__
</div>

<script>__JS__</script>
</body>
</html>
"""


# ── Markdown → HTML ──────────────────────────────────────────────

def _md_to_html(markdown_text: str) -> str:
    """把 Markdown 转成 HTML 片段"""
    if _HAS_MARKDOWN2:
        extras = [
            "tables",
            "fenced-code-blocks",
            "strike",
            "task_list",
        ]
        html = markdown2.markdown(markdown_text, extras=extras)
    else:
        # 降级：简单替换，保证基本可读
        html = _simple_md_to_html(markdown_text)
    return html


def _simple_md_to_html(text: str) -> str:
    """
    markdown2 未安装时的轻量降级方案。
    只处理最常见的 markdown 元素，保证报告在浏览器中可读。
    """
    import html as html_module

    lines = text.split("\n")
    result = []
    in_code_block = False
    in_table = False

    for line in lines:
        # 代码块
        if line.startswith("```"):
            if in_code_block:
                result.append("</code></pre>")
                in_code_block = False
            else:
                lang = line[3:].strip()
                result.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            continue

        if in_code_block:
            result.append(html_module.escape(line))
            continue

        # 表格
        if "|" in line and line.strip().startswith("|"):
            if not in_table:
                result.append("<table>")
                in_table = True
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                result.append("<tr>" + "".join(f"<th>{html_module.escape(c)}</th>" for c in cells) + "</tr>")
            elif re.match(r"[\|\s\-:]+$", line):
                pass  # 分隔行
            else:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                result.append("<tr>" + "".join(f"<td>{html_module.escape(c)}</td>" for c in cells) + "</tr>")
            continue
        else:
            if in_table:
                result.append("</table>")
                in_table = False

        # details / summary（三虾报告里的折叠历史）
        if line.startswith("<details") or line.startswith("</details") or \
           line.startswith("<summary") or line.startswith("</summary"):
            result.append(line)
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            content = _inline_md(m.group(2))
            result.append(f"<h{level}>{content}</h{level}>")
            continue

        # 水平线
        if re.match(r"^[-*_]{3,}$", line.strip()):
            result.append("<hr>")
            continue

        # 列表
        if re.match(r"^[\s]*[-*+]\s+", line):
            content = _inline_md(re.sub(r"^[\s]*[-*+]\s+", "", line))
            result.append(f"<li>{content}</li>")
            continue

        # 普通段落
        stripped = line.strip()
        if stripped:
            result.append(f"<p>{_inline_md(stripped)}</p>")
        else:
            result.append("")

    if in_table:
        result.append("</table>")
    if in_code_block:
        result.append("</code></pre>")

    return "\n".join(result)


def _inline_md(text: str) -> str:
    """处理行内 markdown：加粗、斜体、行内代码"""
    import html as html_module
    text = html_module.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         text)
    text = re.sub(r"`(.+?)`",       r"<code>\1</code>",     text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


# ── 公开接口 ─────────────────────────────────────────────────────

LEVEL_LABELS = {1: "🟢 温柔杠", 2: "🟡 正常杠", 3: "🔴 魔鬼杠"}
MODE_LABELS  = {"single": "单虾 Review", "three": "三虾互杠"}


def export_html(
    markdown_content: str,
    output_path: str,
    mode: str = "single",
    level: int = 2,
    content_type: str = "auto",
    provider: str = "",
    auto_open: bool = False,
) -> str:
    """
    将 Markdown 报告导出为 HTML 文件。

    参数：
        markdown_content: Markdown 格式的报告文本
        output_path:      输出 HTML 文件路径
        mode:             "single" | "three"
        level:            杠精等级 1/2/3
        content_type:     内容类型标签
        provider:         LLM 提供商名称
        auto_open:        是否自动用系统浏览器打开

    返回：
        保存的 HTML 文件绝对路径
    """
    body_html = _md_to_html(markdown_content)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    level_label = LEVEL_LABELS.get(level, "")
    mode_label  = MODE_LABELS.get(mode, mode)
    title = f"{mode_label} · {content_type} · Level {level}"

    # 用 replace 而非 format，避免 CSS/JS 里的 { } 被误解析为占位符
    html = _HTML_TEMPLATE
    html = html.replace("__CSS__",          _CSS)
    html = html.replace("__JS__",           _JS)
    html = html.replace("__TITLE__",        title)
    html = html.replace("__TIMESTAMP__",    timestamp)
    html = html.replace("__MODE_LABEL__",   mode_label)
    html = html.replace("__LEVEL__",        str(level))
    html = html.replace("__LEVEL_LABEL__",  level_label)
    html = html.replace("__CONTENT_TYPE__", content_type)
    html = html.replace("__PROVIDER__",     provider)
    html = html.replace("__BODY__",         body_html)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    if auto_open:
        webbrowser.open(out_path.resolve().as_uri())

    return str(out_path.resolve())
