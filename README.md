# RuoYi AI Workspace

本仓库按技术形态划分为后端与前端。当前唯一可运行服务是
`backend/admin`：一个基于 FastAPI 与 SQLite 的独立管理后台后端。

## 目录结构

```text
/
├─ backend/
│  ├─ admin/             # 现有 FastAPI 管理后台后端
│  └─ agent/             # Agent 后端预留边界，当前无运行时
├─ frontend/
│  └─ admin/             # 管理后台前端预留边界，当前无运行时
├─ docs/                    # 产品与历史文档
└─ scripts/                 # 根命令包装
```

## 环境要求

- Python `>=3.9`
- 开发依赖：pytest、Ruff

## 安装

```bash
cd backend/admin
python3 -m pip install -e ".[dev]"
```

## 启动

```bash
cd backend/admin
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

默认地址：

- API：`http://localhost:8000`
- Swagger UI：`http://localhost:8000/docs`
- OpenAPI：`http://localhost:8000/openapi.json`

## 验证

```bash
cd backend/admin
python3 -m ruff check
python3 -m pytest
```

## 配置

服务通过系统环境变量读取配置。生产或共享环境至少应覆盖：

```text
ADMIN_API_SECRET_KEY
ADMIN_API_DEFAULT_ADMIN_PASSWORD
```

不得提交真实密码、Token 或密钥。SQLite 默认数据文件位于
`backend/admin/data/admin-api.db`，该目录已忽略。

## API

主要接口包括：

- `/api/admin/auth/*`：管理员认证。
- `/api/admin/projects`：项目管理。
- `/api/admin/pages/*`：页面配置及历史版本。
- `/api/admin/interfaces/*`：APP 接口定义、YAML 配置及历史版本。
- `/api/app/projects/*`：APP 读取侧接口。

完整契约以 `backend/admin/openapi.json` 和运行时 `/openapi.json` 为准。
