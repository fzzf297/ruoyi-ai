# Admin Backend

独立轻量管理后台后端，使用 FastAPI + SQLite。它负责管理后台登录、项目配置、页面配置、APP 接口定义和接口 YAML 配置。
项目可配置 `baseUrl`，供 Agent 按声明式接口调用三方只读业务接口。

## Install

```bash
cd backend/admin
python3 -m pip install -e ".[dev]"
```

## Run

```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

默认服务地址：

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Default Admin

开发环境默认会在空库中初始化一个管理员：

```text
username: admin
password: admin123
```

可通过环境变量覆盖：

```text
ADMIN_API_DEFAULT_ADMIN_USERNAME
ADMIN_API_DEFAULT_ADMIN_PASSWORD
ADMIN_API_DEFAULT_ADMIN_DISPLAY_NAME
ADMIN_API_SECRET_KEY
ADMIN_API_DATABASE_URL
```

生产或共享环境必须修改默认密码和 `ADMIN_API_SECRET_KEY`。

## Main APIs

管理端接口：

- `POST /api/admin/auth/login`
- `POST /api/admin/auth/refresh`
- `POST /api/admin/auth/logout`
- `GET /api/admin/auth/me`
- `GET/POST /api/admin/projects`
- `GET/POST /api/admin/projects/{projectId}/pages`
- `GET/POST /api/admin/projects/{projectId}/interfaces`
- `PUT /api/admin/interfaces/{interfaceId}/config-yaml`
- `POST /api/admin/interfaces/config-yaml/validate`
- `GET /api/admin/pages/{pageId}/versions`
- `GET /api/admin/pages/{pageId}/versions/{version}`
- `GET /api/admin/interfaces/{interfaceId}/versions`
- `GET /api/admin/interfaces/{interfaceId}/versions/{version}`

APP 读取接口：

- `GET /api/app/projects/{projectCode}/pages`
- `GET /api/app/projects/{projectCode}/interfaces`

## YAML Example

```yaml
version: 1
kind: api
readOnly: true
request:
  method: GET
  path: /users
  headers:
    X-API-Key: "{secret.apiKey}"
response:
  dataPath: data
```

静态 API Key 由 Agent 环境变量注入，勿写入 Admin 数据库。

带项目认证的只读接口（多 auth 时通过 `interfaceCode` 选择）：

```yaml
version: 1
kind: api
readOnly: true
request:
  method: POST
  path: /system/user/list
  contentType: application/x-www-form-urlencoded
  body:
    pageNum: "{pageNum}"
    pageSize: "10"
response:
  dataPath: rows
auth:
  useProjectAuth: true
  interfaceCode: get_token_a
```

YAML 只作为声明式配置保存和解析，不执行其中任何代码。

`readOnly` 可为 `true` 或 `false`；Admin 会保存两种配置。Agent 仅执行 `readOnly: true` 的 `kind: api` 接口，对 `readOnly: false` 调用 `execute_interface` 将返回 `INTERFACE_WRITE_NOT_ALLOWED`。

Bridge 认证接口示例：

```yaml
version: 1
kind: auth
request:
  method: POST
  path: /api/agent-bridge/auth
response:
  headerNamePath: headerName
  headerValuePath: headerValue
```

同一项目可配置多个 `kind: auth` 接口；业务 API 通过 `auth.interfaceCode` 指定使用哪一个。未指定时，项目内只能有一个 `kind: auth`，否则 Agent 返回 `PROJECT_AUTH_NOT_UNIQUE`。

Auth 请求体可使用 `{secret.clientId}`、`{secret.clientSecret}` 占位；实际值由 Agent 环境变量 `AGENT_PROJECT_SECRETS` 或 `AGENT_PROJECT_<CODE>__<KEY>` 注入（`CODE` 用下划线，与 secret 之间双下划线分隔）。Admin 只保存取 Token 路径和响应解析规则，不保存三方密码或业务 Token。

## 数据库

- 项目、页面、接口元数据存于 `projects`、`admin_pages`、`app_interfaces`。
- 接口 YAML 存于 `interface_configs`（`yaml_text` + `parsed_json`）；`request.headers`、`auth.interfaceCode`、多个 `kind: auth` 等均保存在 `parsed_json` 中。
- 历史版本存于 `app_interface_versions` 等版本表。
- `baseUrl` 由 `004_project_base_url.sql` 增加到 `projects.base_url`；示例项目和接口通过后续 seed/patch 迁移写入。
- 运行中变更接口配置只需在管理后台更新 YAML 并保存，不能手工改 `parsed_json` 与 `yaml_text` 造成不一致。

## Versions

页面配置和 APP 接口配置会自动生成历史版本。创建、修改、启停、删除都会写入版本快照；接口 YAML 保存也会写入接口版本。删除主记录后，版本记录仍可查询。

## Verify

```bash
python3 -m pytest
python3 -m ruff check
```
