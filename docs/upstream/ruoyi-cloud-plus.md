# RuoYi-Cloud-Plus 上游记录

## 来源

- 仓库：`https://github.com/dromara/RuoYi-Cloud-Plus`
- 导入分支：`2.X`
- 导入 Commit：`ce0dd0d9412ab3d1d0d4829ce3719fe8b5239976`
- 导入日期：`2026-06-17`
- 导入路径：`services/cloud`
- License：MIT，保留在 `services/cloud/LICENSE`

## 实际结构与构建

- 工程类型：Spring Boot / Spring Cloud Maven 多模块工程
- 版本：`2.6.2`
- Java：`17`
- Maven Wrapper：无，使用本机 `mvn`
- 根 POM 模块：
  - `ruoyi-auth`
  - `ruoyi-gateway`
  - `ruoyi-gateway-mvc`
  - `ruoyi-visual`
  - `ruoyi-modules`
  - `ruoyi-api`
  - `ruoyi-common`
  - `ruoyi-example`
- 根 POM 默认：`<skipTests>true</skipTests>`

## 运行配置

主要端口：

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

Nacos 配置来源：`services/cloud/script/config/nacos`。

Gateway 路由来源：`services/cloud/script/config/nacos/ruoyi-gateway.yml`。

SQL 来源：`services/cloud/script/sql`。

Docker Compose 来源：`services/cloud/script/docker/docker-compose.yml`。

## 同步方式

1. 在仓库外部临时目录拉取上游 `2.X` 分支。
2. 记录 `git rev-parse HEAD`。
3. 将文件同步到 `services/cloud`，排除 `.git`、`target`、本地日志和临时文件。
4. 不合并 Gateway、Auth、System、Resource、Workflow 等服务边界。
5. 不创建根 Maven 聚合 POM。
6. 同步后执行根目录后端编译和测试命令，测试必须显式 `-DskipTests=false` 并检查 Surefire 实际测试数。
