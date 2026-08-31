# MCP 长期记忆系统

一个可运行的长期记忆 MVP：AI 客户端通过 MCP 工具写入、检索和删除记忆；Vue3 管理端通过 REST API 查看、筛选、编辑和删除记忆。

## 架构

```text
AI Client -- MCP stdio --+
                        +-- MemoryService -- Embedding -- Milvus
Vue3 ------ REST API ---+                +-- MySQL
```

- MySQL 是正文、标签和生命周期状态的事实源。
- Milvus 保存向量及用户隔离字段，可由 MySQL 数据重建。
- `user_id` 是所有检索和修改操作的强制隔离条件。
- 默认嵌入模型为 `BAAI/bge-small-zh-v1.5`，输出 512 维向量。

## 目录

```text
app/
  api/             FastAPI 路由
  db/              SQLAlchemy 模型与 MySQL 会话
  embeddings/      真实/测试嵌入提供器
  schemas/         MCP、REST 与业务契约
  services/        记忆生命周期服务
  vector/          Milvus 向量仓库
  main.py          REST 服务入口
  mcp_server.py    MCP stdio 服务入口
frontend/          Vue3 管理端
docs/              PRD 与实施计划
scripts/           冒烟验证
tests/             自动化测试
```

## 1. 启动基础设施

启动 MySQL：

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker"
docker compose up -d
```

启动 Milvus：

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker\milvus"
docker compose up -d
docker compose ps
```

Milvus 的 `etcd`、`minio`、`standalone` 三个服务均应显示 `healthy`。

## 2. 后端环境（uv 管理）

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker\memory-system"
Copy-Item .env.example .env
uv sync
```

`uv sync` 会根据 `pyproject.toml` 和 `uv.lock` 创建项目专用的 `.venv`，并安装运行依赖与开发依赖。一般不需要手动激活虚拟环境；本项目不再维护单独的 requirements 文件。

复制配置后，请把 `.env` 中的 `MYSQL_PASSWORD=change_me` 改成你本机 MySQL 用户的真实密码。`.env` 已被 Git 忽略，不能提交到公开仓库。

常用依赖管理命令：

```powershell
# 新增运行依赖
uv add 包名

# 新增开发/测试依赖
uv add --dev 包名

# 删除依赖
uv remove 包名

# 按锁文件同步环境
uv sync --frozen
```

默认本地连接：

| 服务 | 地址/配置 |
| --- | --- |
| MySQL | `127.0.0.1:3308/memory_system` |
| Milvus | `http://127.0.0.1:19530` |
| REST API | `http://127.0.0.1:8000` |
| Vue3 | `http://127.0.0.1:5173` |

首次真实写入会下载并缓存 BGE 中文模型。模型缓存完成后，可将 `.env` 中的 `EMBEDDING_LOCAL_FILES_ONLY` 改为 `true`，避免后续启动联网检查。如果访问 Hugging Face 困难，可以在启动进程前设置可用的模型镜像或提前把模型下载到本机缓存。

## 3. 运行 REST API

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

打开：

- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

## 4. 运行 Vue3 管理端

新开一个 PowerShell：

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker\memory-system\frontend"
npm install --cache .npm-cache
npm run dev
```

打开 <http://127.0.0.1:5173>，默认用户为 `demo-user`。

## 5. 运行 MCP Server

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker\memory-system"
uv run python -m app.mcp_server
```

MCP 使用 stdio 传输。客户端配置示例：

```json
{
  "mcpServers": {
    "long-term-memory": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "【项目绝对路径】"
    }
  }
}
```

暴露的必需工具：

- `write_memory(content, user_id, conversation_id?, project_path?, tags?, metadata?)`
- `search_memory(query, user_id, top_k?, conversation_id?, project_path?, include_global?, tags?, start_time?, end_time?)`
- `delete_memory(memory_id, user_id)`

扩展工具：

- `get_memory(memory_id, user_id)`
- `list_memories(user_id, project_path?, include_global?, conversation_id?, tags?)`
- `update_memory(memory_id, user_id, content?, tags?, metadata?, project_path?, make_global?)`

### 全局记忆与项目记忆

- `project_path` 留空：写入全局记忆；检索时只查询全局记忆。
- `project_path` 填绝对路径：写入项目记忆；检索时默认返回“该项目 + 全局记忆”。
- 项目检索传 `include_global=false`：只返回该项目的记忆。
- Windows 路径会自动规范化，例如 `D:\\Work\\Demo` 保存为 `d:/work/demo`。

### Elasticsearch 倒排索引

项目内已提供 Elasticsearch 9.5.1 单节点开发 Compose：

```powershell
cd "D:\新建文件夹\OneDrive\文档\ChatGPT\docker\memory-system"
docker compose -f docker-compose.elasticsearch.yml up -d
docker compose -f docker-compose.elasticsearch.yml ps
```

确认 `http://127.0.0.1:9200` 可访问后，在 `memory-system/.env` 中启用：

```dotenv
ELASTICSEARCH_ENABLED=true
ELASTICSEARCH_URL=http://127.0.0.1:9200
ELASTICSEARCH_INDEX=memory_documents
```

重启后端，并把既有 MySQL 记忆补建倒排索引：

```powershell
uv run python -m scripts.reindex_elasticsearch
```

`search_memory` 的 `search_mode` 支持：

- `semantic`：Milvus 向量搜索，默认模式。
- `keyword`：Elasticsearch 关键词搜索。
- `hybrid`：合并 Milvus 与 Elasticsearch 结果并使用 RRF 排序。

## 6. 测试与验证

不访问生产数据的自动化测试：

```powershell
uv run pytest -q
```

使用真实 MySQL/Milvus 的轻量生命周期冒烟：

```powershell
uv run python -m scripts.smoke_backend
```

使用真实 BGE 模型、MySQL 和 Milvus 的端到端语义冒烟：

```powershell
uv run python -m scripts.smoke_semantic
```

前端正式构建：

```powershell
cd frontend
npm run build
```

## 一致性策略

- 写入：MySQL 先记录 `syncing`，向量写入成功后改为 `active/ready`；失败记录为 `failed`。
- 搜索：Milvus 召回 ID，MySQL 再检查 `user_id` 和 `active` 状态并补齐正文。
- 更新：正文变化时重新生成并覆盖向量；仅标签变化不重复计算向量。
- 删除：先删除 Milvus 向量，再将 MySQL 记录软删除，保证列表和搜索不可见。

## 当前范围

这是本地 MVP。生产部署还应增加身份认证、密钥管理、限流、审计、后台补偿任务、备份以及 HTTPS。
