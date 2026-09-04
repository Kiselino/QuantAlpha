# 1 周速考计划（plan-1wk）

> 适用：已有平台使用经验/时间紧迫者（每日 3-4h）。每日按 protocol 五步闭环执行。
> **公开模板**：复制到本地 `docs/bootcamp/` 运行（个人副本可在下方"实际议程"记录进度）。
> 教材引用 `document/courses/`；每模块对应 mastery.json 考点组。

## 日程总览

| 天 | 主题 | 教材 | 目标考点 |
|---|---|---|---|
| D1 | 诊断摸底 + M1 顾问项目 | lesson1_program、official_read-first-starter-pack + reference/rules.md（顾问路径/考核段） | wq-* 14 考点 |
| D2 | M2 平台机制（原理/设置/计算） | official_how-brain-platform-works、official_simulation-settings、lesson3_neutralization（§中性化公式）、official_test-period | plat-* 18 考点 |
| D3 | M3 数据算子 | official_data、official_how-use-data-explorer、official_vector-datafields、official_group-data-fields、lesson2_expression（§定量探测）、lesson3_neutralization（§分组） | data-* 12 考点 |
| D4 | M4 指标/提交/质量 | official_alpha-submission、official_parameters-simulation-results、official_how-pass-sub-universe-test、lesson4_quality + reference/pitfalls.md（回测效率/过拟合） | metric/submit/quality 考点 |
| D5 | 综合轮（官方作业题 + 错题） | homework_course1/2/3、private/错题本 | 全模块（错题优先） |
| D6 | 模拟笔试（90min ~20 题） | mock_exam/笔试卷 | 全模块 |
| D7 | 模拟面试（30min）+ 冲刺补漏 | mock_exam/面试卷 + qa.db 真实记录 | 全模块弱项 |

## 各天执行要点

- **每日 alpha 复盘（D2 起，15-20min，所有学习日固定环节）**
  - 目的：面试可能问"讲讲你提交过的 alpha"（官方：确认本人实际参与研究）——把 agent 生成的 alpha 变成"自己的"
  - 素材：`data/qa.db` submissions 12 条真实提交记录（hypothesis/expression/dataset_ids 全有），每日 1 条顺序过
  - 流程：读记录 → 用自己的话回答四问 → agent 扮演面试官追问 2-3 个"为什么"
    1. 这个 alpha 的假设（hypothesis）是什么？想抓什么市场现象？
    2. 表达式结构如何实现假设？（字段族 + 算子 + 关键设置）
    3. 结果如何？（提交状态/平台反馈/相关门表现）
    4. 如果现在重做，哪里会改？为什么？
  - 产出：每条约 3-5 句"一句话讲稿"（存 private/alpha_pitch.md，脱敏个人用）
- **D1 上午流程**：四模块摸底抽测（protocol §3，20-25 题，可放宽到 40-60min）→ 出基线报告 → 剩余时间精学 M1（公司/顾问计划/Knowledge Quiz/行为准则）→ 自测 wq-* 5 题
- **D2 核心**：Alpha 运行七步复述（费曼）+ 模拟设置逐项（decay/neutralization/truncation/delay/testPeriod）+ **中性化计算题**（权重流程：减均值→abs 求和→相除）+ trade_when 例题
- **D3 核心**：matrix vs vector（视频原话：知识问卷考点）+ 字段类型规则 + 定量探测法（Six Ways 逻辑链）+ group 字段 densify + bucket
- **D4 核心**：Fitness 公式默写解释 + 提交门槛数值表 + 全套 check 名称含义 + IS/OS/TEST + 质量四原则 + 质量分机制（0.5 默认/泥潭效应/1.5 美元法则）
- **D5**：官方作业题 3 份限时做（各 30-40min）→ 对照答案要点（agent 判分）→ 错题清扫（全部 status=学习中 的考点快速过）
- **D6**：闭卷计时；判分后只补 <6 分考点
- **D7**：面试情境模拟——注意"讲你自己的 alpha"环节用 `qa.db`/`qa report --daily` 真实数据（讲 hypothesis/结构/为什么有效/失败经历）；结束后输出"面试注意清单"

## 实际议程（个人副本中记录，公开模板留空）

| 日期 | 天 | 完成情况 | 得分率 | 达标考点数/60 |
|---|---|---|---|---|
| | | | | |
