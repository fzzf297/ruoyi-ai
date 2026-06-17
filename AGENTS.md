# AGENTS.md

> 适用于本 Monorepo 中所有 AI Agent。
> 核心原则：最小变更、边界清晰、契约稳定、结果可验证。

## 1. 优先级

冲突时依次遵循：

1. 用户当前任务的明确要求。
2. 当前目录或更深层目录的 `AGENTS.md`。
3. 本文件。
4. ADR、接口文档、测试、README。
5. 当前模块已有实现与风格。
6. 上游项目约定。

不得以“最佳实践”为理由推翻仓库已有架构决策。

## 2. 架构边界

```text
apps/web/                 # plus-ui
services/cloud/           # RuoYi-Cloud-Plus
database/                 # 数据库脚本
infra/                    # 部署配置
docs/                     # 文档与 ADR
```

必须遵守：

- 前端、Cloud 后端保持独立构建边界。
- 本仓库不引入 `RuoYi-Vue-Plus`，不创建 `services/monolith`。
- Cloud 后端保持独立 Maven Reactor。
- 禁止用根 POM 聚合 Cloud 后端模块。
- 前端只有一套，只依赖统一外部 API。
- 不修改 Cloud 原有微服务边界。

## 3. 主后端

仓库通过以下配置标识当前主后端：

```text
BACKEND_MODE=cloud
```

允许值：`cloud`。

默认：

- 未指定时按 `cloud` 处理。
- 一个需求只修改 Cloud 后端。
- 未经明确要求，不得引入或修改单体后端。
- 最终结果必须说明是否影响统一 API 与 Cloud 微服务边界。

## 4. 作业流程

开始前必须：

1. 阅读适用的 `AGENTS.md`。
2. 查看 `git status`，保留用户未提交修改。
3. 搜索最接近的已有实现。
4. 确认 `BACKEND_MODE`。
5. 确认真实构建命令，不得猜测脚本名。
6. 判断前端、后端、数据库、配置和部署影响。

实施中必须：

- 采用最小必要变更。
- 复用现有工具、组件、返回结构和异常体系。
- 保持相邻代码风格。
- 每完成一个逻辑闭环就局部验证。
- 无关问题只报告，不顺手重构。

完成后必须：

1. 检查最终 diff。
2. 清理调试代码、临时文件和无关格式化。
3. 执行相关测试、类型检查或构建。
4. 报告未执行的验证及原因。
5. 总结行为变化、关键文件、验证结果和风险。

## 5. 禁止事项

Agent 不得：

- 猜测文件、表、字段、权限、字典或配置。
- 编造不存在的工具类、接口、注解、组件或脚本。
- 用 TODO、空实现或固定成功结果假装完成。
- 捕获异常后静默返回成功。
- 为通过编译删除权限、租户、数据权限、校验或事务。
- 修改与任务无关的文件。
- 全仓批量格式化或批量重命名。
- 未经要求升级框架、依赖、JDK 或 Node 主版本。
- 擅自拆分、合并服务或切换主后端。
- 未验证就声称测试、构建或部署成功。

无法确认时必须先搜索仓库；仍无依据时采用最保守实现并说明假设。

## 6. 代码边界

新增能力放置规则：

- 单一业务使用：业务模块。
- 多业务稳定复用且无业务语义：公共模块。
- Cloud 跨服务契约：对应 `ruoyi-api` 模块。
- 前后端共享契约：`packages/contracts` 或 OpenAPI 生成。
- 无法判断：默认放业务模块。

禁止循环依赖、为单一需求污染公共模块，以及替换现有核心技术栈。

## 7. Java 规范

分层沿用当前模块：

```text
controller
domain/bo
domain/vo
domain/entity
mapper
service
service/impl
```

必须：

- Controller 只负责协议、权限、校验和返回值。
- Service 负责业务规则与事务。
- Mapper 负责持久化。
- BO 用于输入，VO 用于输出。
- Entity 不直接作为公共 API 请求或响应。
- 优先使用构造器注入和 `@RequiredArgsConstructor`。
- 沿用 `R<T>`、`TableDataInfo<T>`、`PageQuery`。
- 沿用 Sa-Token、Jakarta Validation、MyBatis-Plus、MapStruct Plus 和现有异常体系。
- 查询参数化，避免 N+1。
- 事务放在 Service 层。
- 日志不得包含密码、Token、验证码或密钥。

禁止创建第二套响应包装、异常体系、ORM 或对象映射框架。

## 8. 权限与租户

后台业务必须评估：

- 接口和按钮权限。
- 对象级权限。
- 数据权限。
- 租户隔离。
- 缓存 Key 的租户维度。
- 批量操作的逐条权限。

禁止：

- 仅靠前端隐藏按钮授权。
- 全局关闭租户或数据权限。
- 修改、删除接口跳过对象权限校验。
- 批量接口只校验第一条数据。

## 9. 单体后端（本仓库不启用）

本仓库只使用 `plus-ui + RuoYi-Cloud-Plus`，不得新增 `services/monolith` 或引入 `RuoYi-Vue-Plus`。

如用户明确要求新增单体后端，必须先作为架构变更重新评审，不得在普通业务任务中执行。

## 10. Cloud 后端

适用于 `services/cloud`。

- 新服务放入 `ruoyi-modules/ruoyi-<domain>`。
- 跨服务契约放入 `ruoyi-api/ruoyi-api-<domain>`。
- 服务不得依赖其他服务的实现模块、Mapper、Entity 或 ServiceImpl。
- 不得通过共享表绕过服务边界写入其他服务数据。
- 远程调用必须使用专用 DTO，明确失败、超时、重试和幂等。
- 批量场景必须提供批量接口，禁止循环 RPC。

Cloud 外部路径与内部路径可能不同。修改 API 时必须同时检查：

- Gateway Route 与 `StripPrefix`。
- 服务内部 Controller。
- 白名单。
- 前端 API。
- OpenAPI 聚合路径。
- Nginx 或外层代理。

修改 Cloud 配置时必须同步检查 Nacos、部署配置和示例配置。

未经明确架构任务，不得新增服务、修改服务名或 Gateway 前缀。

## 11. 前端规范

适用于 `apps/web`。

沿用当前 Vue 3、TypeScript、Vite、Element Plus、Pinia、Router、Axios、UnoCSS、ESLint 和 Prettier 配置。

必须：

- HTTP API 和类型放在 `src/api`。
- 页面不得创建独立 Axios 实例。
- 请求和响应必须有明确类型。
- 优先复用现有表格、分页、弹窗、上传、字典和权限组件。
- 处理请求失败和重复提交。
- 大列表分页或虚拟化。
- 关键业务规则必须由后端保证。

禁止：

- 无理由使用 `any`、`@ts-ignore` 或大量类型断言。
- 硬编码后端主机、Gateway/Nacos 服务名或内部 Controller 路径。
- 切换后端模式时修改业务页面 URL。

## 12. API 契约

新增或修改接口必须确认：

- 外部 URL 和 Method。
- 权限标识。
- 请求 BO、响应 VO。
- 分页结构。
- 幂等要求。
- 租户和数据权限。
- 错误语义。
- Cloud Gateway 外部路径与服务内部路径映射。

修改 URL、Method、字段类型、分页结构、权限标识或枚举含义属于破坏性变更，必须同步修改前端、OpenAPI、测试和文档。

生成文件不得手工修改，应修改事实来源后重新生成。

## 13. 数据库

所有变更必须通过版本化 SQL：

```text
database/migration/VYYYYMMDD_NNN__description.sql
```

必须：

- 提交结构与必要初始化数据脚本。
- 保持业务表结构唯一事实来源。
- 评估主键、租户、审计、软删除、状态和索引。
- 说明破坏性迁移影响与回滚方式。

未经授权不得执行或提交：

- `DROP TABLE`、`TRUNCATE`。
- 无条件批量 `DELETE`、`UPDATE`。
- 删除生产字段或修改主键类型。
- 重写已执行的历史迁移。

Cloud 各服务共用业务表时，不得维护两份不一致的迁移。

## 14. 配置与依赖

必须区分 `local`、`dev`、`test`、`prod`。

禁止提交真实密码、Token、AccessKey、SecretKey、私钥、OAuth Secret 和生产内网地址。

新增配置项必须更新示例配置，并提供说明、默认值或环境变量占位符。

新增依赖前必须确认仓库是否已有等价能力。

Java 版本统一由父 POM、BOM 或 properties 管理。

前端必须使用现有包管理器和 lockfile，禁止生成第二种 lockfile。

## 15. 验证

“代码看起来正确”不算完成。

Java：

- 优先使用 Maven Wrapper。
- 只验证受影响模块及其依赖。
- 真正运行测试时必须显式使用 `-DskipTests=false`。

示例：

```bash
mvn -f services/cloud/pom.xml -pl <module> -am test -DskipTests=false -Pdev
```

不得仅看到 `BUILD SUCCESS` 就声称测试已执行。

前端根据现有脚本执行相关项：

- ESLint。
- TypeScript 类型检查。
- 生产构建。

缺少数据库、Redis、Nacos、MQ 或外部服务时，必须说明已验证项、未验证项、所缺环境、推荐命令和剩余风险。

## 16. Git 安全

未经明确要求不得：

- `git reset --hard`、`git clean -fd`。
- 强制切换分支、强推或改写历史。
- 自动提交、打 Tag 或合并。
- 删除用户未提交修改。

不得提交本地环境文件、IDE 文件、构建产物、日志、临时文件、数据库备份、密钥、`node_modules` 或 `target`。

## 17. 文档

新模块、服务、环境变量、端口、依赖服务、Gateway 路由、数据库迁移、破坏性 API、部署方式、主后端模式或上游版本发生变化时，必须同步文档。

重大架构决策必须新增或更新 ADR。

## 18. 最终输出

任务完成后必须说明：

```text
完成内容
- 实际行为变化

主要文件
- 关键文件及用途

架构影响
- BACKEND_MODE
- 是否影响另一套后端
- 是否影响统一 API
- 是否修改上游核心

验证
- PASS: 已执行命令与结果
- NOT RUN: 未执行项及原因

风险
- 真实存在的剩余风险
```

## 19. 默认决策

除非用户或 ADR 明确覆盖：

1. 默认 `BACKEND_MODE=cloud`。
2. 新业务只修改 Cloud 后端。
3. Web 前端保持唯一。
4. 外部 API 一致，内部实现可不同。
5. Cloud 后端保持独立 Maven Reactor。
6. 不引入 `RuoYi-Vue-Plus` 或 `services/monolith`。
7. 新业务进入独立业务模块。
8. 不进行无关重构、框架升级或批量格式化。
