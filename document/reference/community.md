# 外部渠道经验库（community.md）

> 来源：官方论坛 / BRAIN 社区 / 教程 / 学术结论等**外部渠道**的量化研究经验（L4 层，传闻性质）。
> 与本地 `experience/playbook.md` / `failures.md`（L3，自己模拟沉淀的实证）严格区分——
> 本文件条目只能作候选方向灵感，**不能作硬约束**（见 generation-guide.md §5 四层可靠性分层）。
> 本文件随仓库公开分发——**必须遵守分享红线：不得掺入个人私有表达式、账号 ID、盈亏数据**。

## 来源分类与可信度标注

| 可信度 | 来源类型 | 说明 |
|---|---|---|
| 高 | 官方文档 / 官方论坛（平台员工发言） | 接近权威，仍建议平台模拟验证 |
| 中 | 知名社区教程 / 可查作者的文章 / 学术论文结论 | 方法可复现，结论因市场而异 |
| 低 | 匿名论坛帖 / 个人博客 / 二手转述 | 仅作方向灵感，备注标"未验证" |

## 条目格式

每条经验以一行表格记录，字段：**日期 / 方向 / 结论 / 来源 URL / 可信度 / 备注**。

- 结论必须是可检验的判断（方向 + 机制 + 边界），**不写具体 alpha 配方**
- 入库前必须展示给用户确认（对话层询问，流程见 generation-guide.md §6）
- 可信度 低 的条目在备注中标"未验证，仅灵感"

## 更新流程

1. `qa update-knowledge` 运行时 agent 询问用户"是否同时更新外部经验？"
2. 用户同意 → agent 网络调研（官方论坛 / BRAIN 社区 / 教程；先确认 cookie 有效）
3. 总结新条目 → 展示给用户确认 → 追加写入本文件

## 条目表

| 日期 | 方向 | 结论 | 来源 URL | 可信度 | 备注 |
|---|---|---|---|---|---|
| 2026-09-01 | 模拟设置 | 设置三角（decay/truncation/neutralization）相互影响；仅调 decay 5→10 即可让 Fitness 0.70→1.02（零代码改动）；decay 分级：1-3→TO 40-60%、4-7→25-40%、8-15→15-25%、15+→<15% | https://support.worldquantbrain.com/hc/en-us/community/posts/40205054470295 | 中 | 社区 Masterclass 帖；与自有实证（decay 8 期权簇）一致 |
| 2026-09-01 | Prod 检测自动化 | 社区分享本地 Prod/自相关检测代码（24h 检测 600 个、SELF_ONLY 或 PPA_AND_SELF 双阈值模式）——可作为提交前自动筛选参考 | https://support.worldquantbrain.com/hc/en-us/community/posts/36947868698519 | 低 | 未验证；L4 代码技巧，仅方向灵感 |
| 2026-09-01 | 失败 alpha 价值 | 失败 alpha 的真正价值在于分析失败原因（Sharpe 分解/ladder/换手/相关），而非成败本身——结构化归因是成长路径 | https://support.worldquantbrain.com/hc/en-us/community/posts/38186475692311 | 中 | 与项目 failures 归因机制理念一致 |
| 2026-09-01 | 算子序列 | 时序→截面（ts_rank 后 rank/group_rank）：去个股自身基线偏差、保留历史上下文；截面→时序（rank 后 ts_rank(rank(x),N)）：衡量相对地位改善/恶化 | https://support.worldquantbrain.com/hc/en-us/community/posts/42801563919895 | 中 | Deep Dive 帖；序列选择影响信号分布，生成时须有意识 |
| 2026-09-01 | decay 参数 | 反转类 alpha decay 5-8 合适、动量类 10+（效应数月）；原则=用能保持 TO<70% 的最小 decay，从低开始逐步加 | https://support.worldquantbrain.com/hc/en-us/community/posts/40782573762583 | 中 | 与自有 decay 经验值（技术 10-30）互补 |
| 2026-09-01 | 中性化 | 中性化剥离市场噪声/风险因子；sub-industry vs industry 分组选择影响相关性与 Fitness | https://support.worldquantbrain.com/hc/en-us/community/posts/38706536824855 | 中 | 社区帖；与黄金组合 subindustry 分组一致 |
| 2026-09-01 | 信号拥挤 | 热门信号随参与者增加性能衰减（Signal Crowding）——需持续寻找低拥挤信号源 | https://support.worldquantbrain.com/hc/en-us/community/posts/38706522115735 | 中 | 与"避开已提交饱和簇"策略一致 |
