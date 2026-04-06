"""
PDF 解析适配器
=============
用 PyMuPDF (fitz) 提取 PDF 文本内容，供杠精虾 review。

处理策略：
  - 逐页提取文字，保留段落结构
  - 表格：以文字形式提取，保留行列关系（fitz 本身支持）
  - 图片中的文字：跳过（需 OCR，M3 暂不支持，v2.0 再做）
  - 超大 PDF（> MAX_PAGES 页）：只取前 N 页，并提示用户

依赖：pip install pymupdf
"""

from dataclasses import dataclass
from pathlib import Path

MAX_PAGES = 50       # 超过此页数只取前 MAX_PAGES 页
MIN_CONTENT = 100    # 最少有效字符数，低于此认为提取失败（可能是扫描版 PDF）


@dataclass
class PDFParseResult:
    file_path: str
    content: str          # 提取出的文字内容
    total_pages: int
    parsed_pages: int     # 实际解析的页数（可能因 MAX_PAGES 截断）
    char_count: int
    success: bool
    warning: str = ""     # 非致命性提示（如"只取了前N页"）
    error: str = ""


def parse_pdf(file_path: str) -> PDFParseResult:
    """
    解析 PDF 文件，返回结构化文本。

    参数：
        file_path: PDF 文件的绝对/相对路径

    返回：
        PDFParseResult，通过 .content 取正文
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return PDFParseResult(
            file_path=file_path, content="", total_pages=0, parsed_pages=0,
            char_count=0, success=False,
            error="缺少依赖：请运行 pip install pymupdf"
        )

    path = Path(file_path)
    if not path.exists():
        return PDFParseResult(
            file_path=file_path, content="", total_pages=0, parsed_pages=0,
            char_count=0, success=False,
            error=f"文件不存在: {file_path}"
        )

    if path.suffix.lower() != ".pdf":
        return PDFParseResult(
            file_path=file_path, content="", total_pages=0, parsed_pages=0,
            char_count=0, success=False,
            error=f"不是 PDF 文件: {file_path}"
        )

    print(f"[pdf_parser] 正在解析: {file_path}")

    try:
        with fitz.open(file_path) as doc:
            total_pages = len(doc)
            warning = ""

            # 超大 PDF 截断
            parse_up_to = total_pages
            if total_pages > MAX_PAGES:
                parse_up_to = MAX_PAGES
                warning = f"PDF 共 {total_pages} 页，超过限制，只解析前 {MAX_PAGES} 页"
                print(f"[pdf_parser] ⚠️  {warning}")

            pages_text = []
            for page_num in range(parse_up_to):
                page = doc[page_num]
                # get_text("blocks") 保留段落结构，b[4] 为文字内容，图片块的 b[4] 为空会被过滤
                blocks = page.get_text("blocks")
                page_content = "\n".join(
                    b[4].strip() for b in blocks
                    if b[4].strip()
                )
                if page_content:
                    pages_text.append(f"--- 第 {page_num + 1} 页 ---\n{page_content}")

            content = "\n\n".join(pages_text)

        # with 块结束，doc 已自动关闭
        # 检测是否是扫描版 PDF（文字极少）
        if len(content.strip()) < MIN_CONTENT:
            return PDFParseResult(
                file_path=file_path, content=content,
                total_pages=total_pages, parsed_pages=parse_up_to,
                char_count=len(content), success=False,
                error="提取到的文字过少，可能是扫描版 PDF（图片型），需要 OCR 才能处理"
            )

        print(f"[pdf_parser] 解析完成：{parse_up_to}/{total_pages} 页，{len(content)} 字符")
        return PDFParseResult(
            file_path=file_path, content=content,
            total_pages=total_pages, parsed_pages=parse_up_to,
            char_count=len(content), success=True,
            warning=warning
        )

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[pdf_parser] ❌ {err}")
        return PDFParseResult(
            file_path=file_path, content="", total_pages=0, parsed_pages=0,
            char_count=0, success=False, error=err
        )


def parse_pdf_for_review(file_path: str) -> str:
    """
    解析 PDF 并格式化为带元信息的文本，直接可以丢给杠精虾 review。
    失败时抛出异常。
    """
    result = parse_pdf(file_path)

    if not result.success:
        raise RuntimeError(f"PDF 解析失败: {result.error}\n文件: {file_path}")

    header = (
        f"【来源 PDF】{Path(file_path).name}\n"
        f"【页数】{result.parsed_pages}/{result.total_pages} 页"
    )
    if result.warning:
        header += f"\n【注意】{result.warning}"

    return f"{header}\n\n{result.content}"
