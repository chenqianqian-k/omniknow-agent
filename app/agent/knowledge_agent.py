from collections.abc import Iterator

from langchain.agents import create_agent
#from langchain.messages import ToolMessage
from langchain.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    ToolMessage,
)
from langchain.tools import tool

from app.rag.qa import get_llm
from app.rag.retriever import (
    get_document_content,
    search_knowledge_base,
)
from app.memory.session_store import save_session
from app.memory.long_term_memory import (
    delete_memory,
    get_memories,
    save_memory,
)

from app.tools.web_search import search_web

#from langgraph.checkpoint.memory import InMemorySaver #新增2026724
from langgraph.checkpoint.sqlite import SqliteSaver

from app.rag.ingest import list_documents

import sqlite3
from pathlib import Path


DEFAULT_USER_ID = "default-user"


@tool
def knowledge_search(query: str) -> str:
    """搜索本地知识库。

    当用户询问上传文档、通知书、公司资料、规章制度或其他
    可能需要从知识库获取依据的问题时，调用此工具。
    """
    results = search_knowledge_base(
        query=query,
        top_k=3,
        recall_k=10,
    )

    if not results:
        return "知识库中没有检索到相关资料。"

    context_parts = []

    for result in results:
        context_parts.append(
            f"""[重排序结果{result["rank"]}]
文件：{result["file_name"]}
文件类型：{result["file_type"]}
来源位置：{result["location_label"]}
原向量距离：{result["distance"]}
重排序分数：{result["rerank_score"]}
内容：
{result["content"]}"""
        )

    return "\n\n".join(context_parts)

@tool
def knowledge_document_list() -> str:
    """查询当前知识库中已经入库的文档列表。"""
    documents = list_documents()

    if not documents:
        return "当前知识库中没有任何文档。"

    lines = ["当前知识库包含以下文档："]

    for index, document in enumerate(documents, start=1):
        lines.append(
            f"{index}. {document['file_name']}，"
            f"共 {document['chunk_count']} 个文本块"
        )

    return "\n".join(lines)


@tool
def document_summary(file_name: str) -> str:
    """读取指定文档的内容，用于总结、概括或分析整份文档。

    Args:
        file_name: 知识库中的完整文件名，包括文件扩展名。
    """
    document_chunks = get_document_content(
        file_name=file_name,
        max_chunks=30,
    )

    if not document_chunks:
        return (
            f"知识库中没有找到文件：{file_name}。"
            "请先调用knowledge_document_list确认完整文件名。"
        )

    file_type = document_chunks[0].get(
        "file_type",
        "unknown",
    )

    content_parts = [
        f"文件名：{file_name}",
        f"文件类型：{file_type}",
        f"读取文本块数量：{len(document_chunks)}",
        "文档内容：",
    ]

    for index, chunk in enumerate(
        document_chunks,
        start=1,
    ):
        content_parts.append(
            f"\n【文本块{index}，"
            f"{chunk['location_label']}】\n"
            f"{chunk['content']}"
        )

    return "\n".join(content_parts)


@tool
def save_user_memory(
    memory_key: str,
    memory_value: str,
) -> str:
    """当用户明确要求记住长期信息时，保存或更新一条用户长期记忆。

    Args:
        memory_key: 记忆的简短类型，例如name、nickname、research_direction。
        memory_value: 需要长期保存的具体内容。
    """
    result = save_memory(
        user_id=DEFAULT_USER_ID,
        memory_key=memory_key,
        memory_value=memory_value,
    )

    return (
        "长期记忆保存成功："
        f"{result['memory_key']} = "
        f"{result['memory_value']}"
    )

@tool
def get_user_memories() -> str:
    """查询用户已经保存的全部长期记忆。

    当用户询问自己的姓名、称呼、研究方向、回答偏好、
    长期项目背景，或者询问“你记得我什么”时，调用此工具。
    """
    memories = get_memories(
        user_id=DEFAULT_USER_ID
    )

    if not memories:
        return "当前没有保存任何用户长期记忆。"

    memory_lines = [
        "当前已保存的用户长期记忆："
    ]

    for memory in memories:
        memory_lines.append(
            f"- {memory['memory_key']}："
            f"{memory['memory_value']}"
        )

    return "\n".join(memory_lines)


@tool
def delete_user_memory(
    memory_key: str,
) -> str:
    """当用户明确要求忘记或删除某项长期信息时，删除对应长期记忆。

    Args:
        memory_key: 需要删除的记忆类型，例如name、nickname、research_direction。
    """
    deleted = delete_memory(
        user_id=DEFAULT_USER_ID,
        memory_key=memory_key,
    )

    if not deleted:
        return (
            "没有找到需要删除的长期记忆："
            f"{memory_key}"
        )

    return (
        "长期记忆删除成功："
        f"{memory_key}"
    )

@tool
def web_search(query: str) -> str:
    """搜索互联网中的实时或外部信息。

    当用户询问最新新闻、近期动态、当前政策、实时信息、
    开源项目、互联网资料，或者知识库中不存在的外部信息时，
    调用此工具。

    Args:
        query: 适合发送给搜索引擎的简洁搜索问题。
    """
    try:
        results = search_web(
            query=query,
            max_results=5,
        )

    except Exception as error:
        return f"联网搜索失败：{error}"

    if not results:
        return "没有搜索到相关的互联网资料。"

    result_parts = []

    for result in results:
        result_parts.append(
            f"""[网页结果{result["rank"]}]
标题：{result["title"]}
链接：{result["url"]}
相关度：{result["score"]}
内容摘要：
{result["content"]}"""
        )

    return "\n\n".join(result_parts)

SYSTEM_PROMPT = """你是一个具有知识库检索、文档处理、短期会话记忆和长期记忆能力的智能Agent。

你可以根据用户的问题，自主决定是否调用工具以及调用哪个工具。

你目前可以使用以下工具：
1. knowledge_search：检索知识库中的具体内容，用于回答与上传文档有关的具体问题。
2. knowledge_document_list：查询知识库中已有的文档列表、文件名称和文档数量。
3. document_summary：读取指定文档的整体内容，用于总结、概括或分析文档。
4. save_user_memory：当用户明确要求记住某项长期信息时，保存或更新长期记忆。
5. get_user_memories：查询用户已经保存的长期记忆，用于回答用户姓名、称呼、研究方向、稳定偏好和长期项目背景等问题。
6. delete_user_memory：当用户明确要求忘记或删除某项长期信息时，删除对应的长期记忆。
7. web_search：搜索互联网中的实时或外部信息，用于获取最新新闻、近期动态、当前政策、开源项目和知识库之外的公开资料。

必须遵守以下规则：

一、知识库检索规则
1. 如果用户询问上传文档中的具体内容，例如通知书、简历、公司资料等，必须调用knowledge_search。
2. 不得凭记忆回答知识库相关问题，也不能使用之前对话中的检索结果代替本轮工具调用。
3. 只能依据工具本轮返回的资料回答知识库问题。
4. 如果工具返回的资料无法回答问题，明确说明“根据当前知识库资料，无法回答该问题”。
5. 使用knowledge_search回答时，需要在答案末尾标明资料的文件名和来源位置。PDF使用页码，PPTX使用幻灯片编号，DOCX、Markdown和TXT标注为文档正文。

二、文档列表与总结规则
6. 如果用户询问知识库中有哪些文件、文件名称、文档数量或已经上传了什么资料，必须调用knowledge_document_list。
7. 使用knowledge_document_list回答时，只能列出工具实际返回的文档，不得虚构文件。
8. 如果用户要求总结、概括或整体分析某份文档，必须调用document_summary。
9. 如果无法确定用户所指文档的完整文件名，先调用knowledge_document_list确认完整文件名，再调用document_summary。
10. 使用document_summary回答时，只能依据工具返回的文档内容进行总结，不得补充文档中不存在的信息。

三、长期记忆保存规则
11. 只有当用户明确表达“记住”“以后记得”“保存这个信息”等长期保存意图时，才允许调用save_user_memory。
12. 用户没有明确要求保存时，不得擅自写入长期记忆。
13. 适合保存的长期记忆包括用户姓名、称呼、长期研究方向、稳定偏好和长期项目背景。
14. 临时任务参数、当前运行状态、一次性要求和容易过期的信息不得保存为长期记忆。
15. API Key、密码、身份证号、银行卡号、验证码等敏感信息不得保存为长期记忆。
16. memory_key必须使用简短且稳定的英文名称，例如name、nickname、research_direction、answer_preference和project_background。
17. 如果用户提供了多个相互独立的长期信息，应根据内容分别调用save_user_memory保存，不要把完全不同的信息合并到同一个memory_key中。
18. 如果同一个memory_key已经存在，可以调用save_user_memory更新该长期记忆。
19. 当用户询问自己的姓名、称呼、研究方向、稳定偏好、长期项目背景，或者询问“你记得我什么”时，必须调用get_user_memories。
20. 不得仅根据当前会话历史回答长期用户信息；需要调用get_user_memories确认已经保存的内容。
21. 只能依据get_user_memories返回的内容回答长期记忆问题。
22. 如果工具没有返回相关记忆，应明确说明当前没有保存该信息，不得自行猜测。
23. 只有当用户明确表达“忘记”“删除记忆”“不要再记住”等意图时，才允许调用delete_user_memory。
24. 调用delete_user_memory时，需要根据用户描述确定对应的memory_key。
25. 如果无法判断应删除哪个memory_key，应先调用get_user_memories查看已经保存的记忆，再决定是否删除。
26. 不得因为用户修改某项信息而先删除旧记忆；对于信息更新，应直接调用save_user_memory覆盖原值。
27. 删除成功后，应明确告诉用户删除的是哪项长期记忆。

四、一般回答规则
28. 如果是问候、简单交流或与知识库无关的一般问题，可以直接回答，不需要调用知识库工具。
29. 短期会话历史只用于理解当前会话上下文，不得将其自动保存为长期记忆。
30. 所有回答都应当准确、简洁、清晰，不得编造信息。

五、联网搜索规则
31. 当用户询问最新、最近、当前、今日、实时、新闻、政策变化、开源项目动态或其他可能发生变化的信息时，必须调用web_search。
32. 当问题明确涉及用户上传的文档时，应优先调用knowledge_search，不得使用web_search代替本地知识库检索。
33. 当用户要求结合本地文档和互联网信息进行分析时，可以先调用knowledge_search，再调用web_search。
34. 只能依据web_search本轮返回的网页资料回答实时或外部信息，不得编造搜索结果中不存在的事实。
35. 使用web_search回答时，应在答案中保留相关网页的标题和链接，方便用户核查。
36. 如果联网搜索失败或没有搜索到相关资料，应明确说明，不得根据模型记忆伪造最新信息。
"""


# 1. 创建内存状态保存器
#CHECKPOINTER = InMemorySaver()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
CHECKPOINT_DB_PATH = MEMORY_DIR / "conversation_memory.db"

MEMORY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CHECKPOINT_CONNECTION = sqlite3.connect(
    str(CHECKPOINT_DB_PATH),
    check_same_thread=False,
)

CHECKPOINTER = SqliteSaver(
    CHECKPOINT_CONNECTION
)



# 2. 创建具有记忆能力的Agent
def create_knowledge_agent():
    """创建具有知识库检索和短期记忆能力的Agent。"""
    model = get_llm()

    return create_agent(
        model=model,
        tools=[
            knowledge_search,
            knowledge_document_list,
            document_summary,
            save_user_memory,
            get_user_memories,
            delete_user_memory,
            web_search,
        ],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=CHECKPOINTER,
    )

# 3. 在程序启动时只创建一次Agent
AGENT = create_knowledge_agent()

# 4. Agent执行函数
def run_agent(
    query: str,
    thread_id: str = "default",
) -> dict:
    """在指定会话中执行Agent。"""
    result = AGENT.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": query,
                }
            ]
        },
        config={
            "configurable": {
                "thread_id": thread_id,
            }
        },
    )

    save_session(
    thread_id=thread_id,
    first_query=query,
    )

    messages = result["messages"]
    final_message = messages[-1]

    current_turn_messages = []

    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            break

        current_turn_messages.append(message)

    tool_records = []

    for message in current_turn_messages:
        if isinstance(message, ToolMessage):
            tool_records.append(
                {
                    "tool_name": message.name,
                    "content": message.content,
                }
            )

    return {
        "answer": final_message.content,
        "tool_called": len(tool_records) > 0,
        "tool_records": tool_records,
    }


def extract_chunk_text(
    message_chunk: AIMessageChunk,
) -> str:
    """从模型流式消息块中提取文本。"""
    content = message_chunk.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if not isinstance(block, dict):
                continue

            if block.get("type") in {
                "text",
                "text_delta",
            }:
                text_parts.append(
                    block.get("text", "")
                )

        return "".join(text_parts)

    return ""


def stream_agent(
    query: str,
    thread_id: str = "default",
) -> Iterator[dict]:
    """在指定会话中流式执行Agent。"""
    clean_query = query.strip()
    clean_thread_id = thread_id.strip()

    if not clean_query:
        raise ValueError("用户问题不能为空")

    if not clean_thread_id:
        raise ValueError("thread_id不能为空")

    agent_input = {
        "messages": [
            {
                "role": "user",
                "content": clean_query,
            }
        ]
    }

    agent_config = {
        "configurable": {
            "thread_id": clean_thread_id,
        }
    }

    called_tools = []

    for stream_mode, chunk in AGENT.stream(
        agent_input,
        config=agent_config,
        stream_mode=[
            "messages",
            "updates",
        ],
    ):
        if stream_mode == "messages":
            message_chunk, metadata = chunk

            if not isinstance(
                message_chunk,
                AIMessageChunk,
            ):
                continue

            text = extract_chunk_text(
                message_chunk
            )

            if text:
                yield {
                    "type": "token",
                    "content": text,
                }

        elif stream_mode == "updates":
            for node_name, node_update in chunk.items():
                if not isinstance(
                    node_update,
                    dict,
                ):
                    continue

                node_messages = node_update.get(
                    "messages",
                    [],
                )

                if not isinstance(
                    node_messages,
                    list,
                ):
                    node_messages = [
                        node_messages
                    ]

                for message in node_messages:
                    if not isinstance(
                        message,
                        ToolMessage,
                    ):
                        continue

                    tool_name = (
                        message.name
                        or "unknown_tool"
                    )

                    if tool_name in called_tools:
                        continue

                    called_tools.append(tool_name)

                    yield {
                        "type": "tool",
                        "tool_name": tool_name,
                    }

    save_session(
        thread_id=clean_thread_id,
        first_query=clean_query,
    )

    yield {
        "type": "done",
        "tool_called": len(called_tools) > 0,
        "tool_names": called_tools,
    }


def get_session_messages(
    thread_id: str,
) -> list[dict]:
    """读取指定会话中的用户消息和Agent回答。"""
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    state = AGENT.get_state(config)
    messages = state.values.get("messages", [])

    formatted_messages = []

    for message in messages:
        if isinstance(message, HumanMessage):
            formatted_messages.append(
                {
                    "role": "user",
                    "content": message.content,
                }
            )

        elif isinstance(message, AIMessage):
            if not message.content:
                continue

            formatted_messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                }
            )

    return formatted_messages


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="知识库Agent")
    parser.add_argument("query", help="用户问题")
    args = parser.parse_args()

    result = run_agent(args.query)

    print("\nAgent回答：")
    print(result["answer"])

    print("\n是否调用知识库工具：")
    print(result["tool_called"])

    if result["tool_records"]:
        print("\n工具调用记录：")

        for record in result["tool_records"]:
            print(f"- 工具：{record['tool_name']}")
