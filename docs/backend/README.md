# 独立管理后台后端

本文描述当前仓库新增的独立轻量后端服务 `admin-api`。它不依赖 RuoYi Cloud 后端，也不修改 RuoYi 微服务边界；后续仓库中 RuoYi 相关内容可以按新的产品方向逐步剔除。

## 目标

- 提供管理后台登录，只用于进入后台维护项目配置。
- 管理可配置的前端页面：页面编码、名称、路由、排序、状态和 JSON 配置。
- 管理供 APP 使用的接口定义：接口编码、方法、路径、鉴权模式、状态、说明。
- 为接口维护声明式 YAML 配置，后端负责解析和校验，不执行 YAML 中的任意代码。
- 自动生成 OpenAPI，Vue 前端可通过 `/openapi.json` 对接类型和请求层。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| Web 框架 | FastAPI |
| 存储 | SQLite |
| 文档 | FastAPI OpenAPI / Swagger UI |
| 密码哈希 | Python 标准库 PBKDF2-HMAC-SHA256 |
| Token | 标准库 HMAC-SHA256 签名 JWT 形态 token |
| YAML | PyYAML |
| 测试 | pytest |

## 目录

```text
admin-api/
├─ app/
│  ├─ main.py
│  ├─ api/
│  ├─ core/
│  ├─ db/
│  ├─ models/
│  ├─ repositories/
│  ├─ schemas/
│  └─ services/
├─ migrations/
├─ tests/
├─ pyproject.toml
└─ README.md
```

SQLite 默认文件为 `admin-api/data/admin-api.db`，该目录不会提交到 git。

## 本地启动

安装依赖：

```bash
cd admin-api
python3 -m pip install -e ".[dev]"
```

启动服务：

```bash
sh scripts/monorepo.sh admin:dev
```

或通过根目录 npm 脚本：

```powershell
npm run admin:dev
```

默认地址：

- API：`http://localhost:8000`
- Swagger UI：`http://localhost:8000/docs`
- OpenAPI JSON：`http://localhost:8000/openapi.json`

默认初始化管理员来自环境变量：

```text
ADMIN_API_DEFAULT_ADMIN_USERNAME=admin
ADMIN_API_DEFAULT_ADMIN_PASSWORD=admin123
```

生产或共享环境必须修改默认密码和 `ADMIN_API_SECRET_KEY`。

## API 分组

管理后台接口统一需要 Bearer Token：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/admin/auth/login` | 管理员登录 |
| POST | `/api/admin/auth/refresh` | 刷新 token |
| POST | `/api/admin/auth/logout` | 登出并吊销 refresh token |
| GET | `/api/admin/auth/me` | 当前管理员 |
| GET/POST | `/api/admin/projects` | 项目列表/新增 |
| GET/PUT/DELETE | `/api/admin/projects/{projectId}` | 项目详情/修改/删除 |
| GET/POST | `/api/admin/projects/{projectId}/pages` | 页面配置列表/新增 |
| GET/PUT/DELETE | `/api/admin/pages/{pageId}` | 页面配置详情/修改/删除 |
| PATCH | `/api/admin/pages/{pageId}/status` | 页面启停 |
| GET | `/api/admin/pages/{pageId}/versions` | 页面配置历史版本列表 |
| GET | `/api/admin/pages/{pageId}/versions/{version}` | 页面配置指定历史版本 |
| GET/POST | `/api/admin/projects/{projectId}/interfaces` | APP 接口列表/新增 |
| GET/PUT/DELETE | `/api/admin/interfaces/{interfaceId}` | APP 接口详情/修改/删除 |
| PATCH | `/api/admin/interfaces/{interfaceId}/status` | APP 接口启停 |
| GET | `/api/admin/interfaces/{interfaceId}/config` | 查询接口 YAML 配置 |
| PUT | `/api/admin/interfaces/{interfaceId}/config-yaml` | 保存接口 YAML 配置 |
| POST | `/api/admin/interfaces/config-yaml/validate` | 仅校验 YAML |
| GET | `/api/admin/interfaces/{interfaceId}/versions` | APP 接口历史版本列表 |
| GET | `/api/admin/interfaces/{interfaceId}/versions/{version}` | APP 接口指定历史版本 |

APP 读取侧接口默认不受管理后台登录限制：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/app/projects/{projectCode}/pages` | 读取启用页面配置 |
| GET | `/api/app/projects/{projectCode}/interfaces` | 读取启用接口定义与解析后的配置 |

## YAML 配置规则

接口 YAML 是声明式配置。MVP 必填结构：

```yaml
version: 1
request:
  method: GET
  path: /users
response:
  dataPath: data
```

规则：

- 根节点必须是 YAML mapping。
- 必须包含 `version`。
- 必须包含 `request.method` 和 `request.path`。
- `request.method` 只能是 `GET`、`POST`、`PUT`、`PATCH`、`DELETE`。
- `request.path` 必须以 `/` 开头。
- 保存到某个接口时，YAML 的 method/path 必须和接口定义一致。
- 禁止出现 `script`、`exec`、`eval`、`shell`、`command` 等可执行语义字段。

## 历史版本

页面配置和 APP 接口配置都会自动记录版本：

- 页面：新增、修改、启停、删除前记录快照。
- APP 接口：新增、修改、启停、保存 YAML、删除前记录快照。
- 版本号从 `1` 开始递增，列表按版本倒序返回。
- 删除主记录后，历史版本仍保留，可继续通过版本接口查询。

页面版本 `snapshot` 是页面完整快照。APP 接口版本 `snapshot` 包含：

```json
{
  "interface": {},
  "config": {}
}
```

其中 `config` 为当前接口 YAML 配置快照；如果当时尚未配置 YAML，则为 `null`。

## Vue 对接

Vue 前端可以直接读取 `/openapi.json` 生成类型，也可以按 Swagger UI 手写 `src/api`。登录成功后，管理后台请求统一携带：

```text
Authorization: Bearer <accessToken>
```

YAML 编辑页建议使用 Monaco Editor 或 CodeMirror；前端负责编辑体验，后端负责最终语法和安全校验。

## 验证

```bash
sh scripts/monorepo.sh admin:test
sh scripts/monorepo.sh admin:lint
```

`admin:test` 使用 pytest 覆盖登录、配置 CRUD、YAML 校验、未登录拦截和 APP 公开读取。`admin:lint` 使用 ruff。

## 部署

开发阶段不需要 Nginx，可以直接让 Vue dev server 代理到 FastAPI。

生产阶段建议：

```text
Nginx
  -> /        Vue 静态文件
  -> /api/    FastAPI admin-api
```

Nginx 主要用于 HTTPS、静态文件、反向代理、上传限制和后续多服务转发；不是本服务的运行时硬依赖。
