# Alpha 生成与优化操作指南（generation）

> 定位：面向任何 agent 工具（opencode / claude code / codex）的候选生成与优化操作手册。
> 随仓库公开分发，与具体工具无关。**生成候选前必须通读本指南**。
> 读取时机：进入生成环节前（`AGENTS.md` 导航表）。
> 启动与模式询问见 `document/flows/startup.md`；用户 vs 顾问权限见 `document/flows/access.md`；
> 用户深问概念时见 `document/flows/learning.md`。

---

## 1. 三模式执行细则（启动时三选一）

> 启动流程 `document/flows/startup.md` §5 询问运行模式；会话中可随时口头切换。
> **教程未通过者**（startup.md §4 检查 6）：进入生成前先完成当日 bootcamp 学习段；教学模式与学习闭环自然融合（讲概念即补知识），随机/快速模式在批次间隔插入学习段。教材 `document/courses/`、闭环协议 `document/courses/bootcamp/protocol.md`（个人档案在本地 gitignored `docs/bootcamp/`）。

### 1.1 教学模式（人机交互学习核心）

**定位**：边做边学——agent 主导"教学式生成"，每环节先讲概念（为什么），用户确认理解后再执行。

**执行要点**：

1. 进入生成前：讲解本批主题背后的核心概念（如"动量信号为什么用 `ts_rank`"），
   用户理解后进入六环节（§2）
2. 六环节每步先给出**一句话原理**（"这一步是把输入固化成硬约束，避免生成跑偏"），再执行
3. 用户可随时打断深问（"`ts_decay_linear` 和 `ts_mean` 有什么区别？"）——
   进入 `document/flows/learning.md` 教学流程，讲清楚后回到生成
4. 模拟结果输出后：逐条讲解 PASS/FAIL 含义（"LOW_SHARPE 说明信号不稳定，通常
   换更长窗口或换基本面字段"），归因讲解见 §4
5. 每轮结束输出"今日学习要点"（验证了什么/证伪了什么/明天怎么调）

**节奏**：宁慢勿快，以用户理解为先；候选数量可减至 5-10 个/批。

### 1.2 随机模式（快速探索 + 顺带教学）

**定位**：随机主题快速探索，期间穿插讲解，节奏比教学模式快。

**执行要点**：

1. 主题来源：`qa suggest` 随机抽取（启动时已询问，见 startup.md §5）
2. 按六环节（§2）正常生成，**每批开头与结尾各给 1-2 句要点讲解**（主题思路 +
   本批学到了什么），不逐候选讲解
3. 用户追问时同样转 `document/flows/learning.md` 深入教学
4. 模拟结果输出后给一句话归因总结（PASS 由什么结构贡献 / FAIL 疑似什么原因）
5. 每轮结束输出"今日学习要点"（简版）

### 1.3 快速模式（高价值复用，两引擎任选/组合）

**定位**：用户有正事，agent 后台跑。**主题与方向来自历史数据，不询问用户**。
两引擎可任选或组合，agent 按可用素材自主决策：

| 引擎 | 素材来源 | 动作 |
|---|---|---|
| a. 主题深挖/发散 | `data/qa.db` 历史高 Fitness/高通过率主题（`qa report --daily` 汇总可辅助） | 深挖：同主题换字段族/窗口/中性化变体；发散：迁移到相似数据集族 |
| c. 模版生成 | `document/reference/templates.md` 有效模版库 + `document/courses/` 官方示例 | 选模版 → 套字段/数据集 → 生成变体（模版含参数经验值） |

> 失败优化（原引擎 b）**已并入常规迭代**（§4：失败 → 优化 = 下一个生成批次的自然组成），不再作为快速模式独立引擎——避免与正常迭代重复。

**循环结构（默认最多 10 轮）：**

```
每轮：选引擎（有模版优先 c；否则 a）
     → 读知识（§2b 顺序）→ 生成 10-15 候选
     → 写入 data/candidates/YYYY-MM-DD-quick-N.json → qa run
```

- **输出纪律**：每轮只输出一行进度：
  `[轮次 N/10] 引擎：c(模版 T1) | 模拟 M 个 | PASS K | 最佳 Fitness/S`
- **主题止损**（引擎 a 每主题最多两批）：
  1. 第一批全灭 → 读本批 failures 归因 → 调参/同方向变体 → 生成 `-opt.json` 再跑一次
  2. 优化批仍无 PASS 且 **Fitness < 0.75 且 Sharpe < 1.0**（双低判定）→ 止损换主题
  3. 优化批出现 Fitness ≥ 0.75 **或** Sharpe ≥ 1.0 → 视为接近标准，允许再续一轮优化
- **提前停止**：出现 PASS（自动暂存）→ 立即结束循环，输出完整摘要
- **强制停止**：429/THROTTLED/配额受限/用户打断 → 停止并报告现状
- **结束输出**：完整摘要（每轮引擎/主题+结果、PASS 候选指标、暂存清单）→ 等用户确认提交
- **合规**：提交仍需逐条人工确认（红线不变）；经验沉淀照常但不主动展示；
  教学讲解不主动输出，用户要求时再补充

---

## 2. 生成流程六环节

生成候选不是自由发挥，而是按以下六环节执行的有约束研究流程。

### a. 输入：把对话产物固化为硬约束

生成前先把 4 轮对话产物明确下来，作为本批候选的**硬约束**：

| 维度 | 选项 | 说明 |
|---|---|---|
| 方向 | 多 / 空 / 双向 | 信号预期方向，决定表达式取正/取负 |
| 时间尺度 | 5-20d / 20-60d / 60-252d | 决定 `ts_*` 窗口参数 |
| 载体 | 价格 / 波动 / 基本面 | 决定字段族选择 |
| 风险偏好 | 保守 / 均衡 / 激进 | 决定复杂度与换手容忍度 |

- 所有候选必须满足四项硬约束；与用户约束冲突时以用户最新要求为准（见 §5 用户覆盖原则）。
- **生成前追问机制**（对话层约定，默认开启可跳过）：用户提想法后，先追问 2-3 个封闭问题
  （方向？时间尺度？载体？）→ 给出 2-3 个候选方向并附解释 → 用户挑选 → 再生成。

### b. 知识加载顺序

按固定顺序加载知识（先"什么有效/无效"，再"有什么可用"）：

1. `experience/playbook.md` —— 什么**有效**：成功方法论；**生成/优化时引用条目号**
   （双读者化：报告与学习要点标注"本候选基于 playbook \<日期\> \<条目\>"）
2. `experience/failures.md` —— 什么**无效**：已证伪死路，直接避开，不重复投入
3. `experience/fields/top_fields.json` —— 每数据集 userCount top 15，选字段的起点
4. `document/reference/operators.md` —— 67 算子语法 / 参数 / 官方示例
5. `experience/fields/fields.json` —— 全量字段白名单 + 类型（validate 预检依据）
6. `document/reference/templates.md` —— 有效模版库（快速模式引擎 c 必读，其余模式可参考）

### c. 字段与表达式

**想法 → 字段族映射**（选字段先看数据集前缀）：

| 想法 | 字段族 |
|---|---|
| 价值 / 质量 / 成长 | `fundamental*`（基本面） |
| 预期修正 / 盈利惊喜 | `analyst*`、`earnings*`（分析师） |
| 新闻漂移 / 情绪反转 | `news*`、`socialmedia*`、`sentiment*`（另类） |
| 趋势 / 反转 / 低波动 | `pv*`、`option*`、`model*`、`univ*`（价格/波动/技术） |

- **黄金组合**：`group_rank(ts_rank(x, N), subindustry)`（基本面字段效果最好）
- **单数据集优先（ATOM）**：单数据集表达放宽提交标准（只看 2Y Sharpe D1>1）
- **复杂度**：平台上限 算子 ≤30 / 深度 ≤8；推荐 ≤10 / ≤4（更稳）
- **每候选一条可证伪假设**：写成"如果 X 成立则 Y 信号有效"，失败时能明确归因
- 常用算子子集（validate 白名单内的核心集）：`ts_rank` / `ts_mean` / `ts_delta` /
  `ts_decay_linear` / `ts_backfill` / `ts_zscore` / `rank` / `zscore` / `group_rank` / `vec_avg`

### d. 设置选择三层决策

1. **数据集经验值**（第一层）：decay 基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
   （数值以 quantalpha-design.md 为准，本处为速查）
2. **失败历史反向调整**（第二层）：读本批/历史 failures 反向调参——
   HIGH_TURNOVER → 增大 decay；CONCENTRATED_WEIGHT → ts_backfill / 降 truncation；
   LOW_SHARPE → 延长 lookback / 换基本面字段（完整映射见 `document/reference/pitfalls.md`）。
   **注意**：ts_backfill 是"假设不是修复"——只适用于结构性低频数据（基本面/预期类），
   高频信号（快反转/新闻）长 backfill 会虚高 Sharpe 且错过 regime 切换（pitfalls.md 实测警告）
3. **合法边界**（第三层）：以 `validate_settings` 白名单为准（decay 0-63 整数、
   neutralization 枚举、truncation 0-1、未知键拦截），超界即被预检拒绝
4. **设置三角参考**（第四层，T7）：decay/truncation/neutralization 相互影响——
   Fitness 卡壳（0.7-1.0）时先调设置再改代码（decay 分级：1-3→TO 40-60%、4-7→25-40%、
   8-15→15-25%、15+→<15%；反转类 5-8、动量类 10+），见 `document/reference/templates.md` T7

### e. 输出：候选 JSON

每候选写入 `data/candidates/YYYY-MM-DD.json`，格式：

```json
{
  "description": "一句话描述（含方向/时间尺度）",
  "hypothesis": "设计逻辑三件套：假设 + 预期信号来源 + 可能失败点（必填非空）",
  "expression": "FASTEXPR 表达式",
  "dataset_ids": ["表达式字段归属的数据集 id"],
  "settings": {"decay": 0, "neutralization": "INDUSTRY", "truncation": 0.08},
  "language": "FASTEXPR"
}
```

- `language` 可选，默认 `"FASTEXPR"`（v1.6 起 validate 对非 FASTEXPR 直接拒绝）
- **设计逻辑三件套（假设 / 预期信号来源 / 可能失败点）全部写进 `hypothesis` 字段**，
  候选报告与提交确认时直接展示，实现知情确认（机械确认 → 知情确认）

### f. 质量自检清单（写文件前逐项过）

- [ ] 算子 ∈ 白名单（**以 validate 为准**；67 算子全名单与语法见 `document/reference/operators.md`）
- [ ] 字段 ∈ `experience/fields/fields.json`（validate 白名单）
- [ ] 类型合规：VECTOR 需 `vec_*` 包裹、GROUP 仅作 `group_*` 的 group_by、UNIVERSE/SYMBOL 禁用
- [ ] 复杂度 ≤30 算子 / ≤8 深度
- [ ] 避开 failures 死路（不与已证伪方向重复）
- [ ] **多空平衡**（官方 13306223024151）：非 INDUSTRY/SUBINDUSTRY 中性化的候选，检查表达式是否含分组中性化收尾（`group_neutralize`/`group_normalize`），避免长空失衡引入市场风险
- [ ] **dataset_ids 与表达式字段归属一致**（validate 不查，agent 必须自查）
- [ ] 无保留字冲突（保留字作字段名会被平台拒绝）
- [ ] 避免规模乘子（`rank(-assets)` / `1-rank(cap)`——易挂子宇宙测试）

---

## 3. 权限差异（用户 vs 顾问）

不写死用户/顾问双分支，**统一以 `qa status` 阶段检测输出为准**（能力矩阵与顾问路径见
`document/flows/access.md`）：

- 字段范围：用户阶段 USA；顾问阶段 12 区域（`experience/fields/` 按账户抓取，
  `qa update-knowledge --force` 刷新）
- 表达式语言：顾问阶段可用 PYTHON/ML（**语法细节待补充**；当前 validate 对非 FASTEXPR
  一律拒绝并提示"PYTHON 暂不支持本地预检，当前阶段仅支持 FASTEXPR"）
- 设置项：无论阶段，均以 `validate_settings` 白名单为准

---

## 4. 失败 → 优化（agent 自主模式）

**优化循环 = 下一个生成批次**（无独立代码优化器）。用户说"优化这批候选"后，agent 自主决策：

1. 读本批失败（failures 表 / `experience/failures.md`；`qa report` 可看归因统计）
2. **归因分类**：方向性（假设证伪）/ 参数可修（LOW_SHARPE、HIGH_TURNOVER 等）/ 相关门饱和
3. **决策**：调参 / 同方向变体 / 换方向 / 止损
4. **执行**：生成下一批 → `data/candidates/YYYY-MM-DD-opt.json`（不覆盖原批，保留对比）
5. **输出决策理由**：明确"为什么这样调"（例："上批 LOW_SHARPE → 延长窗口"），衔接学习机制

**止损纪律**：连续 2 批无 PASS → agent 主动报告"该方向连续 N 批无达标，建议换方向/止损"，
由用户拍板；**不自动停止，但必须报告**。

**归因分离**：模拟失败（`f_*`）→ 优化表达式；提交被拒（`sub_*`）→ 避开饱和簇；
相关门被拒（`corr_*`）→ **本地默认放弃不重试**（已提交集不会缩小，等待无意义，重试会撞
ALREADY_SUBMITTED）；**例外**：若本 alpha 的 Sharpe 比与其相关度高于 cutoff 的所有已提交
alpha 的 Sharpe 高 ≥10%，平台提交时自动豁免（官方教程 alpha-submission）——本地无法计算，
坚信满足时到平台提交核实。生成侧靠"避开已提交信号簇"从源头减少此类被拒。

**合规红线**：优化后 PASS 仍走暂存 + 人工确认，不新增自动提交路径。

---

## 5. 用户覆盖原则

> 知识库与经验是参考而非束缚。若用户明确要求忽略某条经验或按自己的想法来，
> 以用户要求为准（用户覆盖优先）。

但需区分两类：

| 类型 | 覆盖 | 说明 |
|---|---|---|
| 规则类（L1/L2：字段类型 / 算子上限 / 设置值域） | **无效** | validate 代码强制；坚持时向用户解释"这是平台规则无法绕过" |
| 策略类（L3/L4：方向有效性 / 组合偏好） | **有效** | 以用户要求为准 |

---

## 6. 四层可靠性分层（agent 必须区分）

| 层 | 来源 | 性质 | 用法 |
|---|---|---|---|
| L1 | 平台 API 元数据（operators / fields / simulations 响应） | 权威 | 代码强制（validate 白名单） |
| L2 | 平台公开文档（operators.md / rules.md / pitfalls.md） | 权威 | 代码部分强制（算子白名单/复杂度） |
| L3 | 模拟沉淀（playbook / failures） | 实证（自己的数据） | 强参考，生成前必读 |
| L4 | 论坛 / 网络经验（community.md） | 传闻 | 只能作候选方向灵感，**不能作硬约束**；标注来源 + 可信度 |

---

## 7. 外部经验与调研

- 外部经验更新（community.md 写入流程）：见 `document/flows/update-knowledge.md`
- 调研访问规则（cookie 验证 / 登录墙处理）：见 `document/flows/update-knowledge.md`
- 网络模版收集：见 `document/flows/update-knowledge.md` + `document/reference/templates.md`
