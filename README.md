# ruoyi-ai Monorepo

本仓库整合 `plus-ui` 前端与 `RuoYi-Cloud-Plus` 微服务后端，作为后续智能操作助手能力的工程基座。

## 目录结构

```text
/
├─ apps/
│  └─ web/                  # plus-ui
├─ services/
│  └─ cloud/                # RuoYi-Cloud-Plus
├─ database/                # 数据库说明与后续迁移入口
├─ infra/                   # 部署与基础设施说明
├─ scripts/                 # 根目录统一命令入口
├─ docs/
│  ├─ upstream/             # 上游来源、版本和同步方式
│  └─ original-root-readme.md
├─ AGENTS.md
├─ package.json
└─ .env.example
```

原项目根 README 已原样归档到 [docs/original-root-readme.md](docs/original-root-readme.md)。

## 环境要求

| 组件 | 要求 | 依据 |
|------|------|------|
| Node.js | `>=20.19.0` | `apps/web/package.json` |
| npm | `>=8.19.0` | `apps/web/package.json` |
| JDK | 17，或上游 README 标识支持的 21 | `services/cloud/pom.xml` / 上游 README |
| Maven | 本机 `mvn` | `RuoYi-Cloud-Plus` 未提供 Maven Wrapper |
| Docker | Docker Compose v2 | `services/cloud/script/docker/docker-compose.yml` |

Windows 优先使用 PowerShell 脚本。后端 Docker 编排复用上游配置，其中包含 `network_mode: host` 和 `/docker/...` 挂载路径；在 Windows 上建议使用 WSL2/Linux Docker 环境运行。

## 统一命令

根目录 `package.json` 只是命令入口，不改变前端和后端的独立构建边界。

```bash
npm run web:install
npm run web:dev
npm run web:build
npm run web:lint
npm run web:typecheck
npm run cloud:compile
npm run cloud:test
npm run cloud:infra:up
npm run cloud:infra:down
npm run verify
```

Shell 环境可直接使用：

```bash
./scripts/monorepo.sh web:install
./scripts/monorepo.sh verify
```

## 前端开发

前端位于 `apps/web`，保持 plus-ui 原有 Node/Vite 工程。

```bash
npm run web:install
npm run web:dev
```

上游开发配置：

- 前端端口：`80`
- 开发 API 前缀：`/dev-api`
- Vite Proxy：`/dev-api/**` -> `http://localhost:8080/**`
- Axios baseURL：`import.meta.env.VITE_APP_BASE_API`

## 后端开发

Cloud 后端位于 `services/cloud`，保持 RuoYi-Cloud-Plus 原有 Maven 多模块工程。

```bash
npm run cloud:compile
npm run cloud:test
```

后端根 POM 默认跳过测试，测试命令固定使用 `-DskipTests=false`，并由脚本读取 Surefire XML 确认实际测试数大于 0。

主要服务端口：

| 服务 | 端口 |
|------|------|
| Gateway | `8080` |
| Auth | `9210` |
| System | `9201` |
| Gen | `9202` |
| Job | `9203` |
| Resource | `9204` |
| Workflow | `9205` |
| Monitor | `9100` |
| SnailJob | `8800` |

## 初始化

基础设施优先复用：

- Docker Compose：`services/cloud/script/docker/docker-compose.yml`
- Nacos 配置：`services/cloud/script/config/nacos`
- SQL 脚本：`services/cloud/script/sql`

启动基础服务：

```bash
npm run cloud:infra:up
```

最小基础服务包括 MySQL、Nacos、Redis、MinIO、SnailJob。

数据库初始化：

| 数据库 | SQL |
|--------|-----|
| `ry-cloud` | `services/cloud/script/sql/ry-cloud.sql` |
| `ry-job` | `services/cloud/script/sql/ry-job.sql` |
| `ry-workflow` | `services/cloud/script/sql/ry-workflow.sql` |
| `ry-seata` | `services/cloud/script/sql/ry-seata.sql`，仅启用 Seata 时需要 |

Nacos 初始化：

1. 登录 `http://localhost:8848/nacos`。
2. 创建或使用 `dev` namespace。
3. 将 `services/cloud/script/config/nacos/*.yml` 和 `seata-server.properties` 导入 `DEFAULT_GROUP`。
4. 启动服务前校对 `datasource.yml`：上游 Nacos 示例密码是 `password`，Docker Compose MySQL root 密码是 `ruoyi123`，两者必须统一。

Redis 默认配置来自 `application-common.yml`：`localhost:6379`，密码 `ruoyi123`。

## 前端到 Gateway 链路

开发环境：

```text
Browser
  -> http://localhost:80
  -> /dev-api/auth/code
  -> Vite Proxy rewrite /dev-api
  -> http://localhost:8080/auth/code
  -> Gateway
  -> ruoyi-auth
```

生产环境：

```text
Browser
  -> /prod-api/**
  -> Nginx location /prod-api/
  -> Gateway 127.0.0.1:8080
```

Gateway 路由保持上游 Nacos 配置：

- `/auth/**` -> `ruoyi-auth`
- `/system/**`、`/monitor/**` -> `ruoyi-system`
- `/tool/**` -> `ruoyi-gen`
- `/resource/**` -> `ruoyi-resource`
- `/workflow/**`、`/warm-flow-ui/**` -> `ruoyi-workflow`
- `/demo/**` -> `ruoyi-demo`

前端不得直接访问内部微服务端口。

## 验证

结构验收：

```bash
Test-Path apps/web/.git
Test-Path services/cloud/.git
Test-Path apps/web/LICENSE
Test-Path services/cloud/LICENSE
Test-Path services/monolith
```

全量验证：

```bash
npm run verify
```

`verify` 会执行前端依赖安装、ESLint、TypeScript 检查、生产构建、后端编译和后端测试。缺少 Docker、数据库、Redis、Nacos 或外部服务时，后端启动类或集成测试可能失败，应按失败日志补齐环境后重试。

## 上游记录

- [plus-ui](docs/upstream/plus-ui.md)
- [RuoYi-Cloud-Plus](docs/upstream/ruoyi-cloud-plus.md)

## 架构边界

- 只使用 `plus-ui + RuoYi-Cloud-Plus`。
- 不引入 `RuoYi-Vue-Plus`。
- 不新增 `services/monolith`。
- 不创建根 Maven 聚合 POM。
- 不合并 Gateway、Auth、System、Resource、Workflow 等 Cloud 微服务边界。
- 根目录脚本只做编排，前后端仍按各自工具链独立构建。
