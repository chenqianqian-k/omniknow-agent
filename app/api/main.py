import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.agent.knowledge_agent import (
    DEFAULT_USER_ID,
    get_session_messages,
    run_agent,
)
from app.memory.session_store import list_sessions
from app.memory.long_term_memory import (
    delete_memory,
    get_memories,
)
from app.rag.ingest import (
    UPLOAD_DIR,
    delete_document,
    ingest_pdf,
    list_documents,
)


app = FastAPI(
    title="Knowledge Agent API",
    description="基于DeepSeek、LangGraph和ChromaDB的知识库问答Agent",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="用户问题",
    )

    thread_id: str = Field(
        default="default",
        min_length=1,
        max_length=100,
        description="对话会话ID",
    )


class ChatResponse(BaseModel):
    answer: str
    tool_called: bool


class DeleteDocumentRequest(BaseModel):
    file_hash: str | None = None
    file_name: str | None = None

@app.get("/")
def root():
    return {
        "name": "Knowledge Agent API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/sessions")
def get_sessions():
    try:
        sessions = list_sessions()

        return {
            "total": len(sessions),
            "sessions": sessions,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"获取历史会话失败：{error}",
        ) from error

@app.get("/sessions/{thread_id}")
def get_session(thread_id: str):
    try:
        messages = get_session_messages(thread_id)

        if not messages:
            raise HTTPException(
                status_code=404,
                detail="没有找到该历史会话",
            )

        return {
            "thread_id": thread_id,
            "message_count": len(messages),
            "messages": messages,
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"读取会话消息失败：{error}",
        ) from error


@app.get("/memories")
def get_long_term_memories():
    try:
        memories = get_memories(
            user_id=DEFAULT_USER_ID
        )

        return {
            "user_id": DEFAULT_USER_ID,
            "total": len(memories),
            "memories": memories,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"获取长期记忆失败：{error}",
        ) from error


@app.delete("/memories/{memory_key}")
def remove_long_term_memory(
    memory_key: str,
):
    try:
        deleted = delete_memory(
            user_id=DEFAULT_USER_ID,
            memory_key=memory_key,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="没有找到需要删除的长期记忆",
            )

        return {
            "deleted": True,
            "user_id": DEFAULT_USER_ID,
            "memory_key": memory_key,
            "message": "长期记忆删除成功",
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"删除长期记忆失败：{error}",
        ) from error


@app.get("/documents")
def get_documents():
    try:
        documents = list_documents()

        return {
            "total": len(documents),
            "documents": documents,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"获取文档列表失败：{error}",
        ) from error


@app.delete("/documents")
def remove_document(request: DeleteDocumentRequest):
    try:
        result = delete_document(
            file_hash=request.file_hash,
            file_name=request.file_name,
        )

        if not result["deleted"]:
            raise HTTPException(
                status_code=404,
                detail=result["message"],
            )

        return result

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"删除文档失败：{error}",
        ) from error


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        #result = run_agent(request.query)
        result = run_agent(
            query=request.query,
            thread_id=request.thread_id,
        )

        return ChatResponse(
            answer=result["answer"],
            tool_called=result["tool_called"],
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Agent执行失败：{error}",
        ) from error


@app.post("/documents/upload")
def upload_document(file: UploadFile = File(...)):
    original_name = file.filename or "unknown.pdf"
    safe_name = Path(original_name).name

    if Path(safe_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="当前只支持上传PDF文件",
        )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_path = UPLOAD_DIR / safe_name

    try:
        with save_path.open("wb") as output_file:
            shutil.copyfileobj(
                file.file,
                output_file,
            )

        ingest_result = ingest_pdf(str(save_path))

        if ingest_result["already_exists"]:
            return {
                "message": "PDF已经存在，未重复写入知识库",
                "document": ingest_result,
            }

        return {
            "message": "PDF上传并入库成功",
            "document": ingest_result,
        }

    except Exception as error:
        if save_path.exists():
            save_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"文档处理失败：{error}",
        ) from error

    finally:
        file.file.close()