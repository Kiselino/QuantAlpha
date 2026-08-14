# 量化陷阱与反过拟合

> agent 生成候选时必须考虑；供筛选与复盘参考。

## 过拟合风险

- **试验预算**：5 年日数据最多约 45 个独立变体；Novy-Marx best-k-of-n 偏误 t≥5-7
- **衰减**：样本外衰减 26%（McLean-Pontiff）；半衰期 >5 天才算稳健
- **拥挤**：避免大家都用的字段/信号（字段 `userCount` 高 = 饱和信号）
- **幸存者偏差**：delisting 平均 -30%

## 表达式设计约束（生成时）

- 算子数 ≤10，嵌套 ≤4（平台复杂度上限：算子 30、深度 8）
- 优先生成**单数据集**表达（ATOM 原则）
- 假设-因子对齐：每个候选必须有明确的研究假设（为什么这个信号有效）
- 避免规模乘子（`rank(-assets)`、`1-rank(cap)`）——易挂子宇宙测试
- 信号簇划分按**数据来源/经济逻辑**，不按算子族

## 反过拟合实践（依赖平台机制）

- 本地零回测（P1）——数据类反过拟合检查由平台模拟承担：
  - 子宇宙测试（TOP3000 → 检查 TOP1000）
  - illiquid 50% 测试（最不流动一半 after-cost Sharpe）
  - Test Period（IS 内 train/test 划分）
- 结构类控制（本地做）：AST 复杂度、去重哈希、相关性（日收益）
- 失败修复：低覆盖率用 `ts_backfill`；流动/非流动分开 decay

## 常见失败与修复

| 失败 | 修复 |
|---|---|
| LOW_SHARPE | 延长 lookback / 换基本面字段 / 黄金组合 |
| HIGH_TURNOVER | 增大 decay（技术 10-30）或 ts_rank 平滑 |
| LOW_SUB_UNIVERSE_SHARPE | 去规模乘子；流动部分分开 decay |
| CONCENTRATED_WEIGHT | 降 truncation；检查覆盖（ts_backfill） |
| LOW_FITNESS | 通常由高换手导致——先降 turnover |
