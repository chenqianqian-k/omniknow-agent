import json
import shutil
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.knowledge_agent import (
    DEFAULT_USER_ID,
    get_session_messages,
    run_agent,
    stream_agent,
)
from app.memory.session_store import list_sessions
from app.memory.long_term_memory import (
    delete_memory,
    get_memories,
)
from app.rag.ingest import (
    SUPPORTED_EXTENSIONS,
    UPLOAD_DIR,
    delete_document,
    ingest_document,
    list_documents,
)

from app.tasks.document_processor import (
    process_document_task,
)
from app.tasks.document_task_store import (
    create_document_task,
    get_document_task as get_document_task_record,
    update_document_task,
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


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """以NDJSON格式流式返回Agent执行事件。"""

    def generate_events():
        try:
            for event in stream_agent(
                query=request.query,
                thread_id=request.thread_id,
            ):
                event_json = json.dumps(
                    event,
                    ensure_ascii=False,
                )

                yield event_json + "\n"

        except Exception as error:
            error_event = {
                "type": "error",
                "message": (
                    f"Agent流式执行失败：{error}"
                ),
            }

            yield (
                json.dumps(
                    error_event,
                    ensure_ascii=False,
                )
                + "\n"
            )

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/documents/upload-async",
    status_code=202,
)
def upload_document_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """接收文档并创建后台入库任务。"""
    original_name = (
        file.filename
        or "unknown"
    )

    safe_name = Path(original_name).name

    file_extension = (
        Path(safe_name)
        .suffix
        .lower()
    )

    if not file.filename:
        file.file.close()

        raise HTTPException(
            status_code=400,
            detail="上传文件缺少文件名",
        )

    if (
        file_extension
        not in SUPPORTED_EXTENSIONS
    ):
        file.file.close()

        supported_text = ", ".join(
            sorted(SUPPORTED_EXTENSIONS)
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "不支持该文件格式。"
                f"当前支持：{supported_text}"
            ),
        )

    task = create_document_task(
        file_name=safe_name
    )

    task_id = task["task_id"]

    task_upload_dir = (
        UPLOAD_DIR
        / task_id
    )

    task_upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_path = (
        task_upload_dir
        / safe_name
    )

    try:
        with save_path.open("wb") as output_file:
            shutil.copyfileobj(
                file.file,
                output_file,
            )

    except Exception as error:
        update_document_task(
            task_id=task_id,
            status="failed",
            message="上传文件保存失败",
            error_message=str(error),
        )

        raise HTTPException(
            status_code=500,
            detail=f"保存上传文件失败：{error}",
        ) from error

    finally:
        file.file.close()

    background_tasks.add_task(
        process_document_task,
        task_id,
        str(save_path),
    )

    return {
        "task_id": task_id,
        "file_name": safe_name,
        "status": "pending",
        "message": (
            "文档已接收，"
            "后台入库任务已经创建"
        ),
    }


@app.get(
    "/document-tasks/{task_id}"
)
def get_document_task_status(
    task_id: str,
):
    """查询指定文档入库任务的状态。"""
    try:
        task = get_document_task_record(
            task_id
        )

        if task is None:
            raise HTTPException(
                status_code=404,
                detail="没有找到该文档任务",
            )

        return task

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
            detail=(
                f"查询文档任务失败：{error}"
            ),
        ) from error

@app.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
):
    """上传文档，并将文档内容写入知识库。"""
    original_name = (
        file.filename
        or "unknown"
    )

    # 只保留文件名，避免文件名中携带目录路径
    safe_name = Path(original_name).name
    file_extension = (
        Path(safe_name)
        .suffix
        .lower()
    )

    # 检查用户是否真正上传了带文件名的文件
    if not file.filename:
        file.file.close()

        raise HTTPException(
            status_code=400,
            detail="上传文件缺少文件名",
        )

    # 检查文件格式
    if file_extension not in SUPPORTED_EXTENSIONS:
        file.file.close()

        supported_text = ", ".join(
            sorted(SUPPORTED_EXTENSIONS)
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "不支持该文件格式。"
                f"当前支持：{supported_text}"
            ),
        )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_path = UPLOAD_DIR / safe_name

    try:
        # 将用户上传的文件保存到data/uploads目录
        with save_path.open("wb") as output_file:
            shutil.copyfileobj(
                file.file,
                output_file,
            )

        # 根据文件类型自动选择对应的解析方式
        ingest_result = ingest_document(
            str(save_path)
        )

        if ingest_result["already_exists"]:
            return {
                "message": (
                    "该文档已经存在，"
                    "未重复写入知识库"
                ),
                "document": ingest_result,
            }

        return {
            "message": "文档上传并入库成功",
            "document": ingest_result,
        }

    except ValueError as error:
        if save_path.exists():
            save_path.unlink()

        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        if save_path.exists():
            save_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=f"文档处理失败：{error}",
        ) from error

    finally:
        file.file.close()
