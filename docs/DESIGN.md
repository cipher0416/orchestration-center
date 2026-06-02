# OpenAN Orchestration Center 设计文档

*最后更新: 2026-06-02 (第二轮修复)*

## 1. 系统架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    workflow-designer                      │
│                React 18 + Vite + Tailwind                  │
│                    Port 3003 (开发)                        │
└──────────────────────┬──────────────────────────────────┘
                       │ REST / SSE
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI Backend (port 60000)              │
│                                                          │
│  ┌─────────────────────┐  ┌─────────────────────────┐   │
│  │  Internal API        │  │  External API            │   │
│  │  /rest/v1/orchestrate│  │  /api/v1/*               │   │
│  └─────────┬───────────┘  └───────────┬─────────────┘   │
│            │                          │                  │
│  ┌─────────▼──────────────────────────▼─────────────┐   │
│  │              Core Domain Layer                     │   │
│  │  PSOP Generator ← IntentPSOP Generator             │   │
│  │  WorkflowRetrieval (semantic search via LLM)       │   │
│  │  PsopPublisher (version management)                │   │
│  └─────────┬─────────────────────────────────────────┘   │
│            │                                              │
│  ┌─────────▼─────────────────────────────────────────┐   │
│  │          DynamicWorkflowEngine                     │   │
│  │  DAG step traversal · parallel A2A calls           │   │
│  │  async LLM routing · SSE push · A2A-T negotiation  │   │
│  └─────────┬─────────────────────────────────────────┘   │
│            │                                              │
│  ┌─────────▼─────────────────────────────────────────┐   │
│  │           Pluggable Storage Layer                   │   │
│  │  HandlerRegistry → file JSON / PostgreSQL           │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐  ┌──────────┐  ┌───────────┐
   │Agent A  │  │ Agent B  │  │ Agent C..  │
   │uvicorn  │  │ uvicorn  │  │ uvicorn    │
   └─────────┘  └──────────┘  └───────────┘
         A2A Protocol (gRPC/HTTP) + A2A-T Negotiation
```

**数据流方向**: 用户意图/PreFlow → PSOP生成 → 存储 → 执行引擎 → A2A Agent并行调用 → SSE事件推送 → 执行记录存储

---

## 2. 领域模型设计

### 2.1 核心模型关系

```
PreFlow (人工SOP模板)
  │  id, name, steps_md (markdown)
  │  related_preflow ──────────────┐
  ▼                                │
PSOP (可执行工作流) ◄───────────────┘
  │  id, name, steps[Step]
  │
  │  Step { name, type: ALL_SUCCESS|ANY_SUCCESS,
  │         layer: int, context_from: ["*"|step_name],
  │         subtasks[Task], next[JumpCondition] }
  │
  │  Task { task_id, description, agent, skill, status }
  │  JumpCondition { step, condition }
  │
  ▼
ExecutionRecord (执行记录)
  execution_id, psop_id, status, execution_history, events, final_psop
```

### 2.2 分层上下文传播机制

- **Layer 0**: 执行层（叶子Agent），无上下文依赖
- **Layer >= 1**: 聚合层，通过 `context_from` 指定依赖的前驱步骤
- `context_from: ["*"]` 表示接收所有前驱的输出做综合分析
- 引擎在 `_build_context_for_step` 中递归收集前驱输出，粗估截断至 ~6000 tokens

### 2.3 模型层设计评价

| 方面 | 评价 | 状态 |
|------|------|------|
| `PreFlow` / `PSOP` / `ExecutionRecord` 使用 Pydantic | ✅ 类型安全，自动校验 | — |
| `Task.agent` / `Task.skill` 是裸字符串 | ⚠️ 无外键约束，可能引用不存在的Agent/Skill | 待优化 |
| `JumpCondition.condition` 是自由字符串 | ⚠️ 缺乏结构化条件模型，LLM容易产生幻觉 | 待优化 |
| ~~`ExecutionRecord.started_at` 使用 `datetime.now` (无时区)~~ | ✅ 已修复：改用 `datetime.now(timezone.utc)` | **已修复** |
| ~~`ExecutionRecord.status` 是 `str` 而非 `Enum`~~ | ✅ 已修复：新增 `ExecutionStatus` Enum | **已修复** |
| ~~`WorkflowSearchResult` 是普通类（非 Pydantic）~~ | ✅ 已修复：改为 Pydantic `BaseModel` | **已修复** |
| `PublishedWorkflow` 也是普通类 | 🔴 同上 | 待优化 |
| `sse_executor` 中 `started_at` / `completed_at` | ✅ 已修复：统一使用 UTC | **已修复** |
| `events` / `execution_history` 无大小限制 | ⚠️ 长流程可能内存膨胀 | 待优化 |

---

## 3. 执行引擎设计

### 3.1 `DynamicWorkflowEngine` 控制流

```
run()
 ├─ 找到初始步骤 (layer=0, 无前驱)
 ├─ while pending:
 │   ├─ pop 步骤索引
 │   ├─ 检查所有前驱是否完成 → 未完成则 defer（死锁保护：超 N 次跳过）
 │   ├─ _execute_subtasks(step) ──→ asyncio.gather / asyncio.as_completed 并行调用
 │   │    ├─ ANY_SUCCESS: 首个成功即返回 (asyncio.as_completed)
 │   │    └─ ALL_SUCCESS: 并行执行，任一失败则标记失败 (asyncio.gather)
 │   ├─ 存储输出到 step_outputs
 │   ├─ _determine_next_steps (async) ──→ 返回所有候选步骤（不过滤前驱，交由主循环 defer）
 │   │    ├─ 无条件路由: 返回所有非哨兵步骤
 │   │    └─ 条件路由: _llm_route_decision ──→ asyncio.to_thread 异步LLM调用
 │   └─ 将下一步插入 pending 队列前部 (DFS)
 └─ finally: 关闭 httpx 客户端
```

### 3.2 执行引擎设计问题

| 问题 | 严重度 | 说明 | 状态 |
|------|--------|------|------|
| **同步 LLM 调用阻塞事件循环** | 🔴 致命 | `_llm_route_decision` 改为 `async`，通过 `asyncio.to_thread` 执行同步 LLM 调用 | **已修复** |
| **Subtask 串行执行** | 🔴 严重 | 改用 `asyncio.gather`（ALL_SUCCESS）和 `asyncio.as_completed`（ANY_SUCCESS）并行执行 | **已修复** |
| **条件路由未就绪步骤被静默丢弃** | 🔴 严重 | 移除 `_determine_next_steps` 中的前驱过滤，所有候选步骤交由主循环 defer 逻辑处理 | **已修复** |
| **流式响应文本可能丢失** | 🔴 严重 | `response_text` 初始化为 `None`，使用 `(response_text or "") + part.text` 安全追加 | **已修复** |
| **死锁检测是启发式的** | ⚠️ 中 | `dc > len(steps)` 可能误杀合法步骤或循环 N×M 次才放弃 | 待优化 |
| **A2A Client 每次调用都重新创建** | ⚠️ 中 | `ClientFactory(config).create(agent_card)` 每次新建，无缓存 | 待优化 |
| ~~Agent 查找是 O(n) 线性扫描~~ | ⚠️ 低 | ✅ 已修复：init 时构建 `_agent_map = {name: card}` | **已修复** |
| ~~`_find_step_index` 每次 O(n)~~ | ⚠️ 低 | ✅ 已修复：init 时构建 `_step_index = {name: idx}` | **已修复** |
| **无超时/取消机制** | ⚠️ 中 | 某 Agent 挂起则整个 workflow 永久阻塞 | 待优化 |
| ~~`samples.*` 导入到生产代码~~ | ⚠️ 中 | ✅ 已修复：改为 lazy import (ImportError fallback) | **已修复** |
| **sse_executor 执行历史失败时为空** | ⚠️ 中 | 改为从 `engine.execution_history` 捕获 partial history | **已修复** |

---

## 4. 存储层设计

### 4.1 双模存储架构

```
                   HandlerRegistry
                   ┌─────────────┐
                   │ _registry   │ (class dict)
                   │ get_handler │──── 根据 InterfaceType + persistence_mode 分发
                   └──────┬──────┘
          ┌───────────────┼───────────────┐
     file mode       postgresql mode
  ┌──────┴──────┐  ┌───────┴──────────┐
  │BaseHandler  │  │Custom*Handler    │
  │ 子类8个     │  │ 子类8个          │
  │→WorkflowStorage│→psop_processor   │
  │  (文件JSON) │  │  execution_rec.. │
  └─────────────┘  └──────────────────┘

非 file 模式且未注册 handler → 抛出 ValueError（不再静默降级）
```

### 4.2 每次操作的存储模式

| 操作 | File 模式 | PostgreSQL 模式 |
|------|-----------|----------------|
| 列出/获取 PSOP | `WorkflowStorage` 直接 | `HandlerRegistry` → DB handler |
| 保存/删除 PSOP | `HandlerRegistry` → file handler | `HandlerRegistry` → DB handler |
| 执行记录 CRUD | `HandlerRegistry` | `HandlerRegistry` |
| PreFlow | `WorkflowStorage` 直接 (仅file) | 同（无 DB handler） |

### 4.3 存储层设计问题

| 问题 | 严重度 | 说明 | 状态 |
|------|--------|------|------|
| ~~DB模式未注册handler时静默降级为文件~~ | 🔴 严重 | 改为抛出 `ValueError`，明确要求注册 handler | **已修复** |
| ~~`db_connection.py` 在 import 时就加载配置和建库~~ | 🔴 严重 | 改为 lazy init：`_ensure_conn_info()` 延迟到首次调用 | **已修复** |
| ~~`custom_handle.py` 中 `**kwargs` 被静默丢弃~~ | ⚠️ 中 | 所有子类 handler 改为透传 `**kwargs` | **已修复** |
| **无连接池** | ⚠️ 中 | 每次数据库操作 `create_connection() + close()`，高并发不可用 | 待优化 |
| ~~DB handler 不验证受影响行数~~ | ⚠️ 中 | ✅ 已修复：DELETE 改用 `cursor.rowcount` 验证 | **已修复** |
| **`WorkflowStorage.update_psop` 存在 check-then-write 竞态** | ⚠️ 中 | 检查文件是否存在和写入之间可能被其他进程删除 | 待优化 |
| **`list_psops` 读取每个文件内容** | ⚠️ 低 | O(n) 磁盘 I/O，无缓存 | 待优化 |
| **DB 表无外键约束** | ⚠️ 中 | `execution_records.psop_id` 无 FK，可能孤立 | 待优化 |
| **JSON 反序列化错误被静默吞掉** | ⚠️ 中 | `get_psop_by_id` 中 `json.loads` 异常裸奔，`load_psop` 全部 catch 返回 None | 待优化 |

---

## 5. API 层设计

### 5.1 端点总览（22个）

**内部 API** (`/rest/v1/orchestrate`):
- Workflow CRUD: `GET/POST /workflows`, `GET/DELETE /workflows/{id}`
- 生成: `POST /parse-pdf`, `/generate-from-preflow`, `/generate-from-intent`
- 检索: `POST /retrieve-by-intent`, `/retrieve-topn-by-intent`
- Agent卡: `GET /agent-cards`
- 模板: `GET /templates`, `POST /templates/{id}/import`
- 执行: `GET /execute` (+ semaphore + RateLimiter), `/execution-records`, `/execution-records/{id}`
- 记录删除: `DELETE /execution-records/{id}`

**外部 API** (`/api/v1`):
- `POST /orchestrate/sop`, `/orchestrate/intent`, `/orchestrate/search`
- `POST /orchestrate/execute` (自动编排+执行 SSE)
- `GET /orchestrate/execute/{id}` (按 ID 执行 SSE)
- `GET /executions/{id}`

**Legacy 路由** (`/psops`, `/agent-cards`) — 已添加 RateLimiter 保护

### 5.2 中间件栈

| 中间件 | 作用 | 问题 | 状态 |
|--------|------|------|------|
| CORS | `allow_origins=["*"]` | 开发环境可接受，生产需限制 | — |
| ConnectionLimitMiddleware | 限制并发连接数 (默认 200) | ~~吞噬异常~~ → ✅ 已修复：HTTPException 透传 | **已修复** |
| TimeoutMiddleware | 请求总超时 (默认 300s) | `asyncio.wait_for` 取消协程可能导致资源泄漏 | 待优化 |
| logging_middleware | 请求/响应日志 + UUID | 无问题 | — |
| security_middleware | URL长度 + Body大小检查 | ~~消费 `request.stream()`~~ → ✅ 改为 Content-Length header 检查 | **已修复** |
| RateLimiter (per-endpoint) | 基于 IP 的速率限制 (默认 50/s) | 内存存储（多进程不共享），不处理反向代理 IP | 待优化 |

### 5.3 API 层设计问题

| 问题 | 严重度 | 说明 | 状态 |
|------|--------|------|------|
| ~~`security_middleware` 破坏所有 POST 路由~~ | 🔴 致命 | 改为 Content-Length header 检查，不再消费 `request.stream()` | **已修复** |
| ~~内部 execute 端点无 semaphore 无 rate limit~~ | 🔴 严重 | 添加 `execute_semaphore` + `RateLimiter("start_process_stream")` | **已修复** |
| ~~Legacy 路由完全未受保护~~ | 🔴 严重 | 添加 RateLimiter 依赖注入 | **已修复** |
| ~~`ConnectionLimitMiddleware` 吞噬异常~~ | ⚠️ 中 | HTTPException 先行透传，其余记录堆栈并返回 500 | **已修复** |
| ~~`get_agent_cards()` 同步阻塞事件循环~~ | 🔴 严重 | 改为 `async` 函数，通过 `asyncio.to_thread` 执行同步 HTTP 调用 | **已修复** |
| **执行记录的 internal 端点无 rate limit** | ⚠️ 中 | `/execution-records` 系列端点未保护 | 待优化 |
| **`orchestrate_sop` 输入歧义** | ⚠️ 中 | 既接受 JSON body 又接受文件上传，按 content-type 区分，脆弱 | 待优化 |
| **External API `execute_workflow` 强制先搜索后执行** | ⚠️ 低 | 用户无法跳过搜索直接执行新意图 | 待优化 |
| ~~`list_agent_cards` 端点仍使用同步 registry 调用~~ | ⚠️ 低 | ✅ 已修复：改为 `await get_agent_cards()` | **已修复** |

---

## 6. 前端设计

### 6.1 架构

- React 18 + Vite + Tailwind CSS + React Flow (xyflow)
- i18next 国际化（zh/en）
- Axios HTTP 客户端，120s 超时
- 三标签页：Agent 注册中心 / 编排中心 / 执行中心
- **三标签始终挂载**，用 CSS 隐藏/显示切换

### 6.2 前端设计问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| **Backend URL 硬编码** `http://127.0.0.1:60000` | ⚠️ 低 | 无环境变量覆盖 |
| **语言初始化双重来源** | ⚠️ 低 | `i18n.js` 用 LanguageDetector，`App.jsx` 单独操作 localStorage，可能冲突 |
| **API 响应 `data` 层级不一致** | ⚠️ 中 | 部分函数 unwrap `.data`，部分不 unwrap，返回结构不统一 |
| **`getStartProcessStreamUrl` 不转义参数** | ⚠️ 低 | `psopId` 含特殊字符会出问题 |
| **三组件始终挂载** | ⚠️ 低 | 内存占用大，但 Tab 切换快 |
| **默认主题是 Dark** | ⚠️ 低 | 可能不符合企业内部系统习惯 |
| **默认语言是 zh** | ⚠️ 低 | 国际化产品通常默认 en |

---

## 7. 配置系统

### 7.1 设计

```
etc/conf/server.conf    (基础配置, key=value 行)
etc/conf/server.properties (覆盖配置, 更高优先级)
etc/conf/db_config.json     (PostgreSQL 连接)
etc/conf/llm_config.json    (LLM 提供商配置)
```

- `get_conf()` 每次读取两个文件合并，**无缓存**
- 所有 key 自动小写化
- 无类型转换（全部是字符串）
- `#` 注释支持 naive（值内部的 `#` 会被截断）

### 7.2 配置系统问题

| 问题 | 严重度 | 状态 |
|------|--------|------|
| ~~`get_conf()` 每次重读磁盘，无缓存~~ | ⚠️ 低 | **已修复**：添加 `@lru_cache(maxsize=1)` |
| `get_root_path` 依赖文件在 `<root>/common/util/config_util.py` 的假设 | ⚠️ 低 | 待优化 |
| `server.conf` 缺失时静默继续（空配置） | ⚠️ 中 | 待优化 |
| ~~`db_config.json` 在 import 时即加载校验~~ | 🔴 严重 | **已修复**：改为 lazy init（`_ensure_conn_info()` 首次调用时加载） |

---

## 8. 整体架构风险总结

### 8.1 致命/严重问题修复记录

| # | 问题 | 位置 | 修复方案 | 状态 |
|---|------|------|----------|------|
| 1 | `security_middleware` 消费 `request.stream()` | `frontend_support_server.py` | 改用 Content-Length header 检查 | ✅ **已修复** |
| 2 | `_llm_route_decision` 同步阻塞事件循环 | `exec_engine.py` | `async def` + `asyncio.to_thread` | ✅ **已修复** |
| 3 | Subtask 串行执行 | `exec_engine.py` | `asyncio.gather` / `asyncio.as_completed` | ✅ **已修复** |
| 4 | 流式响应文本多 chunk 时数据丢失 | `exec_engine.py` | `(response_text or "") +` 安全累加 | ✅ **已修复** |
| 5 | 条件路由未就绪步骤静默丢弃 | `exec_engine.py` | 移除前驱过滤，交由主循环 defer | ✅ **已修复** |
| 6 | 内部 execute 端点无保护 | `frontend_support_server.py` | 添加 semaphore + RateLimiter | ✅ **已修复** |
| 7 | `get_agent_cards()` 在 event loop 中同步阻塞 | `response_utils.py` | 改为 `async`，`asyncio.to_thread` 包装 | ✅ **已修复** |
| 8 | `db_connection.py` import 时强制加载 DB 配置 | `db_connection.py` | Lazy init `_ensure_conn_info()` | ✅ **已修复** |
| 9 | DB 模式未注册 handler 静默降级为文件 | `default_handle.py` | 抛出 `ValueError` | ✅ **已修复** |
| 10 | `ConnectionLimitMiddleware` 吞噬异常 | `middleware.py` | HTTPException 透传 | ✅ **已修复** |
| 11 | Legacy 路由无保护 | `frontend_support_server.py` | 添加 RateLimiter | ✅ **已修复** |
| 12 | `custom_handle.py` `**kwargs` 丢弃 | `custom_handle.py` | 透传 `**kwargs` | ✅ **已修复** |
| 13 | 执行失败时 `execution_history` 为空 | `sse_executor.py` | 从 `engine.execution_history` 捕获 | ✅ **已修复** |
| 14 | `ExecutionRecord.started_at` 无时区 | `execution_record.py` | 改为 UTC 时区 | ✅ **已修复** |

### 8.2 架构层面不合理的核心设计

| # | 问题 | 状态 |
|---|------|------|
| 1 | **缺少异步调用抽象层**：引擎混合同步/异步调用 | ✅ **已修复**：`_llm_route_decision` 改为 async，`get_agent_cards()` 改为 async |
| 2 | **handler 注册缺乏强制性**：未注册时静默降级 | ✅ **已修复**：非 file 模式未注册抛出 `ValueError` |
| 3 | **存储层有两个入口**：部分直调 WorkflowStorage，部分经 HandlerRegistry | ⚠️ 待优化：DB 模式下 PreFlow 无 handler |
| 4 | **samples 模块耦合进生产代码** | ⚠️ 待优化：A2A-T 配置应提升到 `common/` |
| 5 | **API 层 semaphore 重复代码** | ⚠️ 待优化：应抽取为装饰器或 FastAPI 依赖 |
| 6 | ~~无真正的并行执行~~：subtask 串行，step 间 DFS | ✅ **已修复**：subtask 改为 asyncio.gather 并行 |
| 7 | ~~时间戳模型不一致~~：`started_at` 无时区 | ✅ **已修复**：统一 UTC 时区 |

### 8.3 仍待处理的问题

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| 1 | `PublishedWorkflow` 非 Pydantic | 🔴 | `core/publish.py` |
| 2 | `list_agent_cards` 端点未使用 async `get_agent_cards()` | ⚠️ | `frontend_support_server.py:535-562` |
| 3 | 死锁检测为启发式（`dc > len(steps)`） | ⚠️ | `exec_engine.py` |
| 4 | A2A Client 每次重建 | ⚠️ | `exec_engine.py` |
| 5 | DB 无连接池 / 无外键约束 | ⚠️ | `database/` |
| 6 | `samples.*` 导入到生产代码 | ⚠️ | ✅ 已修复：a2at_config 提取到 `common/a2at_config.py`，negotiation_utils 用 try/except 懒加载 |

---

## 9. 正面评价（设计优点）

1. **分层上下文传播（`layer` + `context_from`）** 是精巧的多 Agent 协作设计，支持跨层聚合
2. **插件式存储（`HandlerRegistry`）** 设计方向正确，file/DB 切换只需更换 handler
3. **PSOP 的 DAG 模型** 支持条件分支和并发，语义清晰
4. **SSE 流式推送** 实现正确，加上 `execution_history` 和 `events` 可完整回放
5. **Prompt 工程** 精心设计了 few-shot 示例和 JSON schema 约束
6. **原子写入** 模式（`tempfile + os.replace`）防止文件损坏
7. **Subtask 并行执行**（asyncio.gather）充分发挥 PSOP 模型的并行潜力
8. **全链路 async** 消除了事件循环阻塞风险
