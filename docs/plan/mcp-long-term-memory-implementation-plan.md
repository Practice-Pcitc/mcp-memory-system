# Implementation Plan

**PRD Source**: `docs/prd/mcp-long-term-memory-system.md`
**Plan File**: `docs/plan/mcp-long-term-memory-implementation-plan.md`
**Mode**: `full`
**Track**: `fullstack`
**Scope**: `all`
**Skill**: `pg-prd-code-generator`
**Skill Version**: `v1.2`

## Goal

- 交付可运行、可测试的 MCP 长期记忆系统 MVP，覆盖 MySQL、Milvus、MCP、REST API 和 Vue3 管理端。

## In Scope

- 配置管理、MySQL 模型、Milvus Collection、可插拔嵌入服务。
- 记忆写入、搜索、编辑、删除和列表。
- `write_memory`、`search_memory`、`delete_memory` MCP 工具。
- Vue3 管理界面和基础自动化测试。

## Out of Scope

- 生产级登录认证、OAuth、租户计费和分布式任务队列。
- 大规模性能压测、云部署和高可用集群。

## Execution Rules

- 计划项按顺序推进，默认不跳步。
- 每处理一个 item 前，先把状态改为 `doing`。
- 每处理完一个 item，必须立即回写状态、验证结果和改动说明。

## Progress Summary

| ID | Title | Status | Acceptance | Notes |
| --- | --- | --- | --- | --- |
| P1-01 | 需求、配置与项目骨架 | done | 需求、配置示例和依赖清单可追踪 | 骨架验证通过 |
| P1-02 | MySQL、嵌入与 Milvus 适配层 | done | 可初始化表和 Collection，并支持向量 CRUD | 实际基础设施初始化通过 |
| P1-03 | 记忆业务服务 | done | 写入、搜索、编辑、删除、列表形成闭环 | 实际 MySQL/Milvus 冒烟通过 |
| P2-01 | MCP 工具服务 | done | 三个必需工具可发现和调用 | 工具注册验证通过 |
| P2-02 | REST API | done | 前端所需接口和健康检查可用 | OpenAPI 路径验证通过 |
| P3-01 | 后端自动化测试 | done | 核心业务测试通过 | 5 项测试通过 |
| P3-02 | Vue3 管理端 | done | 列表、筛选、搜索、编辑、删除可操作 | Vite 正式构建通过 |
| P4-01 | 集成验证与交付说明 | done | 启动、验证和故障排查文档完整 | 全量回归通过 |

## Phase 1 - 后端基础与核心业务

### Item P1-01 - 需求、配置与项目骨架

- Status: `done`
- Objective: 建立可追踪需求、配置、依赖和 Python 包结构。
- Work: 落盘 PRD/计划，添加环境变量示例、依赖清单和基础包目录。
- Targets: `docs/`, `.env.example`, `pyproject.toml`, `uv.lock`, `app/`, `tests/`
- Acceptance: 新环境可按依赖清单安装，配置字段覆盖 MySQL、Milvus、嵌入和服务端口。
- Dependencies: Python 3.10 与 uv。
- Started At: `2026-08-27 11:00`
- Completed At: `2026-08-27 11:08`
- Changed Files:
  - `docs/prd/mcp-long-term-memory-system.md`: 结构化用户需求。
  - `docs/plan/mcp-long-term-memory-implementation-plan.md`: 权威实施计划。
  - `.env.example`: 本地服务配置示例。
  - `pyproject.toml`: Python 项目元数据、运行依赖与开发依赖。
  - `uv.lock`: uv 可复现依赖锁文件。
  - `app/__init__.py`: 后端包入口。
  - `tests/__init__.py`: 测试包入口。
- Validation:
  - Ran: `uv sync --frozen`、`uv run pytest -q`
  - Result: `pass（5 tests）`
- Notes:
  - Python 依赖已迁移为 uv 管理。

### Item P1-02 - MySQL、嵌入与 Milvus 适配层

- Status: `done`
- Objective: 建立结构化事实源和可重建向量索引。
- Work: SQLAlchemy 模型、连接管理、嵌入提供器、Milvus Collection 与向量 CRUD。
- Targets: `app/db/`, `app/embeddings/`, `app/vector/`
- Acceptance: 初始化无异常；向量层可插入、搜索、更新和删除。
- Dependencies: P1-01、运行中的 MySQL/Milvus。
- Started At: `2026-08-27 11:08`
- Completed At: `2026-08-27 11:18`
- Changed Files:
  - `app/config.py`: 环境变量和连接配置。
  - `app/db/`: SQLAlchemy 模型、引擎和会话。
  - `app/embeddings/`: 真实语义模型与测试嵌入提供器。
  - `app/vector/`: Milvus Collection 和向量 CRUD。
- Validation:
  - Ran: `python -m compileall -q app`
  - Ran: `python -c "init_database(); MilvusVectorStore(...).ensure_collection()"`
  - Result: `pass`
- Notes:
  - 已在实际 MySQL 创建表，并在实际 Milvus 创建 `memory_embeddings` Collection。

### Item P1-03 - 记忆业务服务

- Status: `done`
- Objective: 形成跨 MySQL 与 Milvus 的记忆生命周期闭环。
- Work: 写入、搜索、编辑、软删除、列表与同步状态处理。
- Targets: `app/services/`, `app/schemas/`
- Acceptance: 用户隔离生效，失败时记录同步状态，结果保持向量相关性顺序。
- Dependencies: P1-02。
- Started At: `2026-08-27 11:18`
- Completed At: `2026-08-27 11:30`
- Changed Files:
  - `app/schemas/`: MCP、REST 和业务服务共享契约。
  - `app/services/memory_service.py`: 记忆生命周期和用户隔离。
  - `scripts/smoke_backend.py`: 实际 MySQL/Milvus 冒烟验证。
- Validation:
  - Ran: `python -m compileall -q app scripts`
  - Ran: `python -m scripts.smoke_backend`
  - Result: `pass`
- Notes:
  - 冒烟测试完成真实写入、语义检索、更新、删除以及删除后不可检索验证。

## Phase 2 - 协议与接口

### Item P2-01 - MCP 工具服务

- Status: `done`
- Objective: 向 AI 客户端暴露记忆工具。
- Work: 实现 FastMCP 服务和三个必需工具。
- Targets: `app/mcp_server.py`
- Acceptance: 工具名称和参数符合 PRD，返回结构化结果。
- Dependencies: P1-03。
- Started At: `2026-08-27 11:30`
- Completed At: `2026-08-27 11:36`
- Changed Files:
  - `app/dependencies.py`: 统一构造生产依赖。
  - `app/mcp_server.py`: FastMCP 服务和三个必需工具。
- Validation:
  - Ran: `python -c "...mcp._tool_manager.list_tools()..."`
  - Result: `pass`
- Notes:
  - 已验证工具集合严格为 `write_memory`、`search_memory`、`delete_memory`。

### Item P2-02 - REST API

- Status: `done`
- Objective: 为 Vue3 提供管理接口。
- Work: FastAPI 启动、CORS、健康检查、记忆 CRUD 和语义搜索接口。
- Targets: `app/api/`, `app/main.py`
- Acceptance: OpenAPI 可访问，接口状态码与错误结构清晰。
- Dependencies: P1-03。
- Started At: `2026-08-27 11:36`
- Completed At: `2026-08-27 11:43`
- Changed Files:
  - `app/api/routes.py`: 健康检查与记忆管理接口。
  - `app/main.py`: FastAPI、CORS 和异常处理。
- Validation:
  - Ran: `python -c "...app.openapi()['paths']..."`
  - Result: `pass`
- Notes:
  - 已验证 OpenAPI 包含健康、列表、写入、搜索、详情、更新和删除路径。

## Phase 3 - 质量与界面

### Item P3-01 - 后端自动化测试

- Status: `done`
- Objective: 验证核心业务和用户隔离。
- Work: 使用 SQLite 与假嵌入/向量仓库测试写入、搜索、编辑和删除。
- Targets: `tests/`
- Acceptance: `pytest` 全部通过。
- Dependencies: P2-02。
- Started At: `2026-08-27 11:43`
- Completed At: `2026-08-27 11:55`
- Changed Files:
  - `tests/fakes.py`: 隔离的向量仓库测试替身。
  - `tests/conftest.py`: SQLite 服务夹具。
  - `tests/test_memory_service.py`: 生命周期、失败状态和用户隔离测试。
  - `tests/test_api.py`: REST CRUD 与搜索契约测试。
- Validation:
  - Ran: `python -m pytest -q`
  - Result: `pass (5 passed)`
- Notes:
  - Starlette 输出一条未来迁移提示，不影响当前测试结果。

### Item P3-02 - Vue3 管理端

- Status: `done`
- Objective: 提供记忆可视化管理能力。
- Work: Vite/Vue3 页面、筛选、语义搜索、编辑和删除交互。
- Targets: `frontend/`
- Acceptance: `npm run build` 通过，页面覆盖 PRD 操作。
- Dependencies: P2-02。
- Started At: `2026-08-27 11:55`
- Completed At: `2026-08-27 12:12`
- Changed Files:
  - `frontend/src/App.vue`: 记忆写入、筛选、搜索、编辑和删除页面。
  - `frontend/src/api.js`: REST API 客户端。
  - `frontend/src/styles.css`: 响应式视觉样式。
  - `frontend/package.json`: Vue3/Vite 构建配置。
- Validation:
  - Ran: `npm run build`
  - Result: `pass (Vite 7.3.6)`
- Notes:
  - npm 使用项目内 `.npm-cache`，避免全局缓存目录权限问题。

## Phase 4 - 集成交付

### Item P4-01 - 集成验证与交付说明

- Status: `done`
- Objective: 提供可复现启动和验证路径。
- Work: README、环境配置、初始化、MCP/REST/前端运行和故障排查。
- Targets: `README.md`, `.env.example`
- Acceptance: 新用户可按文档启动并完成一条记忆写入与检索。
- Dependencies: P3-01、P3-02。
- Started At: `2026-08-27 12:12`
- Completed At: `2026-08-27 12:38`
- Changed Files:
  - `README.md`: 基础设施、REST、Vue、MCP、测试和一致性说明。
  - `scripts/smoke_semantic.py`: 真实 BGE/MySQL/Milvus 端到端验证。
  - `app/vector/milvus_store.py`: 写后 flush，保证冒烟中的读后写可见性。
- Validation:
  - Ran: `python -m scripts.smoke_semantic`
  - Ran: `python -m compileall -q app scripts tests`
  - Ran: `python -m pytest -q`
  - Ran: `python -m pip check`
  - Ran: `npm run build`
  - Result: `pass`
- Notes:
  - 真实语义嵌入维度 512，端到端写入、检索和删除通过。
  - 测试有一条 Starlette 关于未来 `httpx2` 迁移的弃用提示，不影响当前结果。

## Change Log

- `2026-08-27 11:00` 初始化 PRD 和实施计划，P1-01 进入 doing。
- `2026-08-27 11:08` P1-01 骨架验证通过并完成；P1-02 进入 doing。
- `2026-08-27 11:18` P1-02 实际 MySQL/Milvus 初始化通过并完成；P1-03 进入 doing。
- `2026-08-27 11:30` P1-03 实际生命周期冒烟通过并完成；P2-01 进入 doing。
- `2026-08-27 11:36` P2-01 工具注册验证通过并完成；P2-02 进入 doing。
- `2026-08-27 11:43` P2-02 OpenAPI 验证通过并完成；P3-01 进入 doing。
- `2026-08-27 11:55` P3-01 后端 5 项测试通过并完成；P3-02 进入 doing。
- `2026-08-27 12:12` P3-02 Vue3 正式构建通过并完成；P4-01 进入 doing。
- `2026-08-27 12:38` P4-01 真实语义端到端和全量回归通过，全部计划项完成。
