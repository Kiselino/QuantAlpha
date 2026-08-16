# Alpha 生成与优化操作指南（generation-guide）

> 定位：面向任何 agent 工具（opencode / claude code / codex）的候选生成与优化操作手册。
> 随仓库公开分发，与具体工具无关。**生成候选前必须通读本指南**。
> 主题来源遵循 AGENTS.md 启动流程步骤 6（① `qa suggest` 随机 ② 网络热门 ③ 用户指定）——
> 用户选择后再进入生成，不擅自替用户选主题。

---

## 1. 生成流程六环节

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
4. `knowledge/operators.md` —— 67 算子语法 / 参数 / 官方示例
5. `experience/fields/fields.json` —— 全量字段白名单 + 类型（validate 预检依据）

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
2. **失败历史反向调整**（第二层）：读本批/历史 failures 反向调参——
   HIGH_TURNOVER → 增大 decay；CONCENTRATED_WEIGHT → ts_backfill / 降 truncation；
   LOW_SHARPE → 延长 lookback / 换基本面字段（完整映射见 `knowledge/pitfalls.md`）
3. **合法边界**（第三层）：以 `validate_settings` 白名单为准（decay 0-63 整数、
   neutralization 枚举、truncation 0-1、未知键拦截），超界即被预检拒绝

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

- `language` 可选，默认 `"FASTEXPR"`（v1.6 起 validate 对非 FASTEXPR 直接拒绝，见 §2）
- **设计逻辑三件套（假设 / 预期信号来源 / 可能失败点）全部写进 `hypothesis` 字段**，
  候选报告与提交确认时直接展示，实现知情确认（机械确认 → 知情确认）

### f. 质量自检清单（写文件前逐项过）

- [ ] 算子 ∈ 白名单（**以 validate 为准**；67 算子全名单与语法见 `knowledge/operators.md`）
- [ ] 字段 ∈ `experience/fields/fields.json`（validate 白名单）
- [ ] 类型合规：VECTOR 需 `vec_*` 包裹、GROUP 仅作 `group_*` 的 group_by、UNIVERSE/SYMBOL 禁用
- [ ] 复杂度 ≤30 算子 / ≤8 深度
- [ ] 避开 failures 死路（不与已证伪方向重复）
- [ ] **dataset_ids 与表达式字段归属一致**（validate 不查，agent 必须自查）
- [ ] 无保留字冲突（保留字作字段名会被平台拒绝）
- [ ] 避免规模乘子（`rank(-assets)` / `1-rank(cap)`——易挂子宇宙测试）

---

## 2. 顾问阶段差异

不写死用户/顾问双分支，**统一以 `qa status` 阶段检测输出为准**：

- 字段范围：用户阶段 USA；顾问阶段 12 区域（`experience/fields/` 按账户抓取，
  `qa update-knowledge --force` 刷新）
- 表达式语言：顾问阶段可用 PYTHON/ML（**语法细节待补充**；当前 validate 对非 FASTEXPR
  一律拒绝并提示"PYTHON 暂不支持本地预检，当前阶段仅支持 FASTEXPR"）
- 设置项：无论阶段，均以 `validate_settings` 白名单为准

---

## 3. 失败 → 优化（agent 自主模式）

**优化循环 = 下一个生成批次**（无独立代码优化器）。用户说"优化这批候选"后，agent 自主决策：

1. 读本批失败（failures 表 / `experience/failures.md`；`qa report` 可看归因统计）
2. **归因分类**：方向性（假设证伪）/ 参数可修（LOW_SHARPE、HIGH_TURNOVER 等）/ 相关门饱和
3. **决策**：调参 / 同方向变体 / 换方向 / 止损
4. **执行**：生成下一批 → `data/candidates/YYYY-MM-DD-opt.json`（不覆盖原批，保留对比）
5. **输出决策理由**：明确"为什么这样调"（例："上批 LOW_SHARPE → 延长窗口"），衔接学习机制

**止损纪律**：连续 2 批无 PASS → agent 主动报告"该方向连续 N 批无达标，建议换方向/止损"，
由用户拍板；**不自动停止，但必须报告**。

**归因分离**：模拟失败（`f_*`）→ 优化表达式；提交被拒（`sub_*`）→ 避开饱和簇；
相关门被拒（`corr_*`）→ **直接放弃不重试**（已提交集不会缩小，重试无意义且会撞
ALREADY_SUBMITTED）——生成侧靠"避开已提交信号簇"从源头减少此类被拒。

**合规红线**：优化后 PASS 仍走暂存 + 人工确认，不新增自动提交路径。

---

## 4. 用户覆盖原则

> 知识库与经验是参考而非束缚。若用户明确要求忽略某条经验或按自己的想法来，
> 以用户要求为准（用户覆盖优先）。

但需区分两类：

| 类型 | 覆盖 | 说明 |
|---|---|---|
| 规则类（L1/L2：字段类型 / 算子上限 / 设置值域） | **无效** | validate 代码强制；坚持时向用户解释"这是平台规则无法绕过" |
| 策略类（L3/L4：方向有效性 / 组合偏好） | **有效** | 以用户要求为准 |

---

## 5. 四层可靠性分层（agent 必须区分）

| 层 | 来源 | 性质 | 用法 |
|---|---|---|---|
| L1 | 平台 API 元数据（operators / fields / simulations 响应） | 权威 | 代码强制（validate 白名单） |
| L2 | 平台公开文档（operators.md / rules.md / pitfalls.md） | 权威 | 代码部分强制（算子白名单/复杂度） |
| L3 | 模拟沉淀（playbook / failures） | 实证（自己的数据） | 强参考，生成前必读 |
| L4 | 论坛 / 网络经验（community.md） | 传闻 | 只能作候选方向灵感，**不能作硬约束**；标注来源 + 可信度 |

---

## 6. 外部经验更新（community.md 写入流程）

`qa update-knowledge` 运行时，agent 询问用户"是否同时更新外部经验？"→ 用户同意后：

1. 网络调研（官方论坛 / BRAIN 社区 / 教程；**先确认 cookie 有效，见 §7**）
2. 总结为新条目：方向 + 结论 + 来源 URL + 日期 + 可信度
3. **展示给用户确认** → 追加写入 `knowledge/community.md`
4. **禁止掺入个人私有表达式 / 账号信息**（分享红线）

> 机械抓取（字段）与判断性内容（外部经验）分离：CLI 命令本身不弹交互，询问由 agent 在会话中执行。

---

## 7. 调研访问规则

- BRAIN 平台匿名访问是登录墙（返回 JS 空壳页面）
- 调研（算子文档、字段、模拟示例等）前：先 `qa status` 验证 cookie 有效；失效则 `qa login` 刷新
- 携带 `secrets/worldquant_cookies.txt` 访问；`/operators/{name}` 详情页含官方
  SIMULATION_EXAMPLE（完整 settings 含 language），是生成指南的优质参考源
- 遇到官网墙异常时**优先怀疑 cookie 过期**——更新登录状态后重试，不要盲目换信息来源
