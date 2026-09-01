# 平台规则速查（BRAIN）

> 供 agent 生成候选与筛选时参考。权威来源：以 quantalpha-design.md 为准 + 官方文档/论坛调研。

## 提交门槛（硬性）

| 指标 | 要求 |
|---|---|
| Fitness | ≥1.0（D1）/ ≥1.3（D0） |
| Sharpe | >1.25（D1）/ >2.0（D0） |
| Turnover | 1% ~ 70%（理想 <30%） |
| 自相关 | <0.7（Sharpe≥1.375 可豁免） |
| 子宇宙 | `subuniverse_sharpe ≥ 0.75·√(sub/alpha)·alpha_sharpe` |
| 单股权重 | <30%（目标 ≤10%） |

> 数值以 quantalpha-design.md 提交门槛章节为准（本表为速查）。

**Fitness 公式（官方）：** `Fitness = Sharpe · √(|Returns| / max(Turnover, 0.125))`——高 Return、高 Sharpe、低 TO（<40% 更佳）三管齐下。

**ATOM 原则：** 单数据集表达（只用 1 个数据集的字段，**排除 country/sector 等分组字段**）放宽提交标准——只看最近 2Y Sharpe（USA D1>1.0），不做完整 IS Ladder 测试。**生成候选应优先单数据集**。

**Test Period 机制：** IS 内划分 Train/Test（橙色 = test 段），统计默认看训练段；提交前必须显示 Test Period（walk-forward 反过拟合）。相关设置项：testPeriod 范围 P0-P6Y、lookback 0-1024、selectionLimit 10-1000、selectionHandling POSITIVE。

## 提交检查管线（平台全套 check，提交前 agent 应自检同维度）

- 相关性：`SELF_CORRELATION`（对已提交集日收益 max Pearson <0.7）、`PROD_CORRELATION`
- 收益类：`SHARPE` / `SUB_UNIVERSE_SHARPE` / `SUPER_UNIVERSE_SHARPE` / `RANK_SHARPE` / `PRE_CLOSE_SHARPE` / `Y_SHARPE` / `IS_LADDER_SHARPE` / `CLUSTER_TEST`
- 换手类：`HIGH_TURNOVER` / `AFTER_COST_SHARPE` / `HIGH_TURNOVER_RETURNS_RATIO` / `INVESTABLE_MAX_POSITION_*` / `ORTHOGONAL_RAM_NEUTRALIZATION` / `PNL_REALIZATION_HORIZON` / `TURNOVER`
- 结构类：`IMBALANCE` / `CONCENTRATED_WEIGHT` / `WEIGHT` / `DRAWDOWN` / `BIAS` / `WITH_RATIO` / `WITH_VALUES` / `REVERSION_COMPONENT`
- 编译/资格：`COMPILE_ERROR` / `INVALID_CODE` / `INVALID_UNIVERSE` / `AVAILABLE_SETTING` / `USER_DEFINED_FIELDS` / `DUPLICATE_ALPHA` / `ALREADY_SUBMITTED` / `DATA_DIVERSITY` / `DATA_SET_AUTHORIZATION` / `REGION_AUTHORIZATION`
- 配额类：`REGULAR_SUBMISSION` / `RESEARCHER_REGULAR_SUBMISSION` / `SUPER_SUBMISSION` / `POWER_POOL_*` / `REGULAR_SUBMISSION_REACHED` / `D0*`

## 模拟默认设置（对齐平台）

delay=1、universe=TOP3000、truncation=0.08、decay=0、neutralization=INDUSTRY、pasteurization=ON、nanHandling=OFF、testPeriod=P1Y。

## 字段优先级（通过率实证）

**基本面 40% > 混合 12.7% > 纯技术 5.3% > 其他 0%**

- 黄金组合：`group_rank(ts_rank(x, N), subindustry)`
- decay 经验值：基本面 0 / 分析师 0-4 / 技术 10-30；truncation 0.05-0.1
- 失败主因：LOW_SHARPE 90.7% / LOW_FITNESS 66.2% / LOW_SUB_UNIVERSE_SHARPE 51.0%

## 计分规则

- 每日最高 2000 分（通常 1-2 个高质量 alpha 即达）；相对分（看当天其他用户）
- 得分 = Quantity Factor × Quality Factor（按当日提交用户归一化）；Quality Factor 依赖：Universe（**越小分越高**）、SelfCorrelation（越低越好）、Fitness、Delay（**D1 比 D0 贡献更多**）
- 等级：Bronze>1000 / Silver>5000 / Gold>10000；**10000 分 → 顾问邀请资格**
- 小宇宙（TOP500/200）+ D1 比大宇宙/D0 得分更高
- 美东 3AM 结算（"日"边界按美东，非本地）；T+1 记账（约北京 14-15 点）
- IQC：最终分 = 25% IS + 75% OS；IS Score = D1 Score + D0/3；评分指标 = 合并序列 Sharpe / Returns-Drawdown / Turnover（<12.5% 不再加分）
- D0 访问权限：需 5,000 Individual Qualifier Score

## 收入机制（顾问阶段）

| 组成 | 金额 | 核心变量 |
|---|---|---|
| Base Payment | 1-60 USD/天 | 每日前 4 个 alpha + 每月前 5 个 D0 计入；Value Factor + Quantity + Self Growth（注：顾问阶段"提交 3+ 个当天奖励封顶"为计分口径，Base 计入口径为前 4 个） |
| Quarterly Payment | 100-25000 USD/季 | Weight Factor + Value Factor；当季 ≥20 提交天门槛；IQC 期间顾问 Net Weight≈0 |
| Competition | 奖池（ATOM/IQC 等） | 名次（IQC 2026 奖池 $100k，较 2024 $400k 缩减中） |
| Referral Bonus | 100-200 USD/人 上不封顶 | 官方页 $100/人（被荐者提交 10 天+顾问满 1 月）；中文论坛经验 $200/人（被荐者成顾问且提交 >10 天） |

- **1.5USD 大法**：当日只交 1 个 alpha，Base ≥1.5 → 质量不错；只有 1.2 需警惕
- 前 3 个月是"试用期"，核心目标是**积累 Value Factor**，之后收入数倍提升
- **Super Alpha**：累计提交 100 个 alpha 后解锁，可组合已有 alpha（每日 1 个上限，收入常更高）；社区门槛经验：fit>5 + prod corr<0.7
- **研究小组**：提交 30 个 alpha 后可申请，双周评比有额外奖金
- 评级（Spectacular/Excellent）≠ 高 Quality Factor / 高 base
- 税务：劳务报酬代扣代缴（800 以下免税、以上 20%）；Base 每两月发放 + Quarterly 每季（1/3/5/6/7/9/11/12 月发薪日）

## 顾问路径（中国区官方流程）

10,000 分 + Gold → 进入 Challenge - Mainland China 排行榜（近 60 天有提交的 Gold 用户综合排名：IS Score + Uniqueness + 提交天数）→ 研究能力测试笔试 → 5 分钟面谈（身份核实 + 平台基础知识）→ Workday 顾问申请表 → 背调（授权书+身份证+问卷）→ 签约 → 填银行卡 → **Full Consultant**。顾问每月须保住 ≥1 个合格 alpha，否则 Tier-2 归零。

## 组合视角（alpha 非独立）

- 提交检查 `SELF_CORRELATION`：与已提交全部 alpha 日收益 max Pearson <0.7
- 低相关要靠**不同数据来源/经济逻辑**，不是调参（换窗口/中性化无效）
- 提交前可调 `/correlations/self` 免费查相关门

## 平台 API 备忘

- 会话：JWT cookie（`t=...`，实测约 4h，`token.expiry ≈ 14222s`）；401/403 = 过期需更新（`qa login` 或复制 cURL）；登录端点 `POST /authentication`（Basic Auth，API 登录无需验证码）
- 数据集枚举：`GET /data-sets?region=USA&universe=TOP3000&delay=1&instrumentType=EQUITY&limit=20`
- 字段元数据：`GET /data-fields?dataset.id={id}&region=...&delay=1&universe=TOP3000&limit=50&offset={n}`（**参数名 `dataset.id` 点号写法**）
- 用户 alpha：`GET /users/self/alphas?limit=100`
- 阶段检测：`GET /users/self`（level/geniusLevel/consultant）
- 限流头：`x-ratelimit-limit-minute`（30/分）；429 区分 `THROTTLED`
- 模拟状态值：`COMPLETE`（非 COMPLETED）；is 数据在 alpha 详情
- 每日模拟限额：`DAILY_SIMULATION_LIMIT_EXCEEDED`（美东时间重置）；约 ~800 模拟/晚；提交配额官方 unlimited
- 并发：API 3 并发；SSO：BRAIN 会话 → `/authentication/support` → Zendesk JWT → 论坛 API（机制已验证可复用）
- 其他端点：`/operators`（算子参考）、`/suggest/fields`、`/suggest/examples`（字段/示例建议）、`/data-categories`、`/tutorials`、`/competitions`（分页 limit=100）
- 外部参考 SDK：`wqb`（PyPI, rocky-d/wqb）——含 search_operators/search_datasets/search_fields/check/submit 与限流常量，可对照参考
- 已证伪：无 "FastSim"、无 delay-2、无 equal/volume weighting 开关、无官方公共 SDK（顾问专属）

## 合规红线

1. **禁止无人值守自动提交**——提交必须展示检查 + 用户显式确认
2. 禁止分享真实表达式/账号 ID/盈亏数据（playbook 必须脱敏）
3. 允许 AI 生成初步想法、批量模拟、优化流程、复盘
4. 模拟配额内运行，不做 24h 刷量
