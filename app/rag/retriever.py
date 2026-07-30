from pathlib import Path

from app.rag.ingest import get_vector_store
from app.rag.reranker import rerank_documents


def build_location_info(
    metadata: dict,
) -> dict:
    """根据文档类型生成统一的来源位置信息。"""
    file_name = metadata.get(
        "file_name",
        "未知文件",
    )

    # 新入库文档会直接保存file_type。
    # 旧文档没有该字段，因此从扩展名推断。
    file_type = metadata.get("file_type")

    if not file_type:
        file_type = (
            Path(file_name)
            .suffix
            .lower()
            .lstrip(".")
        )

    # 优先读取新版入库代码保存的位置字段
    location_type = metadata.get("location_type")
    location = metadata.get("location")
    location_label = metadata.get("location_label")

    # 兼容旧版已经入库的文档
    if not location_type:
        if file_type == "pdf":
            location_type = "page"

        elif file_type == "pptx":
            location_type = "slide"

        else:
            location_type = "document"

    # 兼容旧版page字段。
    # metadata中的page从0开始，所以需要加1。
    if location is None:
        if location_type in {
            "page",
            "slide",
        }:
            location = (
                metadata.get("page", 0)
                + 1
            )
        else:
            location = 1

    # 如果没有location_label，则根据文档类型生成
    if not location_label:
        if location_type == "page":
            location_label = f"第{location}页"

        elif location_type == "slide":
            location_label = (
                f"第{location}张幻灯片"
            )

        else:
            location_label = "文档正文"

    # 保留page字段，兼容knowledge_agent.py中的旧代码
    if location_type in {
        "page",
        "slide",
    }:
        page = location
    else:
        page = 1

    return {
        "file_type": file_type,
        "location_type": location_type,
        "location": location,
        "location_label": location_label,
        "page": page,
    }


def search_knowledge_base(
    query: str,
    top_k: int = 3,
    recall_k: int = 10,
) -> list[dict]:
    """从知识库召回候选文本，并使用Reranker重新排序。"""
    clean_query = query.strip()

    if not clean_query:
        raise ValueError("检索问题不能为空")

    if top_k < 1:
        raise ValueError(
            "top_k必须大于等于1"
        )

    if recall_k < top_k:
        raise ValueError(
            "recall_k不能小于top_k"
        )

    vector_store = get_vector_store()

    # 第一阶段：使用Embedding和ChromaDB召回候选文本
    results = (
        vector_store
        .similarity_search_with_score(
            query=clean_query,
            k=recall_k,
        )
    )

    candidate_documents = []

    for rank, (document, distance) in enumerate(
        results,
        start=1,
    ):
        metadata = document.metadata

        location_info = build_location_info(
            metadata
        )

        candidate_documents.append(
            {
                "rank": rank,
                "content": document.page_content,
                "file_name": metadata.get(
                    "file_name",
                    "未知文件",
                ),
                "file_type": (
                    location_info["file_type"]
                ),
                "location_type": (
                    location_info[
                        "location_type"
                    ]
                ),
                "location": (
                    location_info["location"]
                ),
                "location_label": (
                    location_info[
                        "location_label"
                    ]
                ),

                # 暂时保留，兼容Agent中的旧代码
                "page": location_info["page"],

                "distance": round(
                    float(distance),
                    4,
                ),
            }
        )

    if not candidate_documents:
        return []

    # 第二阶段：使用Cross-Encoder Reranker重新排序
    reranked_documents = rerank_documents(
        query=clean_query,
        documents=candidate_documents,
        top_k=top_k,
    )

    return reranked_documents


def get_document_content(
    file_name: str,
    max_chunks: int = 30,
) -> list[dict]:
    """根据文件名读取指定文档的文本块。"""
    clean_file_name = file_name.strip()

    if not clean_file_name:
        raise ValueError("文件名不能为空")

    if max_chunks < 1:
        raise ValueError(
            "max_chunks必须大于等于1"
        )

    vector_store = get_vector_store()

    stored_data = vector_store.get(
        where={
            "file_name": clean_file_name,
        },
        include=[
            "documents",
            "metadatas",
        ],
    )

    texts = stored_data.get(
        "documents",
        [],
    )

    metadatas = stored_data.get(
        "metadatas",
        [],
    )

    document_chunks = []

    for chunk_index, (text, metadata) in enumerate(
        zip(texts, metadatas),
        start=1,
    ):
        metadata = metadata or {}

        location_info = build_location_info(
            metadata
        )

        document_chunks.append(
            {
                "content": text,
                "file_name": metadata.get(
                    "file_name",
                    clean_file_name,
                ),
                "file_type": (
                    location_info["file_type"]
                ),
                "location_type": (
                    location_info[
                        "location_type"
                    ]
                ),
                "location": (
                    location_info["location"]
                ),
                "location_label": (
                    location_info[
                        "location_label"
                    ]
                ),

                # 兼容Agent中的旧代码
                "page": location_info["page"],

                # 相同页面或相同文档内用于保持原有顺序
                "chunk_index": chunk_index,
            }
        )

    document_chunks.sort(
        key=lambda chunk: (
            chunk["location"],
            chunk["chunk_index"],
        )
    )

    return document_chunks[:max_chunks]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="测试知识库检索和重排序"
    )

    parser.add_argument(
        "query",
        help="需要检索的问题",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Reranker重排序后最终返回的数量",
    )

    parser.add_argument(
        "--recall-k",
        type=int,
        default=10,
        help="向量检索阶段召回的候选数量",
    )

    args = parser.parse_args()

    search_results = search_knowledge_base(
        query=args.query,
        top_k=args.top_k,
        recall_k=args.recall_k,
    )

    if not search_results:
        print("没有检索到相关内容")

    for result in search_results:
        print("=" * 70)
        print(
            f"最终排名：{result['rank']}"
        )
        print(
            f"文件：{result['file_name']}"
        )
        print(
            f"文件类型：{result['file_type']}"
        )
        print(
            f"来源位置："
            f"{result['location_label']}"
        )
        print(
            f"原向量距离："
            f"{result['distance']}"
        )
        print(
            f"重排序分数："
            f"{result['rerank_score']}"
        )
        print("内容：")
        print(result["content"])
