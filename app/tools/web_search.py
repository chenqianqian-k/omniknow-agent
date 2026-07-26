import os

from dotenv import load_dotenv
from langchain_tavily import TavilySearch


load_dotenv()


def search_web(
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """搜索互联网并返回格式统一的网页结果。"""
    clean_query = query.strip()

    if not clean_query:
        raise ValueError("搜索问题不能为空")

    if max_results < 1 or max_results > 10:
        raise ValueError(
            "max_results必须在1到10之间"
        )

    api_key = os.getenv("TAVILY_API_KEY")

    if not api_key:
        raise ValueError(
            "未配置TAVILY_API_KEY"
        )

    search_tool = TavilySearch(
        max_results=max_results,
        topic="general",
        search_depth="basic",
        include_answer=False,
        include_raw_content=False,
    )

    response = search_tool.invoke(
        {
            "query": clean_query,
        }
    )

    raw_results = response.get(
        "results",
        [],
    )

    formatted_results = []

    for rank, result in enumerate(
        raw_results,
        start=1,
    ):
        formatted_results.append(
            {
                "rank": rank,
                "title": result.get(
                    "title",
                    "未知标题",
                ),
                "url": result.get(
                    "url",
                    "",
                ),
                "content": result.get(
                    "content",
                    "",
                ),
                "score": round(
                    float(result.get("score", 0)),
                    4,
                ),
            }
        )

    return formatted_results