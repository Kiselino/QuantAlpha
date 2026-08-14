# 平台规则速查（BRAIN）

> 供 agent 生成候选与筛选时参考。权威来源：设计文档 §2 + 官方文档/论坛调研。

## 提交门槛（硬性）

| 指标 | 要求 |
|---|---|
| Fitness | ≥1.0（D1）/ ≥1.3（D0） |
| Sharpe | >1.25（D1）/ >2.0（D0） |
| Turnover | 1% ~ 70%（理想 <30%） |
| 自相关 | <0.7（Sharpe≥1.375 可豁免） |
| 子宇宙 | `subuniverse_sharpe ≥ 0.75·√(sub/alpha)·alpha_sharpe` |
| 单股权重 | <30%（目标 ≤10%） |

**ATOM 原则：** 单数据集表达（只用 1 个数据集的字段）放宽提交标准——只看最近 2Y Sharpe（USA D1>1.0）。**生成候选应优先单数据集**。

## 模拟默认设置（对齐平台）

delay=1、universe=TOP3000、truncation=0.08、decay=0、neutralization=INDUSTRY、pasteurization=ON、nanHandling=OFF、testPeriod=P1Y。

## 字段优先级（通过率实证）

**基本面 40% > 混合 12.7% > 纯技术 5.3% > 其他 0%**

- 黄金组合：`group_rank(ts_rank(x, N), subindustry)`
- decay 经验值：基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- 失败主因：LOW_SHARPE 90.7% / LOW_FITNESS 66.2% / LOW_SUB_UNIVERSE_SHARPE 51.0%

## 计分规则

- 每日最高 2000 分（通常 1-2 个高质量 alpha 即达）；相对分（看当天其他用户）
- 等级：Bronze>1000 / Silver>5000 / Gold>10000；**10000 分 → 顾问邀请资格**
- 小宇宙（TOP500/200）+ D1 比大宇宙/D0 得分更高
- 美东 3AM 结算（"日"边界按美东，非本地）

## 组合视角（alpha 非独立）

- 提交检查 `SELF_CORRELATION`：与已提交全部 alpha 日收益 max Pearson <0.7
- 低相关要靠**不同数据来源/经济逻辑**，不是调参（换窗口/中性化无效）
- 提交前可调 `/correlations/self` 免费查相关门

## 平台 API 备忘

- 数据集枚举：`GET /data-sets?region=USA&universe=TOP3000&delay=1&instrumentType=EQUITY&limit=20`
- 字段元数据：`GET /data-fields?dataset.id={id}&region=...&delay=1&universe=TOP3000&limit=50&offset={n}`（**参数名 `dataset.id` 点号写法**）
- 用户 alpha：`GET /users/self/alphas?limit=100`
- 阶段检测：`GET /users/self`（level/geniusLevel/consultant）
- 限流头：`x-ratelimit-limit-minute`（30/分）；429 区分 `THROTTLED`
- 模拟状态值：`COMPLETE`（非 COMPLETED）；is 数据在 alpha 详情

## 合规红线

1. **禁止无人值守自动提交**——提交必须展示检查 + 用户显式确认
2. 禁止分享真实表达式/账号 ID/盈亏数据（playbook 必须脱敏）
3. 允许 AI 生成初步想法、批量模拟、优化流程、复盘
4. 模拟配额内运行，不做 24h 刷量
