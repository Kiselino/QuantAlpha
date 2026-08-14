# 字段元数据（精选）

- `TOP_FIELDS.json` — 每数据集 userCount 前 15 个字段（USA TOP3000 D1 维度），共数百个常用字段
- 字段对象：`{id, description, dataset, type, coverage, userCount}`
- 生成候选时：agent 应从本文件选择字段，**优先基本面数据集**（通过率最高），避免使用 `userCount` 过高的饱和字段

> 全量 8642 字段元数据在私有调研资产中；`qa update-knowledge`（第三批）可重新抓取。
