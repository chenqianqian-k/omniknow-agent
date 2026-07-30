# OmniKnow Agent

> 一个具备多格式文档检索、Agent 工具调用、联网搜索、流式回答与持久化记忆能力的知识库智能体。

OmniKnow Agent 是一个面向个人知识管理与文档问答场景构建的 Agent 应用。项目基于 DeepSeek、LangChain、ChromaDB 和 FastAPI，支持 PDF、DOCX、PPTX、Markdown 和 TXT 等常见文档的解析入库，并通过 BGE Embedding 向量召回与 Cross-Encoder Reranker 重排序构建两阶段 RAG 检索流程。

系统可以根据用户意图自主调用知识库检索、文档总结、文档列表、联网搜索和长期记忆等工具；使用 LangGraph Checkpointer 与 SQLite 持久化会话状态，并支持 Agent 流式回答、异步文档入库、后台任务状态查询、历史会话恢复和跨会话长期记忆。

## 核心能力

### 多格式文档知识库

- 支持 PDF、DOCX、PPTX、Markdown 和 TXT 文档
- 根据文件扩展名自动选择对应文档解析方式
- 支持文档内容切分、向量化与 ChromaDB 持久化
- 基于 SHA-256 文件哈希检测重复文档
- 支持已入库文档查询、删除和整体总结
- PDF 保留页码，PPTX 保留幻灯片编号
- DOCX、Markdown 和 TXT 使用文档正文作为来源位置

### 两阶段知识检索

- 使用 BGE Embedding 与 ChromaDB 召回 Top-10 候选文本块
- 使用 `bge-reranker-base` 对候选文本进行 Cross-Encoder 重排序
- 保留相关性最高的 Top-3 证据
- 将证据内容、文件名和来源位置交给 DeepSeek 生成回答

### Agent工具调用

- 基于 LangChain `create_agent` 构建多工具 Agent
- 根据用户意图自主选择知识库、联网搜索和长期记忆工具
- 使用系统提示词约束知识库问答必须基于工具返回的证据
- 记录当前轮次的工具调用信息
- 支持普通对话与知识库问答的自主路由

### 流式回答

- 使用 LangChain Agent `stream()` 获取模型消息和工具状态
- 使用 FastAPI `StreamingResponse` 返回 NDJSON 事件流
- 前端逐行读取 `token`、`tool`、`done` 和 `error` 事件
- 使用 Streamlit 占位区域增量展示模型回答
- 实时展示本轮工具调用情况

### 异步文档入库

- 使用 FastAPI `BackgroundTasks` 在响应返回后处理文档
- 上传接口立即返回唯一 `task_id`
- 使用 SQLite 持久化文档任务状态
- 支持 `pending`、`processing`、`completed` 和 `failed` 状态
- 前端根据 `task_id` 轮询文档处理进度
- 避免文档解析和向量化长时间阻塞上传请求

### 双层记忆机制

- 使用 LangGraph `SqliteSaver` 持久化会话上下文
- 通过 `thread_id` 隔离不同对话
- 支持历史会话查询、恢复和继续对话
- 使用独立 SQLite 数据库保存用户长期记忆
- 支持长期记忆的新增、更新、查询和删除

### 应用服务

- FastAPI 后端接口
- Streamlit 交互界面
- 多格式文档上传与知识库管理
- 历史会话查询与恢复
- 长期记忆查询与管理
- Shell 脚本一键启动前后端服务

## Agent工具

| 工具名称 | 主要功能 | 典型使用场景 |
|---|---|---|
| `knowledge_search` | 检索本地知识库 | 查询文档中的具体事实 |
| `knowledge_document_list` | 查询已入库文档 | 查看知识库包含哪些文件 |
| `document_summary` | 读取并总结指定文档 | 总结 PDF、DOCX、PPTX、Markdown 或 TXT 文档 |
| `web_search` | 搜索实时互联网信息 | 查询新闻、项目和时效性信息 |
| `save_user_memory` | 保存或更新长期记忆 | 保存用户的长期回答偏好 |
| `get_user_memories` | 查询长期记忆 | 跨会话读取已保存的信息 |
| `delete_user_memory` | 删除指定长期记忆 | 清除不再需要的用户信息 |

LangChain Agent 会结合系统提示词、用户问题和工具描述，自主决定是否调用工具以及调用哪一个工具。

例如：

```text
产品手册中的保修期限是多久？
→ knowledge_search

知识库里有哪些文件？
→ knowledge_document_list

请总结product_manual.pdf的主要内容。
→ document_summary

请搜索最近的LangChain开源项目。
→ web_search

请记住，我偏好简洁的回答。
→ save_user_memory

我保存了哪些回答偏好？
→ get_user_memories
```

## 系统架构

OmniKnow Agent 采用分层架构，将交互界面、API 服务、Agent 编排、工具调用、知识检索与持久化记忆进行解耦。

LangChain Agent 根据用户意图自主选择知识库检索、联网搜索或长期记忆等工具，并调用 DeepSeek 完成工具决策、信息整合与回答生成。会话状态通过 LangGraph Checkpointer 和 SQLite 进行持久化。

<p align="center">
  <img
    src="assets/3efb6fac-d827-4758-9e4e-b56a92e98d6c.png"
    alt="OmniKnow Agent System Architecture"
    width="1000"
  >
</p>

整体调用关系如下：

```text
用户
→ Streamlit交互界面
→ FastAPI后端服务
→ LangChain Agent
→ 工具调用与DeepSeek回答生成
```

其中，会话状态的保存关系为：

```text
LangChain Agent
→ LangGraph Checkpointer
→ SQLite会话数据库
```

## 知识库问答流程

项目采用多格式文档解析、向量召回与 Cross-Encoder 重排序相结合的知识库问答流程。

用户上传文档后，系统首先根据文件扩展名选择对应的解析方式。PDF 按页面解析，PPTX 按幻灯片解析，DOCX 提取段落和表格内容，Markdown 与 TXT 按文本内容读取。解析结果经过统一切分后写入 ChromaDB。

用户提问时，系统使用 BGE Embedding 对问题进行向量化，并从 ChromaDB 召回 Top-10 候选文本块；随后使用 BGE Reranker 重新计算问题与候选文本之间的相关性，选择 Top-3 证据交给 DeepSeek 生成回答。

<p align="center">
  <img
    src="assets/two-stage-retrieval.png"
    alt="OmniKnow Agent Two-Stage Knowledge Retrieval Pipeline"
    width="1000"
  >
</p>

完整执行过程如下：

1. 根据文件格式解析 PDF、DOCX、PPTX、Markdown 或 TXT 文档。
2. 使用 `RecursiveCharacterTextSplitter` 对文档内容进行文本切分。
3. 使用 `bge-small-zh-v1.5` 对文本块和用户问题进行向量化。
4. 从 ChromaDB 中召回向量距离最接近的 Top-10 文本块。
5. 使用 `bge-reranker-base` 联合编码用户问题与候选文本。
6. 根据 Reranker 相关性分数重新排列候选文本。
7. 保留得分最高的 Top-3 证据。
8. 将证据内容、文件名和来源位置返回给 Agent。
9. DeepSeek 根据用户问题与检索证据生成最终回答。

不同格式文档使用不同的来源位置表示：

- PDF：显示对应页码
- PPTX：显示对应幻灯片编号
- DOCX：显示为文档正文
- Markdown：显示为文档正文
- TXT：显示为文档正文

Embedding 模型适合从大量文本块中快速召回候选内容，Reranker 则进一步判断问题与候选文本之间的相关性，从而改善最终证据的排序质量。

## 流式回答

普通 `invoke()` 需要等待 Agent 完整执行后一次性返回结果。项目新增 `stream_agent()`，同时订阅 LangChain Agent 的 `messages` 和 `updates` 流。

```text
用户问题
→ Agent判断并调用工具
→ 流式产生模型Token
→ FastAPI转换为NDJSON事件
→ Streamlit逐段更新回答
```

流式接口返回以下事件：

| 事件类型 | 作用 |
|---|---|
| `token` | 模型生成的文本片段 |
| `tool` | 本轮已经完成的工具调用 |
| `done` | 本轮 Agent 执行结束 |
| `error` | 流式执行过程中发生异常 |

FastAPI 使用 `StreamingResponse` 将事件逐行发送给前端。Streamlit 通过 `requests.iter_lines()` 读取 NDJSON 数据，并在同一个占位区域中持续拼接模型输出。

## 异步文档入库

同步文档上传需要等待解析、切分、向量化和 ChromaDB 写入全部完成。为了降低大文档处理对上传请求的阻塞，项目使用 FastAPI `BackgroundTasks` 实现后台文档处理。

```text
上传文档
→ 保存文件
→ 创建SQLite任务记录
→ 返回HTTP 202和task_id
→ 后台解析并写入ChromaDB
→ 前端轮询任务状态
```

任务生命周期如下：

```text
pending
   ↓
processing
   ├── completed
   └── failed
```

任务状态保存在：

```text
data/tasks/document_tasks.db
```

前端获得 `task_id` 后，通过任务状态查询接口轮询处理进度，并根据任务状态展示等待中、处理中、处理成功或处理失败。

## 记忆机制

OmniKnow Agent 将记忆分为会话记忆和用户长期记忆。

### 会话记忆

会话记忆用于保存同一个对话中的完整消息状态，包括用户消息、Agent 回答和工具调用过程。

项目将 LangGraph `SqliteSaver` 作为 LangChain Agent 的 Checkpointer，通过 SQLite 持久化 Agent 状态，并使用 `thread_id` 区分不同会话。

支持：

- 多轮对话上下文理解
- 不同会话之间的状态隔离
- 服务重启后恢复历史会话
- 查看历史会话列表
- 恢复并继续已有会话

默认保存位置：

```text
data/memory/conversation_memory.db
```

每次调用 Agent 时，都会将当前会话的 `thread_id` 传给 Checkpointer：

```python
config={
    "configurable": {
        "thread_id": thread_id,
    }
}
```

相同的 `thread_id` 会继续读取原有会话状态，不同的 `thread_id` 则对应不同的对话。

### 长期记忆

长期记忆用于保存需要跨会话使用的稳定信息，例如：

- 回答风格偏好
- 长期关注方向
- 稳定的项目背景
- 需要跨会话保留的设置

长期记忆不依赖当前 `thread_id`。即使新建对话，Agent 仍然可以通过长期记忆工具读取已保存的信息。

支持：

- 保存新记忆
- 更新已有记忆
- 查询全部记忆
- 删除指定记忆

默认保存位置：

```text
data/memory/long_term_memory.db
```

当前版本使用单用户配置：

```text
default-user
```

长期记忆只会在用户明确表达“请记住”“以后记得”或“保存这个信息”等意图时写入，不会自动保存每一条聊天内容。

## 技术栈

| 模块 | 使用技术 |
|---|---|
| Agent构建与工具调用 | LangChain |
| 大语言模型 | DeepSeek API |
| 会话状态管理 | LangGraph Checkpointer |
| 后端服务 | FastAPI、Uvicorn |
| 流式传输 | StreamingResponse、NDJSON |
| 后台任务 | FastAPI BackgroundTasks |
| 交互界面 | Streamlit |
| 向量数据库 | ChromaDB |
| Embedding | BAAI/bge-small-zh-v1.5 |
| Reranker | BAAI/bge-reranker-base |
| 联网搜索 | Tavily Search API |
| 会话持久化 | LangGraph SqliteSaver、SQLite |
| 长期记忆 | SQLite |
| 任务状态 | SQLite |
| PDF解析 | PyPDFLoader |
| DOCX解析 | python-docx |
| PPTX解析 | python-pptx |
| Markdown与TXT解析 | Python文本读取 |
| 文本切分 | RecursiveCharacterTextSplitter |

## 项目结构

```text
omniknow-agent/
├── app/
│   ├── agent/
│   │   └── knowledge_agent.py
│   ├── api/
│   │   └── main.py
│   ├── memory/
│   │   ├── long_term_memory.py
│   │   └── session_store.py
│   ├── rag/
│   │   ├── ingest.py
│   │   ├── qa.py
│   │   ├── reranker.py
│   │   └── retriever.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── document_processor.py
│   │   └── document_task_store.py
│   └── tools/
│       └── web_search.py
├── assets/
│   ├── 3efb6fac-d827-4758-9e4e-b56a92e98d6c.png
│   └── two-stage-retrieval.png
├── data/
│   ├── chroma/
│   ├── memory/
│   ├── tasks/
│   └── uploads/
├── models/
│   ├── bge-small-zh-v1.5/
│   └── bge-reranker-base/
├── frontend.py
├── start.sh
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

模型文件、上传文档、向量数据库、会话数据库、长期记忆数据库、任务数据库和日志不会提交到 GitHub，需要在本地运行时自动创建或单独下载。

## 环境要求

推荐使用以下环境：

- Python 3.11
- Conda
- CUDA GPU，可选
- DeepSeek 或兼容 OpenAI 接口的大模型服务
- Tavily API Key

Embedding 模型可以在 CPU 上运行。Reranker 同样支持 CPU，但推荐使用 CUDA GPU 以降低重排序延迟。

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/chenqianqian-k/omniknow-agent.git
cd omniknow-agent
```

### 2. 创建Conda环境

```bash
conda create -n knowledge-agent python=3.11 -y
conda activate knowledge-agent
```

### 3. 安装PyTorch

请根据本机 CUDA 环境安装对应版本的 PyTorch。

安装完成后检查：

```bash
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available())"
```

### 4. 安装项目依赖

```bash
pip install -r requirements.txt
```

## 下载本地模型

模型权重不保存在 GitHub 仓库中，需要下载到项目的 `models` 目录。

### 下载Embedding模型

```bash
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-small-zh-v1.5', local_dir='models/bge-small-zh-v1.5')"
```

### 下载Reranker模型

```bash
python -c "from modelscope import snapshot_download; snapshot_download('BAAI/bge-reranker-base', local_dir='models/bge-reranker-base')"
```

下载完成后的目录结构：

```text
models/
├── bge-small-zh-v1.5/
└── bge-reranker-base/
```

## 配置环境变量

复制环境变量示例文件：

```bash
cp .env.example .env
```

然后填写 `.env`：

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://your-api-provider.example.com/v1
DEEPSEEK_MODEL=your_model_name

TAVILY_API_KEY=your_tavily_api_key

RERANKER_DEVICE=cuda:0
```

如果不使用 GPU，可以设置：

```env
RERANKER_DEVICE=cpu
```

`.env` 中包含真实密钥，禁止将其上传到 GitHub。

## 启动项目

为启动脚本添加执行权限：

```bash
chmod +x start.sh
```

一键启动前后端：

```bash
bash start.sh
```

启动完成后访问：

- Streamlit 前端：`http://localhost:6008`
- FastAPI 接口文档：`http://localhost:6006/docs`
- 后端健康检查：`http://localhost:6006/health`

按下 `Ctrl+C` 可以同时停止后端与前端服务。

## 手动启动

如果不使用启动脚本，可以分别启动后端和前端。

### 启动FastAPI

```bash
uvicorn app.api.main:app \
    --host 0.0.0.0 \
    --port 6006
```

### 启动Streamlit

```bash
streamlit run frontend.py \
    --server.address 0.0.0.0 \
    --server.port 6008
```

在远程服务器中运行时，需要同时配置对应的端口映射。

## API接口

| 请求方法 | 接口路径 | 功能 |
|---|---|---|
| `GET` | `/` | 获取服务基本信息 |
| `GET` | `/health` | 检查后端服务状态 |
| `POST` | `/chat` | 普通非流式 Agent 对话 |
| `POST` | `/chat/stream` | NDJSON 流式 Agent 对话 |
| `POST` | `/documents/upload` | 同步上传并写入文档 |
| `POST` | `/documents/upload-async` | 创建异步文档入库任务 |
| `GET` | `/document-tasks/{task_id}` | 查询文档任务状态 |
| `GET` | `/documents` | 查询已入库文档 |
| `DELETE` | `/documents` | 删除知识库文档 |
| `GET` | `/sessions` | 查询历史会话 |
| `GET` | `/sessions/{thread_id}` | 获取指定会话消息 |
| `GET` | `/memories` | 查询用户长期记忆 |
| `DELETE` | `/memories/{memory_key}` | 删除指定长期记忆 |

完整接口参数可以在后端服务启动后通过 Swagger UI 查看：

```text
http://localhost:6006/docs
```

## 使用示例

### 查询文档内容

```text
产品手册中的保修期限是多久？
```

Agent 将调用：

```text
knowledge_search
```

### 查看知识库文档

```text
知识库里有哪些文件？
```

Agent 将调用：

```text
knowledge_document_list
```

### 总结完整文档

支持总结 PDF、DOCX、PPTX、Markdown 和 TXT 文档。

例如：

```text
请总结product_manual.pdf的主要内容。
```

Agent 将调用：

```text
document_summary
```

### 搜索实时信息

```text
请搜索最近的LangChain开源项目，并提供来源链接。
```

Agent 将调用：

```text
web_search
```

### 保存长期记忆

```text
请记住，我偏好简洁的回答。
```

Agent 将调用：

```text
save_user_memory
```

### 跨会话读取记忆

新建对话后输入：

```text
我保存了哪些回答偏好？
```

Agent 将调用：

```text
get_user_memories
```

## 当前限制

- 当前主要支持单用户使用
- 长期记忆使用固定的 `default-user`
- 当前支持 PDF、DOCX、PPTX、Markdown 和 TXT 文档
- 暂不支持旧版 `.doc` 和 `.ppt` 格式
- 长文档总结受到最大文本块数量限制
- DeepSeek 与 Tavily 功能依赖外部 API
- 本地 Embedding 和 Reranker 模型需要单独下载
- 当前不包含用户登录、权限认证和访问控制
- 文档解析暂未针对扫描版 PDF 和图片内容集成 OCR
- DOCX 和 PPTX 当前主要提取文本内容，不解析图片中的文字
- FastAPI `BackgroundTasks` 适用于当前单机部署，服务中断后不会自动恢复正在执行的文档任务

## 后续计划

- 支持 Excel、HTML 等更多文档格式
- 为扫描版 PDF 和文档图片增加 OCR 解析
- 增加多用户身份认证与数据隔离
- 增加检索结果置信度控制
- 增加知识库检索与工具路由评估
- 使用 Docker 完成项目环境封装

## 项目定位

本项目主要用于学习和实践以下技术：

- RAG知识库问答流程
- LangChain Agent构建与多工具调用
- LangGraph Checkpointer会话状态持久化
- 两阶段文本检索
- Agent流式输出与NDJSON传输
- 后台文档任务与状态管理
- 长短期记忆管理
- FastAPI服务开发
- 大模型应用工程化部署

## License

本项目用于个人学习、技术实践与项目展示。
