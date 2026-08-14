# 字段元数据（精选）

- `TOP_FIELDS.json` — 每数据集 userCount 前 15 个字段（USA TOP3000 D1 维度），共数百个常用字段
- 字段对象：`{id, description, dataset, type, coverage, userCount}`
- 生成候选时：agent 应从本文件选择字段，**优先基本面数据集**（通过率最高），避免使用 `userCount` 过高的饱和字段

## 字段策略要点（平台机制实证）

- **Dataset Usage Management（数据集过度使用）**：某区域某数据集类别"过度使用"→ 该类别字段**临时禁用**（模拟+提交）+ "Overused" 警告，需向平台申请恢复 → **字段策略必须分散多数据集，不能死磕单一类别**
- **Vector 字段**（nws/scl 等 VECTOR 类型）：不能直接用于标量表达式，需 `vec_*` 算子转换；原始 turnover 高，须 `ts_rank`/`ts_decay` 降频

## 字段元数据完整结构（USA 全量 8642 个，供 agent 生成时参考）

- 完整字段对象：`{id, description, category, type, coverage, userCount, alphaCount, themes, dateCoverage, subcategory, region, delay, universe}`
- 类型分布：MATRIX 6794 / VECTOR 1696 / GROUP 142 / UNIVERSE 6 / SYMBOL 4；coverage 均值 0.747
- 数据集规模分布（USA 21 数据集）：model77(3256) > analyst4(1324) > fundamental6(886) > news12(875) > fundamental2(766) > earnings4(375) > fundamental7(311) > 其余 <200
- 可基于 `userCount`（饱和度高）/`coverage`（覆盖度）/`alphaCount`（已被用次数）筛选"热门但少人用"字段，驱动字段多样性

> 全量 8642 字段元数据在私有调研资产中；`qa update-knowledge`（第三批）可重新抓取。
