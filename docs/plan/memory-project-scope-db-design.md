# 全局记忆与项目记忆数据库设计

--- 由 pg-db-design V1.2 生成 ---

## 目标

为现有 `memories` 表增加项目范围。`project_path IS NULL` 表示全局记忆；非空值表示仅属于规范化绝对路径对应项目的记忆。

## 表结构变更

| 表 | 字段 | 类型 | 可空 | 含义 |
| --- | --- | --- | --- | --- |
| memories | project_path | varchar(1024) | 是 | 规范化绝对项目路径；NULL 为全局 |

新增联合索引 `idx_memories_user_project_status(user_id, project_path(191), status)`，覆盖按用户、项目范围和有效状态查询。MySQL 对长 varchar 使用 191 字符前缀，完整路径仍由查询条件精确比较。

```sql
ALTER TABLE memories
  ADD COLUMN project_path VARCHAR(1024) NULL;

CREATE INDEX idx_memories_user_project_status
  ON memories (user_id, project_path(191), status);
```

## 数据与兼容策略

- 旧数据新增字段后为 `NULL`，自动成为全局记忆，不需要批量回填。
- 应用启动时检查列和索引，只在缺失时执行兼容迁移。
- Windows 路径统一转成小写正斜杠形式，例如 `D:\\Work\\Demo` 存为 `d:/work/demo`；POSIX 路径保留大小写并规范化。
- Milvus 同步增加 `project_path` 标量字段，空字符串表示全局，以便向量召回阶段先完成范围过滤。

## 合规与存量偏差

本次是棕地兼容变更，沿用现有 UUID 字符串主键、`created_at/updated_at` 审计字段和既有索引命名，不扩大为全表重构。新增字段、索引命名及 MySQL 字符集策略与项目现状兼容。
