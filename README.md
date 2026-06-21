# Admin API Workspace

本仓库当前只维护独立管理后台后端 `admin-api`。服务基于 FastAPI 与 SQLite，用于管理项目、页面配置、APP 接口定义及声明式 YAML 配置。

## 目录结构

```text
/
├─ admin-api/              # FastAPI 应用、迁移、测试和 OpenAPI
├─ README.md
└─ .env.example
```

## 环境要求

- Python `>=3.9`
- 开发依赖：pytest、Ruff

## 安装

```bash
cd admin-api
python3 -m pip install -e ".[dev]"
```

## 启动

```bash
cd admin-api
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

默认地址：

- API：`http://localhost:8000`
- Swagger UI：`http://localhost:8000/docs`
- OpenAPI：`http://localhost:8000/openapi.json`

## 验证

```bash
cd admin-api
python3 -m ruff check
python3 -m pytest
```

## 配置

配置项示例位于 `.env.example`。本地运行前至少应覆盖：

```text
ADMIN_API_SECRET_KEY
ADMIN_API_DEFAULT_ADMIN_PASSWORD
```

不得提交真实密码、Token 或密钥。SQLite 默认数据文件位于 `admin-api/data/admin-api.db`，该目录已忽略。

## API

主要接口包括：

- `/api/admin/auth/*`：管理员认证。
- `/api/admin/projects`：项目管理。
- `/api/admin/pages/*`：页面配置及历史版本。
- `/api/admin/interfaces/*`：APP 接口定义、YAML 配置及历史版本。
- `/api/app/projects/*`：APP 读取侧接口。

完整契约以 `admin-api/openapi.json` 和运行时 `/openapi.json` 为准。
