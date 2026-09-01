# 经验沉淀（experience）

> 读取时机：**run/submit 结束后**（沉淀规则）+ **生成前**（知识加载，见 generation.md §2b）。
> 本文件定义经验如何自动/手动沉淀，以及**模版总结**环节（v1.7 新增）。

## 1. 沉淀体系概览

| 数据 | 位置 | 内容 | 写入时机 |
|---|---|---|---|
| 成功方法论 | `experience/playbook.md` | 脱敏成功经验（方向+结论+参数经验） | 模拟 PASS / 提交成功（自动） |
| 失败教训 | `experience/failures.md` | 归因失败 + 一句修复建议 | 模拟 FAIL / 提交被拒（自动） |
| 字段知识 | `experience/fields/` | 账户专属字段元数据（update-knowledge 生成） | 手动/首次运行 |
| 审计记录 | `data/audit/` | 操作审计 | 自动 |
| 候选/模拟/提交记录 | `data/qa.db` | 全量历史 | 自动 |
| 每日汇总 | `reports/daily/` | 每日候选清单 | `qa report --daily` |
| **有效模版** | `document/reference/templates.md` | **脱敏结构模式（v1.7）** | **模版总结环节（手动触发）** |

所有自动沉淀幂等去重（SQLite + markdown 双写）。**私有数据一律留在本地
（gitignored），公开文档只进脱敏后的结构模式。**

## 2. playbook 写入规则（自动）

- 模拟 PASS → `_sediment_lesson`：方向 + 结论 + 参数经验，**脱敏**（不写真实表达式/字段依赖）
- **双读者化**：agent 读方法论、用户读结论——报告与学习要点标注
  "本候选基于 playbook \<日期\> \<条目\>"

## 3. failures 写入规则（自动）

- 模拟 FAIL → `_sediment_failure`：按失败名给**一句修复建议**（查 rules.md 失败→修复映射表：
  LOW_SHARPE → 延长 lookback/换基本面；HIGH_TURNOVER → 增大 decay；
  CONCENTRATED_WEIGHT → 降 truncation/ts_backfill）
- 提交被拒 → 前缀区分（`corr_`/`sub_` vs `f_`），归因统计分离

## 4. 模版总结环节（v1.7，手动触发）

**触发时机**：PASS alpha 积累后（如每 5-10 个 PASS）、或用户说"总结模版/沉淀模版"时。

**执行流程**：

1. 读取近期 PASS alpha（`data/qa.db` / `qa report --daily` 汇总）
2. 提取**可复用结构模式**：算子组合骨架 + 适用场景（数据集类型/字段族）+ 参数经验值
   （decay/中性化/截断）
3. 与 `document/reference/templates.md` 现有条目比对：同构合并（保留更多案例数）、
   新结构新增条目
4. **脱敏检查**：只写结构模式，不写真实 alpha 表达式/字段依赖/账号数据
5. 追加/更新条目 → 提交时随 `document/` 一起入库

**合规边界**：模版 = 结构模式（如"黄金组合 `group_rank(ts_rank(x,N), subindustry)`"），
**永不写真实 alpha 表达式/字段依赖**（平台分享红线 + 个人信息约定）。

## 5. 学习要点输出（run 结束后，对话层约定）

```
[学习要点] 今日批次（N 候选 / M PASS / K FAIL）
1. 验证的假设: ……（成功/证伪）
2. 关键失败原因: LOW_SHARPE ×n / 相关门 ×n / ……
3. 新学到/复用的技巧: ……（分体 decay / ts_backfill / 避开饱和簇）
4. 明日方向建议: ……
```

教学模式/随机模式必须输出；快速模式不主动输出（用户要求时补充）。
