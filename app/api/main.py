import json
import time
import uuid

import requests
import streamlit as st

import time
API_BASE_URL = "http://127.0.0.1:6006"


st.set_page_config(
    page_title="OmniKnow Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 OmniKnow Agent")
st.caption("具备知识检索、工具调用、联网搜索与持久化记忆能力的知识库智能体")


# 初始化当前页面的聊天消息
if "messages" not in st.session_state:
    st.session_state.messages = []

# 初始化当前会话ID
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())


with st.sidebar:
    st.header("知识库管理")

    # =====================================================
    # 上传PDF
    # =====================================================

    # =====================================================
    # 异步上传文档
    # =====================================================

    uploaded_file = st.file_uploader(
        "上传知识库文档",
        type=[
            "pdf",
            "docx",
            "pptx",
            "md",
            "markdown",
            "txt",
        ],
        help=(
            "当前支持PDF、DOCX、PPTX、"
            "Markdown和TXT文档"
        ),
    )

    if uploaded_file is not None:
        file_extension = (
            uploaded_file.name
            .rsplit(".", 1)[-1]
            .lower()
        )

        st.caption(
            f"已选择：{uploaded_file.name}｜"
            f"文件类型：{file_extension.upper()}"
        )

    if st.button(
        "上传并写入知识库",
        disabled=uploaded_file is None,
        use_container_width=True,
    ):
        task_status_placeholder = st.empty()

        try:
            task_status_placeholder.info(
                "正在上传文档……"
            )

            content_type = (
                uploaded_file.type
                or "application/octet-stream"
            )

            upload_response = requests.post(
                (
                    f"{API_BASE_URL}"
                    f"/documents/upload-async"
                ),
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        content_type,
                    )
                },
                timeout=60,
            )

            if upload_response.status_code != 202:
                task_status_placeholder.empty()

                st.error(
                    f"创建文档任务失败："
                    f"{upload_response.text}"
                )

            else:
                upload_result = (
                    upload_response.json()
                )

                task_id = upload_result["task_id"]

                task_status_placeholder.info(
                    "文档已上传，"
                    "等待后台处理……"
                )

                task_finished = False
                polling_started_at = (
                    time.monotonic()
                )

                while not task_finished:
                    # 整个轮询过程最多等待10分钟
                    elapsed_seconds = (
                        time.monotonic()
                        - polling_started_at
                    )

                    if elapsed_seconds > 600:
                        task_status_placeholder.empty()

                        st.warning(
                            "任务仍在后台运行，"
                            "当前页面已停止自动查询。"
                        )

                        st.caption(
                            f"任务ID：{task_id}"
                        )

                        break

                    task_response = requests.get(
                        (
                            f"{API_BASE_URL}"
                            f"/document-tasks/"
                            f"{task_id}"
                        ),
                        timeout=30,
                    )

                    if (
                        task_response.status_code
                        != 200
                    ):
                        task_status_placeholder.empty()

                        st.error(
                            f"查询任务状态失败："
                            f"{task_response.text}"
                        )

                        break

                    task = task_response.json()
                    task_status = task["status"]
                    task_message = task["message"]

                    if task_status == "pending":
                        task_status_placeholder.info(
                            "任务等待中："
                            f"{task_message}"
                        )

                    elif task_status == "processing":
                        task_status_placeholder.info(
                            "后台处理中："
                            f"{task_message}"
                        )

                    elif task_status == "completed":
                        task_finished = True
                        task_status_placeholder.empty()

                        result = (
                            task.get("result")
                            or {}
                        )

                        if result.get(
                            "already_exists",
                            False,
                        ):
                            st.warning(task_message)

                        else:
                            st.success(task_message)

                        st.write(
                            f"文件："
                            f"{result.get('file_name', uploaded_file.name)}"
                        )

                        file_type = result.get(
                            "file_type",
                            file_extension,
                        )

                        st.write(
                            f"文件类型："
                            f"{file_type.upper()}"
                        )

                        unit_count = result.get(
                            "unit_count",
                            result.get(
                                "page_count",
                                0,
                            ),
                        )

                        st.write(
                            f"内容单元数："
                            f"{unit_count}"
                        )

                        st.write(
                            f"文本块数："
                            f"{result.get('chunk_count', 0)}"
                        )

                    elif task_status == "failed":
                        task_finished = True
                        task_status_placeholder.empty()

                        error_message = (
                            task.get(
                                "error_message"
                            )
                            or task_message
                        )

                        st.error(
                            f"文档处理失败："
                            f"{error_message}"
                        )

                    else:
                        task_finished = True
                        task_status_placeholder.empty()

                        st.error(
                            f"未知任务状态："
                            f"{task_status}"
                        )

                    if not task_finished:
                        time.sleep(2)

        except requests.Timeout:
            task_status_placeholder.empty()

            st.error(
                "请求超时，请稍后查询任务状态"
            )

        except requests.RequestException as error:
            task_status_placeholder.empty()

            st.error(
                f"无法连接后端：{error}"
            )

    # =====================================================
    # 已入库文档
    # =====================================================

    st.divider()
    st.subheader("已入库文档")

    if "document_notice" in st.session_state:
        st.success(st.session_state.document_notice)
        del st.session_state.document_notice

    try:
        documents_response = requests.get(
            f"{API_BASE_URL}/documents",
            timeout=10,
        )

        if documents_response.status_code == 200:
            documents_result = documents_response.json()
            documents = documents_result["documents"]

            if documents:
                for index, document in enumerate(documents):
                    st.write(f"📄 {document['file_name']}")
                    st.caption(
                        f"文本块数量：{document['chunk_count']}"
                    )

                    with st.expander("删除该文档"):
                        st.warning(
                            "删除后，该文档将无法再被知识库检索。"
                        )

                        if st.button(
                            "确认删除",
                            key=f"delete_document_{index}",
                            use_container_width=True,
                        ):
                            try:
                                delete_response = requests.delete(
                                    f"{API_BASE_URL}/documents",
                                    json={
                                        "file_hash": document.get(
                                            "file_hash"
                                        ),
                                        "file_name": document["file_name"],
                                    },
                                    timeout=30,
                                )

                                if delete_response.status_code == 200:
                                    delete_result = (
                                        delete_response.json()
                                    )

                                    st.session_state.document_notice = (
                                        f"已删除："
                                        f"{delete_result['file_name']}，"
                                        f"共删除 "
                                        f"{delete_result['deleted_chunk_count']} "
                                        f"个文本块"
                                    )

                                    st.rerun()

                                else:
                                    st.error(
                                        f"删除失败："
                                        f"{delete_response.text}"
                                    )

                            except requests.RequestException as error:
                                st.error(
                                    f"无法连接后端：{error}"
                                )

                    st.divider()

            else:
                st.info("知识库中暂无文档")

        else:
            st.error(
                f"获取文档列表失败："
                f"{documents_response.text}"
            )

    except requests.RequestException as error:
        st.warning(
            f"暂时无法连接后端服务：{error}"
        )

    # =====================================================
    # 长期记忆
    # =====================================================

    st.divider()
    st.subheader("长期记忆")

    if "memory_notice" in st.session_state:
        st.success(
            st.session_state.memory_notice
        )
        del st.session_state.memory_notice

    try:
        memories_response = requests.get(
            f"{API_BASE_URL}/memories",
            timeout=10,
        )

        if memories_response.status_code == 200:
            memories_result = memories_response.json()
            memories = memories_result["memories"]

            if memories:
                for index, memory in enumerate(memories):
                    memory_key = memory["memory_key"]
                    memory_value = memory["memory_value"]

                    st.markdown(
                        f"**{memory_key}**"
                    )

                    st.write(memory_value)

                    st.caption(
                        f"最后更新："
                        f"{memory['updated_at']}"
                    )

                    with st.expander("删除该记忆"):
                        st.warning(
                            "删除后，新对话将无法再读取这条长期记忆。"
                        )

                        if st.button(
                            "确认删除记忆",
                            key=(
                                f"delete_memory_"
                                f"{index}_"
                                f"{memory_key}"
                            ),
                            use_container_width=True,
                        ):
                            try:
                                delete_memory_response = (
                                    requests.delete(
                                        f"{API_BASE_URL}/memories/"
                                        f"{memory_key}",
                                        timeout=30,
                                    )
                                )

                                if (
                                    delete_memory_response.status_code
                                    == 200
                                ):
                                    delete_result = (
                                        delete_memory_response.json()
                                    )

                                    st.session_state.memory_notice = (
                                        f"已删除长期记忆："
                                        f"{delete_result['memory_key']}"
                                    )

                                    st.rerun()

                                else:
                                    st.error(
                                        f"删除长期记忆失败："
                                        f"{delete_memory_response.text}"
                                    )

                            except requests.RequestException as error:
                                st.error(
                                    f"无法连接后端：{error}"
                                )

                    st.divider()

            else:
                st.info("暂无长期记忆")

        else:
            st.error(
                f"获取长期记忆失败："
                f"{memories_response.text}"
            )

    except requests.RequestException as error:
        st.warning(
            f"无法读取长期记忆：{error}"
        )

    # =====================================================
    # 新建对话
    # =====================================================

    # =====================================================
    # 新建对话
    # =====================================================

    st.divider()

    if st.button(
        "新建对话",
        use_container_width=True,
    ):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    # =====================================================
    # 历史会话
    # =====================================================

    st.divider()
    st.subheader("历史会话")

    try:
        sessions_response = requests.get(
            f"{API_BASE_URL}/sessions",
            timeout=10,
        )

        if sessions_response.status_code == 200:
            sessions_result = sessions_response.json()
            sessions = sessions_result["sessions"]

            if sessions:
                for session in sessions:
                    session_thread_id = session["thread_id"]
                    session_title = session["title"]

                    is_current_session = (
                        session_thread_id
                        == st.session_state.thread_id
                    )

                    if is_current_session:
                        button_label = f"● {session_title}"
                    else:
                        button_label = session_title

                    if st.button(
                        button_label,
                        key=f"session_{session_thread_id}",
                        use_container_width=True,
                    ):
                        try:
                            session_response = requests.get(
                                f"{API_BASE_URL}/sessions/"
                                f"{session_thread_id}",
                                timeout=10,
                            )

                            if session_response.status_code == 200:
                                session_result = (
                                    session_response.json()
                                )

                                st.session_state.thread_id = (
                                    session_thread_id
                                )

                                st.session_state.messages = (
                                    session_result["messages"]
                                )

                                st.rerun()

                            else:
                                st.error(
                                    f"读取该会话的消息失败："
                                    f"{session_response.text}"
                                )

                        except requests.RequestException as error:
                            st.error(
                                f"无法读取历史会话：{error}"
                            )

                    st.caption(
                        f"最后更新：{session['updated_at']}"
                    )

            else:
                st.info("暂无历史会话")

        else:
            st.error(
                f"获取历史会话失败："
                f"{sessions_response.text}"
            )

    except requests.RequestException as error:
        st.warning(
            f"无法读取历史会话：{error}"
        )


# =====================================================
# 显示当前会话消息
# =====================================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =====================================================
# 聊天输入
# =====================================================

query = st.chat_input(
    "请输入你想询问的问题"
)


if query:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": query,
        }
    )

    with st.chat_message("user"):
        st.markdown(query)

    answer = ""
    tool_names = []

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        status_placeholder = st.empty()

        status_placeholder.info(
            "Agent正在思考……"
        )

        try:
            with requests.post(
                f"{API_BASE_URL}/chat/stream",
                json={
                    "query": query,
                    "thread_id": (
                        st.session_state.thread_id
                    ),
                },
                stream=True,
                timeout=(10, 300),
            ) as response:
                if response.status_code != 200:
                    answer = (
                        f"请求失败："
                        f"{response.text}"
                    )

                    status_placeholder.empty()
                    st.error(answer)

                else:
                    for line in response.iter_lines():
                        if not line:
                            continue

                        try:
                            line_text = line.decode(
                                "utf-8"
                            )

                            event = json.loads(
                                line_text
                            )

                        except (
                            UnicodeDecodeError,
                            json.JSONDecodeError,
                        ):
                            continue

                        event_type = event.get(
                            "type"
                        )

                        if event_type == "token":
                            token = event.get(
                                "content",
                                "",
                            )

                            answer += token

                            answer_placeholder.markdown(
                                answer + "▌"
                            )

                        elif event_type == "tool":
                            tool_name = event.get(
                                "tool_name",
                                "unknown_tool",
                            )

                            if (
                                tool_name
                                not in tool_names
                            ):
                                tool_names.append(
                                    tool_name
                                )

                            status_placeholder.info(
                                f"正在调用工具："
                                f"{tool_name}"
                            )

                        elif event_type == "done":
                            event_tool_names = (
                                event.get(
                                    "tool_names",
                                    [],
                                )
                            )

                            for tool_name in (
                                event_tool_names
                            ):
                                if (
                                    tool_name
                                    not in tool_names
                                ):
                                    tool_names.append(
                                        tool_name
                                    )

                            status_placeholder.empty()

                        elif event_type == "error":
                            error_message = event.get(
                                "message",
                                "Agent执行失败",
                            )

                            status_placeholder.empty()
                            st.error(error_message)

                            if not answer:
                                answer = error_message

                    if answer:
                        answer_placeholder.markdown(
                            answer
                        )

                    else:
                        answer = (
                            "Agent未返回有效回答"
                        )

                        answer_placeholder.warning(
                            answer
                        )

                    if tool_names:
                        st.caption(
                            "本轮调用工具："
                            + "、".join(tool_names)
                        )

                    else:
                        st.caption(
                            "本次未调用Agent工具"
                        )

        except requests.Timeout:
            answer = (
                answer
                or "请求超时，请稍后重试"
            )

            status_placeholder.empty()
            answer_placeholder.markdown(
                answer
            )

            st.error("Agent请求超时")

        except requests.RequestException as error:
            answer = (
                answer
                or f"无法连接后端：{error}"
            )

            status_placeholder.empty()
            answer_placeholder.markdown(
                answer
            )

            st.error(
                f"无法连接后端：{error}"
            )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )
