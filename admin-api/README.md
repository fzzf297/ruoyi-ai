# Admin API

独立轻量管理后台后端，使用 FastAPI + SQLite。它负责管理后台登录、项目配置、页面配置、APP 接口定义和接口 YAML 配置。

## Install

```bash
cd admin-api
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
request:
  method: GET
  path: /users
response:
  dataPath: data
```

YAML 只作为声明式配置保存和解析，不执行其中任何代码。

## Versions

页面配置和 APP 接口配置会自动生成历史版本。创建、修改、启停、删除都会写入版本快照；接口 YAML 保存也会写入接口版本。删除主记录后，版本记录仍可查询。

## Verify

```bash
python3 -m pytest
python3 -m ruff check
```
