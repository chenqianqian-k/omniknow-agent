import hashlib

from pathlib import Path
#from uuid import uuid4

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma"

EMBEDDING_MODEL = "/root/autodl-tmp/knowledge-agent/models/bge-small-zh-v1.5"
COLLECTION_NAME = "knowledge_base"

def calculate_file_hash(file_path: str) -> str:
    """计算文件的SHA-256哈希值。"""
    hash_calculator = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(8192):
            hash_calculator.update(chunk)

    return hash_calculator.hexdigest()


def get_embeddings() -> HuggingFaceEmbeddings:
    """加载文本向量模型。"""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vector_store() -> Chroma:
    """连接持久化的 ChromaDB 向量库。"""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def load_and_split_pdf(
    pdf_path: str,
    file_hash: str | None = None,
):
    """解析PDF，并切分为适合检索的文本块。"""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF不存在：{path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("当前版本只支持PDF文件")

    if file_hash is None:
        file_hash = calculate_file_hash(str(path))

    loader = PyPDFLoader(str(path))
    documents = loader.load()

    for document in documents:
        document.metadata["file_name"] = path.name
        document.metadata["source"] = str(path)
        document.metadata["file_hash"] = file_hash

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""],
    )

    chunks = splitter.split_documents(documents)

    return documents, chunks


def ingest_pdf(pdf_path: str) -> dict:
    """将PDF文本块向量化并写入ChromaDB，同时检测重复文件。"""
    path = Path(pdf_path)
    file_hash = calculate_file_hash(str(path))

    vector_store = get_vector_store()

    existing_data = vector_store.get(
        where={
            "file_hash": file_hash,
        },
        include=["metadatas"],
    )

    if existing_data["ids"]:
        existing_metadatas = existing_data.get("metadatas", [])

        page_numbers = {
            metadata.get("page")
            for metadata in existing_metadatas
            if metadata and metadata.get("page") is not None
        }

        return {
            "file_name": path.name,
            "page_count": len(page_numbers),
            "chunk_count": len(existing_data["ids"]),
            "collection": COLLECTION_NAME,
            "file_hash": file_hash,
            "already_exists": True,
        }

    pages, chunks = load_and_split_pdf(
        pdf_path=str(path),
        file_hash=file_hash,
    )

    ids = [
        f"{file_hash}-{index}"
        for index, _ in enumerate(chunks)
    ]

    vector_store.add_documents(
        documents=chunks,
        ids=ids,
    )

    return {
        "file_name": path.name,
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "collection": COLLECTION_NAME,
        "file_hash": file_hash,
        "already_exists": False,
    }

def list_documents() -> list[dict]:
    """查询知识库中已经入库的文档。"""
    vector_store = get_vector_store()

    stored_data = vector_store.get(
        include=["metadatas"],
    )

    documents = {}

    for metadata in stored_data.get("metadatas", []):
        if not metadata:
            continue

        file_name = metadata.get("file_name", "未知文件")
        file_hash = metadata.get("file_hash")

        document_key = file_hash or file_name

        if document_key not in documents:
            documents[document_key] = {
                "file_name": file_name,
                "file_hash": file_hash,
                "chunk_count": 0,
            }

        documents[document_key]["chunk_count"] += 1

    return list(documents.values())


def delete_document(
    file_hash: str | None = None,
    file_name: str | None = None,
) -> dict:
    """删除指定文档在ChromaDB中的全部文本块。"""
    if not file_hash and not file_name:
        raise ValueError("file_hash和file_name至少需要提供一个")

    vector_store = get_vector_store()

    if file_hash:
        search_condition = {"file_hash": file_hash}
    else:
        search_condition = {"file_name": file_name}

    stored_data = vector_store.get(
        where=search_condition,
        include=["metadatas"],
    )

    chunk_ids = stored_data.get("ids", [])

    if not chunk_ids:
        return {
            "deleted": False,
            "file_name": file_name,
            "deleted_chunk_count": 0,
            "message": "没有找到需要删除的文档",
        }

    metadatas = stored_data.get("metadatas", [])

    if not file_name and metadatas:
        file_name = metadatas[0].get("file_name", "未知文件")

    vector_store.delete(ids=chunk_ids)

    return {
        "deleted": True,
        "file_name": file_name,
        "deleted_chunk_count": len(chunk_ids),
        "message": "文档已从知识库删除",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="将PDF写入知识库")
    parser.add_argument("pdf_path", help="PDF文件路径")   #定义需要接收的参数
    args = parser.parse_args()

    result = ingest_pdf(args.pdf_path)

    print("PDF入库成功")
    print(f"文件：{result['file_name']}")
    print(f"页数：{result['page_count']}")
    print(f"文本块数：{result['chunk_count']}")
    print(f"集合：{result['collection']}")