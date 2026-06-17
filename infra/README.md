# 基础设施

基础设施配置优先复用 `RuoYi-Cloud-Plus` 上游脚本。

## Docker

- Compose：`services/cloud/script/docker/docker-compose.yml`
- 附加数据库示例：`services/cloud/script/docker/database.yml`
- Nginx：`services/cloud/script/docker/nginx/conf/nginx.conf`
- Redis 配置：`services/cloud/script/docker/redis/conf/redis.conf`

启动基础服务：

```bash
npm run cloud:infra:up
```

停止基础服务：

```bash
npm run cloud:infra:down
```

## Nacos

配置来源：

```text
services/cloud/script/config/nacos/
```

需要导入 `*.yml` 和 `seata-server.properties` 到 `dev` namespace、`DEFAULT_GROUP`。

## 注意事项

- 上游 Docker Compose 使用 `network_mode: host`。
- 上游挂载路径为 `/docker/...`。
- Windows 原生 Docker Desktop 可能需要额外适配；优先使用 WSL2/Linux Docker 环境。
- 启动服务前必须校对 MySQL 密码和 Nacos `datasource.yml` 密码一致。
