# AGENTS.md

> 适用于本仓库中的所有 AI Agent。
> 核心原则：最小变更、边界清晰、契约稳定、结果可验证。

## 1. 优先级

冲突时依次遵循：

1. 用户当前任务的明确要求。
2. 当前目录或更深层目录的 `AGENTS.md`。
3. 本文件。
4. 接口文档、迁移、测试和 README。
5. 当前模块已有实现与风格。

不得以“最佳实践”为理由擅自替换仓库已有架构。

## 2. 架构边界

```text
admin-api/               # FastAPI + SQLite 独立后端
  app/api/               # HTTP 路由、鉴权依赖和协议转换
  app/services/          # 业务规则
  app/repositories/      # 持久化访问
  app/schemas/           # 请求与响应模型
  app/core/              # 配置、安全和异常
  app/db/                # 数据库连接与初始化
  migrations/            # 版本化 SQL
  tests/                 # pytest 测试
docs/                    # 产品与历史文档
scripts/                 # 根命令包装
```

必须遵守：

- 当前运行时只有 `admin-api`。
- 不新增未获授权的前端、Java 后端或第二套 API 服务。
- `docs/` 中的历史资料默认保留；未经明确要求不得删除。
- API 路由保持薄层，业务规则放在 Service，SQL 访问放在 Repository/DB 层。
- Pydantic Schema 是对外请求和响应契约，数据库 Row 不直接作为公共响应。

## 3. 作业流程

开始前必须：

1. 阅读适用的 `AGENTS.md`。
2. 查看 `git status`，保留用户未提交修改。
3. 搜索最接近的已有实现。
4. 确认真实构建和测试命令，不得猜测脚本名。
5. 判断 API、数据库、配置和文档影响。

实施中必须：

- 采用最小必要变更。
- 复用现有返回结构、异常体系和安全工具。
- 保持相邻代码风格。
- 每完成一个逻辑闭环就局部验证。
- 无关问题只报告，不顺手重构。

完成后必须：

1. 检查最终 diff。
2. 清理调试代码、临时文件和无关格式化。
3. 执行 Ruff 和相关 pytest。
4. 报告未执行的验证及原因。
5. 总结行为变化、关键文件、验证结果和风险。

## 4. Python 与 FastAPI 规范

必须：

- 支持 `admin-api/pyproject.toml` 声明的 Python 版本。
- 路由层只负责协议、认证、校验和返回值。
- Service 负责业务规则和事务边界。
- Repository/DB 层负责参数化 SQL 与持久化。
- 使用 Pydantic 模型表达请求和响应。
- 使用现有 `AppError` 体系返回业务错误。
- 优先复用现有配置、安全、分页和版本快照实现。
- 日志和错误不得包含密码、Token、密钥或完整认证头。

禁止：

- 捕获异常后静默返回成功。
- 用 TODO、空实现或固定成功结果假装完成。
- 为通过测试删除认证、校验、事务或安全限制。
- 新建第二套响应包装、异常体系或 ORM。
- 无理由使用宽泛 `Any`、忽略类型问题或关闭 Ruff 规则。

## 5. 认证与安全

后台接口必须评估：

- Access Token 与 Refresh Token 的签发和吊销。
- 登录失败锁定与状态校验。
- 管理接口认证依赖。
- 对象存在性和输入校验。
- YAML 禁止可执行语义字段。
- CORS 仅允许显式配置的来源。

禁止提交真实密码、Token、AccessKey、SecretKey、私钥和生产地址。

## 6. API 契约

新增或修改接口必须确认：

- URL 和 Method。
- 认证要求。
- 请求 Schema、响应 Schema 与分页结构。
- 错误状态码和错误语义。
- 幂等、并发与历史版本影响。
- `admin-api/openapi.json` 是否需要同步生成。

修改 URL、Method、字段类型、分页结构或枚举含义属于破坏性变更，必须同步修改测试和文档。生成文件应从事实来源重新生成，不手工制造不一致。

## 7. 数据库

所有结构变更必须通过版本化 SQL 放入：

```text
admin-api/migrations/<NNN>_<description>.sql
```

必须：

- 保持迁移顺序稳定。
- 使用参数化查询。
- 评估主键、唯一约束、外键、审计时间和索引。
- 不重写已执行的历史迁移；新增后续迁移。

未经授权不得执行或提交 `DROP TABLE`、`TRUNCATE`、无条件批量 `DELETE/UPDATE`，不得删除生产字段或修改主键类型。

## 8. 配置与依赖

- 新增配置项必须更新 `.env.example` 和说明。
- 示例配置只能使用占位符或明确的本地默认值。
- 新增依赖前先确认现有依赖或标准库是否已有等价能力。
- 不得未经要求升级 Python 主版本或核心依赖。
- 不提交 `.env`、SQLite 数据文件、虚拟环境、缓存、日志或构建产物。

## 9. 验证

优先执行根脚本：

```bash
sh scripts/monorepo.sh admin:lint
sh scripts/monorepo.sh admin:test
sh scripts/monorepo.sh verify
```

直接命令：

```bash
cd admin-api
python3 -m ruff check
python3 -m pytest
```

不得在未运行命令时声称测试、检查或部署成功。

## 10. Git 安全

未经明确要求不得：

- `git reset --hard`、`git clean -fd`。
- 强制切换分支、强推或改写历史。
- 自动提交、打 Tag、合并或推送。
- 删除用户未提交修改。

不得提交 IDE 文件、缓存、日志、临时文件、数据库文件、密钥或虚拟环境。

## 11. 最终输出

任务完成后必须说明：

```text
完成内容
- 实际行为变化

主要文件
- 关键文件及用途

架构影响
- API、数据库、配置和部署影响

验证
- PASS: 已执行命令与结果
- NOT RUN: 未执行项及原因

风险
- 真实存在的剩余风险
```
