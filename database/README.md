# 数据库

当前业务表结构和初始化数据复用 `RuoYi-Cloud-Plus` 上游 SQL。

## 上游 SQL

| 数据库 | SQL |
|--------|-----|
| `ry-cloud` | `services/cloud/script/sql/ry-cloud.sql` |
| `ry-job` | `services/cloud/script/sql/ry-job.sql` |
| `ry-workflow` | `services/cloud/script/sql/ry-workflow.sql` |
| `ry-seata` | `services/cloud/script/sql/ry-seata.sql` |

`ry-config.sql` 用于 Nacos 外置数据库配置场景。

## 后续迁移

新增业务数据库变更统一放入：

```text
database/migration/VYYYYMMDD_NNN__description.sql
```

不得重写已经执行过的历史迁移。当前整合不新增业务表，不新增迁移脚本。
