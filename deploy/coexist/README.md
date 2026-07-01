# 经典 RuoYi 与 ruoyi-ai 共存部署

两套系统**完全独立**：不同目录、不同数据库、不同进程，仅共用 80 端口（由 ruoyi-ai 的 nginx 按路径分流）。

## 你要部署的是哪个？

| 项目 | 地址 | 形态 |
|------|------|------|
| **经典 RuoYi**（你给的链接） | gitee.com/y_project/RuoYi | 单体：Thymeleaf 页面 + Java API，一个 jar |
| RuoYi-Vue（前后端分离） | gitee.com/y_project/RuoYi-Vue | Vue 前端 + Spring Boot API，调试更重 |

下文按**经典 RuoYi** 说明；若实际要 Vue 版，路径用 `/prod-api/` 反代，前端静态挂 nginx 子目录即可。

## 隔离原则（避免冲突）

| 资源 | ruoyi-ai | 经典 RuoYi |
|------|----------|------------|
| 代码目录 | `/opt/ruoyi-ai` | `/opt/ruoyi-classic`（单独 clone） |
| 数据库 | SQLite（容器卷） | MySQL（独立容器/库 `ry`） |
| 后端端口 | 8000/8001（仅 Docker 内网） | **8080 仅本机** |
| 对外入口 | nginx 路径 `/api/admin/` `/api/agent/` `/docs` | nginx 路径 `/`（其余全部） |
| 认证 | 各自独立，互不通票 | 各自独立 |

**不会冲突**：RuoYi 用 `/login`、`/system/` 等；ruoyi-ai 用 `/api/admin/`、`/api/agent/`，路径不重叠。

## 1.8G 内存调试策略

同时跑两套时建议：

```bash
# ruoyi-ai 停掉 agent，省 ~80MB
sh /opt/ruoyi-ai/deploy/debug-stack.sh

# 已加 swap
sh /opt/ruoyi-ai/deploy/add-swap.sh
```

| 组件 | 建议内存上限 |
|------|----------------|
| MySQL | 384MB |
| Java RuoYi | `-Xmx256m -Xms128m` |
| ruoyi-ai admin+nginx | ~50MB |
| agent | 调试 RuoYi 时**先不启** |

## 部署步骤（服务器）

### 1. MySQL（仅 RuoYi 使用）

```bash
mkdir -p /opt/ruoyi-classic && cd /opt/ruoyi-classic
cp /opt/ruoyi-ai/deploy/coexist/docker-compose.mysql.yml .
cp /opt/ruoyi-ai/deploy/coexist/mysql.env.example .env
# 编辑 .env 改密码
docker compose -f docker-compose.mysql.yml up -d
```

### 2. 克隆并初始化经典 RuoYi

```bash
cd /opt/ruoyi-classic
git clone https://gitee.com/y_project/RuoYi.git app
# 1.8G 机器建议用 springboot2 分支 + JDK8，比 master(SB4/JDK17) 略省资源：
# git clone -b springboot2 https://gitee.com/y_project/RuoYi.git app

cd app
# 导入 SQL（文件名以仓库 sql/ 目录为准）
docker exec -i ruoyi-classic-mysql mysql -uruoyi -p<密码> ry < sql/ry_20240601.sql
```

修改 `ruoyi-admin/src/main/resources/application-druid.yml` 指向 `127.0.0.1:3306/ry`（见 `ruoyi-application-snippet.yml`）。

`application.yml` 中 **`server.port: 8080`**，不要改 80。

### 3. 编译并启动 RuoYi（低内存）

```bash
cd /opt/ruoyi-classic/app
mvn -DskipTests package -pl ruoyi-admin -am
nohup java -Xmx256m -Xms128m -jar ruoyi-admin/target/ruoyi-admin.jar \
  --server.port=8080 > /var/log/ruoyi-classic.log 2>&1 &
```

### 4. 启用 nginx 共存

```bash
cd /opt/ruoyi-ai
sh deploy/coexist/enable-coexist.sh
```

访问：

- 经典 RuoYi：`http://<服务器IP>/`（默认 admin/admin123）
- ruoyi-ai 文档：`http://<服务器IP>/docs`

## 若你要的是 RuoYi-Vue

1. 后端仍放 `/opt/ruoyi-classic`，端口 8080，`context-path` 或前端 `VUE_APP_BASE_API=/prod-api`
2. nginx 增加：

```nginx
location /prod-api/ {
    proxy_pass http://host.docker.internal:8080/;
    # ...headers
}
location / {
    root /opt/ruoyi-vue/dist;
    try_files $uri $uri/ /index.html;
}
```

3. 前端在**本机** `npm run build` 后把 `dist/` 上传到服务器，不要在本机 1.8G 上跑 `npm run dev`。

## 与本仓库的关系

- **不会**把 Java 代码并入 `ruoyi-ai` 仓库（见 AGENTS.md 架构边界）
- `deploy/coexist/` 仅提供**共存配置模板**，RuoYi 源码与 MySQL 数据在 `/opt/ruoyi-classic`
