import os
from functools import lru_cache
from pathlib import Path

from sentence_transformers import CrossEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RERANKER_MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "bge-reranker-base"
)

RERANKER_DEVICE = os.getenv(
    "RERANKER_DEVICE",
    "cuda:0",
)


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """加载并缓存Reranker模型。"""
    if not RERANKER_MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Reranker模型不存在："
            f"{RERANKER_MODEL_PATH}"
        )

    return CrossEncoder(
        str(RERANKER_MODEL_PATH),
        device=RERANKER_DEVICE,
        max_length=512,
    )


def rerank_documents(
    query: str,
    documents: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """根据问题对候选文本进行相关性重排序。"""
    clean_query = query.strip()

    if not clean_query:
        raise ValueError("重排序问题不能为空")

    if top_k < 1:
        raise ValueError("top_k必须大于等于1")

    if not documents:
        return []

    reranker = get_reranker()

    query_document_pairs = [
        [
            clean_query,
            document["content"],
        ]
        for document in documents
    ]

    scores = reranker.predict(
        query_document_pairs,
        batch_size=8,
        show_progress_bar=False,
    )

    reranked_documents = []

    for document, score in zip(
        documents,
        scores,
    ):
        reranked_document = document.copy()

        reranked_document["rerank_score"] = round(
            float(score),
            4,
        )

        reranked_documents.append(
            reranked_document
        )

    reranked_documents.sort(
        key=lambda document: document["rerank_score"],
        reverse=True,
    )

    final_documents = reranked_documents[:top_k]

    for rank, document in enumerate(
        final_documents,
        start=1,
    ):
        document["rank"] = rank

    return final_documents