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

## 平台报错快速映射（Help Center 错误信息大全精选）

| 报错/提示 | 含义与修复 |
|---|---|
| `DAILY_SIMULATION_LIMIT_EXCEEDED` | 每日模拟限额，美东时间重置，明日再试 |
| "Alpha better suited for Delay 1" | D1 Sharpe 高于 D0 → 建议提交 D1（成本更低） |
| "表达式过复杂" | 算子调用超限（上限 30/深度 8），简化 |
| "未知字段/变量" | 字段在该区域/延迟不覆盖，换字段 |
| "保留字冲突" | 避免保留字作字段名 |
| "必须 ≥10 个成分 alpha（SuperAlpha）" | Super 提交前先凑足成分 |
| 均值回归警告 | 信号有均值回复特性，注意方向选择 |
| "Overused"（数据集警告） | 该数据集类别过度使用，临时禁用（见 fields/README.md） |

## 权威修复文章索引（Help Center 文章 ID，登录后可查）

| 主题 | 文章 ID |
|---|---|
| 错误信息大全（~40 种报错对照） | `18423410021783` |
| better Fitness | `20251386376471` |
| better Correlation | `20251385275671` |
| better Ladder | `6726865162903` |
| better Return | `20251364149655` |
| better Sharpe | `20251383456663` |
| better Sub-universe Sharpe（含 NaN 公式） | `6568644868375` |
| better Turnover | `20251419309719` |
| Weight Coverage | `19248385997719` |
| 术语表 | `4902349883927` |
| HCAC 评分 | `26743191705879` |
| Power Pool 主题 | `38927747787031` |

## 特殊字段与机制

- **Vector 字段（nws/scl 等）**：需 `vec_*` 算子转矩阵；原始 turnover 可达 130-200%，必须加 `ts_rank`/`ts_decay` 降频
- **不流动 50% 测试**：交易成本后最不流动 50% 的 Sharpe ≥ **52.5%** 原始 Sharpe；修复：提高不流动部分权重、分开 decay、`group_neutralize()`/`vector_neut()` 对规模/流动性因子中性化
- **权重测试细节**：单股 ≤10% book size（truncation 0.1 即 10% 上限）；长/短边 <10 只或总数 <20 只易失败；低覆盖率：`group_count(is_nan(a),market)>40?a:nan`、`ts_backfill(a,2)`（日数据）、`ts_backfill(a,60)`（季频基本面）
- **算子族饱和**：每个算子族 3-5 个 ACTIVE 后 SELF_CORRELATION 拦截（社区经验）——跟踪已提交信号簇分布，**换簇不换参**

## 已证伪概念（勿再投入）

- 无 delay-2、无 "FastSim"、无 equal/volume weighting 开关（delay 只有 0/1）
- "付费保留名额"政策不存在
- 无官方公共 SDK（顾问专属）；无公开封号案例（不代表安全——ToS 禁止自动化）
