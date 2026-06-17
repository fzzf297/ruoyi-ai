# RuoYi 智能操作助手 — 后端技术文档

> 配套主方案见仓库根目录 `README.md`（v4.0）。本文覆盖 **RuoYi Java 后端支撑能力** 与 **Agent 服务（Python / FastAPI / LangGraph）实现层**。
> RuoYi Java 后端是最终鉴权、数据范围、业务规则与操作日志事实源；Agent 服务负责推理编排、工具调用、确认、语音转写与 SSE 事件。
> 技术栈：RuoYi Java / Spring Boot · Python 3.11+ · FastAPI · LangGraph · LangChain · Redis · PostgreSQL · httpx · Pydantic v2。

## 目录

1. [范围与目标](#1-范围与目标)
2. [技术栈与依赖](#2-技术栈与依赖)
3. [整体架构](#3-整体架构)
4. [工程目录结构](#4-工程目录结构)
5. [RuoYi Java 后端支撑](#5-ruoyi-java-后端支撑)
6. [运行期上下文与 Token 注入](#6-运行期上下文与-token-注入)
7. [Agent Runtime（LangGraph）](#7-agent-runtimelanggraph)
8. [核心模块组件](#8-核心模块组件)
   - [8.1 Tool Registry & Manifest](#81-tool-registry--manifest)
   - [8.2 Tool Retrieval](#82-tool-retrieval)
   - [8.3 工具执行网关](#83-工具执行网关)
   - [8.4 Entity Resolver](#84-entity-resolver)
   - [8.5 Confirmation Service](#85-confirmation-service)
   - [8.6 RuoYi Client](#86-ruoyi-client)
   - [8.7 Conversation / Memory](#87-conversation--memory)
   - [8.8 Audit Service](#88-audit-service)
   - [8.9 STT Service](#89-stt-service)
9. [API 与 SSE](#9-api-与-sse)
10. [持久化与数据表](#10-持久化与数据表)
11. [安全模型](#11-安全模型)
12. [并发、幂等与一致性](#12-并发幂等与一致性)
13. [可观测性](#13-可观测性)
14. [评估与测试](#14-评估与测试)
15. [配置项](#15-配置项)
16. [开发任务拆解清单](#16-开发任务拆解清单)

---

## 1. 范围与目标

RuoYi Java 后端负责：

- 提供现有系统管理 REST API，包含用户、登录日志、部门、角色、字典等 MVP 接口
- 使用当前用户 token 完成最终鉴权、数据范围过滤、业务规则校验和操作日志记录
- 允许 Agent 服务在网关/CORS/安全过滤器中以当前用户 token 调用既有 API
- 支撑 Agent 链路追踪、写接口幂等、权限元数据、菜单/OpenAPI/工具刷新

Agent 服务负责：

- 接收前端消息，编排 LLM 推理与多步工具调用（ReAct）
- 从用户可见工具中检索候选工具
- 解析自然语言中的实体（用户/部门/角色/字典/时间/选中项）到系统 ID
- 写操作生成确认任务，确认后重校验并幂等执行
- 接收浏览器语音上传，完成 STT 转写后复用普通消息链路
- 通过 SSE 推送结构化事件
- 记录 Agent 侧审计与链路追踪

Agent **不负责**：最终鉴权、业务规则裁决、直连数据库、Token 签发。RuoYi Java 后端 **不负责**：LLM 推理、语音转写、Agent 会话记忆、确认任务持久化。

## 2. 技术栈与依赖

| 类别 | 选型 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | SSE（`StreamingResponse`/`sse-starlette`）、依赖注入 |
| 编排 | LangGraph | 状态图、interrupt、checkpoint |
| LLM 接入 | LangChain | tool-calling、模型抽象 |
| 校验 | Pydantic v2 | State、Manifest、入参 schema |
| HTTP 客户端 | httpx（async） | 调用 RuoYi REST，连接池、超时 |
| STT 接入 | 可插拔 provider | 语音转文本；原始音频默认不落库 |
| 缓存/锁/checkpoint | Redis | `langgraph.checkpoint` Redis 实现、分布式锁、确认任务、检索缓存 |
| 持久化 | PostgreSQL（asyncpg / SQLAlchemy async） | 会话、确认、审计 |
| 配置 | pydantic-settings | 环境变量 |
| 可观测 | structlog + OpenTelemetry（可选） | 脱敏日志、trace |
| 评估 | pytest + 自研 eval runner | 固定评估集 |

## 3. 整体架构

```mermaid
flowchart LR
    FE[前端面板] -->|REST + SSE| API[FastAPI 层]
    API --> RT[Agent Runtime / LangGraph]
    RT --> TR[Tool Registry]
    RT --> RET[Tool Retrieval]
    RT --> GW[Tool 执行网关]
    GW --> ER[Entity Resolver]
    GW --> CONF[Confirmation Service]
    GW --> RYC[RuoYi Client]
    RYC -->|当前用户 token| RUOYI[(RuoYi 后端)]
    RT --> CONV[Conversation/Memory]
    RT --> AUD[Audit Service]
    RT -.checkpoint.-> REDIS[(Redis)]
    CONF --> REDIS
    CONV --> PG[(PostgreSQL)]
    AUD --> PG
    CONF --> PG
```

分层原则：

- **API 层**：协议适配（REST/SSE）、token 提取、请求级上下文构造，不含业务逻辑。
- **Runtime 层**：LangGraph 图与节点，负责编排。
- **服务层**：Tool/Resolver/Confirmation/RuoYiClient/Audit，各自单一职责。
- **基础设施层**：Redis、PostgreSQL、RuoYi REST。

## 4. 工程目录结构

```text
agent-service/
├─ app/
│  ├─ main.py                      # FastAPI 入口、生命周期、路由注册
│  ├─ api/
│  │  ├─ sessions.py               # /ai/sessions* 路由
│  │  ├─ sse.py                    # SSE 流封装
│  │  ├─ voice.py                  # 语音上传与 STT 转写入口
│  │  └─ deps.py                   # 依赖注入：取 token、构造 RuntimeContext
│  ├─ runtime/
│  │  ├─ graph.py                  # LangGraph 组装（节点 + 边 + interrupt）
│  │  ├─ state.py                  # ConversationState（TypedDict）
│  │  ├─ context.py                # RuntimeContext + contextvar 注入
│  │  └─ nodes/                    # 每个节点一个文件
│  │     ├─ load_state.py
│  │     ├─ refresh_context.py
│  │     ├─ retrieve_tools.py
│  │     ├─ agent_reason.py
│  │     ├─ validate_params.py
│  │     ├─ resolve_entities.py
│  │     ├─ ask_clarification.py
│  │     ├─ prepare_confirm.py
│  │     ├─ execute_tool.py
│  │     ├─ observe_result.py
│  │     ├─ format_output.py
│  │     └─ persist_audit.py
│  ├─ tools/
│  │  ├─ registry.py               # Manifest 加载、启停、权限标签
│  │  ├─ manifest.py               # Manifest Pydantic 模型 + 校验
│  │  ├─ retrieval.py              # Tool Retrieval（关键词/embedding）
│  │  ├─ gateway.py                # 执行网关（9 步）
│  │  ├─ adapters/                 # 复杂工具 Tool Adapter
│  │  └─ manifests/                # YAML Manifest 文件
│  ├─ resolver/
│  │  ├─ base.py                   # Resolver 协议、ResolveResult
│  │  ├─ user.py / dept.py / role.py / dict.py / time_range.py
│  │  └─ registry.py               # 实体类型 → resolver
│  ├─ confirm/
│  │  ├─ service.py                # 生成确认任务、hash、幂等键、重校验
│  │  └─ reconcile.py              # running 超时对账任务
│  ├─ clients/
│  │  └─ ruoyi.py                  # httpx 封装、token 透传、错误归一化
│  ├─ persistence/
│  │  ├─ models.py                 # agent_session/confirmation/audit_event
│  │  ├─ repo.py                   # 仓储
│  │  └─ checkpoint.py             # LangGraph Redis checkpointer 封装
│  ├─ audit/
│  │  └─ service.py                # 审计事件、脱敏
│  ├─ security/
│  │  ├─ redaction.py              # 日志/审计脱敏
│  │  └─ ratelimit.py              # 限流与成本熔断
│  ├─ stt/
│  │  ├─ base.py                   # STT Provider 协议
│  │  └─ service.py                # 音频校验、转写、错误归一化
│  ├─ schemas/
│  │  └─ events.py                 # SSE 事件、错误码、对外 DTO
│  └─ config.py                    # 配置
├─ eval/
│  ├─ suites/                      # 评估集（YAML/JSON）
│  └─ runner.py                    # eval 执行与断言
├─ tests/
├─ pyproject.toml
└─ README.md
```

## 5. RuoYi Java 后端支撑

### 5.1 必须支撑的能力

| 能力 | MVP 要求 | 说明 |
|------|----------|------|
| 当前用户 token 调用 | 必须 | Agent 透传 `Authorization`，RuoYi 按普通用户请求鉴权 |
| 数据范围生效 | 必须 | list/detail/write 前校验均受当前用户数据范围约束 |
| 操作日志标记来源 | 必须 | 写操作日志记录 `source=agent` 或等价字段 |
| 链路 ID 落库 | 必须 | 操作日志保存 `X-Correlation-Id`，便于串联前端/Agent/RuoYi |
| 写接口幂等头 | MVP 写操作必须 | 对新增、修改、启停、删除用户支持 `X-Idempotency-Key` |
| 权限元数据 | 必须 | OpenAPI 或旁路扫描能识别 `required_permissions` |
| 工具刷新 | 建议 P1 提供 | 菜单、权限、接口元数据变更后通知 Agent 刷新缓存 |

### 5.2 请求头与操作日志

Agent 调用 RuoYi API 时统一携带：

| Header | 必填 | 用途 |
|--------|------|------|
| `Authorization: Bearer <token>` | 是 | 当前登录用户 token |
| `X-Agent-Source: ai-assistant` | 是 | 标识请求来自 AI 助手 |
| `X-Correlation-Id` | 是 | 单轮对话链路 ID，贯穿 SSE、Agent 日志、RuoYi 日志 |
| `X-Idempotency-Key` | 写操作必填 | 防重复提交；只读接口不需要 |

RuoYi 侧处理规则：

- 安全过滤器按普通用户 token 解析身份、角色和权限，不给 Agent 特权。
- 操作日志记录 `source`、`correlation_id`、`idempotency_key`、请求路径、操作人、结果码。
- 日志中禁止打印完整 token、Cookie、Authorization 头、密码、密钥等敏感字段。
- 若缺少或非法 token，按现有未登录/过期逻辑返回，Agent 归一化为 `AUTH_EXPIRED`。

### 5.3 幂等与写操作

MVP 写操作包括 `create_user`、`update_user`、`change_user_status`、`delete_users`。RuoYi 需要在这些接口上支持幂等语义：

1. 同一用户、同一接口、同一 `X-Idempotency-Key` 的重复请求返回同一执行结果。
2. 首次请求进入执行前记录幂等键、请求摘要、操作人、接口、状态。
3. 执行成功后保存结果摘要；重复请求直接返回成功摘要，不重复写业务数据。
4. 执行失败按失败类型保存状态；可重试失败允许同幂等键重放，不可重试失败返回原失败结果。
5. 幂等记录 TTL 建议不短于 Agent 确认任务 TTL，MVP 可取 24 小时。

若个别既有接口短期无法做到强幂等：

- 必须在 Agent Manifest 中声明 `idempotent: false` 与 `retry_on_timeout: false`。
- RuoYi 仍需记录 `X-Correlation-Id` 与 `X-Idempotency-Key`，便于人工核对是否已经写入。
- Agent 超时后标记 `failed_retryable`，提示用户核对，不自动重复提交非幂等写。

### 5.4 权限元数据、菜单与工具刷新

Agent 工具必须声明 `required_permissions`，来源优先级：

1. 旁路 YAML 手工声明，MVP 优先。
2. SpringDoc/OpenAPI + 权限注解扫描，作为候选生成。
3. Java 注解 `@AgentTool`，P6 后作为增强，不影响业务逻辑。

RuoYi 侧需要保证：

- 当前用户可见菜单接口稳定可用，Agent 用当前 token 拉取，用于导航和工具可见性过滤。
- 控制器上的 `@SaCheckPermission`、菜单权限字符、OpenAPI operationId 尽量稳定。
- 标准 CRUD 接口有清晰 DTO schema，便于 Agent 生成 `input_schema` 与字段映射。
- 无法识别权限标记的接口默认不能启用为 Agent 工具。
- 导出、导入、下载、清空、重置密码、权限分配、租户/安全配置等高风险接口默认不自动启用。
- 菜单、权限、接口元数据变更后，可通过管理接口、消息事件或手动刷新触发 Agent 清理工具缓存。

字段映射约定：

| Agent 规范字段 | RuoYi DTO 字段 | 示例 |
|----------------|----------------|------|
| `user_id` | `userId` | 修改用户 |
| `dept_id` | `deptId` | 调整部门 |
| `role_ids` | `roleIds` | 设置角色 |
| `status` | `status` | 启停用户 |

Agent 执行前按 Manifest `field_mapping` 转换为 RuoYi DTO；RuoYi 不接收前端展示文案作为写入依据。

## 6. 运行期上下文与 Token 注入

**最关键的安全设计**：token 与实时权限**不进任何 LangGraph State**，避免被 checkpointer 序列化落库。改为请求级注入。

```python
# runtime/context.py
import contextvars
from dataclasses import dataclass

@dataclass
class RuntimeContext:
    session_id: str
    user_id: int
    request_token: str            # memory only, per-request, never persisted / never in State
    user_permissions: list[str]
    user_roles: list[str]
    page_context: dict

_ctx: contextvars.ContextVar[RuntimeContext] = contextvars.ContextVar("agent_runtime_ctx")

def set_runtime(ctx: RuntimeContext): _ctx.set(ctx)
def get_runtime() -> RuntimeContext: return _ctx.get()
```

```python
# api/deps.py
async def build_runtime(request: Request, session_id: str) -> RuntimeContext:
    token = extract_bearer(request)                  # 从 Authorization 头
    if not token: raise AuthExpired()
    perms, roles, user_id = await ruoyi.fetch_permissions(token)  # 实时权限
    page_ctx = await get_page_context(request)
    return RuntimeContext(session_id, user_id, token, perms, roles, page_ctx)
```

- 每个请求（`/messages`、`/confirm`、SSE）都重新构造 `RuntimeContext` 并 `set_runtime`。
- 节点内通过 `get_runtime()` 读取 token / 实时权限，不从 `state` 读。
- `ConversationState` 只存 `permission_snapshot_hash`（见 §7.2、§11）。

## 7. Agent Runtime（LangGraph）

### 7.1 图与节点

```python
# runtime/graph.py（示意）
builder = StateGraph(ConversationState)
for name, fn in NODES.items(): builder.add_node(name, fn)
builder.set_entry_point("load_state")
builder.add_edge("load_state", "refresh_context")
builder.add_edge("refresh_context", "retrieve_tools")
builder.add_edge("retrieve_tools", "agent_reason")
builder.add_conditional_edges("agent_reason", route_after_reason, {
    "direct_answer": "format_output",
    "clarify": "ask_clarification",
    "confirm": "prepare_confirm",
    "call_tool": "validate_params",
})
builder.add_edge("validate_params", "resolve_entities")
builder.add_conditional_edges("resolve_entities", route_after_resolve, {
    "clarify": "ask_clarification",     # ambiguous/not_found/forbidden
    "confirm": "prepare_confirm",       # 写操作
    "execute": "execute_tool",          # 只读
})
builder.add_edge("execute_tool", "observe_result")
builder.add_conditional_edges("observe_result", route_after_observe, {
    "continue": "retrieve_tools",       # 多步：二次检索
    "finish": "format_output",
})
builder.add_edge("format_output", "persist_audit")
builder.add_edge("persist_audit", END)
graph = builder.compile(checkpointer=redis_checkpointer, interrupt_before=["execute_tool_after_confirm"])
```

| 节点 | 职责 | 关键点 |
|------|------|--------|
| load_state | 加载会话状态 | thread_id=session_id |
| refresh_context | 刷新权限/page_context | 从 RuntimeContext 注入，写 snapshot_hash |
| retrieve_tools | 检索候选工具 | 注入精简签名 |
| agent_reason | LLM 推理与工具选择 | tool-calling，限制在候选内 |
| validate_params | 入参 schema 校验 | Pydantic / jsonschema |
| resolve_entities | 实体解析 | 走当前 token |
| ask_clarification | 生成补参/消歧事件 | clarify SSE |
| prepare_confirm | 生成确认任务 + interrupt | 写 confirm_payload_hash |
| execute_tool | 调 RuoYi | 执行前重校验、幂等键 |
| observe_result | 决定继续/结束 | step_count、超时 |
| format_output | 整理输出 | data/text |
| persist_audit | 落审计 | 脱敏 |

### 7.2 ConversationState

```python
class ConversationState(TypedDict):
    session_id: str
    user_id: int
    phase: Literal["idle", "clarifying", "awaiting_confirm", "executing"]
    messages: list[dict]
    summary: str | None
    permission_snapshot_hash: str         # 仅 hash，不含明文权限
    page_context: dict
    available_tool_names: list[str]
    retrieved_tools: list[dict]
    pending_tool_call: str | None
    tool_params: dict
    missing_fields: list[str]
    disambiguation: dict | None
    confirm_id: str | None
    confirm_payload_hash: str | None
    confirm_payload: dict | None
    last_tool_result: dict | None
    step_count: int
    correlation_id: str
```

> **严禁** 在 State 放 `request_token`、明文权限列表、明文敏感字段。

### 7.3 interrupt 与 resume

写操作在 `prepare_confirm` 后 interrupt。`/confirm` 触发 resume：用 `confirm_id` 定位任务 → 校验 `payload_hash` → 从当前请求**重新注入 token 与实时权限** → 执行前重校验（§8.5）→ `execute_tool`。checkpoint 中不含 token，resume 必须靠新请求注入。

### 7.4 步数与超时

单轮最大步数 8；单工具超时 10s（查询可配 20s）；整轮 60s。超限返回已完成信息并提示缩小范围。

## 8. 核心模块组件

### 8.1 Tool Registry & Manifest

- Manifest 用 Pydantic 模型校验；YAML 文件位于 `tools/manifests/`，启动时加载到 Registry。
- 字段：`name/title/description/category/source/enabled/http/required_permissions/risk_level/confirm_required/idempotent/retry_on_timeout/entity_fields/field_mapping/input_schema/output_schema/confirm_template/audit/examples`。
- OpenAPI 生成的 Manifest 默认 `enabled: false`，人工审核后启用。
- 校验规则（同主方案 §9.3）：写接口必须有 risk_level/confirm_required；medium/high 必须有 confirm_template；high 必须二次确认；name 全局唯一；权限非空；entity_fields 类型必须已注册 resolver；`idempotent: false` 必须显式 `retry_on_timeout`（默认 false）；examples ≥2。

### 8.2 Tool Retrieval

- MVP：权限过滤后按关键词/拼音/菜单名/路由/别名轻量排序；≤20 个全放上下文。
- 增长后：embedding 向量检索 + Top-K + 工具包联动 + 多步二次检索。
- **注入精简签名**（name/title/description/必填参数/1-2 examples），完整 schema 仅在 validate 阶段用。
- 接口 `retrieve(query, available_tools) -> list[ToolSignature]` 输入输出稳定，升级不改主链路。

### 8.3 工具执行网关

`gateway.py` 统一 9 步：

1. enabled 检查
2. `required_permissions` 检查（实时权限）
3. input_schema 严格校验
4. Entity Resolver（当前 token）
5. 写操作 → 生成确认任务；只读 → 直接调用
6. 确认后校验 confirm hash、实时权限、实体存在性与可见性、幂等键
7. 调 RuoYi
8. 归一化响应
9. 写审计

**写操作硬时序**：`validate_params -> resolve_entities -> prepare_confirm -> execute_tool`；confirm_template 占位符来自已解析实体 `display`；任一写入字段 `ambiguous/not_found/forbidden` 不进 prepare_confirm；execute 前重校验快照，禁用前端回传展示文案作为执行参数。

### 8.4 Entity Resolver

```python
# resolver/base.py
class ResolveResult(BaseModel):
    status: Literal["resolved", "ambiguous", "not_found", "forbidden"]
    field: str
    value: int | str | None = None
    display: str | None = None
    confidence: float = 0.0
    candidates: list[dict] = []
    source: str | None = None

class Resolver(Protocol):
    entity_type: str
    async def resolve(self, ctx: RuntimeContext, raw: str, hint: dict) -> ResolveResult: ...
```

- 实体类型：user / dept / role / dict / time_range / page_selection。
- **数据范围约束**：所有 list 查询走 `ctx.request_token`，结果天然受数据范围约束。
- **防探测**：`not_found` 与 `forbidden` 对外提示一致；`forbidden` 仅内部审计区分。
- 多候选 → `ambiguous`，由 `ask_clarification` 出 clarify 事件（≤5 选项），不允许自动猜测执行写操作。
- 时间解析用 `Asia/Shanghai`，转 RuoYi 约定格式。

### 8.5 Confirmation Service

- 生成确认任务：`confirm_id`（`conf_` 前缀）、`payload_hash`（sha256 参数快照）、`idempotency_key`、`expires_at`（TTL 5min）。
- 存 Redis（带 TTL）+ PostgreSQL（`agent_confirmation`），payload 脱敏、不含 token。
- **执行前重校验**（任一不过即拒绝）：confirm 存在且未过期；payload_hash 匹配；token 有效；实时权限具备；实体存在性与可见性复查；high 已二次确认。
- 状态机：`pending/running/succeeded/failed_retryable/failed_final/canceled/expired`。

### 8.6 RuoYi Client

```python
# clients/ruoyi.py
class RuoYiClient:
    async def request(self, ctx, method, path, *, params=None, json=None, idem_key=None):
        headers = {"Authorization": f"Bearer {ctx.request_token}",
                   "X-Agent-Source": "ai-assistant",
                   "X-Correlation-Id": ctx_correlation_id()}
        if idem_key: headers["X-Idempotency-Key"] = idem_key
        # httpx async 调用 + 超时 + 错误归一化（RUOYI_API_ERROR / PERMISSION_DENIED / AUTH_EXPIRED）
```

- token 逐请求透传；透传 `X-Agent-Source`、`X-Correlation-Id`、`X-Idempotency-Key`。
- 错误归一化为统一错误码（§9.3）；不向上抛原始堆栈/内网信息。
- 超时与重试策略受 Manifest `idempotent`/`retry_on_timeout` 控制（§12）。

### 8.7 Conversation / Memory

- 最近 N=10 轮原文，长会话压缩 summary。
- summary 不含 token/密码/密钥/敏感字段，只保留业务目标、有效实体显示名与 ID、进行中补参状态、最近失败原因。
- checkpoint 用 Redis（thread_id=session_id）；会话元数据落 `agent_session`。

### 8.8 Audit Service

- 事件：`session_created/tool_retrieved/tool_called/clarification_requested/confirmation_created/action_executed/action_failed/permission_drift_detected/confirmation_reconciled`。
- 全部脱敏后落 `agent_audit_event`，带 `correlation_id`。

### 8.9 STT Service

- 负责校验浏览器上传的音频格式、大小、时长，并调用可插拔 STT provider 生成 transcript。
- 支持的默认格式：`audio/webm;codecs=opus`；可配置增加 `audio/mp4`、`audio/wav` 等 provider 支持格式。
- 原始音频只在请求处理内存和临时流中存在，默认不落 PostgreSQL、Redis checkpoint 或审计表。
- transcript 作为用户消息进入普通 `/messages` 主链路；后续工具选择、确认、SSE 推送与文字输入完全一致。
- STT 失败统一返回 `VOICE_TRANSCRIBE_FAILED`，不进入 LangGraph 推理。

## 9. API 与 SSE

### 9.1 REST 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ai/sessions` | 创建会话 |
| GET | `/ai/sessions/{id}/stream` | SSE 事件流 |
| POST | `/ai/sessions/{id}/messages` | 发送用户消息 |
| POST | `/ai/sessions/{id}/voice/messages` | 上传语音，转写后进入普通消息链路 |
| POST | `/ai/sessions/{id}/confirm` | 确认/拒绝（需重携 token） |
| POST | `/ai/sessions/{id}/cancel` | 取消补参/确认 |
| GET | `/ai/sessions/{id}/history` | 状态恢复，不触发推理 |

> `session_id` 即 LangGraph `thread_id`。`/confirm` resume 后结果从当前 SSE 推送；断开后前端重连新建 SSE 并经 `/history` 恢复。

#### 9.1.1 REST DTO

`POST /ai/sessions`

```json
{ "client_id": "web", "locale": "zh-CN" }
```

响应：

```json
{ "session_id": "sess_...", "phase": "idle" }
```

`POST /ai/sessions/{id}/messages`

```json
{
  "client_message_id": "msg_client_...",
  "content": "停用当前选中的用户",
  "input_type": "text",
  "page_context": {
    "route": "/system/user",
    "page_title": "用户管理",
    "query_params": { "deptId": "12" },
    "route_fingerprint": "sha256:...",
    "selected_rows_summary": [
      { "resource_type": "user", "primary_key": 1024, "display": "张三 / zhangsan", "route": "/system/user", "selected_at": "2026-06-16T15:30:00+08:00" }
    ]
  }
}
```

响应只表示接收成功，推理结果从 SSE 返回：

```json
{ "accepted": true, "message_id": "msg_...", "correlation_id": "corr_..." }
```

`POST /ai/sessions/{id}/voice/messages` 使用 `multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `audio` | file | 是 | 浏览器录音 Blob |
| `client_message_id` | string | 是 | 前端生成的去重 ID |
| `duration_ms` | integer | 是 | 录音时长 |
| `mime_type` | string | 是 | 如 `audio/webm;codecs=opus` |
| `locale` | string | 否 | 默认 `zh-CN` |
| `page_context` | JSON string | 是 | 与文字消息一致 |

响应：

```json
{ "accepted": true, "message_id": "msg_...", "transcript": "打开用户管理", "correlation_id": "corr_..." }
```

`POST /ai/sessions/{id}/confirm`

```json
{
  "confirm_id": "conf_...",
  "action": "confirm",
  "payload_hash": "sha256:...",
  "ack_checked": true,
  "second_confirm_text": "确认删除"
}
```

规则：

- `action` 取值：`confirm/reject/modify`。
- `medium` 风险可不传 `ack_checked` 和 `second_confirm_text`。
- `high` 风险必须满足服务端确认策略：`ack_checked=true` 或 `second_confirm_text` 命中确认任务里的 challenge；缺失返回 `SECOND_CONFIRM_REQUIRED`。
- `payload_hash` 不匹配返回 `CONFIRM_HASH_MISMATCH`，不得执行工具。

`POST /ai/sessions/{id}/cancel`

```json
{ "target": "clarify" }
```

`target` 取值：`clarify/confirm/current_turn`。取消确认会将确认任务标记为 `canceled`。

`GET /ai/sessions/{id}/history`

按 `phase` 返回用于 UI 重建的快照：

```json
{
  "session_id": "sess_...",
  "phase": "awaiting_confirm",
  "messages": [],
  "pending_confirm": {
    "confirm_id": "conf_...",
    "risk_level": "high",
    "title": "确认删除用户",
    "summary": "将删除 2 个用户",
    "affected_resources": [],
    "payload_hash": "sha256:...",
    "expires_at": "2026-06-16T15:35:00+08:00",
    "second_confirm": { "mode": "text", "challenge": "确认删除" }
  },
  "last_event_id": "evt_...",
  "last_seq": 42
}
```

### 9.2 SSE 事件

基础字段 `seq/event_id/session_id/correlation_id/type/created_at/payload`；类型：`text/text_done/route/data/clarify/confirm/action_result/tool_status/error`。事件结构见主方案 §15。

SSE 恢复规则：

- 服务端 SSE 必须同时设置标准 SSE `id: <event_id>` 与 JSON 内的 `event_id`。
- `seq` 在同一 `session_id` 内单调递增；`event_id` 全局唯一。
- 前端重连时通过 `Last-Event-ID` 续传；服务端从事件缓存中重放该事件之后的事件。
- 事件缓存窗口建议不短于 10 分钟；若 `Last-Event-ID` 已过期，返回 `SSE_REPLAY_EXPIRED`，前端改走 `/history` 重建 UI。
- 若发现 seq gap，前端不得重复驱动推理，只能调用 `/history` 对齐状态。

### 9.3 错误码

`AUTH_EXPIRED / PERMISSION_DENIED / TOOL_NOT_FOUND / TOOL_DISABLED / VALIDATION_ERROR / ENTITY_AMBIGUOUS / ENTITY_NOT_FOUND / CONFIRM_EXPIRED / CONFIRM_HASH_MISMATCH / SECOND_CONFIRM_REQUIRED / STALE_SELECTION / EXECUTION_TIMEOUT / SSE_REPLAY_EXPIRED / RUOYI_API_ERROR / MODEL_ERROR / RATE_LIMITED / COST_LIMIT_EXCEEDED / VOICE_PERMISSION_DENIED / VOICE_RECORDING_TOO_LONG / VOICE_TRANSCRIBE_FAILED / VOICE_UNSUPPORTED_FORMAT`。

## 10. 持久化与数据表

| 表 | 用途 | 关键字段 |
|----|------|----------|
| `agent_session` | 会话元数据 | id, user_id, phase, summary, permission_snapshot_hash, created_at, updated_at |
| `agent_confirmation` | 确认任务 | confirm_id, session_id, user_id, tool_name, risk_level, payload_hash, payload_json(脱敏), idempotency_key, status, running_started_at, expires_at |
| `agent_audit_event` | 审计 | id, session_id, user_id, correlation_id, event_type, tool_name, risk_level, payload_summary, result_code, created_at |

Redis：LangGraph checkpoint、`agent:session:{id}:lock` 锁、确认任务缓存（TTL）、SSE 事件缓存、检索缓存。

语音数据：默认不新增音频持久化表；只在会话消息中保留 transcript，不保存原始音频 Blob、频谱或浏览器权限状态。

## 11. 安全模型

- **Token**：不入 State、不落库；contextvar/`config.configurable` 逐请求注入；SSE 内存持有、断连释放；日志/审计禁打印 token。
- **权限三层**：工具可见性过滤（非边界）→ 执行前校验（辅助）→ RuoYi 最终鉴权（边界）。
- **permission_snapshot_hash**：仅审计 + 漂移检测；执行前以**实时权限**裁决，漂移则按实时拒绝并记 `permission_drift_detected`。
- **Prompt 注入**：工具返回值结构化注入、不拼系统提示；系统提示要求忽略数据中指令；不依据结果 URL 外联；参数过 schema 不接受额外字段；page_context 白名单。
- **脱敏**：密码/token/secret 永不展示；手机号/邮箱按 RuoYi 脱敏；高敏字段不接入工具；导出类不开放。
- **语音**：原始音频默认不落库、不进 State、不进审计；仅 transcript 进入普通消息链路；STT provider 日志必须脱敏。
- **page_context**：只接收 `route/page_title/query_params/route_fingerprint/selected_rows_summary`；选区必须带 `resource_type/primary_key/route/selected_at`，执行前按当前 token 复查。
- **字段映射**：Agent 内部使用 snake_case 规范字段，调用 RuoYi 前必须按 Manifest `field_mapping` 转 DTO 字段，禁止把前端展示文案作为执行参数。
- **风险等级**：none/low/medium/high/forbidden（forbidden 仅审核期分类）。
- **限流与成本**：单用户频率/每日 token 配额/并发会话上限；成本熔断降级为「仅导航 + 提示人工」。

## 12. 并发、幂等与一致性

- 同一 `session_id` 写操作互斥（Redis 锁）。
- 重复确认通过 `idempotency_key` 返回同一结果。
- RuoYi 支持幂等头则透传；不支持时：**非幂等写操作（idempotent=false）超时不自动重试**，标记 `failed_retryable` 提示核对；幂等写操作可安全重试。
- **running 超时对账**（`confirm/reconcile.py`）：定时扫描 `running_started_at` 超时的确认任务，标记 `failed_retryable`，记 `confirmation_reconciled`，处理进程崩溃导致的悬挂。

## 13. 可观测性

- 链路：每轮生成 `correlation_id`，贯穿 SSE 事件、Agent 日志、RuoYi header、RuoYi 操作日志扩展字段。
- 指标：tool_selection_accuracy、entity_resolution_success_rate、clarification_rate、confirmation_accept_rate、action_success_rate、avg_turn_latency、model_error_rate、permission_denied_rate、permission_drift_rate、llm_cost_per_user。
- 日志：structlog + 脱敏中间件，统一字段。

## 14. 评估与测试

- 评估集（`eval/suites/`）：导航、单步查询、补参、消歧、多步、上下文、语音转写、权限不足、高风险二次确认、token 过期重放、权限漂移、并发、数据范围、批量部分失败、prompt 注入红队、running 对账。
- 断言：选对工具、未调未授权工具、写前必 confirm、high 风险缺少二次确认字段不得执行、正确解析/消歧、预期 SSE 序列、history 可恢复、Manifest 字段映射正确、写审计、不泄露敏感字段、not_found/forbidden 提示一致。
- 门槛：导航 ≥95%、只读查询 ≥90%、写确认覆盖率=100%、未授权写=0、幂等重复=0、红队通过=100%、P95 首 token ≤3s。
- 确定性：固定 `temperature=0`、固定模型版本、每用例 N≥3 取通过率、模型/prompt 变更触发全量回归。
- CI：P2 后接 smoke eval；P4 后接写操作 eval。

## 15. 配置项

| 配置 | 说明 |
|------|------|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_TEMPERATURE` | 模型（评估固定 temperature=0） |
| `RUOYI_BASE_URL` | RuoYi 后端地址 |
| `REDIS_URL` / `POSTGRES_DSN` | 基础设施 |
| `CONFIRM_TTL_SECONDS` | 确认 TTL，默认 300 |
| `MAX_STEPS` / `TOOL_TIMEOUT` / `TURN_TIMEOUT` | 8 / 10s / 60s |
| `RATE_LIMIT_*` / `DAILY_TOKEN_QUOTA` | 限流与成本 |
| `TOOL_RETRIEVAL_MODE` | keyword / embedding |
| `STT_PROVIDER` / `STT_MODEL` | 语音转写 provider 与模型 |
| `VOICE_MAX_DURATION_SECONDS` / `VOICE_MAX_BYTES` | 录音最大时长与大小 |
| `SSE_REPLAY_TTL_SECONDS` | SSE 事件缓存窗口 |

## 16. 开发任务拆解清单

对应主方案 P0–P8，可据此建卡：

- [ ] **P0 骨架**：FastAPI + 生命周期、`RuntimeContext`/contextvar、token 提取、统一错误码、structlog 脱敏、SSE 封装、Redis/PG 连接
- [ ] **P0 状态机**：`ConversationState`、LangGraph 组装、Redis checkpointer、`/sessions` 创建
- [ ] **RuoYi 支撑**：token 调用放行、`X-Correlation-Id` 落操作日志、`X-Idempotency-Key`、权限元数据、工具刷新
- [ ] **P1 导航**：菜单拉取（当前 token）、navigate 工具、route 事件、导航评估
- [ ] **P2 查询工具**：query_* Manifest、Tool Registry 加载与校验、`retrieve_tools` 占位（精简签名）、data 事件、smoke eval
- [ ] **P3 实体解析**：user/dept/role/dict/time_range resolver（当前 token）、ambiguous/not_found/forbidden（提示一致）、clarify、page_selection
- [ ] **P4 写操作**：create/update/status/delete、Confirmation Service、prepare_confirm + interrupt、强制时序、执行前重校验、幂等键、服务端校验二次确认、字段映射、批量部分失败、running 对账、history 恢复、写操作 eval
- [ ] **语音输入**：`/voice/messages`、音频校验、STT 转写、transcript 注入消息链路、VOICE_* 错误码、语音 eval
- [ ] **P5 多步与检索**：ReAct 多步、observe_result 二次检索、embedding + Top-K、工具包、step/超时保护
- [ ] **P6 工具链**：旁路 YAML 规范、`agent-tool scan/validate/eval` CLI、Manifest 校验、评估模板生成
- [ ] **P7 OpenAPI 候选**：SpringDoc 解析、disabled Manifest、风险初判、人工审核
- [ ] **P8 生产化**：指标、链路追踪、重试降级、限流熔断、安全回归（含红队）、压测并发、灰度开关
