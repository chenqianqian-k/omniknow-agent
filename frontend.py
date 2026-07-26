import uuid

import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:6006"


st.set_page_config(
    page_title="Knowledge Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Knowledge Agent")
st.caption(
    "基于 DeepSeek、LangGraph 和 ChromaDB 的知识库问答 Agent"
)


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

    uploaded_file = st.file_uploader(
        "上传PDF文档",
        type=["pdf"],
    )

    if st.button(
        "上传并写入知识库",
        disabled=uploaded_file is None,
        use_container_width=True,
    ):
        try:
            with st.spinner("正在解析并写入知识库……"):
                response = requests.post(
                    f"{API_BASE_URL}/documents/upload",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/pdf",
                        )
                    },
                    timeout=300,
                )

            if response.status_code == 200:
                result = response.json()
                document = result["document"]

                if document.get("already_exists", False):
                    st.warning(result["message"])
                else:
                    st.success(result["message"])

                st.write(f"文件：{document['file_name']}")
                st.write(f"页数：{document['page_count']}")
                st.write(f"文本块数：{document['chunk_count']}")

            else:
                st.error(f"上传失败：{response.text}")

        except requests.RequestException as error:
            st.error(f"无法连接后端：{error}")

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

query = st.chat_input("请输入你想询问的问题")


if query:
    st.session_state.messages.append(
        {
            "role": "user",
            "content": query,
        }
    )

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Agent正在思考……"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/chat",
                    json={
                        "query": query,
                        "thread_id": st.session_state.thread_id,
                    },
                    timeout=300,
                )

                if response.status_code == 200:
                    result = response.json()
                    answer = result["answer"]

                    st.markdown(answer)

                    if result["tool_called"]:
                        st.caption("已调用Agent工具")
                    else:
                        st.caption("本次未调用Agent工具")

                else:
                    answer = f"请求失败：{response.text}"
                    st.error(answer)

            except requests.RequestException as error:
                answer = f"无法连接后端：{error}"
                st.error(answer)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )