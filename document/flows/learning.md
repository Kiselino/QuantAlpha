# 人机交互学习（learning）

> 读取时机：**用户问"为什么/是什么"时**（教学模式中随时深问、会话中任意时刻提问）。
> 与教学模式的分工：教学模式 = 生成过程中讲解当下思路；本文件 = 系统性教学框架，
> 用户指定任意主题进入深入学习。

## 0. 合规边界（硬约束，不可违背）

- 学习素材**仅限**官方公开材料（How BRAIN Works、Simulation Settings、Submission Tests、
  Challenge 规则、零基础学量化）+ 仓库内自己的脱敏经验（playbook/templates）
- **永不收集/整理/传播面试真题、答案、题库、面经**——平台零容忍，违规直接取消资格
- 教学讲解用项目真实素材（生成过的表达式、模拟结果、失败案例），但**不分享真实 alpha
  表达式/账号数据**（讲解用结构模式 + 脱敏示例）

## 1. 定位与触发

| 触发场景 | 动作 |
|---|---|
| 教学模式生成中用户打断深问 | 进入本流程，讲清楚后回到生成 |
| 会话中任意时刻"什么是 X？" | 按四大方向定位主题 → 讲解 → 实操示例 |
| 用户说"讲讲/教教我/我不懂" | 同上；可主动推荐相关学习方向 |
| 模拟结果看不懂（PASS/FAIL 指标） | 用本批真实数据讲解指标含义 |

## 2. 四大学习方向（对齐官方学习指南）

### 方向 1：WorldQuant 与顾问项目

- 覆盖：公司背景、10K 门槛、顾问 vs 用户权限区别、顾问职责与收入构成、平台行为准则
- 素材：`document/flows/access.md`（能力矩阵/顾问路径）+ `document/reference/rules.md`（计分/行为准则）
- 讲解要点：资格与等级正交（GOLD ≠ 顾问）；排行榜排名维度；收入机制

### 方向 2：BRAIN 平台基础

- 覆盖：Alpha 是什么与运行原理（How BRAIN platform works）、Simulation Settings 各项含义、
  FASTEXPR 语言支持的语法结构
- 素材：官方 How BRAIN Works / Simulation Settings（`document/flows/update-knowledge.md` §2 访问方式）
  + 项目实操（本批候选的 settings 为什么这么选）
- 讲解要点：
  - simulation 是平台评分器不是回测；settings 各参数（decay/neutralization/truncation）影响什么指标
  - **Alpha 定义（官方 5971767795479）**：数学预测模型 = 数据字段 × 算子的组合，输出为宇宙内每只股票的权重向量
  - **平台七步操作（官方教程 how-brain-platform-works）**：市场数据视为矩阵（行=日期，列=股票）→ 按表达式逐日评估 → 每只股票取多/空仓位 → 生成 PnL 图。理解这七步帮助你判断表达式在模拟中的行为
  - **Delay 概念（官方教程 simulation-settings）**：delay = 数据可用性与交易时间的假设——D1 用昨日数据（收盘后交易），D0 用当日盘中最新数据
  - **D0 vs D1（官方教程 D0）**：D0 更快捕捉短期事件（财报惊喜/新产品公告/宏观新闻）；PnL 分解为交易 PnL + 持仓 PnL，D0 目标是捕捉更多持仓 PnL（更长持有期）与隔夜收益现象
  - **论文实现方法（官方 5971656020503）**：学术结果只是指引，用最简形式实现，再按平台机制改进

### 方向 3：数据探索与操作符

- 覆盖：数据字段分类（基本面/分析师/技术/另类）与结构差异、Data Explorer 指标含义、
  常用数据探索表达式、操作符类别与用途
- 素材：`document/reference/fields.md` + `document/reference/operators.md` + 实操表达式拆解
- 讲解要点：字段类型（VECTOR/GROUP/UNIVERSE）决定算子选择；算子类别→数据操作→目的；
  **group_neutralize vs Neutralization setting（官方 6425949726487）**：两者同一操作
  （分组减均值），但 setting 是提交前最后一步对全 alpha 做中性化（保证多空平衡），
  `group_neutralize(x, group)` 只中性化表达式的特定部分；
  **group 类算子选择（社区 38337681301143）**：`group_rank` = 组内 0-1 排名
  （"同行强弱"，抗离群）、`group_zscore` = 组内标准化、`group_neutralize` = 组内去均值

### 方向 4：回测结果与提交

- 覆盖：回测指标定义与计算（Fitness/Sharpe/TO/自相关）、提交标准与各项测试、
  提交的 do/don't、IS/OS/TEST 概念
- 素材：`document/reference/rules.md`（门槛/检查）+ 真实 PASS/FAIL 案例（`data/qa.db`）
- 讲解要点：为什么门槛是这些数值；失败归因（LOW_SHARPE/HIGH_TURNOVER/CONCENTRATED_WEIGHT）
  各自意味着什么

## 3. 教学原则

1. **讲"为什么"不讲"是什么"**——概念背后逻辑（"Sharpe 衡量信号稳定性，所以
   平台用它筛掉碰运气的结果"）
2. **用项目真实素材**：拿本批表达式/模拟结果/失败案例当教具，抽象概念落到实操
3. **可打断**：讲解中用户随时插问，不要求一口气讲完
4. **复杂度自适应**：用户理解后进阶（如从"分组归一化是什么"到"为什么 group_rank
   比 rank 稳"）
5. **结束回到流程**：教学不是独立环节——讲完回到生成/模拟/提交的主流程
6. **推荐官方自学路径**（社区帖 22863075241623 整理的官方材料顺序）：Introduction to Alphas →
   How BRAIN platform works → BRAIN Expression Language → Understanding Data →
   Data Explorer → Operators → Vector/Group Data Fields → 模拟设置与提交测试——
   与下方四大方向一致，用户可自选入口

## 4. 常见问题锚点（FAQ 索引）

| 问题 | 答案位置 |
|---|---|
| Sharpe / Fitness / TO / 自相关是什么、怎么算 | 方向 4（rules.md 门槛章节） |
| 为什么我的 alpha 总是 LOW_SHARPE | 方向 4 + `document/reference/pitfalls.md` 失败映射 |
| 分组归一化（group_rank）是什么、有什么用 | 方向 3（operators.md group 类） |
| decay 参数是干什么的、怎么选 | 方向 2 + generation.md §2d 三层决策 |
| 模拟和回测有什么区别 | 方向 2（How BRAIN Works） |
| 字段的 VECTOR/GROUP 类型是什么 | 方向 3（fields.md + operators.md 类型规则） |
| 顾问资格怎么拿、权限差在哪 | 方向 1（access.md） |
| IS/OS/TEST 是什么 | 方向 4（官方 Submission Tests） |

## 5. 学习素材获取

官方材料通过 `document/flows/update-knowledge.md` §2 调研规则获取
（cookie 验证 → Zendesk API 抓取 help center 文章 → 本地化讲解）。
外部素材源（官方推荐，5968002400663）：SSRN 论文库、stockcharts.com 技术指标入门、
零基础学量化系列——作为方向性启发，具体有效性以平台模拟为准（论文实现要义见方向 2）。
