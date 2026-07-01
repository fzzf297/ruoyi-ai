# Agent Backend

Agent 服务基于 LangGraph 编排，通过 HTTP 调用 `backend/admin` 的只读公共接口
（`/api/app/*`）获取项目和接口配置，对外提供会话式对话接口。
当接口 YAML 标记为 `kind: api` 且 `readOnly: true` 时，Agent 可按项目 `baseUrl`
调用三方只读业务接口；如配置 `useProjectAuth`，会先调用本项目 `kind: auth`
bridge 取鉴权头，用完即丢。

## 目录结构

```text
backend/agent/
├─ app/
│  ├─ api/          # HTTP 路由与协议转换
│  ├─ services/     # 业务编排
│  ├─ repositories/ # 持久化访问
│  ├─ schemas/      # 请求与响应模型
│  ├─ core/         # 配置、安全、异常
│  ├─ db/           # 数据库连接与初始化
│  ├─ graphs/       # LangGraph 状态图
│  └─ tools/        # LangChain 工具
├─ migrations/      # 版本化 SQL
└─ tests/           # pytest 测试
```

## 环境要求

- Python `>=3.9`
- 开发依赖：pytest、Ruff
- 运行依赖：LangGraph、LangChain、FastAPI、httpx

## 安装

```bash
cd backend/agent
python3 -m pip install -e ".[dev]"
```

## 启动

```bash
cd backend/agent
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

默认地址：

- API：`http://localhost:8001`
- Swagger UI：`http://localhost:8001/docs`

需同时运行 `backend/admin`（默认 `http://localhost:8000`）以提供只读数据。

## 验证

```bash
cd backend/agent
python3 -m ruff check
python3 -m pytest
```

## 配置

服务通过环境变量读取配置，至少应覆盖：

```text
AGENT_LLM_BASE_URL
AGENT_LLM_API_KEY
AGENT_LLM_MODEL
AGENT_ADMIN_BASE_URL
```

可选三方调用安全项：

```text
AGENT_THIRD_PARTY_ALLOWED_HOSTS   # 逗号分隔 host；host 与解析后的 IP 都会校验
AGENT_THIRD_PARTY_MAX_RESPONSE_BYTES
```

示例见 `.env.example`。不得提交真实密钥或 Token。
SQLite 默认数据文件位于 `backend/agent/data/agent.db`，该目录已忽略。

## 三方 Bridge 执行约束

- Admin 只保存 `baseUrl`、接口路径、请求模板和响应 `dataPath`，不保存三方密码或业务 Token。
- Agent 只执行 `kind: api` 且 `readOnly: true` 的接口，并且仅允许 `GET` / `POST`。
- Admin 可保存 `readOnly: false` 的接口配置，但 Agent `execute_interface` 会返回 `INTERFACE_WRITE_NOT_ALLOWED`，不执行写接口。
- `kind: auth` 响应需返回 `headerName + headerValue`，或 `headerName + token + tokenPrefix`；可选 `expiresIn` + YAML 中 `expiresInPath`。
- 路径、query、body、headers 支持 `{paramName}` 占位；path 段参数会 URL 编码，且禁止 `{secret.*}`；headers/body 支持 `{secret.apiKey}` 等静态认证头，由 `AGENT_PROJECT_SECRETS` 或 `AGENT_PROJECT_<CODE>__<KEY>` 注入。
- 同一项目可有多个 `kind: auth`；业务接口通过 `auth.interfaceCode` 选择认证配置，未指定时项目内只能有一个 auth。
- `list_executable_interfaces` 仅返回 `kind: api`、`readOnly: true` 且方法为 `GET` / `POST` 的接口，并附带 `params`、`authRequired`、`authInterfaceCode`，便于对话时向用户收集参数。
- `AGENT_THIRD_PARTY_ALLOWED_HOSTS` 为空时，拒绝 `localhost`、私网/链路本地 IP、解析到这些地址的普通域名与云 metadata 主机；`host.docker.internal` 等仅 allowlist 显式允许的主机名也需配置后才可访问；`127.0.0.0/8` 等即使用户写入 allowlist 也会被硬拦截。
- Docker compose 会把 `AGENT_PROJECT_SECRETS`、`AGENT_THIRD_PARTY_ALLOWED_HOSTS`、`AGENT_THIRD_PARTY_MAX_RESPONSE_BYTES` 传给 agent 容器；如使用 `ruoyi-classic` 默认 `baseUrl=http://host.docker.internal:8080`，需设置 `AGENT_THIRD_PARTY_ALLOWED_HOSTS=host.docker.internal`。

### YAML 示例

静态 API Key（headers）：

```yaml
version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /items
  headers:
    X-API-Key: "{secret.apiKey}"
response:
  dataPath: data
```

多 auth 项目选择 `get_token_b`：

```yaml
version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /items
response:
  dataPath: items
auth:
  useProjectAuth: true
  interfaceCode: get_token_b
```

## 数据库

- Agent **不保存**三方接口 YAML；运行时通过 HTTP 读取 Admin `/api/app/projects/{code}/interfaces` 及配置。
- Agent 自有 SQLite（`agent_sessions`、`agent_messages` 等）仅用于会话与消息，与三方接口定义无关。
- `list_executable_interfaces` / `execute_interface` 的过滤与执行规则在 Agent 代码中实现，**不依赖 Agent 侧数据库迁移**。
