# Agent Backend

Agent 服务基于 LangGraph 编排，通过 HTTP 调用 `backend/admin` 的只读公共接口
（`/api/app/*`）获取能力，对外提供会话式对话接口。

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

示例见 `.env.example`。不得提交真实密钥或 Token。
SQLite 默认数据文件位于 `backend/agent/data/agent.db`，该目录已忽略。
