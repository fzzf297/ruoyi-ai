# RuoYi AI Workspace

本仓库按技术形态划分为后端与前端。可运行服务包括
`backend/admin`（FastAPI + SQLite 管理后台后端）和
`backend/agent`（LangGraph + FastAPI Agent 服务，只读调用 admin）。

## 目录结构

```text
/
├─ backend/
│  ├─ admin/             # FastAPI 管理后台后端
│  └─ agent/             # Agent 服务（LangGraph + LangChain，只读 admin）
├─ frontend/
│  └─ admin/             # 管理后台前端预留边界，当前无运行时
├─ docs/                    # 产品与历史文档
└─ scripts/                 # 根命令包装
```

## 环境要求

- Python `>=3.9`
- 开发依赖：pytest、Ruff
- Agent 额外依赖：LangGraph、LangChain、langchain-openai、httpx

## 安装

```bash
cd backend/admin
python3 -m pip install -e ".[dev]"

cd backend/agent
python3 -m pip install -e ".[dev]"
```

## 启动

admin（默认端口 8000）：

```bash
cd backend/admin
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

agent（默认端口 8001，需先启动 admin）：

```bash
cd backend/agent
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

默认地址：

- admin API：`http://localhost:8000`
- admin Swagger UI：`http://localhost:8000/docs`
- admin OpenAPI：`http://localhost:8000/openapi.json`
- agent API：`http://localhost:8001`
- agent Swagger UI：`http://localhost:8001/docs`

## 验证

```bash
cd backend/admin
python3 -m ruff check
python3 -m pytest

cd backend/agent
python3 -m ruff check
python3 -m pytest
```

或使用根脚本一次验证全部：

```bash
sh scripts/monorepo.sh verify
```

## 配置

### admin

通过系统环境变量读取配置。生产或共享环境至少应覆盖：

```text
ADMIN_API_SECRET_KEY
ADMIN_API_DEFAULT_ADMIN_PASSWORD
```

SQLite 默认数据文件位于 `backend/admin/data/admin-api.db`，该目录已忽略。

### agent

通过系统环境变量读取配置。至少应覆盖：

```text
AGENT_LLM_BASE_URL
AGENT_LLM_API_KEY
AGENT_LLM_MODEL
AGENT_ADMIN_BASE_URL
```

示例见 `backend/agent/.env.example`。SQLite 默认数据文件位于
`backend/agent/data/agent.db`，该目录已忽略。

不得提交真实密码、Token 或密钥。

## API

### admin

- `/api/admin/auth/*`：管理员认证。
- `/api/admin/projects`：项目管理。
- `/api/admin/pages/*`：页面配置及历史版本。
- `/api/admin/interfaces/*`：APP 接口定义、YAML 配置及历史版本。
- `/api/app/projects/*`：APP 读取侧接口（免鉴权只读，供 agent 调用）。

完整契约以 `backend/admin/openapi.json` 和运行时 `/openapi.json` 为准。

### agent

- `POST /api/agent/sessions`：创建会话。
- `GET /api/agent/sessions/{id}/history`：查询会话历史。
- `POST /api/agent/sessions/{id}/messages`：发送消息（SSE 流式响应）。

agent 自身接口不鉴权，通过 HTTP 调用 admin 的 `/api/app/*` 只读接口获取数据。

## Docker

使用 docker-compose 启动 admin + agent（需 Docker 环境）：

```bash
docker compose up --build -d
```

- admin：`http://localhost:8000`
- agent：`http://localhost:8001`

生产部署前请替换 `.env` 中的默认密钥与密码。

## 负载测试

启动 agent 后，运行内置负载脚本测试 session/health 接口（默认 50 请求、并发 10）：

```bash
cd backend/agent
python3 scripts/load_test.py
```

如需压测聊天接口，设置有效 LLM key：

```bash
AGENT_LLM_API_KEY=sk-xxxx python3 scripts/load_test.py
```

## 部署（内网离线）

**目标机从第一次部署起就不联网**（不 pull 镜像、不 apt/dnf、不 pip）。所有制品在**可联网的 x86_64 构建机**上打好包，再 U 盘/内网 SCP 传到目标机安装。

目标机安装内容（均在离线包内）：
- Docker 引擎 + compose 插件（`bootstrap-docker-offline.sh`）
- admin / agent / nginx 镜像 tar
- compose、nginx 配置、`.env`、安装脚本

### 流程概览

```text
[可联网 x86_64 构建机]                    [内网目标机，全程无网]
  sh deploy/prepare-offline-bundle.sh  →  拷贝 ruoyi-ai-offline-bundle.tar.gz
  产出 .tar.gz                                sh deploy/install-from-archive.sh ...
```

### 1. 构建机：打离线包（需 Docker + 互联网，x86_64）

```bash
AGENT_LLM_API_KEY=sk-xxxx \
ADMIN_API_DEFAULT_ADMIN_PASSWORD='your-admin-password' \
sh deploy/prepare-offline-bundle.sh
```

产出：`deploy/ruoyi-ai-offline-bundle.tar.gz`（含 Docker 引擎 + 全部镜像）

构建机也可以是另一台 x86 服务器（临时联网），**不是你的内网目标机**。

### 2. 目标机：首次安装（零网络）

将 `ruoyi-ai-offline-bundle.tar.gz` 拷到目标机后：

```bash
# 将仓库 deploy/ 目录一并拷入，或直接从包内解压后执行：
sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz /opt/ruoyi-ai
```

等价于：`解压 → 离线装 Docker → docker load → 修复数据卷权限 → compose up`

### 3. 一键：构建机 SSH 到目标机（目标机仍不访问互联网）

跳板机能 SSH 到目标机、但目标机不能上网时：

```bash
DEPLOY_HOST=10.0.0.5 DEPLOY_USER=root DEPLOY_PASSWORD='xxx' \
AGENT_LLM_API_KEY=sk-xxxx \
sh deploy/offline-deploy.sh
```

仅打离线包、不传输：

```bash
BUNDLE_ONLY=1 AGENT_LLM_API_KEY=sk-xxxx sh deploy/offline-deploy.sh
```

### 4. 目标机后续升级（仍零网络）

```bash
cd /opt/ruoyi-ai
sh deploy/install-from-archive.sh /path/to/ruoyi-ai-offline-bundle.tar.gz
```

### 部署后架构

- `admin` / `agent` 仅在 Docker 内网互通，**不暴露宿主机端口**
- `nginx` 容器作为唯一入口，监听 **80** 端口
- 访问：`http://<目标机IP>/docs`、`http://<目标机IP>/api/agent/`

### 联网构建（仅开发/调试，非内网首次部署）

需要目标机临时能访问 Docker Hub 时，可用 `deploy/server-deploy.sh`（**不适合纯内网首次部署**）。

### 5. 备份

```bash
sh deploy/backup.sh
```

备份文件保存在 `backups/YYYYmmdd-HHMMSS/`。

### 升级

在可联网机器重新执行 `deploy/build-images.sh`，将新的 tar 文件传到内网机器加载后，运行 `deploy/deploy.sh` 即可滚动更新。
