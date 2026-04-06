"""
URL 爬取适配器
=============
用 Jina Reader (https://r.jina.ai) 把任意 URL 转成干净的 Markdown 文本。

原理：在 URL 前加 https://r.jina.ai/ 前缀，Jina 会自动：
  - 抓取页面内容
  - 去掉广告/导航/页脚等噪音
  - 返回干净的 Markdown 正文

优势：零代码、无需 API Key、免费额度充足、中英文都支持。
"""

import httpx
from dataclasses import dataclass


JINA_BASE = "https://r.jina.ai/"
DEFAULT_TIMEOUT = 30  # 秒


@dataclass
class FetchResult:
    url: str
    content: str          # 提取出的 Markdown 正文
    char_count: int
    success: bool
    error: str = ""


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> FetchResult:
    """
    抓取 URL 内容，返回干净的 Markdown 文本。

    参数：
        url:     要抓取的网页地址（http/https 均可）
        timeout: 超时秒数

    返回：
        FetchResult，通过 .content 取正文，通过 .success 判断是否成功
    """
    # 确保 URL 有协议前缀
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    jina_url = f"{JINA_BASE}{url}"
    print(f"[url_fetcher] 正在抓取: {url}")

    try:
        headers = {
            "Accept": "text/markdown",          # 告诉 Jina 返回 Markdown 格式
            "X-Return-Format": "markdown",
            "User-Agent": "GangjingXia/1.0",
        }
        resp = httpx.get(jina_url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()

        content = resp.text.strip()

        if not content:
            return FetchResult(url=url, content="", char_count=0, success=False,
                               error="页面内容为空")

        print(f"[url_fetcher] 抓取成功，{len(content)} 字符")
        return FetchResult(url=url, content=content, char_count=len(content), success=True)

    except httpx.TimeoutException:
        err = f"请求超时（{timeout}s），建议检查网络或增大 timeout"
        print(f"[url_fetcher] ❌ {err}")
        return FetchResult(url=url, content="", char_count=0, success=False, error=err)

    except httpx.HTTPStatusError as e:
        err = f"HTTP 错误 {e.response.status_code}"
        print(f"[url_fetcher] ❌ {err}")
        return FetchResult(url=url, content="", char_count=0, success=False, error=err)

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        print(f"[url_fetcher] ❌ {err}")
        return FetchResult(url=url, content="", char_count=0, success=False, error=err)


def fetch_url_for_review(url: str) -> str:
    """
    抓取 URL 并格式化为带元信息的文本，直接可以丢给杠精虾 review。
    失败时抛出异常。
    """
    result = fetch_url(url)

    if not result.success:
        raise RuntimeError(f"无法抓取 URL: {result.error}\nURL: {url}")

    # 加上来源标注，让杠精虾知道这是网页内容
    return f"【来源 URL】{url}\n\n{result.content}"
