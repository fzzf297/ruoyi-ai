# plus-ui 上游记录

## 来源

- 仓库：`https://github.com/JavaLionLi/plus-ui`
- 导入分支：`ts`
- 导入 Commit：`d0d451967676707021b9857df529c395b27e90a7`
- 导入日期：`2026-06-17`
- 导入路径：`apps/web`
- License：MIT，保留在 `apps/web/LICENSE`

## 实际结构与构建

- 工程类型：Vue 3 + TypeScript + Vite + Element Plus
- 包管理器：npm
- Node 要求：`>=20.19.0`
- npm 要求：`>=8.19.0`
- 主要脚本：
  - `npm run dev`
  - `npm run build:prod`
  - `npm run build:dev`
  - `npm run preview`
  - `npm run lint:eslint`

## 运行配置

- 开发端口：`VITE_APP_PORT=80`
- 开发 API 前缀：`VITE_APP_BASE_API='/dev-api'`
- 生产 API 前缀：`VITE_APP_BASE_API='/prod-api'`
- Vite Proxy：`/dev-api/**` -> `http://localhost:8080/**`
- 客户端 ID：`e5cd7e4891bf95d1d19206ce24a7b32e`

## 同步方式

1. 在仓库外部临时目录拉取上游指定分支。
2. 记录 `git rev-parse HEAD`。
3. 将文件同步到 `apps/web`，排除 `.git`、`node_modules`、`dist`、本地日志和临时文件。
4. 不手工修改上游生成文件；需要修改时优先保留局部补丁并记录原因。
5. 同步后执行根目录前端验证命令。
