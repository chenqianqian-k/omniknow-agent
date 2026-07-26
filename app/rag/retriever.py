from app.rag.ingest import get_vector_store
from app.rag.reranker import rerank_documents


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

    results = vector_store.similarity_search_with_score(
        query=clean_query,
        k=recall_k,
    )

    candidate_documents = []

    for rank, (document, distance) in enumerate(
        results,
        start=1,
    ):
        candidate_documents.append(
            {
                "rank": rank,
                "content": document.page_content,
                "file_name": document.metadata.get(
                    "file_name",
                    "未知文件",
                ),
                "page": (
                    document.metadata.get(
                        "page",
                        -1,
                    )
                    + 1
                ),
                "distance": round(
                    float(distance),
                    4,
                ),
            }
        )

    if not candidate_documents:
        return []

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
    vector_store = get_vector_store()

    stored_data = vector_store.get(
        where={"file_name": file_name},
        include=["documents", "metadatas"],
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

    for text, metadata in zip(
        texts,
        metadatas,
    ):
        document_chunks.append(
            {
                "content": text,
                "page": (
                    metadata.get("page", 0)
                    + 1
                ),
                "file_name": metadata.get(
                    "file_name",
                    file_name,
                ),
            }
        )

    document_chunks.sort(
        key=lambda chunk: chunk["page"]
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
        print(f"最终排名：{result['rank']}")
        print(f"文件：{result['file_name']}")
        print(f"页码：{result['page']}")
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